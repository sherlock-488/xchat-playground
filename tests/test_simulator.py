"""Tests for the event simulator module."""

import pytest

from playground.simulator.events import EventSimulator, EventType


@pytest.fixture
def sim():
    return EventSimulator()


class TestEventSimulator:
    def test_chat_received_structure(self, sim):
        event = sim.generate(EventType.CHAT_RECEIVED)
        assert event["event_type"] == "chat.received"
        assert "direct_message_events" in event
        assert len(event["direct_message_events"]) == 1
        msg = event["direct_message_events"][0]
        assert msg["event_type"] == "MessageCreate"
        assert "dm_conversation_id" in msg
        assert "sender_id" in msg

    def test_chat_received_encrypted_payload(self, sim):
        event = sim.generate(EventType.CHAT_RECEIVED, encrypted=True)
        msg = event["direct_message_events"][0]["message"]
        assert "encrypted_content" in msg
        assert msg["encrypted_content"].startswith("STUB_ENC_")
        assert msg["encryption_type"] == "XChaCha20Poly1305"

    def test_chat_received_plaintext(self, sim):
        event = sim.generate(EventType.CHAT_RECEIVED, encrypted=False)
        msg = event["direct_message_events"][0]["message"]
        assert "text" in msg
        assert "encrypted_content" not in msg

    def test_chat_received_custom_ids(self, sim):
        event = sim.generate(
            EventType.CHAT_RECEIVED,
            sender_id="AAA",
            recipient_id="BBB",
        )
        assert event["for_user_id"] == "BBB"
        msg = event["direct_message_events"][0]
        assert msg["sender_id"] == "AAA"
        assert "AAA" in msg["participant_ids"]
        assert "BBB" in msg["participant_ids"]

    def test_chat_received_custom_conversation_id(self, sim):
        event = sim.generate(
            EventType.CHAT_RECEIVED,
            conversation_id="MY_CONV_123",
        )
        msg = event["direct_message_events"][0]
        assert msg["dm_conversation_id"] == "MY_CONV_123"

    def test_chat_sent_structure(self, sim):
        event = sim.generate(EventType.CHAT_SENT)
        assert event["event_type"] == "chat.sent"
        msg = event["direct_message_events"][0]
        assert msg["event_type"] == "MessageCreate"
        assert "message" in msg

    def test_conversation_join_structure(self, sim):
        event = sim.generate(EventType.CONVERSATION_JOIN, user_id="XYZ")
        assert event["event_type"] == "chat.conversation_join"
        assert event["for_user_id"] == "XYZ"
        msg = event["direct_message_events"][0]
        assert msg["event_type"] == "ParticipantsJoin"
        assert "XYZ" in msg["participant_ids"]

    def test_generated_events_have_timestamps(self, sim):
        for et in EventType:
            event = sim.generate(et)
            assert "created_at" in event
            assert event["created_at"].endswith("Z")

    def test_load_fixture_chat_received(self, sim):
        fixture = sim.load_fixture("chat_received")
        assert fixture["event_type"] == "chat.received"

    def test_load_fixture_missing(self, sim):
        with pytest.raises(FileNotFoundError):
            sim.load_fixture("nonexistent_fixture")

    def test_message_ids_are_unique(self, sim):
        events = [sim.generate(EventType.CHAT_RECEIVED) for _ in range(10)]
        ids = [e["direct_message_events"][0]["id"] for e in events]
        assert len(set(ids)) == 10, "Message IDs should be unique"
