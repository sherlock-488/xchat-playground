/**
 * xchat-playground Web UI
 * Communicates with the local FastAPI server at http://127.0.0.1:7474
 */

// ── State ──────────────────────────────────────────────────────────────────

let autoRefresh = true;
let autoRefreshTimer = null;
let eventCount = 0;

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadEvents();
  loadReproPacks();
  startAutoRefresh();
});

// ── Navigation ─────────────────────────────────────────────────────────────

function showPanel(name) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById(`panel-${name}`).classList.add("active");
  document.getElementById(`nav-${name}`).classList.add("active");
}

// ── Health check ───────────────────────────────────────────────────────────

async function checkHealth() {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  try {
    const r = await fetch("/health");
    if (r.ok) {
      dot.style.background = "var(--green)";
      label.textContent = "server online";
    } else {
      dot.style.background = "var(--yellow)";
      label.textContent = `server error ${r.status}`;
    }
  } catch {
    dot.style.background = "var(--red)";
    label.textContent = "server offline";
  }
}

// ── Events ─────────────────────────────────────────────────────────────────

async function loadEvents() {
  try {
    const r = await fetch("/api/events?limit=50");
    const data = await r.json();
    renderEvents(data.events || []);
    updateStats(data.events || []);
  } catch (e) {
    console.error("Failed to load events:", e);
  }
}

function renderEvents(events) {
  const list = document.getElementById("event-list");
  if (!events.length) {
    list.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:20px 0">
      No events yet. Use <strong>Simulate →</strong> to inject test events.
    </div>`;
    return;
  }

  list.innerHTML = [...events].reverse().map((e, i) => {
    const badges = [];
    if (e.simulated) badges.push(`<span class="badge badge-blue">simulated</span>`);
    if (e.signature_valid === false) badges.push(`<span class="badge badge-red">sig invalid</span>`);
    if (e.signature_valid === true) badges.push(`<span class="badge badge-green">sig valid</span>`);

    const typeColor = {
      "chat.received": "var(--green)",
      "chat.sent": "var(--blue)",
      "chat.conversation_join": "var(--purple)",
      "signature_error": "var(--red)",
    }[e.event_type] || "var(--text)";

    const time = e.received_at ? new Date(e.received_at).toLocaleTimeString() : "";

    return `
      <div class="event-item">
        <div class="event-header" onclick="toggleEvent(this)">
          <span class="event-type" style="color:${typeColor}">${e.event_type}</span>
          ${badges.join(" ")}
          <span class="event-time">${time}</span>
          <span style="color:var(--muted);font-size:11px;margin-left:8px">▼</span>
        </div>
        <div class="event-body">
          <pre>${JSON.stringify(e.payload, null, 2)}</pre>
        </div>
      </div>
    `;
  }).join("");
}

function toggleEvent(header) {
  const body = header.nextElementSibling;
  body.classList.toggle("open");
  const arrow = header.querySelector("span:last-child");
  arrow.textContent = body.classList.contains("open") ? "▲" : "▼";
}

function updateStats(events) {
  document.getElementById("stat-total").textContent = events.length;
  document.getElementById("stat-received").textContent =
    events.filter(e => e.event_type === "chat.received").length;
  document.getElementById("stat-errors").textContent =
    events.filter(e => e.signature_valid === false || e.event_type === "signature_error").length;
  document.getElementById("stat-simulated").textContent =
    events.filter(e => e.simulated).length;
}

async function clearEvents() {
  await fetch("/api/events", { method: "DELETE" });
  loadEvents();
}

function toggleAutoRefresh() {
  autoRefresh = !autoRefresh;
  const btn = document.getElementById("auto-btn");
  if (autoRefresh) {
    btn.textContent = "⏸ Auto-refresh ON";
    startAutoRefresh();
  } else {
    btn.textContent = "▶ Auto-refresh OFF";
    clearInterval(autoRefreshTimer);
  }
}

function startAutoRefresh() {
  clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    if (autoRefresh) {
      loadEvents();
      checkHealth();
    }
  }, 2000);
}

// ── Simulate ───────────────────────────────────────────────────────────────

async function injectEvents() {
  const type = document.getElementById("sim-type").value;
  const sender = document.getElementById("sim-sender").value;
  const recipient = document.getElementById("sim-recipient").value;
  const count = parseInt(document.getElementById("sim-count").value) || 1;

  const results = [];
  for (let i = 0; i < count; i++) {
    const r = await fetch(`/api/simulate/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_id: sender, recipient_id: recipient }),
    });
    const data = await r.json();
    results.push(data);
  }

  const el = document.getElementById("sim-result");
  el.style.display = "block";
  el.textContent = `Injected ${count} × ${type}\n\n${JSON.stringify(results[0], null, 2)}`;

  // Switch to events panel
  showPanel("events");
  loadEvents();
}

