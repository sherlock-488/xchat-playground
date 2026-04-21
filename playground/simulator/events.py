"""Generate XChat Activity API event fixtures locally.

Three fixture schemas are available:

  "demo"     — Flat structure for teaching and local testing. Easy to read.
               Uses direct_message_events / encrypted_content style.
               NOT the observed XAA envelope — for education only.

  "docs"     — Mirrors payload examples given in official docs.x.com pages.
               Currently only profile.update.bio has a complete official
               delivery example. Use this schema for that event type.

  "observed" — Mirrors the envelope structure consumed by xchat-bot-python
               (github.com/xdevplatform/xchat-bot-python).
               Uses data.event_type + data.payload with encoded_event /
               encrypted_conversation_key fields.
               Field-level schema inferred from official bot source until
               docs.x.com publishes a complete XChat payload reference.
               ⚠️  Currently only supported for chat.received.
               chat.sent and chat.conversation_join have no confirmed
               official payload shape yet — use schema="demo" for those.

  "official" — DEPRECATED alias for "observed". Will be removed in a future
               release. Use --schema observed instead.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
import warnings
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from playground.crypto.stub import STUB_PREFIX


class EventType(str, Enum):
    CHAT_RECEIVED = "chat.received"
    CHAT_SENT = "chat.sent"
    CONVERSATION_JOIN = "chat.conversation_join"
    PROFILE_UPDATE_BIO = "profile.update.bio"


# Fixtures directory (bundled with the package)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class EventSimulator:
    """Generate XChat / X Activity API event fixtures for local testing.

    All events are 100% offline — no X API credentials required.

    Schema modes:
        "demo"     — Flat, easy-to-read structure for teaching (default).
                     Supported for all chat event types.
        "docs"     — Mirrors official docs.x.com delivery examples.
                     Currently supported for PROFILE_UPDATE_BIO only.
        "observed" — Mirrors xchat-bot-python envelope (data.payload).
                     Only supported for CHAT_RECEIVED; raises ValueError
                     for other event types (payload shape not yet confirmed).
        "official" — DEPRECATED alias for "observed".
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
        strict: bool = False,
        # profile.update.bio specific
        bio_before: str = "Mars & Cars",
        bio_after: str = "Mars, Cars & AI",
        tag: str = "",
        filter_user_id: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """Generate a single event fixture dict.

        Args:
            schema: "demo" (flat, easy-to-read, default), "docs" (official
                    docs.x.com examples), "observed" (xchat-bot-python envelope),
                    or "official" (deprecated alias for "observed").
            strict: When True with schema="observed"/"official", strip the
                    _schema and _note metadata fields for a clean XAA envelope.
        """
        # Handle deprecated "official" alias
        if schema == "official":
            warnings.warn(
                "schema='official' is deprecated — use schema='observed' instead. "
                "'official' will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            schema = "observed"

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conv_id = conversation_id or f"DM_{sender_id}_{recipient_id}"
        msg_id = str(uuid.uuid4()).replace("-", "")[:16]

        if schema == "observed":
            if event_type != EventType.CHAT_RECEIVED:
                raise ValueError(
                    f"schema='observed' is currently only modelled for "
                    f"EventType.CHAT_RECEIVED (inferred from xchat-bot-python). "
                    f"'{event_type.value}' has no confirmed official payload shape yet. "
                    f"Use schema='demo' for {event_type.value}, or open an issue if "
                    f"you have observed the real payload structure."
                )
            result = self._observed_envelope(
                event_type,
                sender_id,
                recipient_id,
                conv_id,
                msg_id,
                now,
                message_text,
            )
            if strict:
                result.pop("_schema", None)
                result.pop("_note", None)
            return result

        if schema == "docs":
            if event_type == EventType.PROFILE_UPDATE_BIO:
                return self._profile_update_bio_docs(
                    user_id=filter_user_id or user_id or sender_id,
                    bio_before=bio_before,
                    bio_after=bio_after,
                    tag=tag,
                )
            raise ValueError(
                f"schema='docs' is currently only supported for "
                f"EventType.PROFILE_UPDATE_BIO (the only event type with a "
                f"complete official delivery example in docs.x.com). "
                f"Use schema='demo' for {event_type.value}."
            )

        # Default: demo schema
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
        elif event_type == EventType.PROFILE_UPDATE_BIO:
            # demo schema for profile.update.bio falls through to docs shape
            return self._profile_update_bio_docs(
                user_id=filter_user_id or user_id or sender_id,
                bio_before=bio_before,
                bio_after=bio_after,
                tag=tag,
            )
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
            stub_bytes = base64.b64encode(plaintext.encode()).decode()
            payload["direct_message_events"][0]["message"] = {
                "encrypted_content": f"STUB_ENC_{stub_bytes}",
                "encryption_type": "XChaCha20Poly1305",
                "key_version": "1",
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

    def _profile_update_bio_docs(
        self,
        user_id: str,
        bio_before: str,
        bio_after: str,
        tag: str,
    ) -> dict:
        """Generate a profile.update.bio event using the official docs.x.com shape.

        Source: X Activity API quickstart — profile.update.bio delivery example.
        This is the only XAA event type with a complete official payload example
        in docs.x.com as of 2026-04-17.

        Schema: docs (aligned with official docs.x.com delivery example)
        """
        envelope: dict = {
            "data": {
                "filter": {
                    "user_id": user_id,
                },
                "event_type": "profile.update.bio",
                "payload": {
                    "before": bio_before,
                    "after": bio_after,
                },
            }
        }
        if tag:
            envelope["data"]["tag"] = tag
        return envelope

    def _observed_envelope(
        self,
        event_type: EventType,
        sender_id: str,
        recipient_id: str,
        conversation_id: str,
        message_id: str,
        timestamp: str,
        plaintext: str,
    ) -> dict:
        """Generate an event using the observed XAA envelope structure.

        Mirrors the structure consumed by xchat-bot-python:
            data.event_type + data.payload with encoded_event /
            encrypted_conversation_key / conversation_key_version.

        NOTE: Field-level schema inferred from official bot source code.
        Stub values used — real decryption requires chat-xdk + private keys.
        Schema: observed (inferred from xchat-bot-python, not yet in docs.x.com)
        """
        stub_encoded = STUB_PREFIX + base64.b64encode(plaintext.encode()).decode()
        stub_enc_key = base64.b64encode(os.urandom(32)).decode()

        return {
            "_schema": "observed-xaa",
            "_note": (
                "Stub fixture — mirrors xchat-bot-python envelope. "
                "encoded_event uses STUB_ENC_ prefix: run 'playground crypto stub <value>' to decode. "
                "Real decryption requires chat-xdk + private keys from state.json. "
                "Schema: observed (inferred from xchat-bot-python, not yet in docs.x.com)."
            ),
            "data": {
                "event_type": event_type.value,
                "payload": {
                    "conversation_id": conversation_id,
                    "encoded_event": stub_encoded,
                    "sender_id": sender_id,
                    "encrypted_conversation_key": stub_enc_key,
                    "conversation_key_version": "1",
                    "conversation_key_change_event": None,
                    "conversation_token": f"STUB_TOKEN_{message_id}",
                },
            },
        }
