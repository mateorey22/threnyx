#!/usr/bin/env python3
"""
Nostr crypto primitives: BIP-340 Schnorr sign/verify, event hashing/signing.
NIP-59 gift wrap (seal + wrap), NIP-17 DM send/receive.
"""
import hashlib
import json
import os
import time
import secrets
from typing import Optional, Tuple, Dict, Any

import secp256k1


class NostrKey:
    """Nostr secp256k1 keypair using the C library directly."""

    def __init__(self, priv_hex: str = None):
        self.ctx = secp256k1.lib.secp256k1_context_create(
            secp256k1.lib.SECP256K1_CONTEXT_SIGN | secp256k1.lib.SECP256K1_CONTEXT_VERIFY
        )
        if priv_hex:
            self.priv_bytes = bytes.fromhex(priv_hex)
        else:
            self.priv_bytes = secrets.token_bytes(32)

        # Create keypair
        self.keypair = secp256k1.ffi.new('secp256k1_keypair *')
        ret = secp256k1.lib.secp256k1_keypair_create(self.ctx, self.keypair, self.priv_bytes)
        if ret != 1:
            raise ValueError("invalid private key")

        # Get xonly pubkey
        self.xonly_pub = secp256k1.ffi.new('secp256k1_xonly_pubkey *')
        parity = secp256k1.ffi.new('int *')
        secp256k1.lib.secp256k1_keypair_xonly_pub(self.ctx, self.xonly_pub, parity, self.keypair)
        self.parity = parity[0]

        # Serialize pubkey
        ser = secp256k1.ffi.new('unsigned char[32]')
        secp256k1.lib.secp256k1_xonly_pubkey_serialize(self.ctx, ser, self.xonly_pub)
        self.pub_hex = bytes(ser).hex()

    @property
    def priv_hex(self) -> str:
        return self.priv_bytes.hex()

    def schnorr_sign(self, msg_hash: bytes) -> bytes:
        """BIP-340 Schnorr sign."""
        sig = secp256k1.ffi.new('unsigned char[64]')
        ret = secp256k1.lib.secp256k1_schnorrsig_sign(
            self.ctx, sig, msg_hash, self.keypair, secp256k1.ffi.NULL
        )
        if ret != 1:
            raise ValueError("schnorr sign failed")
        return bytes(sig)

    @classmethod
    def schnorr_verify(cls, sig: bytes, msg_hash: bytes, pub_hex: str) -> bool:
        """BIP-340 Schnorr verify."""
        ctx = secp256k1.lib.secp256k1_context_create(secp256k1.lib.SECP256K1_CONTEXT_VERIFY)
        xonly_pub = secp256k1.ffi.new('secp256k1_xonly_pubkey *')
        ret = secp256k1.lib.secp256k1_xonly_pubkey_parse(ctx, xonly_pub, bytes.fromhex(pub_hex))
        if ret != 1:
            return False
        valid = secp256k1.lib.secp256k1_schnorrsig_verify(
            ctx, secp256k1.ffi.new('unsigned char[]', sig), msg_hash, 32, xonly_pub
        )
        return valid == 1