// ── Webhook / CRC ──────────────────────────────────────────────────────────

async function computeCRC() {
  const token = document.getElementById("crc-token").value.trim();
  const secret = document.getElementById("crc-secret").value.trim();

  if (!token || !secret) {
    alert("Please enter both CRC token and consumer secret.");
    return;
  }

  const el = document.getElementById("crc-result");
  el.style.display = "block";

  // POST to /api/webhook/crc — accepts secret in request body (not env var)
  const r = await fetch("/api/webhook/crc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ crc_token: token, consumer_secret: secret }),
  });

  if (r.ok) {
    const data = await r.json();
    el.textContent =
      `HTTP ${r.status}\n\n` +
      `${JSON.stringify(data, null, 2)}\n\n` +
      `Return this JSON body to X when it sends:\n` +
      `GET /your-webhook?crc_token=${token}`;
  } else {
    const text = await r.text();
    el.textContent = `HTTP ${r.status}\n\n${text}`;
  }
}

async function explainSignature() {
  const payload = document.getElementById("sig-payload").value.trim();
  const secret = document.getElementById("sig-secret").value.trim();

  if (!payload || !secret) {
    alert("Please enter both payload and consumer secret.");
    return;
  }

  const r = await fetch("/api/signature/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload, consumer_secret: secret }),
  });

  const el = document.getElementById("sig-result");
  el.style.display = "block";

  if (r.ok) {
    const data = await r.json();
    el.textContent = Object.entries(data)
      .map(([k, v]) => `${k.padEnd(22)} ${v}`)
      .join("\n");
  } else {
    el.textContent = `Error: ${await r.text()}`;
  }
}

// ── Crypto ─────────────────────────────────────────────────────────────────

function loadCryptoExample() {
  document.getElementById("crypto-input").value =
    "STUB_ENC_SGVsbG8gZnJvbSB4Y2hhdC1wbGF5Z3JvdW5kIQ==";
}

async function decryptStub() {
  const payload = document.getElementById("crypto-input").value.trim();
  const el = document.getElementById("crypto-result");
  el.style.display = "block";

  if (!payload) {
    el.textContent = "Please enter an encrypted_content value.";
    return;
  }

  // Client-side stub decode (mirrors playground/crypto/stub.py)
  const STUB_PREFIX = "STUB_ENC_";
  if (payload.startsWith(STUB_PREFIX)) {
    try {
      const b64 = payload.slice(STUB_PREFIX.length);
      const plaintext = atob(b64);
      el.textContent = `Mode:      stub\nPlaintext: ${plaintext}\nNotes:     Decoded from STUB_ENC_ prefix. No real keys used.`;
    } catch (e) {
      el.textContent = `Failed to decode stub payload: ${e}`;
    }
  } else {
    el.textContent = `Mode:      stub\nPlaintext: [REAL_ENCRYPTED: ${payload.slice(0, 40)}...]\nNotes:     This looks like a real encrypted payload.\n           Use 'playground crypto real' with state.json for real decryption.`;
  }
}

