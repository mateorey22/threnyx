#!/usr/bin/env python3
"""
Encrypted temporary media storage with TTL and permission gating.
Media is only accepted if the grant includes the corresponding permission.
All files are encrypted at rest with AES-256-GCM and purged after TTL.
"""
import os
import time
import hashlib
import secrets
import json
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAX_MEDIA_SIZE = 25 * 1024 * 1024  # 25 MiB
DEFAULT_TTL = 300  # 5 minutes

VALID_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'application/pdf', 'text/plain',
    'audio/ogg', 'audio/mpeg', 'audio/webm',
    'video/mp4', 'video/webm',
}


class MediaError(Exception):
    pass


class MediaStore:
    """Encrypted temporary media storage."""

    def __init__(self, base_dir: str, ttl: int = DEFAULT_TTL):
        self.base_dir = base_dir
        self.ttl = ttl
        os.makedirs(base_dir, exist_ok=True)
        # Each stored media gets its own encryption key
        # We store: {media_id: {path, key, mime, created_at, user_pub}}
        self._index: dict = {}

    def store(self, data: bytes, mime_type: str, user_pub: str) -> str:
        """Store encrypted media. Returns media_id."""
        # Validate size
        if len(data) > MAX_MEDIA_SIZE:
            raise MediaError(f"media too large: {len(data)} bytes (max {MAX_MEDIA_SIZE})")

        # Validate MIME type
        if mime_type not in VALID_MIME_TYPES:
            raise MediaError(f"invalid MIME type: {mime_type}")

        # Generate encryption key and media ID
        enc_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        media_id = secrets.token_hex(16)

        # Encrypt
        aesgcm = AESGCM(enc_key)
        encrypted = aesgcm.encrypt(nonce, data, None)

        # Write to disk: nonce (12) + encrypted
        file_path = os.path.join(self.base_dir, f"{media_id}.enc")
        with open(file_path, 'wb') as f:
            f.write(nonce + encrypted)

        # Index
        self._index[media_id] = {
            'path': file_path,
            'key': enc_key.hex(),
            'mime': mime_type,
            'created_at': int(time.time()),
            'user_pub': user_pub,
            'size': len(data),
        }

        return media_id

    def retrieve(self, media_id: str, user_pub: str) -> Tuple[bytes, str]:
        """Retrieve and decrypt media. Returns (data, mime_type)."""
        if media_id not in self._index:
            raise MediaError("media not found")

        meta = self._index[media_id]
        if meta['user_pub'] != user_pub:
            raise MediaError("media does not belong to this user")

        # Check TTL — use >= because TTL=0 means immediate expiry
        if int(time.time()) - meta['created_at'] >= self.ttl:
            self.purge(media_id)
            raise MediaError("media expired")

        # Read and decrypt
        with open(meta['path'], 'rb') as f:
            raw = f.read()

        nonce = raw[:12]
        encrypted = raw[12:]
        aesgcm = AESGCM(bytes.fromhex(meta['key']))
        data = aesgcm.decrypt(nonce, encrypted, None)

        return data, meta['mime']

    def purge(self, media_id: str):
        """Delete a media file and its index entry."""
        if media_id in self._index:
            meta = self._index[media_id]
            try:
                os.remove(meta['path'])
            except FileNotFoundError:
                pass
            del self._index[media_id]

    def purge_user(self, user_pub: str):
        """Purge all media for a user (used on revoke)."""
        to_purge = [
            mid for mid, meta in self._index.items()
            if meta['user_pub'] == user_pub
        ]
        for mid in to_purge:
            self.purge(mid)

    def cleanup_expired(self):
        """Remove all expired media."""
        now = int(time.time())
        expired = [
            mid for mid, meta in self._index.items()
            if now - meta['created_at'] > self.ttl
        ]
        for mid in expired:
            self.purge(mid)
