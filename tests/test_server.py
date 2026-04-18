"""Integration tests for the FastAPI webhook server.

Covers: route availability, demo event pre-loading, repro endpoints,
static file serving, health check, CRC/signature helpers,
official-envelope roundtrip, PII scrub coverage, and web asset serving.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from playground.webhook.server import create_app


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


# ── Health & meta ─────────────────────────────────────────────────────────────


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "event_count" in body


def test_docs_available(client):
    r = client.get("/docs")
    assert r.status_code == 200


# ── Demo events pre-loaded ────────────────────────────────────────────────────


def test_demo_events_preloaded(client):
    """App should have ≥2 demo events injected at startup."""
    r = client.get("/api/events")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    types = {e["event_type"] for e in body["events"]}
    assert "chat.received" in types
    assert "chat.sent" in types


def test_demo_events_are_flagged(client):
    r = client.get("/api/events")
    events = r.json()["events"]
    demo_events = [e for e in events if e.get("demo")]
    assert len(demo_events) >= 2


# ── Event log CRUD ────────────────────────────────────────────────────────────


def test_clear_events_empties_log(client):
    r = client.delete("/api/events")
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"
    # After clear, log should be empty (no auto re-inject)
    r2 = client.get("/api/events")
    assert r2.json()["total"] == 0


def test_events_limit_param(client):
    r = client.get("/api/events?limit=1")
    assert r.status_code == 200
    assert len(r.json()["events"]) <= 1


# ── Simulate ──────────────────────────────────────────────────────────────────


def test_simulate_chat_received(client):
    r = client.post("/api/simulate/chat.received", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "injected"
    assert body["event"]["event_type"] == "chat.received"


def test_simulate_chat_sent(client):
    r = client.post("/api/simulate/chat.sent", json={})
    assert r.status_code == 200
    assert r.json()["event"]["event_type"] == "chat.sent"


def test_simulate_conversation_join(client):
    r = client.post("/api/simulate/chat.conversation_join", json={})
    assert r.status_code == 200
    assert r.json()["event"]["event_type"] == "chat.conversation_join"


def test_simulate_unknown_type_returns_400(client):
    r = client.post("/api/simulate/nonexistent.type", json={})
    assert r.status_code == 400


def test_simulate_observed_schema_unsupported_event_returns_400(client):
    """official schema on chat.sent/conversation_join → 400, not 500."""
    for event_type in ("chat.sent", "chat.conversation_join"):
        r = client.post(f"/api/simulate/{event_type}", json={"schema": "official"})
        assert r.status_code == 400, (
            f"{event_type} with schema=official should return 400"
        )
        assert "only modelled for" in r.json()["detail"]


def test_simulate_increments_event_count(client):
    before = client.get("/api/events").json()["total"]
    client.post("/api/simulate/chat.sent", json={})
    after = client.get("/api/events").json()["total"]
    assert after == before + 1


# ── CRC ───────────────────────────────────────────────────────────────────────


def test_crc_endpoint_with_secret_returns_200(client, monkeypatch):
    """When CONSUMER_SECRET is set, GET /webhook should return 200 with response_token."""
    monkeypatch.setenv("CONSUMER_SECRET", "testsecret")
    # Re-create app so it picks up the env var
    from playground.webhook.server import create_app as _create

    c = TestClient(_create())
    r = c.get("/webhook?crc_token=testtoken")
    assert r.status_code == 200
    assert "response_token" in r.json()


def test_compute_crc_api(client):
    r = client.post(
        "/api/webhook/crc",
        json={
            "crc_token": "testtoken",
            "consumer_secret": "mysecret",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "response_token" in body
    assert body["response_token"].startswith("sha256=")


# ── Signature explain ─────────────────────────────────────────────────────────


def test_signature_explain(client):
    r = client.post(
        "/api/signature/explain",
        json={
            "payload": '{"event_type":"chat.received"}',
            "consumer_secret": "mysecret",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "header_value" in body
    assert body["header_value"].startswith("sha256=")


# ── Repro packs ───────────────────────────────────────────────────────────────


def test_repro_list_returns_packs(client):
    r = client.get("/api/repro/list")
    assert r.status_code == 200
    body = r.json()
    assert "packs" in body
    assert len(body["packs"]) >= 1


def test_repro_run_known_pack(client):
    # Get the first available pack ID
    packs = client.get("/api/repro/list").json()["packs"]
    assert packs, "No repro packs registered"
    pack_id = packs[0]["id"]
    r = client.get(f"/api/repro/run/{pack_id}")
    assert r.status_code == 200
    body = r.json()
    assert "reproduced" in body


def test_repro_run_unknown_pack_returns_404(client):
    r = client.get("/api/repro/run/nonexistent-pack-xyz")
    assert r.status_code == 404


# ── Webhook POST (no secret configured) ──────────────────────────────────────


def test_webhook_post_no_secret_logs_event(monkeypatch):
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    payload = json.dumps({"event_type": "chat.received"}).encode()
    r = c.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "chat.received"


def test_webhook_post_invalid_json_still_logs(monkeypatch):
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    r = c.post(
        "/webhook",
        content=b"not-json",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200


# ── UI ────────────────────────────────────────────────────────────────────────


def test_ui_returns_html(client):
    r = client.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "xchat-playground" in r.text


# ── Per-instance isolation ────────────────────────────────────────────────────


def test_two_app_instances_have_separate_event_logs():
    """Each create_app() call must have its own event log."""
    c1 = TestClient(create_app())
    c2 = TestClient(create_app())

    # Inject an event into c1 only
    c1.post("/api/simulate/chat.sent", json={})

    count1 = c1.get("/api/events").json()["total"]
    count2 = c2.get("/api/events").json()["total"]

    # c1 has one more event than c2 (both start with 2 demo events)
    assert count1 == count2 + 1


# ── Official XAA envelope roundtrip ──────────────────────────────────────────


def test_observed_envelope_webhook_export_roundtrip(monkeypatch):
    """Official XAA envelope: POST /webhook → /api/events/export → event_type preserved."""
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())

    # Send an official XAA envelope to /webhook (no secret → no sig required)
    observed_event = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "DM_111_222",
                "encoded_event": "STUB_ENC_SGVsbG8h",
                "encrypted_conversation_key": "STUB_KEY_abc123",
                "conversation_key_version": "1",
                "conversation_token": "STUB_TOKEN_xyz",
            },
        }
    }
    r = c.post(
        "/webhook",
        content=json.dumps(observed_event).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "chat.received"

    # Export and verify event_type is preserved in the JSONL
    export_r = c.get("/api/events/export?skip_demo=true&scrub_pii=false")
    assert export_r.status_code == 200
    lines = [line for line in export_r.text.splitlines() if line.strip()]
    assert lines, "Export should contain at least one event"

    # Find the official event in the export
    exported_events = [json.loads(line) for line in lines]
    received_events = [
        e
        for e in exported_events
        if e.get("data", {}).get("event_type") == "chat.received"
    ]
    assert received_events, "Exported JSONL should contain the chat.received event"
    # Verify the official envelope structure is preserved
    payload = received_events[0]["data"]["payload"]
    assert "encoded_event" in payload


# ── PII scrub covers official schema fields ───────────────────────────────────


def test_pii_scrub_covers_conversation_token_and_encoded_event(client):
    """Export with scrub_pii=true should redact conversation_token and encoded_event."""
    from playground.replay.recorder import EventRecorder

    recorder = EventRecorder(scrub_pii=True)
    event = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "DM_REAL_111_222",
                "conversation_token": "REAL_TOKEN_abc123",
                "encoded_event": "REAL_ENCODED_BASE64_DATA",
                "encrypted_conversation_key": "REAL_KEY_MATERIAL",
                "conversation_key_version": "1",
            },
        }
    }
    scrubbed = recorder.record(event)
    payload = scrubbed["data"]["payload"]

    # conversation_token → FAKE_CONV_xxx (it's in _PII_CONV_FIELDS)
    assert payload["conversation_token"] != "REAL_TOKEN_abc123"
    assert payload["conversation_token"].startswith("FAKE_CONV_")

    # encoded_event → REDACTED_ENCODED_EVENT (crypto blob)
    assert payload["encoded_event"] == "REDACTED_ENCODED_EVENT"

    # encrypted_conversation_key → REDACTED_ENCRYPTED_KEY (crypto blob)
    assert payload["encrypted_conversation_key"] == "REDACTED_ENCRYPTED_KEY"

    # conversation_id → FAKE_CONV_xxx (it's in _PII_CONV_FIELDS)
    assert payload["conversation_id"] != "DM_REAL_111_222"
    assert payload["conversation_id"].startswith("FAKE_CONV_")


# ── Web asset serving ─────────────────────────────────────────────────────────


def test_web_app_js_served(client):
    """GET /web/app.js should return 200 — verifies playground/web/ is packaged."""
    r = client.get("/web/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("content-type", "").lower() or len(r.text) > 0


# ── P0-A: missing signature header rejected when secret is set ────────────────


def test_webhook_missing_sig_header_rejected_when_secret_set(monkeypatch):
    """With CONSUMER_SECRET set, POST /webhook without any signature header → 400."""
    monkeypatch.setenv("CONSUMER_SECRET", "testsecret")
    c = TestClient(create_app())
    r = c.post(
        "/webhook",
        content=json.dumps({"event_type": "chat.received"}).encode(),
        headers={"Content-Type": "application/json"},
        # Deliberately omit x-twitter-webhooks-signature and X-Signature-256
    )
    assert r.status_code == 400
    assert "signature" in r.json()["detail"].lower()


def test_webhook_no_secret_accepts_unsigned(monkeypatch):
    """Without CONSUMER_SECRET, unsigned requests should still be accepted (dev mode)."""
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    r = c.post(
        "/webhook",
        content=json.dumps({"event_type": "chat.received"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200


# ── P0-B: simulate official → export no double-wrap ──────────────────────────


def test_simulate_observed_export_not_double_wrapped(client):
    """simulate chat.received with schema=official → export → no double-wrapped envelope."""
    # Inject an official-schema simulated event
    r = client.post("/api/simulate/chat.received", json={"schema": "official"})
    assert r.status_code == 200

    # Export (skip demo events, no PII scrub for simplicity)
    export_r = client.get("/api/events/export?skip_demo=true&scrub_pii=false")
    assert export_r.status_code == 200

    lines = [line for line in export_r.text.splitlines() if line.strip()]
    assert lines, "Export should contain at least one event"

    exported = [json.loads(line) for line in lines]

    # Find the official event — it should have data.event_type at the top level
    observed_events = [
        e for e in exported if e.get("data", {}).get("event_type") == "chat.received"
    ]
    assert observed_events, "Observed XAA event should appear in export"

    # Verify NO double-wrap: payload should NOT be nested inside another payload
    event = observed_events[0]
    # data.payload should contain XAA fields, not another {"event_type", "payload"} wrapper
    inner = event["data"]["payload"]
    assert "encoded_event" in inner, "encoded_event should be directly in data.payload"
    assert "data" not in inner, (
        "data.payload should not contain another 'data' key (double-wrap)"
    )
    assert "event_type" not in inner, (
        "data.payload should not have event_type (double-wrap)"
    )


# ── Contract tests: normalizer preserves filter/tag/source_schema ─────────────


def test_contract_xaa_envelope_preserves_filter_and_tag(monkeypatch):
    """Receiving an XAA envelope must preserve filter and tag in event log."""
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    payload = {
        "data": {
            "filter": {"user_id": "2244994945"},
            "event_type": "profile.update.bio",
            "tag": "smoke-test",
            "payload": {"before": "old bio", "after": "new bio"},
        }
    }
    r = c.post(
        "/webhook",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    events = c.get("/api/events").json()["events"]
    bio_events = [
        e
        for e in events
        if e["event_type"] == "profile.update.bio" and not e.get("demo")
    ]
    assert bio_events, "profile.update.bio event not found in log"
    ev = bio_events[-1]
    assert ev.get("filter") == {"user_id": "2244994945"}
    assert ev.get("tag") == "smoke-test"
    assert ev.get("source_schema") == "docs"


def test_contract_xaa_envelope_source_schema_observed_for_chat(monkeypatch):
    """chat.received in XAA envelope must be tagged source_schema=observed."""
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    payload = {
        "_schema": "observed-xaa",
        "data": {
            "event_type": "chat.received",
            "payload": {"encoded_event": "STUB_ENC_dGVzdA=="},
        },
    }
    r = c.post(
        "/webhook",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    events = c.get("/api/events").json()["events"]
    chat_events = [
        e for e in events if e["event_type"] == "chat.received" and not e.get("demo")
    ]
    assert chat_events
    assert chat_events[-1].get("source_schema") == "observed"


def test_contract_demo_flat_fixture_tagged_demo(monkeypatch):
    """Flat demo fixtures must be tagged source_schema=demo."""
    monkeypatch.delenv("CONSUMER_SECRET", raising=False)
    c = TestClient(create_app())
    payload = {
        "event_type": "chat.sent",
        "created_at": "2026-04-17T00:00:00Z",
        "for_user_id": "123",
    }
    r = c.post(
        "/webhook",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    events = c.get("/api/events").json()["events"]
    sent_events = [
        e for e in events if e["event_type"] == "chat.sent" and not e.get("demo")
    ]
    assert sent_events
    assert sent_events[-1].get("source_schema") == "demo"
