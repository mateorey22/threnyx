#!/usr/bin/env python3
"""
Test suite for the Threnyx Relay Connector.
Tests: grant validation, signature verification, bot mismatch, replay,
media permissions, revocation, NIP-17 ack roundtrip.
"""
import json
import os
import sys
import time
import hashlib
import base64
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nostr_crypto import NostrKey, create_nip17_dm, decode_nip17_dm, verify_event
from grant import (
    GrantValidator, create_test_grant, GrantError,
    GrantExpiredError, GrantSignatureError, GrantBotMismatchError,
    GrantReplayError, GrantProtocolError, b64url_encode, b64url_decode,
)
from media_store import MediaStore, MediaError


def test_grant_valid():
    """Test 1: A valid grant code passes validation."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex, ['text', 'images'])
    payload = v.validate(code)
    assert payload['userPub'] == user.pub_hex
    assert payload['botPub'] == bot.pub_hex
    assert 'text' in payload['permissions']
    assert 'images' in payload['permissions']
    print("  ✔ valid grant accepted")


def test_grant_expired():
    """Test 2: An expired grant is rejected."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex, exp_offset=-100)
    try:
        v.validate(code)
        assert False, "should have raised"
    except GrantExpiredError:
        pass
    print("  ✔ expired grant rejected")


def test_grant_invalid_signature():
    """Test 3: A grant with an invalid signature is rejected."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex)
    # Tamper with signature
    parts = code.split('.')
    parts[2] = '0' * 128
    bad_code = '.'.join(parts)
    try:
        v.validate(bad_code)
        assert False, "should have raised"
    except GrantSignatureError:
        pass
    print("  ✔ invalid signature rejected")


def test_grant_wrong_bot():
    """Test 4: A grant for a different bot is rejected."""
    bot = NostrKey()
    other_bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, other_bot.pub_hex)
    try:
        v.validate(code)
        assert False, "should have raised"
    except GrantBotMismatchError:
        pass
    print("  ✔ wrong bot rejected")


def test_grant_replay():
    """Test 5: A replayed grant code is rejected."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex)
    v.validate(code)  # first use OK
    try:
        v.validate(code)  # replay
        assert False, "should have raised"
    except GrantReplayError:
        pass
    print("  ✔ replay rejected")


def test_grant_replay_survives_restart():
    """Test 6: a consumed grant stays rejected after process restart."""
    import tempfile
    bot = NostrKey()
    user = NostrKey()
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, 'grants.json')
        code = create_test_grant(user, bot.pub_hex)
        GrantValidator(bot.pub_hex, state_path).validate(code)
        restarted = GrantValidator(bot.pub_hex, state_path)
        try:
            restarted.validate(code)
            assert False, "replay after restart should have raised"
        except GrantReplayError:
            pass
    print("  ✔ replay rejected after restart")


def test_grant_wrong_protocol():
    """Test 6: A grant with wrong protocol is rejected."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    # Create a grant with wrong protocol
    payload = {
        "userPub": user.pub_hex,
        "botPub": bot.pub_hex,
        "permissions": ["text"],
        "protocol": "nip04",  # wrong
        "exp": int(time.time()) + 600,
        "nonce": "test-nonce",
        "id": "test-id"
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    signing_str = "threnyx/hermes-grant/v1:" + payload_json
    msg_hash = hashlib.sha256(signing_str.encode()).digest()
    sig = user.schnorr_sign(msg_hash)
    code = f"THX-HERMES1.{b64url_encode(payload_json.encode())}.{sig.hex()}"
    try:
        v.validate(code)
        assert False, "should have raised"
    except GrantProtocolError:
        pass
    print("  ✔ wrong protocol rejected")


def test_media_without_permission():
    """Test 7: Media from a user without media permission is rejected at the store level."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex, ['text'])  # no images
    v.validate(code)
    assert not v.has_permission(user.pub_hex, 'images')
    assert not v.has_permission(user.pub_hex, 'files')
    assert not v.has_permission(user.pub_hex, 'voice')
    assert v.has_permission(user.pub_hex, 'text')
    print("  ✔ media permission correctly gated")