def compute_event_id(pubkey: str, created_at: int, kind: int, tags: list, content: str) -> str:
    """Compute Nostr event ID (NIP-01)."""
    event_data = [0, pubkey, created_at, kind, tags, content]
    serialized = json.dumps(event_data, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def sign_event(priv_hex: str, pubkey: str, created_at: int, kind: int, tags: list, content: str) -> dict:
    """Create and sign a Nostr event."""
    event_id = compute_event_id(pubkey, created_at, kind, tags, content)
    key = NostrKey(priv_hex)
    sig = key.schnorr_sign(bytes.fromhex(event_id))
    return {
        "id": event_id,
        "pubkey": pubkey,
        "created_at": created_at,
        "kind": kind,
        "tags": tags,
        "content": content,
        "sig": sig.hex()
    }


def verify_event(event: dict) -> bool:
    """Verify a Nostr event signature."""
    event_id = compute_event_id(
        event["pubkey"], event["created_at"], event["kind"],
        event["tags"], event["content"]
    )
    if event_id != event["id"]:
        return False
    return NostrKey.schnorr_verify(
        bytes.fromhex(event["sig"]),
        bytes.fromhex(event_id),
        event["pubkey"]
    )


def create_seal(sender_priv_hex: str, sender_pub_hex: str,
                recipient_pub_hex: str, rumor: dict) -> dict:
    """Create a NIP-59 seal (kind 13).

    The seal contains the rumor encrypted with NIP-44 using the
    conversation key between sender and recipient.
    """
    import nip44

    conv_key = nip44.get_conversation_key(
        bytes.fromhex(sender_priv_hex), recipient_pub_hex
    )
    rumor_json = json.dumps(rumor, separators=(',', ':'))
    encrypted = nip44.encrypt(rumor_json, conv_key)

    # NIP-59 says random time up to 2 days in the past, but many relay
    # subscriptions filter by since=now-2h, so we use current time to
    # ensure delivery. The seal's timestamp is still hidden inside the
    # encrypted gift wrap, so the privacy impact is minimal.
    created_at = int(time.time())
    return sign_event(
        sender_priv_hex, sender_pub_hex, created_at, 13, [], encrypted
    )


def create_gift_wrap(wrapper_priv_hex: str, wrapper_pub_hex: str,
                     recipient_pub_hex: str, seal: dict) -> dict:
    """Create a NIP-59 gift wrap (kind 1059) around a seal."""
    import nip44

    conv_key = nip44.get_conversation_key(
        bytes.fromhex(wrapper_priv_hex), recipient_pub_hex
    )
    seal_json = json.dumps(seal, separators=(',', ':'))
    encrypted = nip44.encrypt(seal_json, conv_key)

    # Use current time — NIP-59 recommends random past time for privacy,
    # but relay subscriptions often filter recent events only.
    created_at = int(time.time())
    tags = [["p", recipient_pub_hex]]
    return sign_event(
        wrapper_priv_hex, wrapper_pub_hex, created_at, 1059, tags, encrypted
    )


def unwrap_gift_wrap(wrapper_priv_hex: str, gift_wrap: dict) -> Tuple[dict, dict]:
    """Decrypt a gift wrap: returns (seal, rumor).

    The wrapper key decrypts the outer layer to get the seal.
    The seal's pubkey identifies the sender; the sender's pubkey
    is used to verify the seal and decrypt the rumor.
    """
    import nip44

    # Check event is a gift wrap
    if gift_wrap["kind"] != 1059:
        raise ValueError("not a gift wrap event")

    # Verify the gift wrap signature
    if not verify_event(gift_wrap):
        raise ValueError("invalid gift wrap signature")

    # Get the recipient from tags
    recipient = None
    for tag in gift_wrap["tags"]:
        if tag[0] == "p":
            recipient = tag[1]
            break
    if not recipient:
        raise ValueError("no recipient in gift wrap")

    # Decrypt the seal with NIP-44
    # Conversation key between wrapper and recipient
    wrapper_pub = gift_wrap["pubkey"]
    conv_key = nip44.get_conversation_key(
        bytes.fromhex(wrapper_priv_hex), wrapper_pub
    )
    seal_json = nip44.decrypt(gift_wrap["content"], conv_key)
    seal = json.loads(seal_json)

    # Verify seal signature
    if not verify_event(seal):
        raise ValueError("invalid seal signature")

    # Decrypt the rumor from the seal
    sender_pub = seal["pubkey"]
    conv_key2 = nip44.get_conversation_key(
        bytes.fromhex(wrapper_priv_hex), sender_pub
    )
    rumor_json = nip44.decrypt(seal["content"], conv_key2)
    rumor = json.loads(rumor_json)

    return seal, rumor


def create_nip17_dm(
    sender_priv_hex: str,
    sender_pub_hex: str,
    recipient_pub_hex: str,
    message: str,
    kind: int = 14,
    extra_tags: list = None
) -> dict:
    """Create a NIP-17 direct message.

    1. Create the rumor (unsigned event, kind 14 for DM)
    2. Create a seal (kind 13) — sender encrypts rumor to recipient
    3. Create a gift wrap (kind 1059) — one-time wrapper key encrypts seal to recipient

    The recipient decrypts the gift wrap with their key, gets the seal,
    verifies the seal is from the sender, then decrypts the rumor.
    """
    # Generate one-time wrapper key
    wrapper_key = NostrKey()

    # Create the rumor (unsigned event)
    created_at = int(time.time())
    tags = [["p", recipient_pub_hex]]
    if extra_tags:
        tags.extend(extra_tags)
    rumor = {
        "id": "",
        "pubkey": sender_pub_hex,
        "created_at": created_at,
        "kind": kind,
        "tags": tags,
        "content": message,
        "sig": ""
    }

    # Create seal
    seal = create_seal(sender_priv_hex, sender_pub_hex, recipient_pub_hex, rumor)

    # Create gift wrap
    gift_wrap = create_gift_wrap(
        wrapper_key.priv_hex, wrapper_key.pub_hex, recipient_pub_hex, seal
    )

    return gift_wrap


def decode_nip17_dm(recipient_priv_hex: str, gift_wrap: dict) -> Tuple[str, dict]:
    """Decode a NIP-17 DM from a gift wrap.

    Returns (sender_pub_hex, rumor).
    """
    seal, rumor = unwrap_gift_wrap(recipient_priv_hex, gift_wrap)
    return seal["pubkey"], rumor
