# xchat-playground 🧪

> **Local simulator & replay lab for XChat bots.**
> Debug webhooks, replay `chat.received` events, and test E2EE decrypt flows —
> all offline, zero API credits burned.

[![CI](https://github.com/sherlock-488/xchat-playground/actions/workflows/ci.yml/badge.svg)](https://github.com/sherlock-488/xchat-playground/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![X Developer Forum](https://img.shields.io/badge/X%20Dev-Forum-1d9bf0)](https://devcommunity.x.com)

---

## Why this exists

Building on XChat means dealing with:

- `chat.received` events that silently fail CRC validation
- Encrypted DM payloads that return `{}` when you look them up via REST
- `dm_events` going quiet after E2EE is enabled on a conversation
- Event format changes that break your handler at 2am

This playground gives you a **local harness** to reproduce, replay, and diff all of the above **before** touching production.

> **Delivery modes:** X Activity API supports both **webhook** (HTTP POST) and **persistent Activity Stream** (long-lived connection). This playground focuses on the webhook delivery path. The official [xchat-bot-python](https://github.com/xdevplatform/xchat-bot-python) template uses Activity Stream. Both are valid — choose based on your architecture.
>
> **Schema note:** Event field-level schema (e.g. `data.payload.encoded_event`) is inferred from the official bot source. X has not yet published a complete XChat payload reference. This repo tracks the official bot as the authoritative contract until docs.x.com catches up.

---

## What's inside

| Module | CLI | What it does |
|--------|-----|-------------|
| **Event Simulator** | `playground simulate` | Generate `chat.received` / `chat.sent` / `chat.conversation_join` fixtures |
| **Webhook Harness** | `playground webhook` | CRC challenge + HMAC-SHA256 signature validation playground |
| **Replay Lab** | `playground replay` | Record → scrub PII → replay → diff against your handler |
| **Crypto Sandbox** | `playground crypto` | Stub or real-key decryption flow walkthrough |
| **Repro Packs** | `playground repro` | One-click presets for known community bug reports |
| **Web UI** | `playground serve` | Browser-based event inspector + debug tools |
| **Doctor** | `playground doctor` | Check your environment is ready |

---

## Quickstart (no API key needed)

```bash
git clone https://github.com/sherlock-488/xchat-playground
cd xchat-playground
pip install uv && uv sync
uv run playground serve
# → open http://localhost:7474/ui
```

That's it. The Web UI opens with demo events pre-loaded so you're never staring at a blank screen.
No X developer account required for local testing.

---

## CLI Reference

```bash
# Start local server + Web UI
uv run playground serve --port 7474

# Check your environment
uv run playground doctor

# Generate event fixtures
uv run playground simulate chat-received --sender-id 123 --recipient-id 456
uv run playground simulate chat-received --no-encrypted  # plaintext mode
uv run playground simulate batch --count 20 --output fixtures/batch.jsonl

# Webhook tools
uv run playground webhook crc <crc_token> --consumer-secret <secret>
uv run playground webhook verify '<payload>' '<x-twitter-webhooks-signature value>'

# Replay
uv run playground replay run fixtures/batch.jsonl --target http://127.0.0.1:8080/webhook
uv run playground replay diff fixtures/batch.jsonl \
  --baseline-url http://127.0.0.1:8080/webhook \
  --candidate-url http://127.0.0.1:8081/webhook

# Crypto sandbox
uv run playground crypto stub "STUB_ENC_SGVsbG8h"
uv run playground crypto real "REAL_PAYLOAD" --state-file state.json

# Repro packs
uv run playground repro list
uv run playground repro run encrypted-lookup-empty --verbose
uv run playground repro run chat-webhook-not-received --verbose
uv run playground repro run legacy-dm-stops-after-e2ee --verbose
```

---

## Repro Packs

One-click reproductions of the most common XChat API issues reported in the developer community:

| Pack ID | Issue |
|---------|-------|
| `chat-webhook-not-received` | CRC not handled / localhost URL / secret mismatch / subscription missing |
| `encrypted-lookup-empty` | `GET /2/dm_events/{id}` returns `{}` for E2EE conversations |
| `legacy-dm-stops-after-e2ee` | Legacy DM endpoint stops updating after conversation upgrade |

Run any pack with `--verbose` for step-by-step explanation and workaround.

---

## Live Webhook Testing

To test with a real X webhook registration, expose your local server publicly:

```bash
# Option 1: cloudflared (recommended, free)
npx cloudflared tunnel --url http://localhost:7474

# Option 2: ngrok
ngrok http 7474
```

Then register the tunnel URL as your webhook in the X Developer Portal.

> **Note:** `http://localhost` and `http://127.0.0.1` are **not** the same in X's OAuth2 validation.
> For local OAuth2 callbacks, use `http://127.0.0.1` — see [Known Gotchas](docs/known-gotchas.md).

---

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- X Developer Account (optional — only needed for live webhook testing)

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Required for live webhook signature validation
CONSUMER_SECRET=your_app_consumer_secret

# Required for real-key crypto (xchat-bot-python login flow)
# state.json is auto-generated by xchat-bot-python — never commit it
```

---

## Project Structure

```
xchat-playground/
├── playground/
│   ├── cli.py              # CLI entry point (typer)
│   ├── simulator/          # Event fixture generator
│   ├── webhook/            # CRC + signature + local server
│   ├── replay/             # Record, replay, diff
│   ├── crypto/             # Stub + real-key decryption
│   └── repro/              # Known-bug repro packs
├── web/                    # Browser UI (index.html + app.js)
├── tests/                  # pytest test suite
└── docs/                   # Detailed documentation
```

---

## Status

> ⚠️ XChat is launching April 17, 2026. This playground tracks the official
> [xchat-bot-python](https://github.com/xdevplatform/xchat-bot-python) template
> and [X Activity API](https://developer.x.com/en/docs/x-api).
> The `crypto real` mode will be updated when `chat-xdk` reaches stable release.

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Found a new XChat API bug? [Open a Repro Pack issue](../../issues/new?template=repro_pack.md) —
if it's reproducible, we'll add it as a preset.

---

## Resources

- [X Developer Portal](https://developer.x.com)
- [X Developer Forum](https://devcommunity.x.com)
- [xchat-bot-python](https://github.com/xdevplatform/xchat-bot-python) — official bot template
- [X Activity API docs](https://developer.x.com/en/docs/x-api/activity-api)
- [@XDevelopers](https://x.com/XDevelopers)
- [X API Changelog](https://developer.x.com/en/updates/changelog)

---

## License

MIT — see [LICENSE](LICENSE).