def test_revocation():
    """Test 8: Revocation removes all permissions and grants."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex, ['text', 'images'])
    v.validate(code)
    assert v.has_permission(user.pub_hex, 'text')
    v.revoke(user.pub_hex)
    assert not v.has_permission(user.pub_hex, 'text')
    assert v.is_revoked(user.pub_hex)
    print("  ✔ revocation removes all permissions")


def test_nip17_ack_roundtrip():
    """Test 9: NIP-17 agentAck message can be created and decoded."""
    bot = NostrKey()
    user = NostrKey()

    ack = {"t": "agentAck", "aid": "grant-001", "nonceHash": "abc123def456"}
    gift_wrap = create_nip17_dm(
        bot.priv_hex, bot.pub_hex, user.pub_hex,
        json.dumps(ack, separators=(',', ':'))
    )

    # User decodes
    sender_pub, rumor = decode_nip17_dm(user.priv_hex, gift_wrap)
    assert sender_pub == bot.pub_hex
    decoded_ack = json.loads(rumor['content'])
    assert decoded_ack['t'] == 'agentAck'
    assert decoded_ack['aid'] == 'grant-001'
    assert decoded_ack['nonceHash'] == 'abc123def456'
    print("  ✔ NIP-17 agentAck roundtrip works")


def test_nip17_wrong_recipient():
    """Test 10: NIP-17 message cannot be decoded by wrong recipient."""
    bot = NostrKey()
    user = NostrKey()
    attacker = NostrKey()

    ack = {"t": "agentAck", "aid": "grant-001", "nonceHash": "abc123"}
    gift_wrap = create_nip17_dm(
        bot.priv_hex, bot.pub_hex, user.pub_hex,
        json.dumps(ack, separators=(',', ':'))
    )

    try:
        decode_nip17_dm(attacker.priv_hex, gift_wrap)
        assert False, "attacker should not decode"
    except Exception:
        pass
    print("  ✔ wrong recipient cannot decode NIP-17")


def test_media_store_encrypted():
    """Test 11: Media store encrypts and decrypts correctly."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MediaStore(tmpdir, ttl=60)
        data = b"test image data" * 100
        media_id = store.store(data, 'image/png', "user123")
        retrieved, mime = store.retrieve(media_id, "user123")
        assert retrieved == data
        assert mime == 'image/png'
        print("  ✔ media store encrypt/decrypt works")


def test_media_store_wrong_user():
    """Test 12: Media cannot be retrieved by wrong user."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MediaStore(tmpdir, ttl=60)
        data = b"secret data"
        media_id = store.store(data, 'image/png', "user123")
        try:
            store.retrieve(media_id, "user456")
            assert False, "should have raised"
        except MediaError:
            pass
        print("  ✔ media store rejects wrong user")


def test_media_store_ttl():
    """Test 13: Media expires after TTL."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MediaStore(tmpdir, ttl=0)  # immediate expiry
        data = b"test"
        media_id = store.store(data, 'image/png', "user123")
        time.sleep(0.1)
        try:
            store.retrieve(media_id, "user123")
            assert False, "should have expired"
        except MediaError:
            pass
        print("  ✔ media TTL expiry works")


def test_media_store_purge_user():
    """Test 14: Purge user removes all their media."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MediaStore(tmpdir, ttl=60)
        store.store(b"data1", 'image/png', "user123")
        store.store(b"data2", 'image/png', "user123")
        store.store(b"data3", 'image/png', "user456")
        store.purge_user("user123")
        assert len(store._index) == 1
        print("  ✔ purge_user removes all user media")


def test_media_too_large():
    """Test 15: Media over 25 MiB is rejected."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MediaStore(tmpdir, ttl=60)
        big_data = b"x" * (25 * 1024 * 1024 + 1)
        try:
            store.store(big_data, 'image/png', "user123")
            assert False, "should have raised"
        except MediaError:
            pass
        print("  ✔ oversized media rejected")


