/**
 * xchat-playground Web UI
 * Communicates with the local FastAPI server at http://127.0.0.1:7474
 */

// ── State ──────────────────────────────────────────────────────────────────

let autoRefresh = true;
let autoRefreshTimer = null;
let eventCount = 0;
const expandedKeys = new Set(); // persists expand state across re-renders

// ── Utils ──────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

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
  // Skip re-render if user is actively selecting text (avoids disrupting copy)
  if (window.getSelection && window.getSelection().toString().length > 0) return;
  try {
    const r = await fetch("/api/events?limit=50");
    const data = await r.json();
    renderEvents(data.events || []);
    updateStats(data.events || []);
  } catch (e) {
    console.error("Failed to load events:", e);
  }
}

function eventKey(e) {
  return `${e.event_type}:${e.received_at}`;
}

function renderEvents(events) {
  const list = document.getElementById("event-list");
  if (!events.length) {
    list.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:20px 0">
      No events yet. Use <strong>Simulate →</strong> to inject test events.
    </div>`;
    return;
  }

  list.innerHTML = [...events].reverse().map((e) => {
    const badges = [];
    if (e.simulated) badges.push(`<span class="badge badge-blue">simulated</span>`);
    if (e.signature_valid === false) badges.push(`<span class="badge badge-red">sig invalid</span>`);
    if (e.signature_valid === true) badges.push(`<span class="badge badge-green">sig valid</span>`);
    // schema badge
    const schemaBadgeColor = {
      "docs":     "badge-green",
      "observed": "badge-yellow",
      "demo":     "badge-blue",
    }[e.source_schema] || "badge-muted";
    if (e.source_schema) badges.push(`<span class="badge ${schemaBadgeColor}">${escHtml(e.source_schema)}</span>`);
    // observed XChat payload status note
    if (e.event_type === "chat.received" && e.source_schema === "observed") {
      badges.push(`<span class="badge badge-yellow" title="XChat payloads are end-to-end encrypted. encoded_event, encrypted_conversation_key, conversation_key_change_event, and conversation_token are encrypted/observed fields. Real plaintext decrypt requires chat-xdk (pending stable release).">encrypted payload only</span>`);
    }

    const typeColor = {
      "chat.received": "var(--green)",
      "chat.sent": "var(--blue)",
      "chat.conversation_join": "var(--purple)",
      "profile.update.bio": "var(--orange)",
      "signature_error": "var(--red)",
    }[e.event_type] || "var(--text)";

    const time = e.received_at ? new Date(e.received_at).toLocaleTimeString() : "";
    const key = eventKey(e);
    const isOpen = expandedKeys.has(key);

    // filter.user_id + tag metadata row — escape all dynamic values
    const metaParts = [];
    if (e.filter && e.filter.user_id) metaParts.push(`<span style="color:var(--muted);font-size:11px">user_id: <span style="color:var(--text)">${escHtml(String(e.filter.user_id))}</span></span>`);
    if (e.tag) metaParts.push(`<span style="color:var(--muted);font-size:11px">tag: <span style="color:var(--text)">${escHtml(String(e.tag))}</span></span>`);
    const metaRow = metaParts.length ? `<div style="padding:4px 12px 0;display:flex;gap:12px">${metaParts.join("")}</div>` : "";

    // profile.update.bio: show before/after diff instead of raw JSON
    let bodyContent;
    if (e.event_type === "profile.update.bio" && e.payload && (e.payload.before !== undefined || e.payload.after !== undefined)) {
      bodyContent = `
        <div style="padding:8px 12px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div>
            <div style="font-size:10px;color:var(--muted);margin-bottom:4px">BEFORE</div>
            <div style="background:rgba(248,81,73,0.1);border:1px solid rgba(248,81,73,0.3);border-radius:4px;padding:6px 8px;color:var(--red);font-size:13px">${escHtml(String(e.payload.before ?? ""))}</div>
          </div>
          <div>
            <div style="font-size:10px;color:var(--muted);margin-bottom:4px">AFTER</div>
            <div style="background:rgba(63,185,80,0.1);border:1px solid rgba(63,185,80,0.3);border-radius:4px;padding:6px 8px;color:var(--green);font-size:13px">${escHtml(String(e.payload.after ?? ""))}</div>
          </div>
        </div>
        <pre style="margin-top:8px">${escHtml(JSON.stringify(e.payload, null, 2))}</pre>`;
    } else {
      bodyContent = `<pre>${escHtml(JSON.stringify(e.payload, null, 2))}</pre>`;
    }

    return `
      <div class="event-item" data-key="${key}">
        <div class="event-header" onclick="toggleEvent(this)">
          <span class="event-type" style="color:${typeColor}">${escHtml(e.event_type)}</span>
          ${badges.join(" ")}
          <span class="event-time">${escHtml(time)}</span>
          <span style="color:var(--muted);font-size:11px;margin-left:8px">${isOpen ? "▲" : "▼"}</span>
        </div>
        ${metaRow}
        <div class="event-body${isOpen ? " open" : ""}">
          ${bodyContent}
        </div>
      </div>
    `;
  }).join("");
}

function toggleEvent(header) {
  const item = header.closest(".event-item");
  const body = item.querySelector(".event-body");
  body.classList.toggle("open");
  const arrow = header.querySelector("span:last-child");
  const isOpen = body.classList.contains("open");
  arrow.textContent = isOpen ? "▲" : "▼";
  const key = item.dataset.key;
  if (isOpen) expandedKeys.add(key); else expandedKeys.delete(key);
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

function onSimTypeChange() {
  const type = document.getElementById("sim-type").value;
  const isProfile = type === "profile.update.bio";
  document.getElementById("sim-chat-fields").style.display = isProfile ? "none" : "";
  document.getElementById("sim-profile-fields").style.display = isProfile ? "" : "none";
}

async function injectEvents() {
  const type = document.getElementById("sim-type").value;
  const count = parseInt(document.getElementById("sim-count").value) || 1;

  let body;
  if (type === "profile.update.bio") {
    const userId = document.getElementById("sim-profile-user-id").value;
    const before = document.getElementById("sim-profile-before").value;
    const after = document.getElementById("sim-profile-after").value;
    const tag = document.getElementById("sim-profile-tag").value;
    body = JSON.stringify({
      schema: "docs",
      filter_user_id: userId,
      bio_before: before,
      bio_after: after,
      ...(tag ? { tag } : {}),
    });
  } else {
    const sender = document.getElementById("sim-sender").value;
    const recipient = document.getElementById("sim-recipient").value;
    body = JSON.stringify({ sender_id: sender, recipient_id: recipient });
  }

  const results = [];
  for (let i = 0; i < count; i++) {
    const r = await fetch(`/api/simulate/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    const data = await r.json();
    results.push(data);
  }

  const el = document.getElementById("sim-result");
  el.style.display = "block";
  el.textContent = `Injected ${count} × ${type}\n\n${JSON.stringify(results[0], null, 2)}`;

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
    el.textContent = "Please enter an encoded_event value (demo: STUB_ENC_… | observed: data.payload.encoded_event).";
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
    el.textContent = `Mode:      stub\nPlaintext: [REAL_ENCRYPTED: ${payload.slice(0, 40)}...]\nNotes:     This looks like a real encrypted payload.\n           Real plaintext decrypt is not available in the playground yet.\n           Use chat-xdk when it becomes publicly/stably available.`;
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
    {
      id: "encrypted-chat-decrypt-pending",
      title: "Received chat.received but cannot read plaintext",
      description: "XChat payloads are E2EE. encoded_event is encrypted. Real decrypt requires chat-xdk (pending stable release).",
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
