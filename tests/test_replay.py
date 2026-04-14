"""Tests for the replay module (recorder, replayer, diff)."""

import json

from playground.replay.diff import diff_responses
from playground.replay.recorder import EventRecorder


class TestEventRecorder:
    def test_record_single_event(self):
        recorder = EventRecorder(scrub_pii=False)
        event = {"event_type": "chat.received", "for_user_id": "123"}
        recorded = recorder.record(event)
        assert recorded["event_type"] == "chat.received"
        assert "_recorded_at" in recorded
        assert recorded["_seq"] == 0

    def test_sequence_increments(self):
        recorder = EventRecorder(scrub_pii=False)
        for i in range(5):
            e = recorder.record({"event_type": "chat.received"})
            assert e["_seq"] == i

    def test_pii_scrubbing_sender_id(self):
        recorder = EventRecorder(scrub_pii=True)
        event = {
            "event_type": "chat.received",
            "for_user_id": "111222333",
            "direct_message_events": [{"sender_id": "444555666"}],
        }
        recorded = recorder.record(event)
        # Real IDs should be replaced
        assert recorded["for_user_id"] != "111222333"
        assert recorded["for_user_id"].startswith("FAKE_USER_")
        dm = recorded["direct_message_events"][0]
        assert dm["sender_id"] != "444555666"
        assert dm["sender_id"].startswith("FAKE_USER_")

    def test_pii_scrubbing_consistent_ids(self):
        """Same real ID should always map to same fake ID."""
        recorder = EventRecorder(scrub_pii=True)
        e1 = recorder.record({"for_user_id": "REAL_ID_999"})
        e2 = recorder.record({"for_user_id": "REAL_ID_999"})
        assert e1["for_user_id"] == e2["for_user_id"]

    def test_pii_scrubbing_participant_ids_list(self):
        recorder = EventRecorder(scrub_pii=True)
        event = {"direct_message_events": [{"participant_ids": ["111", "222"]}]}
        recorded = recorder.record(event)
        ids = recorded["direct_message_events"][0]["participant_ids"]
        assert isinstance(ids, list)
        assert all(i.startswith("FAKE_USER_") for i in ids)

    def test_save_creates_jsonl(self, tmp_path):
        recorder = EventRecorder(
            output_path=tmp_path / "test.jsonl",
            scrub_pii=False,
        )
        recorder.record({"event_type": "chat.received"})
        recorder.record({"event_type": "chat.sent"})
        path = recorder.save()
        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event_type"] == "chat.received"

    def test_clear_resets_state(self):
        recorder = EventRecorder(scrub_pii=False)
        recorder.record({"event_type": "chat.received"})
        recorder.clear()
        assert len(recorder.events) == 0
        next_event = recorder.record({"event_type": "chat.sent"})
        assert next_event["_seq"] == 0


class TestDiffResponses:
    def test_identical_responses(self):
        a = {"status": 200, "body": "ok"}
        b = {"status": 200, "body": "ok"}
        diff = diff_responses(a, b)
        assert diff == ""

    def test_different_responses(self):
        a = {"status": 200, "body": "ok"}
        b = {"status": 403, "body": "forbidden"}
        diff = diff_responses(a, b)
        assert diff != ""
        assert "200" in diff or "403" in diff

    def test_diff_is_unified_format(self):
        a = {"key": "value_a"}
        b = {"key": "value_b"}
        diff = diff_responses(a, b)
        assert "---" in diff or "+++" in diff or "-" in diff
