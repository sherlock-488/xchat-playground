"""Event recorder — capture real XChat events and scrub PII for safe sharing."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Fields to redact (replace with placeholder)
_PII_FIELDS = {
    "sender_id",
    "recipient_id",
    "for_user_id",
    "participant_ids",
    "user_id",
}

_SENSITIVE_PATTERNS = [
    # Bearer tokens / OAuth secrets
    (re.compile(r"Bearer [A-Za-z0-9\-_\.]+"), "Bearer REDACTED"),
    # Numeric IDs > 10 digits (likely real user IDs)
    (re.compile(r'"(\d{10,})"'), '"REDACTED_ID"'),
]


class EventRecorder:
    """Record XChat events to a JSONL file, optionally scrubbing PII.

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
        if key in _PII_FIELDS:
            if isinstance(value, list):
                return [self._fake_id(str(v)) for v in value]
            return self._fake_id(str(value))
        return self._scrub(value)

    def _scrub_string(self, s: str) -> str:
        for pattern, replacement in _SENSITIVE_PATTERNS:
            s = pattern.sub(replacement, s)
        return s

    def _fake_id(self, real_id: str) -> str:
        """Return a consistent fake ID for a real ID (stable across scrubs)."""
        if real_id not in self._id_map:
            idx = len(self._id_map) + 1
            self._id_map[real_id] = f"FAKE_USER_{idx:03d}"
        return self._id_map[real_id]
