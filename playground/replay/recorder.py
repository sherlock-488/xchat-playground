"""Event recorder — capture real XChat events and scrub PII for safe sharing."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── ID fields to replace with stable fake IDs ─────────────────────────────────
# These are numeric user/message identifiers that could identify real people.
_PII_ID_FIELDS = {
    "sender_id",
    "recipient_id",
    "for_user_id",
    "participant_ids",
    "user_id",
    "message_id",
    "id",
}

# ── Conversation/session identifiers to replace ───────────────────────────────
# These can fingerprint a conversation even without direct user IDs.
_PII_CONV_FIELDS = {
    "conversation_id",
    "dm_conversation_id",
    "conversation_token",
}

# ── Crypto blob fields to redact (replace with fixed placeholder) ─────────────
# These are ciphertext/key material — not plaintext PII, but should not be
# shared publicly in bug reports or replay packs.
_CRYPTO_BLOB_FIELDS = {
    "encoded_event": "REDACTED_ENCODED_EVENT",
    "encrypted_conversation_key": "REDACTED_ENCRYPTED_KEY",
    "conversation_key_change_event": "REDACTED_KEY_CHANGE_EVENT",
    "encrypted_content": "REDACTED_ENCRYPTED_CONTENT",
    "recipient_keys": "REDACTED_RECIPIENT_KEYS",
}

_SENSITIVE_PATTERNS = [
    # Bearer tokens / OAuth secrets
    (re.compile(r"Bearer [A-Za-z0-9\-_\.]+"), "Bearer REDACTED"),
    # Numeric IDs > 10 digits (likely real user IDs)
    (re.compile(r'"(\d{10,})"'), '"REDACTED_ID"'),
]


class EventRecorder:
    """Record XChat events to a JSONL file, optionally scrubbing PII.

    Scrubbing covers two layers:
      1. ID fields (sender_id, conversation_id, etc.) → stable FAKE_USER_xxx
      2. Crypto blobs (encoded_event, encrypted_conversation_key, etc.) → REDACTED_*

    Usage:
        recorder = EventRecorder(output_path=Path("recordings/session.jsonl"))
        recorder.record(event_dict)
        recorder.save()
    """

    def __init__(
        self,
        output_path: Path = Path("recordings/session.jsonl"),
        scrub_pii: bool = True,
        id_map: dict[str, str] | None = None,
    ):
        self.output_path = output_path
        self.scrub_pii = scrub_pii
        # Consistent fake IDs: real_id → fake_id mapping for reproducibility
        self._id_map: dict[str, str] = id_map or {}
        self._conv_map: dict[str, str] = {}
        self._counter = 0
        self._events: list[dict] = []

    def record(self, event: dict) -> dict:
        """Record a single event. Returns the (possibly scrubbed) event."""
        entry = copy.deepcopy(event)
        if self.scrub_pii:
            entry = self._scrub(entry)
        entry["_recorded_at"] = datetime.now(timezone.utc).isoformat()
        entry["_seq"] = self._counter
        self._counter += 1
        self._events.append(entry)
        return entry

    def save(self) -> Path:
        """Save all recorded events to JSONL file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w") as f:
            for event in self._events:
                f.write(json.dumps(event) + "\n")
        return self.output_path

    def clear(self) -> None:
        self._events.clear()
        self._counter = 0

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    # ── PII scrubbing ─────────────────────────────────────────────────────────

    def _scrub(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._scrub_value(k, v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._scrub(item) for item in obj]
        elif isinstance(obj, str):
            return self._scrub_string(obj)
        return obj

    def _scrub_value(self, key: str, value: Any) -> Any:
        # Layer 1: crypto blobs — replace with fixed placeholder
        if key in _CRYPTO_BLOB_FIELDS:
            return _CRYPTO_BLOB_FIELDS[key]

        # Layer 2: user/message IDs — replace with stable fake IDs
        if key in _PII_ID_FIELDS:
            if isinstance(value, list):
                return [self._fake_id(str(v)) for v in value]
            return self._fake_id(str(value))

        # Layer 3: conversation identifiers — replace with stable fake conv IDs
        if key in _PII_CONV_FIELDS:
            return self._fake_conv_id(str(value))

        return self._scrub(value)

    def _scrub_string(self, s: str) -> str:
        for pattern, replacement in _SENSITIVE_PATTERNS:
            s = pattern.sub(replacement, s)
        return s

    def _fake_id(self, real_id: str) -> str:
        """Return a consistent fake user ID for a real ID (stable across scrubs)."""
        if real_id not in self._id_map:
            idx = len(self._id_map) + 1
            self._id_map[real_id] = f"FAKE_USER_{idx:03d}"
        return self._id_map[real_id]

    def _fake_conv_id(self, real_id: str) -> str:
        """Return a consistent fake conversation ID."""
        if real_id not in self._conv_map:
            idx = len(self._conv_map) + 1
            self._conv_map[real_id] = f"FAKE_CONV_{idx:03d}"
        return self._conv_map[real_id]
