#!/usr/bin/env python3
"""
Threnyx legacy crypto: ECDH + HKDF + AES-256-GCM.
Used when the contact doesn't have NIP-17 protocol negotiated.

pairKey(priv, pub) = HKDF(ECDH(priv, pub), salt="threnyx/v2", info="conv") → AES-256-GCM key
encrypt(key, obj) = AES-256-GCM(key, random_iv, JSON.stringify(obj)) → {iv: base64, ct: base64}
decrypt(key, box) = AES-256-GCM-decrypt(key, iv, ct) → JSON.parse(result)
"""
import base64
import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

import secp256k1


def secp256k1_ecdh_raw(priv_bytes: bytes, pub_hex: str) -> bytes:
    """ECDH: raw x-coordinate of shared point (same as NIP-44 but separate for clarity)."""
    ctx = secp256k1.lib.secp256k1_context_create(
        secp256k1.lib.SECP256K1_CONTEXT_SIGN | secp256k1.lib.SECP256K1_CONTEXT_VERIFY
    )

    pub_bytes = bytes.fromhex(pub_hex)
    if len(pub_bytes) == 32:
        xonly_pub = secp256k1.ffi.new('secp256k1_xonly_pubkey *')
        ret = secp256k1.lib.secp256k1_xonly_pubkey_parse(ctx, xonly_pub, pub_bytes)
        if ret != 1:
            raise ValueError("invalid public key")
        pub = secp256k1.ffi.new('secp256k1_pubkey *')
        secp256k1.lib.secp256k1_xonly_pubkey_tweak_add(ctx, pub, xonly_pub, b'\x00' * 32)
    else:
        pub = secp256k1.ffi.new('secp256k1_pubkey *')
        ret = secp256k1.lib.secp256k1_ec_pubkey_parse(ctx, pub, pub_bytes, len(pub_bytes))
        if ret != 1:
            raise ValueError("invalid public key")

    @secp256k1.ffi.callback('int(unsigned char *, const unsigned char *, const unsigned char *, void *)')
    def raw_x_cb(output, x32, y32, data):
        secp256k1.ffi.memmove(output, x32, 32)
        return 1

    shared = secp256k1.ffi.new('unsigned char[32]')
    ret = secp256k1.lib.secp256k1_ecdh(ctx, shared, pub, priv_bytes, raw_x_cb, secp256k1.ffi.NULL)
    if ret != 1:
        raise ValueError("ECDH failed")

    return bytes(shared)


def pair_key(priv_hex: str, pub_hex: str) -> bytes:
    """Derive AES-256-GCM key from ECDH + HKDF.

    HKDF(salt="threnyx/v2", info="conv", hash=SHA-256)
    """
    shared = secp256k1_ecdh_raw(bytes.fromhex(priv_hex), pub_hex)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'threnyx/v2',
        info=b'conv',
    )
    return hkdf.derive(shared)


def b64(data: bytes) -> str:
    """Base64 encode."""
    return base64.b64encode(data).decode('ascii')


def ub64(s: str) -> bytes:
    """Base64 decode."""
    return base64.b64decode(s)


def encrypt(key: bytes, obj: Any) -> dict:
    """AES-256-GCM encrypt a JSON-serializable object.
    Returns {iv: base64, ct: base64}.
    """
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    ct = aesgcm.encrypt(iv, plaintext, None)
    return {"iv": b64(iv), "ct": b64(ct)}


def decrypt(key: bytes, box: dict) -> Any:
    """AES-256-GCM decrypt.
    box = {iv: base64, ct: base64}
    Returns the deserialized JSON object, or None on failure.
    """
    try:
        iv = ub64(box["iv"])
        ct = ub64(box["ct"])
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(iv, ct, None)
        return json.loads(plaintext.decode('utf-8'))
    except Exception:
        return None


