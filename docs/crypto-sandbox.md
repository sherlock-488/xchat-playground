# Crypto Sandbox

Understand XChat's E2EE decryption flow without real keys.

> **Schema terminology:** This project uses two schemas:
> - **demo schema** — flat, easy-to-read fixtures (`encrypted_content`, `direct_message_events`). For teaching only, not the real XAA wire format.
> - **observed schema** — mirrors xchat-bot-python (`data.payload.encoded_event`, `encrypted_conversation_key`). Inferred from the official bot source; field names may change when chat-xdk is released.

## Two modes

### Stub mode (default, no keys needed)

The simulator generates "stub encrypted" payloads: `STUB_ENC_<base64(plaintext)>`.

Stub mode simply base64-decodes them, letting you walk through the full
decrypt → handle → reply flow without any X credentials.

```bash
uv run playground crypto stub "STUB_ENC_SGVsbG8h"
# Output: plaintext = "Hello!"
```

### Real-key mode (requires state.json)

After running `xchat-bot-python`'s login + unlock flow, you have a `state.json`
with your private keys. Real-key mode uses these to decrypt actual XChat messages.

```bash
uv run playground crypto real "REAL_ENCRYPTED_PAYLOAD" --state-file state.json
```

> **Note:** Full XChaCha20-Poly1305 decryption requires `chat-xdk`, which is not
> yet officially released by xdevplatform. This module will be updated when
> `chat-xdk` reaches stable release.

## The decryption flow

```
chat.received event arrives (official XAA envelope)
  │
  └── data.payload
        ├── encoded_event              ← base64-encoded encrypted ciphertext
        ├── encrypted_conversation_key ← per-recipient encrypted symmetric key
        ├── conversation_key_version   ← which of your private keys to use
        └── conversation_token         ← opaque conversation identifier
                │
                ▼
  1. Look up private_key[conversation_key_version] from state.json
  2. ECDH (X25519): decrypt encrypted_conversation_key → symmetric_key
  3. XChaCha20-Poly1305: decrypt encoded_event with symmetric_key
                │
                ▼
  plaintext message
```

> **Schema note:** Field names are inferred from [xchat-bot-python](https://github.com/xdevplatform/xchat-bot-python).
> The official chat-xdk library is not yet released; this flow may be updated.

## Common mistake: don't call /2/dm_events/{id}

After E2EE is enabled, `GET /2/dm_events/{id}` returns `{}` for encrypted messages.
The message content is **only** in the Activity Stream event payload.

See: [Repro Pack — encrypted-lookup-empty](repro-packs.md#encrypted-lookup-empty)

## state.json security

**Never commit state.json to git.** It contains your private encryption keys.

```bash
# Verify it's gitignored
git check-ignore -v state.json

# Add to .gitignore if missing
echo "state.json" >> .gitignore
```
