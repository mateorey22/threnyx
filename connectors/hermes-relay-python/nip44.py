#!/usr/bin/env python3
"""
NIP-44 v2 encrypted payloads.
Spec: https://github.com/nostr-protocol/nips/blob/master/44.md
"""
import base64
import hashlib
import hmac
import math
import os
import struct
from typing import Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand, HKDF
from cryptography.hazmat.primitives import hashes
from coincurve import PrivateKey as CCPrivateKey, PublicKey as CCPublicKey

MIN_PLAINTEXT_SIZE = 1
MAX_PLAINTEXT_SIZE = 4294967295
EXTENDED_PREFIX_THRESHOLD = 65536


def secp256k1_ecdh_raw(priv_key_bytes: bytes, pub_key_hex: str) -> bytes:
    """ECDH returning unhashed 32-byte x coordinate (BIP340 bytes(P))."""
    import secp256k1
    ctx = secp256k1.lib.secp256k1_context_create(
        secp256k1.lib.SECP256K1_CONTEXT_SIGN | secp256k1.lib.SECP256K1_CONTEXT_VERIFY
    )

    # Parse public key
    pub_bytes = bytes.fromhex(pub_key_hex)
    if len(pub_bytes) == 32:
        # xonly pubkey — parse and convert to regular pubkey
        xonly_pub = secp256k1.ffi.new('secp256k1_xonly_pubkey *')
        ret = secp256k1.lib.secp256k1_xonly_pubkey_parse(ctx, xonly_pub, pub_bytes)
        if ret != 1:
            raise ValueError("invalid public key")
        pub = secp256k1.ffi.new('secp256k1_pubkey *')
        ret2 = secp256k1.lib.secp256k1_xonly_pubkey_tweak_add(ctx, pub, xonly_pub, b'\x00' * 32)
        if ret2 != 1:
            raise ValueError("failed to convert xonly pubkey")
    elif len(pub_bytes) == 33 or len(pub_bytes) == 65:
        pub = secp256k1.ffi.new('secp256k1_pubkey *')
        ret = secp256k1.lib.secp256k1_ec_pubkey_parse(ctx, pub, pub_bytes, len(pub_bytes))
        if ret != 1:
            raise ValueError("invalid public key")
    else:
        raise ValueError(f"invalid public key length: {len(pub_bytes)}")

    # Custom hash function that returns raw x coordinate (no hashing)
    @secp256k1.ffi.callback('int(unsigned char *, const unsigned char *, const unsigned char *, void *)')
    def raw_x_cb(output, x32, y32, data):
        secp256k1.ffi.memmove(output, x32, 32)
        return 1

    shared_x = secp256k1.ffi.new('unsigned char[32]')
    ret = secp256k1.lib.secp256k1_ecdh(ctx, shared_x, pub, priv_key_bytes, raw_x_cb, secp256k1.ffi.NULL)
    if ret != 1:
        raise ValueError("ECDH failed")

    return bytes(shared_x)


