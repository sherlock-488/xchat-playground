"""Local webhook server for XChat bot development.

Provides:
  GET  /webhook?crc_token=xxx       → CRC challenge response
  POST /webhook                     → Receive & log XChat events
  GET  /ui                          → Browser-based debug UI
  GET  /api/events                  → Recent events (JSON)
  DELETE /api/events                → Clear event log
  POST /api/simulate/{event_type}   → Inject simulated event
  POST /api/signature/explain       → Step-by-step signature breakdown
  POST /api/webhook/crc             → Compute CRC with custom secret (for UI)
  GET  /api/repro/list              → List repro packs
  GET  /api/repro/run/{pack_id}     → Run a repro pack
  GET  /health                      → Health check
  GET  /docs                        → OpenAPI docs (auto-generated)
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from playground.webhook.crc import compute_crc_response
from playground.webhook.signature import explain_signature, verify_signature

# Load .env at import time so env vars are available immediately
load_dotenv()

# Web directory (for static file serving)
_WEB_DIR = Path(__file__).parent.parent.parent / "web"


# ── Models ────────────────────────────────────────────────────────────────────

class SignatureExplainRequest(BaseModel):
    payload: str
    consumer_secret: str


class CRCRequest(BaseModel):
    crc_token: str
    consumer_secret: str


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="xchat-playground",
        description="Local simulator & replay lab for XChat bots",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Re-read env on each factory call so tests and reloads pick up changes
    consumer_secret = os.getenv("CONSUMER_SECRET", "")

    # Per-app event log (avoids global state leaking across test instances)
    event_log: deque[dict] = deque(maxlen=200)

    def _log(entry: dict) -> None:
        event_log.append(entry)

    def _inject_demo_events() -> None:
        """Inject a couple of demo events so the UI is never blank on first open."""
        from playground.simulator.events import EventSimulator, EventType
        sim = EventSimulator()
        now = datetime.now(timezone.utc).isoformat()
        for et, label in [
            (EventType.CHAT_RECEIVED, "chat.received"),
            (EventType.CHAT_SENT, "chat.sent"),
        ]:
            _log({
                "received_at": now,
                "event_type": label,
                "signature_valid": None,
                "simulated": True,
                "demo": True,
                "payload": sim.generate(et),
            })

    _inject_demo_events()

    # Mount /web so index.html can load app.js
    if _WEB_DIR.exists():
        app.mount("/web", StaticFiles(directory=_WEB_DIR), name="web")

    # ── CRC challenge (X calls this to verify your endpoint) ──────────────────

    @app.get("/webhook", summary="CRC Challenge", tags=["webhook"])
    async def crc_challenge(crc_token: str = Query(..., description="Token from X")):
        """Respond to X's CRC challenge for webhook registration."""
        if not consumer_secret:
            raise HTTPException(
                status_code=500,
                detail="CONSUMER_SECRET not set. Set it in .env or environment.",
            )
        return compute_crc_response(crc_token, consumer_secret)

    # ── Webhook receiver ──────────────────────────────────────────────────────

    @app.post("/webhook", summary="Receive XChat Event", tags=["webhook"])
    async def receive_event(
        request: Request,
        x_signature_256: Optional[str] = Header(None, alias="X-Signature-256"),
    ):
        """Receive an XChat Activity API event, validate signature, log it."""
        body = await request.body()

        sig_valid = None
        if consumer_secret and x_signature_256:
            sig_valid = verify_signature(body, x_signature_256, consumer_secret)
            if not sig_valid:
                _log({
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "event_type": "signature_error",
                    "signature_valid": False,
                    "payload": {
                        "received_signature": x_signature_256,
                        "body_preview": body[:200].decode("utf-8", errors="replace"),
                    },
                })
                raise HTTPException(status_code=403, detail="Invalid signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}

        event_type = payload.get("event_type", "unknown")
        _log({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "signature_valid": sig_valid,
            "payload": payload,
        })
        return {"status": "ok", "event_type": event_type}

    # ── API: events ───────────────────────────────────────────────────────────

    @app.get("/api/events", summary="List Recent Events", tags=["api"])
    async def list_events(limit: int = Query(50, le=200)):
        events = list(event_log)[-limit:]
        return {"events": events, "total": len(event_log)}

    @app.delete("/api/events", summary="Clear Event Log", tags=["api"])
    async def clear_events():
        event_log.clear()
        _inject_demo_events()
        return {"status": "cleared"}

    # ── API: signature explain ────────────────────────────────────────────────

    @app.post("/api/signature/explain", summary="Explain Signature", tags=["api"])
    async def signature_explain(req: SignatureExplainRequest):
        """Step-by-step HMAC-SHA256 breakdown — debug why your sig doesn't match."""
        return explain_signature(req.payload.encode(), req.consumer_secret)

    # ── API: CRC compute (for UI — accepts secret in request body) ────────────

    @app.post("/api/webhook/crc", summary="Compute CRC Response", tags=["api"])
    async def compute_crc(req: CRCRequest):
        """Compute CRC challenge response with a custom secret.

        Used by the Web UI so users can test CRC without restarting the server.
        """
        return compute_crc_response(req.crc_token, req.consumer_secret)

    # ── API: simulate event ───────────────────────────────────────────────────

    @app.post("/api/simulate/{event_type}", summary="Inject Simulated Event", tags=["api"])
    async def simulate_event(
        event_type: str,
        body: dict[str, Any] = Body(default_factory=dict),
    ):
        """Generate and inject a simulated event into the event log."""
        from playground.simulator.events import EventSimulator, EventType

        type_map = {
            "chat.received": EventType.CHAT_RECEIVED,
            "chat.sent": EventType.CHAT_SENT,
            "chat.conversation_join": EventType.CONVERSATION_JOIN,
        }
        et = type_map.get(event_type)
        if not et:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown event type: {event_type}. Valid: {list(type_map.keys())}",
            )
        event = EventSimulator().generate(et, **body)
        _log({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "signature_valid": None,
            "simulated": True,
            "payload": event,
        })
        return {"status": "injected", "event": event}

    # ── API: repro packs ──────────────────────────────────────────────────────

    @app.get("/api/repro/list", summary="List Repro Packs", tags=["repro"])
    async def repro_list():
        """List all available repro packs."""
        from playground.repro.registry import list_packs
        return {"packs": list_packs()}

    @app.get("/api/repro/run/{pack_id}", summary="Run Repro Pack", tags=["repro"])
    async def repro_run(pack_id: str, verbose: bool = Query(False)):
        """Run a repro pack by ID and return results."""
        from playground.repro.registry import run_pack
        try:
            return run_pack(pack_id, verbose=verbose)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ── Health check ──────────────────────────────────────────────────────────

    @app.get("/health", summary="Health Check", tags=["meta"])
    async def health():
        return {
            "status": "ok",
            "version": "0.1.0",
            "consumer_secret_set": bool(consumer_secret),
            "event_count": len(event_log),
            "dotenv_loaded": Path(".env").exists(),
        }

    # ── Web UI ────────────────────────────────────────────────────────────────

    @app.get("/ui", response_class=HTMLResponse, summary="Debug UI", tags=["ui"])
    async def ui():
        """Browser-based debug UI."""
        ui_path = _WEB_DIR / "index.html"
        if ui_path.exists():
            return HTMLResponse(ui_path.read_text())
        return HTMLResponse(_INLINE_UI)

    return app


