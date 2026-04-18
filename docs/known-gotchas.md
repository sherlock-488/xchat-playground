# Known Gotchas

A running list of non-obvious issues when building XChat bots.

---

## 1. `http://127.0.0.1` vs `http://localhost` in OAuth2

X's OAuth2 validation treats these as **different URLs**.

When registering your app's callback URL in the X Developer Portal, use:
```
http://127.0.0.1:<PORT>/callback
```
Not `http://localhost:<PORT>/callback`.

If they don't match exactly, OAuth2 will fail with a redirect URI mismatch error.

---

## 2. CRC must return exact JSON format

X sends `GET /webhook?crc_token=<token>` to verify your endpoint.

Your response must be **exactly**:
```json
{"response_token": "sha256=<base64_hmac_sha256>"}
```

Common mistakes:
- Returning `{"status": "ok"}` — endpoint never verified
- Returning the token unchanged — signature wrong
- Returning `200 OK` with empty body — endpoint never verified

Test with: `uv run playground webhook crc <token>`

---

## 3. E2EE messages: don't look up `/2/dm_events/{id}`

After XChat E2EE is enabled on a conversation:
- `GET /2/dm_events/{id}` returns `{}`
- Message content is **only** in the `data.payload.encoded_event` field of the Activity Stream event (observed XAA envelope)

> **Note on simulator field names:** The demo schema uses `encrypted_content` / `direct_message_events` for readability. These are teaching labels, not the real wire format. The observed schema (from xchat-bot-python) uses `data.payload.encoded_event`.

See: [Repro Pack — encrypted-lookup-empty](repro-packs.md#encrypted-lookup-empty)

---

## 4. Legacy DM endpoint goes silent after E2EE upgrade

Once a conversation is upgraded to XChat, `GET /2/users/:id/direct_messages`
stops returning new messages. This is by design — E2EE messages use a different stack.

See: [Repro Pack — legacy-dm-stops-after-e2ee](repro-packs.md#legacy-dm-stops-after-e2ee)

---

## 5. state.json contains private keys — NEVER commit it

`xchat-bot-python`'s `login` + `unlock` flow creates `state.json` with your private encryption keys.

```bash
# Verify it's gitignored
git check-ignore -v state.json

# Add immediately if missing
echo "state.json" >> .gitignore
git rm --cached state.json  # if already tracked
```

---

## 6. Activity API private events require OAuth 2.0 user auth

You cannot subscribe a user to private events (like `chat.received`) using just a Bearer Token.
The user must authorize your app via OAuth 2.0, and your app must have the appropriate scopes.

The official `xchat-bot-python` template handles this with the `login` command.

---

## 7. Self-serve tier: max 1000 subscriptions

The Activity API self-serve tier limits you to 1000 active event subscriptions.
If you're building a multi-user bot, plan for subscription lifecycle management (create/delete).

---

## 8. `chat-xdk` is not yet officially released

The official `xchat-bot-python` template depends on `chat-xdk` as a sibling repo.
It is not yet published to PyPI. Until it is, you need to clone both repos side by side.

Follow the [xchat-bot-python README](https://github.com/xdevplatform/xchat-bot-python) for current setup instructions.

---

## 9. AI-generated replies require X approval before deployment

Per X's Developer Guidelines, bots that send AI-generated replies must receive
X's approval before going live. "Draft-only" or "human-in-the-loop" bots
(where a human reviews and sends) do not require this.

---

## 10. Automated accounts must be labeled

Bots must:
- Have "Automated" label enabled on the account
- State bot identity and operator in the bio
- Be associated with a human-managed account
- Support easy opt-out for users

Failure to comply can result in account suspension.
