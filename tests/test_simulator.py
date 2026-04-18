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
            # profile.update.bio uses docs schema (official XAA envelope) which
            # does not include created_at — this matches the official docs.x.com example
            if et == EventType.PROFILE_UPDATE_BIO:
                assert "data" in event  # docs schema has XAA envelope
                continue
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

    def test_observed_schema_encoded_event_decodable_by_stub_crypto(self, sim):
        """official schema encoded_event must use STUB_ENC_ prefix — StubCrypto can decode it."""
        from playground.crypto.stub import StubCrypto

        event = sim.generate(EventType.CHAT_RECEIVED, schema="official")

        # Verify envelope structure
        assert "data" in event
        payload = event["data"]["payload"]
        encoded_event = payload["encoded_event"]

        # Must start with STUB_ENC_ so StubCrypto recognises it
        assert encoded_event.startswith("STUB_ENC_"), (
            f"encoded_event should start with STUB_ENC_, got: {encoded_event[:30]}"
        )

        # StubCrypto should decode it to non-None plaintext
        result = StubCrypto().decrypt(encoded_event)
        assert result["plaintext"] is not None, (
            "StubCrypto should decode official encoded_event"
        )
        assert len(result["plaintext"]) > 0

    def test_observed_schema_rejected_for_chat_sent(self, sim):
        """schema='official' on chat.sent should raise ValueError (not yet modelled)."""
        with pytest.raises(ValueError, match="only modelled for"):
            sim.generate(EventType.CHAT_SENT, schema="official")

    def test_observed_schema_rejected_for_conversation_join(self, sim):
        """schema='official' on conversation_join should raise ValueError."""
        with pytest.raises(ValueError, match="only modelled for"):
            sim.generate(EventType.CONVERSATION_JOIN, schema="official")

    def test_strict_observed_strips_metadata(self, sim):
        """strict=True should remove _schema and _note from observed fixture."""
        event = sim.generate(EventType.CHAT_RECEIVED, schema="official", strict=True)
        assert "_schema" not in event, "_schema should be stripped in strict mode"
        assert "_note" not in event, "_note should be stripped in strict mode"
        # Core envelope should still be intact
        assert "data" in event
        assert event["data"]["event_type"] == "chat.received"

    def test_non_strict_observed_keeps_metadata(self, sim):
        """Without strict, _schema and _note should be present."""
        event = sim.generate(EventType.CHAT_RECEIVED, schema="official", strict=False)
        assert "_schema" in event
        assert "_note" in event


class TestContractSimulator:
    """Contract tests — verify fixture shapes match docs.x.com examples or observed sources."""

    def test_profile_update_bio_docs_schema_matches_docs_example(self):
        """profile.update.bio docs schema must exactly match docs.x.com quickstart example."""
        sim = EventSimulator()
        event = sim.generate(
            EventType.PROFILE_UPDATE_BIO,
            schema="docs",
            filter_user_id="2244994945",
            bio_before="Mars & Cars",
            bio_after="Mars, Cars & AI",
            tag="Xdevelopers' bio updates",
        )
        # Must have XAA envelope
        assert "data" in event
        data = event["data"]
        # filter.user_id required
        assert "filter" in data
        assert data["filter"]["user_id"] == "2244994945"
        # event_type required
        assert data["event_type"] == "profile.update.bio"
        # tag optional but present when given
        assert data.get("tag") == "Xdevelopers' bio updates"
        # payload must have before/after
        assert "payload" in data
        assert data["payload"]["before"] == "Mars & Cars"
        assert data["payload"]["after"] == "Mars, Cars & AI"

    def test_profile_update_bio_without_tag(self):
        """tag field should be absent when not provided."""
        sim = EventSimulator()
        event = sim.generate(EventType.PROFILE_UPDATE_BIO, schema="docs")
        assert "tag" not in event["data"]

    def test_observed_schema_has_source_annotation(self):
        """observed schema must include _schema='observed-xaa' annotation."""
        sim = EventSimulator()
        event = sim.generate(EventType.CHAT_RECEIVED, schema="observed")
        assert event.get("_schema") == "observed-xaa"

    def test_official_alias_still_works_with_deprecation_warning(self):
        """schema='official' must emit DeprecationWarning and behave like 'observed'."""
        import warnings

        sim = EventSimulator()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            event = sim.generate(EventType.CHAT_RECEIVED, schema="official")
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
        # Should still produce observed-xaa envelope
        assert "data" in event
        assert event["data"]["event_type"] == "chat.received"

    def test_chat_received_observed_envelope_structure(self):
        """chat.received observed schema must have data.payload with encoded_event."""
        sim = EventSimulator()
        event = sim.generate(EventType.CHAT_RECEIVED, schema="observed", strict=True)
        assert "data" in event
        payload = event["data"]["payload"]
        assert "encoded_event" in payload
        assert payload["encoded_event"].startswith("STUB_ENC_")
        assert "encrypted_conversation_key" in payload
        assert "conversation_key_version" in payload