def create_legacy_gift_wrap(
    sender_priv_hex: str,
    sender_pub_hex: str,
    recipient_pub_hex: str,
    payload: dict,
    ephemeral: bool = False
) -> dict:
    """Create a Threnyx legacy gift wrap (kind 1059 or 21059).

    Structure:
    1. inner = encrypt(pairKey(sender_priv, recipient_pub), payload)
    2. Generate ephemeral key: ep = genPriv(), epub = getPub(ep)
    3. outer = encrypt(pairKey(ep, recipient_pub), {from: sender_pub, box: inner})
    4. event = Nostr event kind 1059 (persistent) or 21059 (ephemeral),
       pubkey=epub, content=JSON.stringify(outer), tags=[['p', recipient_pub]]
    5. Sign event with ephemeral key
    """
    from nostr_crypto import sign_event

    # 1. Inner encryption
    inner_key = pair_key(sender_priv_hex, recipient_pub_hex)
    inner = encrypt(inner_key, payload)

    # 2. Ephemeral key
    ep_key = secrets.token_bytes(32)
    import secp256k1
    ctx = secp256k1.lib.secp256k1_context_create(
        secp256k1.lib.SECP256K1_CONTEXT_SIGN | secp256k1.lib.SECP256K1_CONTEXT_VERIFY
    )
    kp = secp256k1.ffi.new('secp256k1_keypair *')
    secp256k1.lib.secp256k1_keypair_create(ctx, kp, ep_key)
    xo = secp256k1.ffi.new('secp256k1_xonly_pubkey *')
    secp256k1.lib.secp256k1_keypair_xonly_pub(ctx, xo, secp256k1.ffi.new('int *'), kp)
    ser = secp256k1.ffi.new('unsigned char[32]')
    secp256k1.lib.secp256k1_xonly_pubkey_serialize(ctx, ser, xo)
    epub_hex = bytes(ser).hex()
    ep_priv_hex = ep_key.hex()

    # 3. Outer encryption
    outer_key = pair_key(ep_priv_hex, recipient_pub_hex)
    outer = encrypt(outer_key, {"from": sender_pub_hex, "box": inner})

    # 4. Create event
    import time
    ts = int(time.time())
    kind = 21059 if ephemeral else 1059
    tags = [["p", recipient_pub_hex]]

    return sign_event(ep_priv_hex, epub_hex, ts, kind, tags, json.dumps(outer, separators=(',', ':')))


def decode_legacy_gift_wrap(recipient_priv_hex: str, event: dict) -> tuple:
    """Decode a Threnyx legacy gift wrap.

    Returns (sender_pub_hex, payload) or raises ValueError.

    Structure:
    1. event.content = JSON({iv, ct}) — outer encrypted box
    2. Decrypt outer with pairKey(recipient_priv, event.pubkey) → {from, box: {iv, ct}}
    3. Decrypt inner box with pairKey(recipient_priv, sender_pub) → payload
    """
    from nostr_crypto import verify_event

    if not verify_event(event):
        raise ValueError("invalid event signature")

    if event["kind"] not in (1059, 21059):
        raise ValueError(f"unexpected kind: {event['kind']}")

    # Check p tag
    p_tag = None
    for tag in event.get("tags", []):
        if tag[0] == "p":
            p_tag = tag[1]
            break
    if not p_tag:
        raise ValueError("no p tag")

    # 1. Parse outer encrypted box
    outer_box = json.loads(event["content"])
    if not isinstance(outer_box, dict) or "iv" not in outer_box or "ct" not in outer_box:
        raise ValueError("invalid outer format: expected {iv, ct}")

    # 2. Decrypt outer with pairKey(recipient_priv, event.pubkey)
    outer_key = pair_key(recipient_priv_hex, event["pubkey"])
    outer_obj = decrypt(outer_key, outer_box)
    if outer_obj is None:
        raise ValueError("failed to decrypt outer layer")
    if not isinstance(outer_obj, dict) or "from" not in outer_obj or "box" not in outer_obj:
        raise ValueError("invalid outer payload: expected {from, box}")

    sender_pub = outer_obj["from"]
    inner_box = outer_obj["box"]

    # 3. Decrypt inner with pairKey(recipient_priv, sender_pub)
    inner_key = pair_key(recipient_priv_hex, sender_pub)
    payload = decrypt(inner_key, inner_box)
    if payload is None:
        raise ValueError("failed to decrypt inner layer")

    return sender_pub, payload
