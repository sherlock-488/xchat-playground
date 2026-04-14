"""Generate XChat Activity API event fixtures locally.

Two fixture schemas are available:

  "demo"     — Flat structure for teaching and local testing. Easy to read.
               Uses direct_message_events / encrypted_content style.
               NOT the official XAA envelope — for education only.

  "official" — Mirrors the envelope structure consumed by xchat-bot-python
               (github.com/xdevplatform/xchat-bot-python).
               Uses data.event_type + data.payload with encoded_event /
               encrypted_conversation_key fields.
               Field-level schema inferred from official bot source until
               docs.x.com publishes a complete XChat payload reference.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from playground.crypto.stub import STUB_PREFIX


class EventType(str, Enum):
    CHAT_RECEIVED = "chat.received"
    CHAT_SENT = "chat.sent"
    CONVERSATION_JOIN = "chat.conversation_join"


# Fixtures directory (bundled with the package)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class EventSimulator:
    """Generate XChat event fixtures for local testing.

    All events are 100% offline — no X API credentials required.

    Schema modes:
        "demo"     — Flat, easy-to-read structure for teaching (default)
        "official" — Mirrors xchat-bot-python envelope (data.payload)
    """

    def generate(
        self,
        event_type: EventType,
        *,
        sender_id: str = "111222333",
        recipient_id: str = "444555666",
        conversation_id: str | None = None,
        user_id: str | None = None,
        encrypted: bool = True,
        message_text: str = "Hello from xchat-playground!",
        schema: str = "demo",
        **kwargs: Any,
    ) -> dict:
        """Generate a single event fixture dict.

        Args:
            schema: "demo" (flat, easy-to-read, default) or "official"
                    (mirrors xchat-bot-python data.payload envelope).
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conv_id = conversation_id or f"DM_{sender_id}_{recipient_id}"
        msg_id = str(uuid.uuid4()).replace("-", "")[:16]

        if schema == "official":
            return self._official_envelope(
                event_type,
                sender_id,
                recipient_id,
                conv_id,
                msg_id,
                now,
                message_text,
            )

        if event_type == EventType.CHAT_RECEIVED:
            return self._chat_received(
                sender_id,
                recipient_id,
                conv_id,
                msg_id,
                now,
                encrypted,
                message_text,
            )
        elif event_type == EventType.CHAT_SENT:
            return self._chat_sent(sender_id, recipient_id, conv_id, msg_id, now)
        elif event_type == EventType.CONVERSATION_JOIN:
            return self._conversation_join(user_id or sender_id, conv_id, now)
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    def load_fixture(self, name: str) -> dict:
        """Load a bundled fixture file by name (without .json extension)."""
        path = FIXTURES_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return json.loads(path.read_text())

    # ── private builders ──────────────────────────────────────────────────────

    def _chat_received(
        self,
        sender_id: str,
        recipient_id: str,
        conversation_id: str,
        message_id: str,
        timestamp: str,
        encrypted: bool,
        plaintext: str,
    ) -> dict:
        payload: dict = {
            "event_type": "chat.received",
            "created_at": timestamp,
            "for_user_id": recipient_id,
            "direct_message_events": [
                {
                    "id": message_id,
                    "event_type": "MessageCreate",
                    "created_at": timestamp,
                    "dm_conversation_id": conversation_id,
                    "sender_id": sender_id,
                    "participant_ids": [sender_id, recipient_id],
                }
            ],
        }

        if encrypted:
            # Stub encrypted payload — format mirrors xchat-bot-python expectations
            stub_bytes = base64.b64encode(plaintext.encode()).decode()
            payload["direct_message_events"][0]["message"] = {
                "encrypted_content": f"STUB_ENC_{stub_bytes}",
                "encryption_type": "XChaCha20Poly1305",
                "key_version": "1",
                # NOTE: real events include a per-recipient encrypted key blob here
                "recipient_keys": {
                    recipient_id: f"STUB_KEY_{os.urandom(8).hex()}",
                },
            }
        else:
            payload["direct_message_events"][0]["message"] = {
                "text": plaintext,
            }

        return payload

    def _chat_sent(
        self,
        sender_id: str,
        recipient_id: str,
        conversation_id: str,
        message_id: str,
        timestamp: str,
    ) -> dict:
        return {
            "event_type": "chat.sent",
            "created_at": timestamp,
            "for_user_id": sender_id,
            "direct_message_events": [
                {
                    "id": message_id,
                    "event_type": "MessageCreate",
                    "created_at": timestamp,
                    "dm_conversation_id": conversation_id,
                    "sender_id": sender_id,
                    "participant_ids": [sender_id, recipient_id],
                    "message": {
                        # sent events typically include plaintext for the sender
                        "text": "[Sent message — plaintext available to sender only]",
                    },
                }
            ],
        }

    def _conversation_join(
        self,
        user_id: str,
        conversation_id: str,
        timestamp: str,
    ) -> dict:
        return {
            "event_type": "chat.conversation_join",
            "created_at": timestamp,
            "for_user_id": user_id,
            "direct_message_events": [
                {
                    "id": str(uuid.uuid4()).replace("-", "")[:16],
                    "event_type": "ParticipantsJoin",
                    "created_at": timestamp,
                    "dm_conversation_id": conversation_id,
                    "participant_ids": [user_id],
                }
            ],
        }

    def _official_envelope(
        self,
        event_type: EventType,
        sender_id: str,
        recipient_id: str,
        conversation_id: str,
        message_id: str,
        timestamp: str,
        plaintext: str,
    ) -> dict:
        """Generate an event using the official XAA envelope structure.

        Mirrors the structure consumed by xchat-bot-python:
            data.event_type + data.payload with encoded_event /
            encrypted_conversation_key / conversation_key_version.

        NOTE: Field-level schema inferred from official bot source code.
        Stub values used — real decryption requires chat-xdk + private keys.
        """
        # Use STUB_ENC_ prefix so StubCrypto.decrypt() can decode this directly.
        # playground crypto stub "STUB_ENC_<base64(plaintext)>" → plaintext
        stub_encoded = STUB_PREFIX + base64.b64encode(plaintext.encode()).decode()
        stub_enc_key = base64.b64encode(os.urandom(32)).decode()

        return {
            "_schema": "official-xaa",
            "_note": (
                "Stub fixture — mirrors xchat-bot-python envelope. "
                "encoded_event uses STUB_ENC_ prefix: run 'playground crypto stub <value>' to decode. "
                "Real decryption requires chat-xdk + private keys from state.json."
            ),
            "data": {
                "event_type": event_type.value,
                "payload": {
                    "conversation_id": conversation_id,
                    "encoded_event": stub_encoded,
                    "encrypted_conversation_key": stub_enc_key,
                    "conversation_key_version": "1",
                    "conversation_token": f"STUB_TOKEN_{message_id}",
                },
            },
        }