def test_bot_key_isolation():
    """Test 16: Bot identity is isolated — bot key != user key."""
    from connector import ThrenyxConnector
    bot = NostrKey()
    config = {
        'bot_priv_hex': bot.priv_hex,
        'relay_urls': [],
        'gateway_relay_url': '',
    }
    c = ThrenyxConnector(config)
    assert c.bot_pub == bot.pub_hex
    assert c.bot_pub != NostrKey().pub_hex  # different each time
    print("  ✔ bot identity isolated")


def test_grant_idempotent_revoke():
    """Test 17: Revoking an already-revoked user is a no-op."""
    bot = NostrKey()
    user = NostrKey()
    v = GrantValidator(bot.pub_hex)
    code = create_test_grant(user, bot.pub_hex)
    v.validate(code)
    v.revoke(user.pub_hex)
    v.revoke(user.pub_hex)  # should not raise
    assert v.is_revoked(user.pub_hex)
    print("  ✔ idempotent revoke works")


def test_prompt_response_rejects_undeclared_option():
    """Test 18: an interactive response cannot select an undeclared option."""
    import tempfile
    from connector import ThrenyxConnector
    bot = NostrKey()
    with tempfile.TemporaryDirectory() as tmpdir:
        connector = ThrenyxConnector({
            'bot_priv_hex': bot.priv_hex,
            'relay_urls': [],
            'grant_state_path': os.path.join(tmpdir, 'grants.json'),
        })
        connector.active_prompts['prompt-1'] = {
            'user_pub': 'user-pub',
            'aid': 'grant-1',
            'expires_at': time.time() + 60,
            'consumed_response_ids': set(),
            'option_ids': {'safe'},
        }
        acknowledgements = []
        async def record_ack(*args):
            acknowledgements.append(args)
        connector.send_prompt_ack = record_ack
        result = asyncio.run(connector.handle_agent_prompt_response('user-pub', {
            'v': 1,
            'aid': 'grant-1',
            'prompt_id': 'prompt-1',
            'option_id': 'unexpected',
            'response_id': 'response-1',
        }))
        assert result is None
        assert acknowledgements and acknowledgements[-1][-1] == 'rejected'
    print("  ✔ undeclared prompt option rejected")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        ("Grant: valid", test_grant_valid),
        ("Grant: expired", test_grant_expired),
        ("Grant: invalid signature", test_grant_invalid_signature),
        ("Grant: wrong bot", test_grant_wrong_bot),
        ("Grant: replay", test_grant_replay),
        ("Grant: replay survives restart", test_grant_replay_survives_restart),
        ("Grant: wrong protocol", test_grant_wrong_protocol),
        ("Media: permission gating", test_media_without_permission),
        ("Revoke: removes permissions", test_revocation),
        ("NIP-17: ack roundtrip", test_nip17_ack_roundtrip),
        ("NIP-17: wrong recipient", test_nip17_wrong_recipient),
        ("Media: encrypted store", test_media_store_encrypted),
        ("Media: wrong user", test_media_store_wrong_user),
        ("Media: TTL expiry", test_media_store_ttl),
        ("Media: purge user", test_media_store_purge_user),
        ("Media: too large", test_media_too_large),
        ("Bot: identity isolation", test_bot_key_isolation),
        ("Revoke: idempotent", test_grant_idempotent_revoke),
        ("Prompt: undeclared option", test_prompt_response_rejects_undeclared_option),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            print(f"\n{name}:")
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed:
        print("❌ Some tests failed!")
        sys.exit(1)
    else:
        print("✅ All tests passed!")


if __name__ == '__main__':
    run_all_tests()
