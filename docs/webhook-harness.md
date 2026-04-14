# Webhook Harness

The webhook harness helps you validate CRC challenges and signature verification locally.

## CRC Challenge

X sends a `GET /webhook?crc_token=xxx` request to verify your endpoint before delivering events.

### What X expects

Your endpoint must return:

```json
{"response_token": "sha256=<base64_hmac_sha256_of_token>"}
```

Where the HMAC key is your **consumer secret**.

### Compute it locally

```bash
uv run playground webhook crc <crc_token> --consumer-secret <your_secret>
```

Or set `CONSUMER_SECRET` in `.env` and the playground server handles it automatically at `GET /webhook?crc_token=xxx`.

### In the Web UI

Go to **Webhook → CRC Challenge Calculator**, enter your token and secret.

---

## Signature Validation

Every POST webhook payload is signed by X with `X-Signature-256: sha256=<base64_hmac>`.

### Verify a signature

```bash
uv run playground webhook verify '<payload_body>' '<X-Signature-256_header_value>'
```

### Step-by-step breakdown

```bash
# See exactly what X computes
curl -X POST http://localhost:7474/api/signature/explain \
  -H "Content-Type: application/json" \
  -d '{"payload": "{\"event_type\":\"chat.received\"}", "consumer_secret": "your_secret"}'
```

Or use **Webhook → Signature Explainer** in the Web UI.

---

## Live Webhook Testing

To receive real webhooks from X, your server must be publicly accessible.

```bash
# cloudflared (free, no account needed)
npx cloudflared tunnel --url http://localhost:7474

# ngrok
ngrok http 7474
```

Register the tunnel URL in the X Developer Portal as your webhook endpoint.

> **Gotcha:** X's OAuth2 callback URL validation treats `http://localhost` and `http://127.0.0.1` differently.
> Always use `http://127.0.0.1` for local OAuth2 callbacks.
