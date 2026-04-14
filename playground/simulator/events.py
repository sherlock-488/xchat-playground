"""Generate XChat Activity API event fixtures locally."""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(str, Enum):
    CHAT_RECEIVED = "chat.received"
    CHAT_SENT = "chat.sent"
    CONVERSATION_JOIN = "chat.conversation_join"


# Fixtures directory (bundled with the package)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class EventSimulator:
    """Generate realistic XChat event fixtures for local testing.

    All events are 100% offline — no X API credentials required.
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
        **kwargs: Any,
    ) -> dict:
        """Generate a single event fixture dict."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conv_id = conversation_id or f"DM_{sender_id}_{recipient_id}"
        msg_id = str(uuid.uuid4()).replace("-", "")[:16]

        if event_type == EventType.CHAT_RECEIVED:
            return self._chat_received(
                sender_id, recipient_id, conv_id, msg_id, now,
                encrypted, message_text,
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
