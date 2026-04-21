"""Repro Pack: received chat.received event but cannot read plaintext.

Common situation: A developer registers a webhook or Activity Stream
subscription, receives chat.received events, but cannot read the
message content because the payload is end-to-end encrypted.

Root cause:
  XChat uses end-to-end encryption. The message content is NOT
  transmitted as plaintext. Instead, the Activity Stream / webhook
  delivers an encrypted envelope containing:

    - encoded_event           — encrypted message blob (observed XAA field)
    - encrypted_conversation_key — conversation key, encrypted to recipient
    - conversation_key_version   — key rotation version
    - conversation_key_change_event — key change event, if any (may be null)
    - conversation_token      — opaque token (observed XAA field)

  Decrypting these fields requires chat-xdk, which is pending stable
  public release. Until then, real plaintext decrypt is experimental.

What you CAN do today:
  - Capture, export, replay, and compare encrypted payloads.
  - Verify event delivery, event_type, event_uuid, filter, tag.
  - Inspect payload shape: conversation_id, encoded_event, sender_id.
  - Confirm schema_source is "observed" (not "docs") for these fields.
  - Use playground repro packs to debug delivery issues.

What you CANNOT do yet (without chat-xdk):
  - Read message plaintext from encoded_event.
  - Decrypt encrypted_conversation_key or conversation_key_change_event.

Forum thread: https://devcommunity.x.com (search "xchat decrypt plaintext")
"""

from __future__ import annotations


class EncryptedChatDecryptPendingPack:
    title = "Received chat.received but cannot read plaintext"
    description = (
        "Explains why XChat payloads are encrypted and what you can "
        "inspect today before chat-xdk reaches stable public release."
    )
    forum_url = "https://devcommunity.x.com"

    def run(self, verbose: bool = False) -> dict:
        checks = self._build_checks()

        return {
            "reproduced": True,
            "summary": (
                "XChat payloads are end-to-end encrypted. "
                "encoded_event, encrypted_conversation_key, "
                "conversation_key_change_event, and conversation_token "
                "are encrypted / observed fields. "
                "Real plaintext decrypt requires chat-xdk, "
                "which is pending stable public release."
            ),
            "what_you_can_do_today": (
                "1. Verify the event arrived (event_uuid present).\n"
                "2. Confirm event_type == 'chat.received'.\n"
                "3. Check filter and tag are preserved.\n"
                "4. Inspect payload.conversation_id and payload.sender_id.\n"
                "5. Confirm payload.encoded_event is present (encrypted blob).\n"
                "6. Confirm payload.conversation_token is present.\n"
                "7. Confirm schema_source is 'observed', not 'docs'.\n"
                "8. Use playground to capture, export, replay, and compare "
                "encrypted payloads even before decrypt works.\n"
                "9. Use 'playground crypto stub STUB_ENC_…' to decode demo fixtures."
            ),
            "what_requires_chat_xdk": (
                "- Reading plaintext from encoded_event.\n"
                "- Decrypting encrypted_conversation_key.\n"
                "- Processing conversation_key_change_event.\n"
                "chat-xdk is pending stable public release. "
                "Real decrypt remains experimental until then."
            ),
            "chat_api_routes_documented": (
                "The following Chat API routes are documented in the official migration guide:\n"
                "  GET  /2/users/{id}/public_keys\n"
                "  GET  /2/chat/conversations\n"
                "  GET  /2/chat/conversations/{conversation_id}\n"
                "  POST /2/chat/conversations/{conversation_id}/messages\n"
                "Note: sending messages also requires chat-xdk for encryption."
            ),
            "checks": checks if verbose else [c["check"] for c in checks],
        }

    def _build_checks(self) -> list[dict]:
        return [
            {
                "check": "Did the event arrive?",
                "how_to_verify": (
                    "Check your webhook handler received an HTTP POST, "
                    "or your Activity Stream consumer received a message. "
                    "Use 'playground serve' + 'playground simulate chat-received' "
                    "to confirm local delivery works."
                ),
            },
            {
                "check": "Is event_type == 'chat.received'?",
                "how_to_verify": (
                    "Inspect data.event_type in the received payload. "
                    "Must equal 'chat.received' (event name is officially documented)."
                ),
            },
            {
                "check": "Is event_uuid present?",
                "how_to_verify": (
                    "Check data.event_uuid in the XAA envelope. "
                    "Useful for deduplication and debugging."
                ),
            },
            {
                "check": "Are filter and tag preserved?",
                "how_to_verify": (
                    "Inspect data.filter.user_id and data.tag. "
                    "These identify which subscription triggered the event."
                ),
            },
            {
                "check": "Is payload.encoded_event present?",
                "how_to_verify": (
                    "Inspect data.payload.encoded_event. "
                    "This is the encrypted message blob (observed XAA field). "
                    "It is NOT plaintext — do not try to JSON-parse it directly."
                ),
            },
            {
                "check": "Is payload.conversation_id present?",
                "how_to_verify": (
                    "Inspect data.payload.conversation_id. "
                    "This identifies the conversation (not encrypted)."
                ),
            },
            {
                "check": "Is payload.conversation_token present?",
                "how_to_verify": (
                    "Inspect data.payload.conversation_token. "
                    "Observed XAA field — opaque token, may be null."
                ),
            },
            {
                "check": "Is schema_source 'observed', not 'docs'?",
                "how_to_verify": (
                    "In xchat-playground, observed chat.received fixtures have "
                    "schema_source='observed'. This is correct — the XAA "
                    "chat.received payload shape is sample-driven, not yet "
                    "fully documented in docs.x.com."
                ),
            },
            {
                "check": "Are you incorrectly expecting plaintext?",
                "how_to_verify": (
                    "XChat is end-to-end encrypted. encoded_event is NEVER plaintext. "
                    "Do NOT call /2/dm_events/{id} to get message content — it returns {}. "
                    "Real decrypt requires chat-xdk + private keys from state.json. "
                    "Use 'playground crypto stub STUB_ENC_…' only for demo fixtures."
                ),
            },
        ]
