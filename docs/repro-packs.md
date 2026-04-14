# Repro Packs

One-click reproductions of known XChat API issues.

```bash
# List all available packs
uv run playground repro list

# Run a pack
uv run playground repro run <pack-id>

# Run with step-by-step details
uv run playground repro run <pack-id> --verbose
```

---

## chat-webhook-not-received

**Symptom:** You registered a webhook and subscribed to `chat.received`, but events never arrive.

**Root causes (in order of frequency):**

1. **CRC challenge not handled** — X sends `GET /webhook?crc_token=xxx` before delivering events. If your endpoint doesn't return `{"response_token": "sha256=..."}`, X marks it as unverified.

2. **Localhost URL** — X cannot reach `http://localhost` or `http://127.0.0.1`. Use a tunnel (cloudflared/ngrok).

3. **Consumer secret mismatch** — If your handler uses a different secret than the one used to register the webhook, all events are rejected with 403.

4. **Subscription not created** — Registering a webhook URL is separate from subscribing a user. You must call `POST /2/users/:id/activity/subscriptions` after registration.

**Workaround:**
```bash
# Debug CRC
uv run playground webhook crc <token> --consumer-secret <secret>

# Expose local server
npx cloudflared tunnel --url http://localhost:7474
```

---

## encrypted-lookup-empty

**Symptom:** `GET /2/dm_events/{id}` returns `{}` after receiving a `chat.received` event.

**Root cause:** After E2EE is enabled for a conversation, the legacy `/2/dm_events` endpoint no longer returns message content. The message is only accessible via the encrypted `encrypted_content` field in the Activity Stream event itself.

**Old flow (broken):**
```python
dm_event_id = event["direct_message_events"][0]["id"]
resp = requests.get(f"/2/dm_events/{dm_event_id}", headers=auth)
text = resp.json()["data"]["text"]  # KeyError! resp.json() == {}
```

**New flow (correct):**
```python
encrypted = event["direct_message_events"][0]["message"]["encrypted_content"]
plaintext = crypto.decrypt(encrypted)  # use your private keys
```

---

## legacy-dm-stops-after-e2ee

**Symptom:** `GET /2/users/:id/direct_messages` stops returning new messages after a conversation is "upgraded" to XChat.

**Root cause:** Once a conversation uses XChat E2EE, messages go through the new encrypted stack — not the legacy DM infrastructure. The legacy endpoint has no access to encrypted message content.

**Migration path:**
```
OLD: poll GET /2/users/:id/direct_messages every N seconds
NEW: subscribe to chat.received via Activity API

Steps:
1. POST /2/users/:id/activity/subscriptions
   body: {"event_types": ["chat.received", "chat.sent"]}

2. Handle chat.received events in your webhook/stream handler

3. Decrypt with private keys from state.json

4. Reply via POST /2/dm_conversations/:id/messages
   (sending still works via REST)
```

---

## Adding a new repro pack

Found a reproducible bug? [Open a Repro Pack issue](../../issues/new?template=repro_pack.md).

If the bug is confirmed, we'll add it as a preset so others can reproduce it with one command.
