#!/usr/bin/env python3
"""
Threnyx ↔ Hermes API Bridge.

A persistent process that:
1. Listens for NIP-17 gift-wrapped messages on Nostr relays
2. Validates THX-HERMES1 grants from Threnyx
3. Forwards messages to the Hermes Gateway via the API server
4. Sends agentAck NIP-17 messages back to the user
5. Returns Hermes responses via NIP-17
6. Handles media with permission gating and TTL
7. Processes agentRevoke to clean up permissions/sessions/media
"""
import asyncio
import json
import os
import sys
import time
import hashlib
import logging
import aiohttp
import websockets
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nostr_crypto import NostrKey, create_nip17_dm, decode_nip17_dm, verify_event
from grant import GrantValidator, GrantError
from media_store import MediaStore, MediaError
from threnyx_crypto import create_legacy_gift_wrap, decode_legacy_gift_wrap, pair_key, encrypt, decrypt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('threnyx-relay')


class ThrenyxConnector:
    """Main connector: Nostr ↔ Hermes API bridge."""

    def __init__(self, config: dict):
        self.config = config
        self.bot_key = NostrKey(config['bot_priv_hex'])
        self.bot_pub = self.bot_key.pub_hex
        state_path = config.get(
            'grant_state_path',
            os.path.join(os.path.dirname(__file__), 'state', 'grants.json')
        )
        if not os.path.isabs(state_path):
            state_path = os.path.join(os.path.dirname(__file__), state_path)
        self.grant_validator = GrantValidator(self.bot_pub, state_path)
        self.media_store = MediaStore(
            os.path.join(os.path.dirname(__file__), 'media_cache'),
            ttl=config.get('media_ttl', 300)
        )

        # Reconstruct authorization only from durable, validated grants.
        self.paired_users: Dict[str, dict] = {}
        for grant_id, grant in self.grant_validator._consumed.items():
            self.paired_users[grant['user_pub']] = {
                'permissions': set(grant['permissions']),
                'paired_at': grant['consumed_at'],
                'grant_id': grant_id,
            }

        # Max messages to keep in context per user
        self.max_history = config.get('max_history', 20)

        # Session reset — matches Telegram gateway config
        # mode: both = idle reset + daily reset, whichever triggers first
        self.session_idle_minutes = config.get('session_idle_minutes', 1440)  # 24h
        self.session_reset_hour = config.get('session_reset_hour', 4)  # 4am
        self.last_activity: Dict[str, float] = {}  # user_pub -> timestamp

        # Nostr relays
        self.relay_urls = config.get('relay_urls', [
            'wss://nos.lol',
            'wss://relay.primal.net',
            'wss://nostr.mom',
            'wss://relay.damus.io',
            'wss://relay.nostr.band',
        ])

        # Hermes API server
        self.hermes_api_url = config.get('hermes_api_url', 'http://localhost:8642')
        self.hermes_api_key = config.get('hermes_api_key', '')

        # Active relay connections
        self.relay_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.seen_events: set = set()
        self.active_prompts: Dict[str, dict] = {}

    async def send_agent_ack(self, user_pub: str, grant_id: str, nonce_hash: str):
        """Send agentAck NIP-17 message to the user (legacy format)."""
        ack = {
            "t": "agentAck",
            "aid": grant_id,
            "nonceHash": nonce_hash
        }
        # Use legacy format — bot doesn't have nip17 protocol in Threnyx contacts
        gift_wrap = create_legacy_gift_wrap(
            self.bot_key.priv_hex, self.bot_pub, user_pub, ack
        )
        await self.publish_to_relays(gift_wrap)
        logger.info(f"Sent agentAck to {user_pub[:16]}... for grant {grant_id}")

    async def handle_grant_code(self, code: str) -> dict:
        """Process a THX-HERMES1 grant code from a user."""
        try:
            payload = self.grant_validator.validate(code)
        except GrantError as e:
            logger.warning(f"Grant validation failed: {e}")
            return {"success": False, "error": str(e)}

        user_pub = payload['userPub']
        nonce_hash = hashlib.sha256(payload['nonce'].encode()).hexdigest()

        # Pair the user
        self.paired_users[user_pub] = {
            'permissions': set(payload.get('_normalized_permissions', ['text'])),
            'paired_at': int(time.time()),
            'grant_id': payload['id'],
        }

        # Send agentAck
        await self.send_agent_ack(user_pub, payload['id'], nonce_hash)

        # Send agentManifest with available commands
        await self.send_agent_manifest(user_pub, payload['id'])

        logger.info(f"User {user_pub[:16]}... paired with permissions: {payload.get('_normalized_permissions')}")
        return {"success": True, "payload": payload}

    async def handle_inbound_message(self, gift_wrap: dict):
        """Handle an inbound gift-wrapped message (NIP-17 or legacy)."""
        try:
            if not verify_event(gift_wrap):
                logger.warning("Invalid gift wrap signature, discarding")
                return

            if gift_wrap['kind'] not in (1059, 21059):
                return

            event_id = gift_wrap['id']
            if event_id in self.seen_events:
                return
            self.seen_events.add(event_id)

            # Check the p tag is for our bot
            p_tag = None
            for tag in gift_wrap.get('tags', []):
                if tag[0] == 'p':
                    p_tag = tag[1]
                    break
            if not p_tag or p_tag != self.bot_pub:
                return

            # Try standard NIP-17 first, then legacy format
            sender_pub = None
            content = None

            # Try NIP-17 standard (seal kind 13 + NIP-44 v2)
            try:
                sender_pub, rumor = decode_nip17_dm(self.bot_key.priv_hex, gift_wrap)
                content = rumor.get('content', '')
                kind = rumor.get('kind', 0)
                logger.info(f"NIP-17 standard message from {sender_pub[:16]}... kind={kind}")
            except Exception:
                # Try legacy format ({from, box} with ECDH+AES-GCM)
                try:
                    sender_pub, payload = decode_legacy_gift_wrap(self.bot_key.priv_hex, gift_wrap)
                    content = json.dumps(payload, separators=(',', ':'))
                    logger.info(f"Legacy message from {sender_pub[:16]}...")
                except Exception as e:
                    logger.warning(f"Failed to decode gift wrap (both formats): {e}")
                    return

        except Exception as e:
            logger.warning(f"Failed to process gift wrap: {e}")
            return

        if not sender_pub or not content:
            return

        # Check session reset conditions (idle + daily, like Telegram gateway)
        self.check_session_reset(sender_pub)

        logger.info(f"Message from {sender_pub[:16]}...")

        # Check if sender is paired
        if sender_pub not in self.paired_users:
            logger.warning(f"Message from unpaired user: {sender_pub[:16]}...")
            return

        # Check text permission
        if not self.grant_validator.has_permission(sender_pub, 'text'):
            logger.warning(f"User {sender_pub[:16]}... lacks text permission")
            return

        # Parse the payload
        try:
            msg_data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            msg_data = None

        if not isinstance(msg_data, dict):
            return

        msg_type = msg_data.get('t', '')

        # Handle agentRevoke
        if msg_type == 'agentRevoke':
            await self.handle_revoke(sender_pub)
            return

        # Handle agentPromptResponse (user responded to a prompt/approval/choice)
        if msg_type == 'agentPromptResponse':
            option_id = await self.handle_agent_prompt_response(sender_pub, msg_data)
            if option_id:
                logger.info(f"Prompt response: user selected {option_id}")
                # TODO: forward to Hermes as prompt_response when API supports it
            return

        # Handle presence pings — respond with presence, don't forward to Hermes
        if msg_type == 'presence':
            await self.send_payload(sender_pub, {"t": "presence"})
            return

        # Handle typing indicator
        if msg_type == 'typing':
            return  # ignore

        # Handle message receipt (delivered/read)
        if msg_type == 'rcpt':
            return  # ignore — just a receipt confirmation

        # Handle message delete
        if msg_type == 'del':
            return  # ignore — Threnyx internal

        # Handle profile
        if msg_type == 'profile':
            return  # ignore

        # Handle actual text messages
        if msg_type == 'msg':
            user_text = msg_data.get('text', '')
            if not user_text.strip():
                return

            mid = msg_data.get('mid', '')

            # Send delivered receipt
            if mid:
                await self.send_payload(sender_pub, {"t": "rcpt", "mid": mid, "status": "delivered"})

            # Forward ALL messages (including /commands) to Hermes
            await self.forward_to_hermes(sender_pub, user_text)

            # Send read receipt
            if mid:
                await self.send_payload(sender_pub, {"t": "rcpt", "mid": mid, "status": "read"})
            return

        # Unknown payload type — log but don't forward
        logger.info(f"Unknown payload type '{msg_type}' from {sender_pub[:16]}... — ignoring")

    def check_session_reset(self, user_pub: str):
        """Check if session should be reset (idle timeout + daily reset, like Telegram).

        Config matches Hermes gateway: mode=both, idle_minutes=1440, at_hour=4
        Whichever triggers first wins.
        """
        now = time.time()
        last = self.last_activity.get(user_pub, 0)

        # Track last daily reset date per user
        last_reset_key = f"_last_daily_reset_{user_pub}"
        last_daily = getattr(self, last_reset_key, 0)

        # Check idle reset (1440 min = 24h)
        if last > 0 and (now - last) > (self.session_idle_minutes * 60):
            if user_pub in self.paired_users:
                old_count = len(self.paired_users[user_pub].get('history', []))
                self.paired_users[user_pub]['history'] = []
                logger.info(f"Session reset (idle {self.session_idle_minutes}min) for {user_pub[:16]}... ({old_count} msgs cleared)")
            self.last_activity[user_pub] = now
            return

        # Check daily reset (at_hour=4, i.e. 4am local)
        import datetime
        now_dt = datetime.datetime.now()
        reset_dt = now_dt.replace(hour=self.session_reset_hour, minute=0, second=0, microsecond=0)
        if now_dt < reset_dt:
            reset_dt = reset_dt - datetime.timedelta(days=1)  # previous day's 4am

        reset_ts = reset_dt.timestamp()
        if last_daily < reset_ts <= now and last > 0:
            if user_pub in self.paired_users:
                old_count = len(self.paired_users[user_pub].get('history', []))
                self.paired_users[user_pub]['history'] = []
                logger.info(f"Session reset (daily at {self.session_reset_hour}h) for {user_pub[:16]}... ({old_count} msgs cleared)")

        setattr(self, last_reset_key, now)

    # Fallback manifest. Production deployments should replace it with the
    # approved gateway registry rather than advertise unsupported commands.
    COMMAND_MANIFEST = [
        {"name": "new", "description": "Nouvelle conversation (efface le contexte)"},
        {"name": "reset", "description": "Réinitialise la conversation (alias /new)"},
        {"name": "model", "description": "Changer ou voir le modèle IA", "options": [{"name": "name"}]},
        {"name": "help", "description": "Afficher l'aide et les commandes disponibles"},
        {"name": "status", "description": "Informations de session"},
        {"name": "retry", "description": "Renvoyer le dernier message"},
        {"name": "undo", "description": "Annuler le dernier échange"},
        {"name": "title", "description": "Nommer la session"},
        {"name": "compress", "description": "Compresser le contexte de conversation"},
        {"name": "voice", "description": "Contrôler les réponses vocales"},
        {"name": "usage", "description": "Afficher l'utilisation de tokens"},
        {"name": "sessions", "description": "Lister les sessions précédentes"},
    ]

    async def send_agent_manifest(self, user_pub: str, grant_id: str):
        """Send agentManifest to Threnyx with the list of available commands."""
        manifest = {
            "t": "agentManifest",
            "v": 1,
            "aid": grant_id,
            "revision": 1,
            "commands": self.COMMAND_MANIFEST,
        }
        await self.send_payload(user_pub, manifest)
        logger.info(f"Sent agentManifest to {user_pub[:16]}... ({len(self.COMMAND_MANIFEST)} commands)")

    async def send_agent_prompt(self, user_pub: str, aid: str, prompt_kind: str,
                                 content: str, options: list, timeout_s: int = 300) -> str:
        """Send an agentPrompt to Threnyx (for approvals, clarifications, choices).

        Returns the prompt_id. Threnyx will display buttons for the user.
        """
        import secrets
        if prompt_kind not in ('approval', 'clarify', 'choice'):
            raise ValueError('invalid prompt_kind')
        if not isinstance(options, list) or not 1 <= len(options) <= 10:
            raise ValueError('prompt must contain 1 to 10 options')
        option_ids = set()
        for option in options:
            option_id = option.get('id') if isinstance(option, dict) else None
            label = option.get('label') if isinstance(option, dict) else None
            if (not isinstance(option_id, str) or not option_id or len(option_id) > 32
                    or not isinstance(label, str) or not label or len(label) > 100
                    or option_id in option_ids):
                raise ValueError('invalid prompt option')
            option_ids.add(option_id)
        timeout_s = max(30, min(86400, int(timeout_s)))
        prompt_id = secrets.token_hex(8)

        prompt = {
            "t": "agentPrompt",
            "v": 1,
            "aid": aid,
            "prompt_id": prompt_id,
            "prompt_kind": prompt_kind,  # "approval", "clarify", "choice"
            "content": content,
            "options": options,  # [{id, label, style?}]
            "timeout_s": timeout_s,
        }

        self.active_prompts[prompt_id] = {
            "user_pub": user_pub,
            "aid": aid,
            "expires_at": time.time() + timeout_s,
            "consumed_response_ids": set(),
            "option_ids": option_ids,
        }

        await self.send_payload(user_pub, prompt)
        logger.info(f"Sent agentPrompt {prompt_id} to {user_pub[:16]}... (kind={prompt_kind})")
        return prompt_id

    async def handle_agent_prompt_response(self, user_pub: str, response: dict) -> Optional[str]:
        """Handle agentPromptResponse from Threnyx.

        Validates: pubkey, aid, prompt_id active, option_id declared,
        expiration, response_id not consumed.
        Returns the selected option_id, or None on failure.
        """
        prompt_id = response.get("prompt_id", "")
        aid = response.get("aid", "")
        option_id = response.get("option_id", "")
        response_id = response.get("response_id", "")

        if (response.get('v') != 1 or not all(isinstance(value, str) and value
                for value in (prompt_id, aid, option_id, response_id))):
            logger.warning('agentPromptResponse: malformed response')
            return None

        # Validate prompt exists and is active
        if prompt_id not in self.active_prompts:
            logger.warning(f"agentPromptResponse: unknown prompt_id {prompt_id}")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "rejected")
            return None

        prompt = self.active_prompts[prompt_id]

        # Validate user
        if prompt["user_pub"] != user_pub:
            logger.warning(f"agentPromptResponse: wrong user for prompt {prompt_id}")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "rejected")
            return None

        # Validate aid
        if prompt["aid"] != aid:
            logger.warning(f"agentPromptResponse: wrong aid for prompt {prompt_id}")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "rejected")
            return None

        if option_id not in prompt['option_ids']:
            logger.warning(f"agentPromptResponse: undeclared option for prompt {prompt_id}")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "rejected")
            return None

        # Check expiration
        if time.time() > prompt["expires_at"]:
            logger.warning(f"agentPromptResponse: prompt {prompt_id} expired")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "expired")
            del self.active_prompts[prompt_id]
            return None

        # Check response_id not already consumed (replay protection)
        if response_id in prompt["consumed_response_ids"]:
            logger.warning(f"agentPromptResponse: response_id {response_id} already consumed (replay)")
            await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "rejected")
            return None

        # Mark as consumed
        prompt["consumed_response_ids"].add(response_id)

        # Send ack
        await self.send_prompt_ack(user_pub, aid, prompt_id, response_id, "accepted")
        logger.info(f"agentPromptResponse accepted: prompt={prompt_id} option={option_id}")
        return option_id

    async def send_prompt_ack(self, user_pub: str, aid: str, prompt_id: str,
                               response_id: str, status: str):
        """Send agentPromptAck to Threnyx."""
        ack = {
            "t": "agentPromptAck",
            "v": 1,
            "aid": aid,
            "prompt_id": prompt_id,
            "response_id": response_id,
            "status": status,  # accepted, rejected, expired
        }
        await self.send_payload(user_pub, ack)
        logger.info(f"Sent agentPromptAck: prompt={prompt_id} status={status}")

    async def handle_revoke(self, user_pub: str):
        """Process agentRevoke: remove all permissions, sessions, and media."""
        logger.info(f"Processing agentRevoke for {user_pub[:16]}...")

        self.grant_validator.revoke(user_pub)
        self.paired_users.pop(user_pub, None)
        self.media_store.purge_user(user_pub)

        logger.info(f"Revoked all access for {user_pub[:16]}...")

    async def forward_to_hermes(self, user_pub: str, user_text: str):
        """Forward a text message to Hermes API server with persistent conversation context."""
        if not user_text.strip():
            return

        # Track activity for session reset
        self.last_activity[user_pub] = time.time()

        logger.info(f"Forwarding to Hermes: '{user_text[:80]}'")

        # Slash commands — forward ALL to Hermes, don't interpret locally
        # (per Threnyx connector prompt: "Toutes les commandes / envoyées par
        #  Threnyx doivent être remises au dispatcher Hermes sans interprétation")

        # Build conversation history
        if user_pub not in self.paired_users:
            self.paired_users[user_pub] = {'permissions': {'text'}, 'history': []}
        elif 'history' not in self.paired_users[user_pub]:
            self.paired_users[user_pub]['history'] = []

        history = self.paired_users[user_pub]['history']

        # Build messages array: system + history + new user message
        messages = [
            {"role": "system", "content": "You are Hermes, a personal AI assistant. Reply concisely in the same language as the user. The user is communicating via Threnyx (Nostr encrypted messaging). You have persistent conversation context across messages."}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        # Send to Hermes API via OpenAI-compatible endpoint
        headers = {
            "Authorization": f"Bearer {self.hermes_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.get('hermes_model', 'openai-gpt-56-luna'),
            "messages": messages,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.hermes_api_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        choices = result.get('choices', [])
                        if choices:
                            response_text = choices[0].get('message', {}).get('content', '')
                        else:
                            response_text = "[Pas de réponse]"
                    else:
                        logger.error(f"Hermes API error status={resp.status}")
                        response_text = f"[Erreur Hermes API: {resp.status}]"
        except Exception as e:
            logger.error(f"Failed to reach Hermes API: {type(e).__name__}")
            response_text = "[Erreur de connexion Hermes]"

        logger.info(f"Hermes responded: '{response_text[:80]}'")

        # Save conversation history
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": response_text})

        # Trim history to max length
        if len(history) > self.max_history * 2:
            self.paired_users[user_pub]['history'] = history[-(self.max_history * 2):]

        # Send response back via NIP-17
        await self.send_nip17_reply(user_pub, response_text)

    async def send_payload(self, user_pub: str, payload: dict):
        """Send a Threnyx payload via legacy gift wrap."""
        gift_wrap = create_legacy_gift_wrap(
            self.bot_key.priv_hex, self.bot_pub, user_pub, payload
        )
        await self.publish_to_relays(gift_wrap)
        logger.info(f"Sent payload '{payload.get('t','')}' to {user_pub[:16]}...")

    async def send_nip17_reply(self, user_pub: str, text: str):
        """Send a text response to the user via legacy gift wrap."""
        response_payload = {
            "t": "msg",
            "mid": hashlib.sha256(
                (self.bot_pub + str(time.time())).encode()
            ).hexdigest()[:32],
            "text": text,
        }

        gift_wrap = create_legacy_gift_wrap(
            self.bot_key.priv_hex, self.bot_pub, user_pub, response_payload
        )
        await self.publish_to_relays(gift_wrap)
        logger.info(f"Sent reply to {user_pub[:16]}... ({len(text)} chars)")

    async def publish_to_relays(self, event: dict):
        """Publish an event to all connected Nostr relays."""
        msg = json.dumps(["EVENT", event])
        for url, ws in list(self.relay_connections.items()):
            try:
                await ws.send(msg)
                # Wait briefly for OK
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    result = json.loads(raw)
                    if result[0] == "OK":
                        logger.info(f"Event {event['id'][:16]}... accepted by {url}")
                    elif result[0] == "NOTICE":
                        logger.warning(f"NOTICE from {url}: {result[1][:100]}")
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                logger.warning(f"Failed to publish to {url}: {e}")

    async def connect_relays(self):
        """Connect to Nostr relays and subscribe to gift wraps."""
        filt = {
            "kinds": [1059, 21059],
            "#p": [self.bot_pub],
            "limit": 0,
        }
        sub_id = "threnyx-" + self.bot_pub[:8]

        for url in self.relay_urls:
            try:
                ws = await websockets.connect(url, ping_interval=30, ping_timeout=10)
                self.relay_connections[url] = ws
                await ws.send(json.dumps(["REQ", sub_id, filt]))
                logger.info(f"Connected to relay: {url}")
            except Exception as e:
                logger.warning(f"Failed to connect to relay {url}: {e}")

    async def listen_relays(self):
        """Listen for incoming events from all relays."""
        logger.info("Listening for Nostr events...")

        while True:
            had_activity = False
            for url, ws in list(self.relay_connections.items()):
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    msg = json.loads(raw)

                    if msg[0] == "EVENT":
                        event = msg[2]
                        await self.handle_inbound_message(event)
                        had_activity = True
                    elif msg[0] == "EOSE":
                        logger.info(f"End of stored events from {url}")
                    elif msg[0] == "NOTICE":
                        logger.info(f"NOTICE from {url}: {msg[1][:100] if len(msg) > 1 else ''}")

                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    logger.warning(f"Relay {url} disconnected, reconnecting in 5s...")
                    self.relay_connections.pop(url, None)
                    await asyncio.sleep(5)
                    try:
                        new_ws = await websockets.connect(url, ping_interval=30, ping_timeout=10)
                        self.relay_connections[url] = new_ws
                        filt = {
                            "kinds": [1059, 21059],
                            "#p": [self.bot_pub],
                            "limit": 0,
                        }
                        await new_ws.send(json.dumps(["REQ", "threnyx-" + self.bot_pub[:8], filt]))
                        logger.info(f"Reconnected to relay: {url}")
                    except Exception as e:
                        logger.error(f"Failed to reconnect to {url}: {e}")
                except Exception as e:
                    logger.error(f"Error on relay {url}: {e}")
                    self.relay_connections.pop(url, None)

            if not had_activity:
                await asyncio.sleep(0.1)

    async def run(self):
        """Main run loop."""
        logger.info("=" * 60)
        logger.info(f"Threnyx ↔ Hermes Relay Connector")
        logger.info(f"Bot pubkey: {self.bot_pub}")
        logger.info(f"Hermes API: {self.hermes_api_url}")
        logger.info(f"Relays: {len(self.relay_urls)} configured")
        logger.info("=" * 60)

        # Connect to relays
        await self.connect_relays()

        # Listen for events
        await self.listen_relays()

    def get_status(self) -> dict:
        return {
            "bot_pub": self.bot_pub,
            "paired_users": len(self.paired_users),
            "relays_connected": len(self.relay_connections),
            "media_items": len(self.media_store._index),
        }


def load_config() -> dict:
    """Load configuration from config.json and environment."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    config = {}

    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    config['bot_priv_hex'] = os.environ.get(
        'THRENYX_BOT_PRIV_KEY', config.get('bot_priv_hex', '')
    )
    config['hermes_api_url'] = os.environ.get(
        'HERMES_API_URL', config.get('hermes_api_url', 'http://localhost:8642')
    )
    config['hermes_api_key'] = os.environ.get(
        'HERMES_API_KEY', config.get('hermes_api_key', '')
    )
    config['media_ttl'] = int(os.environ.get(
        'THRENYX_MEDIA_TTL', str(config.get('media_ttl', 300))
    ))
    config['grant_state_path'] = os.environ.get(
        'THRENYX_GRANT_STATE_PATH',
        config.get('grant_state_path', os.path.join(os.path.dirname(__file__), 'state', 'grants.json'))
    )

    if not config['bot_priv_hex']:
        raise ValueError("bot_priv_hex not configured")

    return config


async def main():
    config = load_config()
    connector = ThrenyxConnector(config)
    await connector.run()


if __name__ == '__main__':
    asyncio.run(main())