def hkdf_extract(ikm: bytes, salt: bytes) -> bytes:
    """HKDF-Extract with SHA256."""
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand with SHA256."""
    hkdf = HKDFExpand(algorithm=hashes.SHA256(), length=length, info=info)
    return hkdf.derive(prk)


def get_conversation_key(priv_key_a: bytes, pub_key_b: str) -> bytes:
    """Calculate conversation key between A (priv) and B (pub)."""
    shared_x = secp256k1_ecdh_raw(priv_key_a, pub_key_b)
    return hkdf_extract(shared_x, b'nip44-v2')


def get_message_keys(conversation_key: bytes, nonce: bytes) -> Tuple[bytes, bytes, bytes]:
    """Derive chacha_key, chacha_nonce, hmac_key from conversation_key and nonce."""
    if len(conversation_key) != 32:
        raise ValueError("invalid conversation_key length")
    if len(nonce) != 32:
        raise ValueError("invalid nonce length")
    keys = hkdf_expand(conversation_key, nonce, 76)
    chacha_key = keys[0:32]
    chacha_nonce = keys[32:44]
    hmac_key = keys[44:76]
    return (chacha_key, chacha_nonce, hmac_key)


def calc_padded_len(unpadded_len: int) -> int:
    """Calculate padded length."""
    if unpadded_len <= 32:
        return 32
    next_power = 1 << (math.floor(math.log2(unpadded_len - 1)) + 1)
    if next_power <= 256:
        chunk = 32
    else:
        chunk = next_power // 8
    return chunk * (math.floor((unpadded_len - 1) / chunk) + 1)


def pad(plaintext: str) -> bytes:
    """Pad plaintext."""
    unpadded = plaintext.encode('utf-8')
    unpadded_len = len(unpadded)
    if unpadded_len < MIN_PLAINTEXT_SIZE or unpadded_len > MAX_PLAINTEXT_SIZE:
        raise ValueError('invalid plaintext length')
    if unpadded_len >= EXTENDED_PREFIX_THRESHOLD:
        prefix = b'\x00\x00' + struct.pack('>I', unpadded_len)
    else:
        prefix = struct.pack('>H', unpadded_len)
    suffix = b'\x00' * (calc_padded_len(unpadded_len) - unpadded_len)
    return prefix + unpadded + suffix


def unpad(padded: bytes) -> str:
    """Remove padding."""
    first_two = struct.unpack('>H', padded[0:2])[0]
    if first_two == 0:
        unpadded_len = struct.unpack('>I', padded[2:6])[0]
        if unpadded_len < EXTENDED_PREFIX_THRESHOLD:
            raise ValueError('invalid padding')
        prefix_len = 6
    else:
        unpadded_len = first_two
        prefix_len = 2
    unpadded = padded[prefix_len:prefix_len + unpadded_len]
    if unpadded_len == 0 or len(unpadded) != unpadded_len:
        raise ValueError('invalid padding')
    if len(padded) != prefix_len + calc_padded_len(unpadded_len):
        raise ValueError('invalid padding')
    return unpadded.decode('utf-8')


def chacha20_encrypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """ChaCha20 encryption (RFC 8439). cryptography lib needs 16-byte nonce."""
    # NIP-44 gives us 12-byte chacha_nonce; cryptography lib needs 16 bytes:
    # 4-byte counter (0) + 12-byte nonce
    padded_nonce = b'\x00\x00\x00\x00' + nonce
    cipher = Cipher(algorithms.ChaCha20(key, padded_nonce), mode=None)
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def chacha20_decrypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """ChaCha20 decryption (same as encrypt)."""
    return chacha20_encrypt(key, nonce, data)


def hmac_aad(key: bytes, message: bytes, aad: bytes) -> bytes:
    """HMAC-SHA256 with AAD."""
    if len(aad) != 32:
        raise ValueError('AAD must be 32 bytes')
    return hmac.new(key, aad + message, hashlib.sha256).digest()


def encrypt(plaintext: str, conversation_key: bytes, nonce: bytes = None) -> str:
    """Encrypt plaintext with NIP-44 v2."""
    if nonce is None:
        nonce = os.urandom(32)
    chacha_key, chacha_nonce, hmac_key = get_message_keys(conversation_key, nonce)
    padded = pad(plaintext)
    ciphertext = chacha20_encrypt(chacha_key, chacha_nonce, padded)
    mac = hmac_aad(hmac_key, ciphertext, nonce)
    payload = bytes([2]) + nonce + ciphertext + mac
    return base64.b64encode(payload).decode('ascii')


def decrypt(payload: str, conversation_key: bytes) -> str:
    """Decrypt NIP-44 v2 payload."""
    if len(payload) == 0 or payload[0] == '#':
        raise ValueError('unknown version')
    if len(payload) < 132:
        raise ValueError('invalid payload size')
    data = base64.b64decode(payload)
    dlen = len(data)
    if dlen < 99:
        raise ValueError('invalid data size')
    version = data[0]
    if version != 2:
        raise ValueError(f'unknown version {version}')
    nonce = data[1:33]
    ciphertext = data[33:dlen - 32]
    mac = data[dlen - 32:dlen]
    chacha_key, chacha_nonce, hmac_key = get_message_keys(conversation_key, nonce)
    calculated_mac = hmac_aad(hmac_key, ciphertext, nonce)
    if not hmac.compare_digest(calculated_mac, mac):
        raise ValueError('invalid MAC')
    padded_plaintext = chacha20_decrypt(chacha_key, chacha_nonce, ciphertext)
    return unpad(padded_plaintext)
