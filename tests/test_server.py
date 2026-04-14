"""Integration tests for the FastAPI webhook server.

Covers: route availability, demo event pre-loading, repro endpoints,
static file serving, health check, and CRC/signature helpers.
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

def test_clear_events_reinjects_demos(client):
    r = client.delete("/api/events")
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"
    # After clear, demo events should be re-injected
    r2 = client.get("/api/events")
    assert r2.json()["total"] >= 2


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
    r = client.post("/api/webhook/crc", json={
        "crc_token": "testtoken",
        "consumer_secret": "mysecret",
    })
    assert r.status_code == 200
    body = r.json()
    assert "response_token" in body
    assert body["response_token"].startswith("sha256=")


# ── Signature explain ─────────────────────────────────────────────────────────

def test_signature_explain(client):
    r = client.post("/api/signature/explain", json={
        "payload": '{"event_type":"chat.received"}',
        "consumer_secret": "mysecret",
    })
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

def test_webhook_post_no_secret_logs_event(client):
    payload = json.dumps({"event_type": "chat.received"}).encode()
    r = client.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "chat.received"


def test_webhook_post_invalid_json_still_logs(client):
    r = client.post(
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
