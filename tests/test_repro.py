"""Tests for repro pack registry and individual packs."""

from __future__ import annotations

import pytest

from playground.repro.registry import ReproRegistry, list_packs, run_pack


class TestReproRegistry:
    def test_all_expected_packs_registered(self):
        packs = list_packs()
        ids = {p["id"] for p in packs}
        assert "xaa-webhook-smoke-test" in ids
        assert "chat-webhook-not-received" in ids
        assert "encrypted-lookup-empty" in ids
        assert "legacy-dm-stops-after-e2ee" in ids
        assert "encrypted-chat-decrypt-pending" in ids

    def test_list_packs_returns_metadata(self):
        packs = list_packs()
        for p in packs:
            assert "id" in p
            assert "title" in p
            assert "description" in p

    def test_get_unknown_pack_raises(self):
        with pytest.raises(ValueError, match="Unknown repro pack"):
            ReproRegistry.get("nonexistent-pack-id")


class TestEncryptedChatDecryptPendingPack:
    def test_run_returns_dict(self):
        result = run_pack("encrypted-chat-decrypt-pending")
        assert isinstance(result, dict)
        assert result["reproduced"] is True

    def test_run_verbose_includes_checks(self):
        result = run_pack("encrypted-chat-decrypt-pending", verbose=True)
        assert "checks" in result
        checks = result["checks"]
        assert isinstance(checks, list)
        assert len(checks) > 0

    def test_run_nonverbose_checks_are_strings(self):
        result = run_pack("encrypted-chat-decrypt-pending", verbose=False)
        checks = result["checks"]
        assert all(isinstance(c, str) for c in checks)

    def test_checks_cover_key_fields(self):
        result = run_pack("encrypted-chat-decrypt-pending", verbose=True)
        check_texts = " ".join(c["check"] for c in result["checks"])
        assert "event_type" in check_texts
        assert "encoded_event" in check_texts
        assert "conversation_id" in check_texts
        assert "schema_source" in check_texts or "observed" in check_texts

    def test_summary_mentions_encryption(self):
        result = run_pack("encrypted-chat-decrypt-pending")
        summary = result["summary"].lower()
        assert "encrypt" in summary

    def test_what_you_can_do_today_present(self):
        result = run_pack("encrypted-chat-decrypt-pending")
        assert "what_you_can_do_today" in result
        assert "conversation_id" in result["what_you_can_do_today"]

    def test_chat_api_routes_documented(self):
        result = run_pack("encrypted-chat-decrypt-pending")
        assert "chat_api_routes_documented" in result
        routes_text = result["chat_api_routes_documented"]
        assert "/2/chat/conversations" in routes_text

    def test_title_and_description_set(self):
        from playground.repro.packs.encrypted_chat_decrypt_pending import (
            EncryptedChatDecryptPendingPack,
        )

        pack = EncryptedChatDecryptPendingPack()
        assert pack.title
        assert pack.description
        assert (
            "chat.received" in pack.title.lower() or "plaintext" in pack.title.lower()
        )