# ── Inline fallback UI (if web/index.html not present) ────────────────────────

_INLINE_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>xchat-playground</title>
<style>
  body { font-family: monospace; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
  h1 { color: #58a6ff; }
  .badge { background: #1f6feb; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
  #events { margin-top: 20px; }
  .event { background: #161b22; border: 1px solid #30363d; border-radius: 6px; margin: 8px 0; padding: 12px; }
  .event-type { color: #3fb950; font-weight: bold; }
  .event-time { color: #8b949e; font-size: 12px; }
  pre { overflow-x: auto; font-size: 12px; }
  button { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 16px;
           border-radius: 6px; cursor: pointer; margin: 4px; }
  button:hover { background: #30363d; }
  .controls { margin-bottom: 16px; }
</style>
</head>
<body>
<h1>🧪 xchat-playground <span class="badge">v0.1.0</span></h1>
<p>Local simulator & replay lab for XChat bots</p>

<div class="controls">
  <button onclick="loadEvents()">↺ Refresh</button>
  <button onclick="clearEvents()">🗑 Clear</button>
  <button onclick="injectEvent('chat.received')">+ Inject chat.received</button>
  <button onclick="injectEvent('chat.sent')">+ Inject chat.sent</button>
  <button onclick="injectEvent('chat.conversation_join')">+ Inject conversation_join</button>
</div>

<div id="status"></div>
<div id="events"><p style="color:#8b949e">No events yet. Inject one above or send a real webhook.</p></div>

<script>
async function loadEvents() {
  const r = await fetch('/api/events?limit=50');
  const data = await r.json();
  const el = document.getElementById('events');
  if (!data.events.length) {
    el.innerHTML = '<p style="color:#8b949e">No events yet.</p>';
    return;
  }
  el.innerHTML = data.events.slice().reverse().map(e => `
    <div class="event">
      <span class="event-type">${e.event_type}</span>
      <span class="event-time"> — ${e.received_at}</span>
      ${e.simulated ? '<span class="badge" style="background:#388bfd">simulated</span>' : ''}
      ${e.signature_valid === false ? '<span class="badge" style="background:#da3633">sig invalid</span>' : ''}
      ${e.signature_valid === true ? '<span class="badge" style="background:#2ea043">sig valid</span>' : ''}
      <pre>${JSON.stringify(e.payload, null, 2)}</pre>
    </div>
  `).join('');
}

async function clearEvents() {
  await fetch('/api/events', { method: 'DELETE' });
  loadEvents();
}

async function injectEvent(type) {
  const r = await fetch('/api/simulate/' + type, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  const data = await r.json();
  document.getElementById('status').textContent = 'Injected: ' + type;
  loadEvents();
}

loadEvents();
setInterval(loadEvents, 3000);
</script>
</body>
</html>
"""
