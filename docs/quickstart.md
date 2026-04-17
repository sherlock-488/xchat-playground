# Quickstart

Get xchat-playground running in under 5 minutes.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended)

## Track A: Local-only (no X account needed)

Zero API credits. Fully offline. Works immediately after install.

### Install

```bash
git clone https://github.com/sherlock-488/xchat-playground
cd xchat-playground
pip install uv
uv sync
```

### Start the server

```bash
uv run playground serve
```

Open http://localhost:7474/ui in your browser.

### Inject your first event

In the Web UI, click **Simulate**, select an event type, and click **Inject Events**.

Or via CLI:

```bash
# chat events (demo schema — flat, easy to read)
uv run playground simulate chat-received
uv run playground simulate chat-received --no-encrypted  # plaintext mode

# profile.update.bio (docs schema — matches official docs.x.com example)
uv run playground simulate profile-update-bio \
  --user-id 2244994945 \
  --before "Mars & Cars" \
  --after "Mars, Cars & AI"
```

### Validate your webhook pipeline locally

```bash
# Generate a batch of fixtures
uv run playground simulate batch --count 10 --output fixtures/test.jsonl

# Replay them against your bot
uv run playground replay run fixtures/test.jsonl \
  --target http://localhost:8080/webhook \
  --consumer-secret your-secret
```

### Check your environment

```bash
uv run playground doctor
```

---

## Track B: Real X webhook smoke test (requires X developer account)

Use `profile.update.bio` — a **public event** that requires no special OAuth
scopes for the monitored user. This is the fastest path to a real X Activity
webhook delivery.

### 1. Get a public HTTPS URL

X requires a publicly accessible HTTPS URL with no port number.

```bash
# Option A: cloudflared (recommended)
npx cloudflared tunnel --url http://localhost:7474

# Option B: ngrok
ngrok http 7474
```

Copy the HTTPS URL (e.g. `https://abc123.trycloudflare.com`).

### 2. Configure your credentials

```bash
cp .env.example .env
# Edit .env and set:
#   CONSUMER_SECRET=<your X app consumer secret>
```

### 3. Register your webhook

```bash
# Using xurl (official X CLI)
xurl post /2/webhooks -d '{"url": "https://your-tunnel.trycloudflare.com/webhook"}'

# Or using xchat-bot-starter-pro
xchat webhook register --url https://your-tunnel.trycloudflare.com/webhook
```

X will immediately send a CRC challenge. playground handles it automatically at `GET /webhook`.

### 4. Create a profile.update.bio subscription

```bash
# Using xurl
xurl post /2/activity/subscriptions \
  -d '{"filter": {"user_id": "<your_user_id>"}, "event_type": "profile.update.bio"}'

# Or using xchat-bot-starter-pro
xchat subscriptions create \
  --user-id <your_user_id> \
  --event-type profile.update.bio
```

### 5. Trigger the event

Go to https://x.com/settings/profile and change your bio.

X will deliver a `profile.update.bio` event to your webhook within a few seconds.
Watch it appear in the playground UI at http://localhost:7474/ui.

### 6. If you missed an event

X keeps a 24-hour replay window. Use `POST /2/webhooks/replay` with 12-digit
UTC timestamps (`yyyymmddhhmm`) and your webhook ID in the body:

```bash
xurl post /2/webhooks/replay \
  -d '{
    "from_date": "202604170000",
    "to_date": "202604172359",
    "webhook_id": "<your_webhook_id>"
  }'
```

---

## Next steps

- [Webhook Harness](webhook-harness.md) — test CRC + signature validation
- [Replay Lab](replay-lab.md) — record and replay real events
- [Crypto Sandbox](crypto-sandbox.md) — understand E2EE decryption
- [Repro Packs](repro-packs.md) — reproduce known API bugs