// ── Repro Packs ────────────────────────────────────────────────────────────

async function loadReproPacks() {
  try {
    const r = await fetch("/api/repro/list");
    if (!r.ok) {
      renderReproPacks(getBuiltinPacks());
      return;
    }
    const data = await r.json();
    renderReproPacks(data.packs || getBuiltinPacks());
  } catch {
    renderReproPacks(getBuiltinPacks());
  }
}

function getBuiltinPacks() {
  return [
    {
      id: "chat-webhook-not-received",
      title: "chat.received webhook not delivered",
      description: "CRC not handled, localhost URL, secret mismatch, or subscription missing.",
    },
    {
      id: "encrypted-lookup-empty",
      title: "GET /2/dm_events/{id} returns {} for encrypted chat",
      description: "After E2EE, message content is only in the Activity Stream event — not the REST API.",
    },
    {
      id: "legacy-dm-stops-after-e2ee",
      title: "Legacy dm_events stops updating after E2EE upgrade",
      description: "Migrate from legacy DM polling to Activity API with chat.received subscription.",
    },
  ];
}

function renderReproPacks(packs) {
  const list = document.getElementById("repro-list");
  list.innerHTML = packs.map(p => `
    <div class="repro-item">
      <div class="repro-title">${p.title}</div>
      <div class="repro-desc">${p.description}</div>
      <button class="btn btn-sm" onclick="runReproPack('${p.id}')">▶ Run</button>
      ${p.forum_url ? `<a href="${p.forum_url}" target="_blank"
        style="font-size:12px;color:var(--blue);margin-left:8px">Forum →</a>` : ""}
      <div id="repro-result-${p.id}" class="code-output" style="margin-top:10px;display:none"></div>
    </div>
  `).join("");
}

async function runReproPack(id) {
  const el = document.getElementById(`repro-result-${id}`);
  el.style.display = "block";
  el.textContent = "Running...";

  try {
    const r = await fetch(`/api/repro/run/${id}?verbose=true`);
    if (r.ok) {
      const data = await r.json();
      el.textContent = JSON.stringify(data, null, 2);
    } else {
      // Fallback: show static explanation
      el.textContent = getStaticReproExplanation(id);
    }
  } catch {
    el.textContent = getStaticReproExplanation(id);
  }
}

function getStaticReproExplanation(id) {
  const explanations = {
    "chat-webhook-not-received": `Root causes (in order of frequency):
1. CRC challenge not handled → endpoint never verified
   Fix: return {"response_token": "sha256=<hmac>"} on GET /webhook?crc_token=xxx

2. Localhost URL → X can't reach it
   Fix: use cloudflared or ngrok tunnel

3. Consumer secret mismatch → all events rejected with 403
   Fix: verify with 'playground webhook verify'

4. Subscription not created after webhook registration
   Fix: POST /2/activity/subscriptions`,

    "encrypted-lookup-empty": `Symptom: GET /2/dm_events/{id} returns {}

Root cause: After E2EE is enabled, message content is encrypted.
The REST endpoint cannot return plaintext for encrypted messages.

Old flow (broken):
  receive chat.received → lookup /2/dm_events/{id} → read .text

New flow (correct):
  receive chat.received → read data.payload.encoded_event → decrypt`,

    "legacy-dm-stops-after-e2ee": `Symptom: GET /2/users/:id/direct_messages stops returning new messages

Root cause: Once a conversation is upgraded to XChat E2EE,
messages go through the new encrypted stack, not legacy DM infrastructure.

Migration path:
  1. Subscribe to chat.received via Activity API
  2. Handle data.payload.encoded_event in Activity Stream event
  3. Decrypt using private keys from state.json
  4. Reply via POST /2/dm_conversations/:id/messages`,
  };
  return explanations[id] || "No explanation available.";
}
