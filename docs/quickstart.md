# Quickstart

Get xchat-playground running in under 5 minutes.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended)

No X developer account needed for local testing.

## Install

```bash
git clone https://github.com/sherlock-488/xchat-playground
cd xchat-playground
pip install uv
uv sync
```

## Start the server

```bash
uv run playground serve
```

Open http://localhost:7474/ui in your browser.

## Inject your first event

In the Web UI, click **Simulate → Inject chat.received**.

Or via CLI:

```bash
uv run playground simulate chat-received
```

## Check your environment

```bash
uv run playground doctor
```

This checks Python version, uv, xurl, .env file, and whether state.json is safely gitignored.

## Next steps

- [Webhook Harness](webhook-harness.md) — test CRC + signature validation
- [Replay Lab](replay-lab.md) — record and replay real events
- [Crypto Sandbox](crypto-sandbox.md) — understand E2EE decryption
- [Repro Packs](repro-packs.md) — reproduce known API bugs
