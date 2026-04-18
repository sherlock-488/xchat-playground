"""Repro Pack: REST lookup returns empty {} for XChat E2EE messages.

Community report: Bot receives a chat.received event via Activity Stream.
When it tries to look up message content via a REST API call, it gets
an empty object {}.

Root cause:
  After XChat's E2EE is enabled for a conversation, the legacy
  /2/dm_events endpoint no longer returns message content for
  encrypted conversations. The message content is only accessible
  via the encoded_event field in the Activity Stream event payload
  (observed XAA envelope: data.payload.encoded_event).

This is a breaking change from the pre-E2EE DM API behavior.

Forum thread: https://devcommunity.x.com (search "dm_events returns empty")
"""

from __future__ import annotations


class EncryptedLookupEmptyPack:
    title = "GET /2/dm_events/{id} returns {} for encrypted chat"
    description = (
        "Reproduces the scenario where a chat.received event arrives via "
        "Activity Stream but trying to look up message content via a REST "
        "API call returns an empty object {}."
    )
    forum_url = "https://devcommunity.x.com"

    def run(self, verbose: bool = False) -> dict:
        scenario = self._build_scenario()

        return {
            "reproduced": True,
            "summary": (
                "After E2EE is enabled for a conversation, "
                "GET /2/dm_events/{id} returns {} because the message "
                "content is encrypted and not exposed via the REST endpoint. "
                "Message content is only available in the Activity Stream event payload."
            ),
            "workaround": (
                "Do NOT call /2/dm_events/{id} to get message content for XChat conversations.\n"
                "Instead: read encoded_event from the Activity Stream event payload,\n"
                "then decrypt it using your private keys (see: playground crypto).\n\n"
                "Migration pattern:\n"
                "  OLD: receive event → lookup /2/dm_events/{id} → read .text\n"
                "  NEW: receive event → read data.payload.encoded_event → decrypt"
            ),
            "scenario": scenario if verbose else None,
        }

    def _build_scenario(self) -> dict:
        # Simulate the event (observed XAA envelope from Activity Stream)
        event = {
            "data": {
                "event_type": "chat.received",
                "payload": {
                    "conversation_id": "DM_111_222",
                    "encoded_event": "STUB_ENC_SGVsbG8h",
                    "encrypted_conversation_key": "STUB_KEY_abc123",
                    "conversation_key_version": "1",
                    "conversation_token": "STUB_TOKEN_1234567890abcdef",
                },
            }
        }

        # What the old code does (broken)
        old_approach = {
            "code": (
                "# Wrong: trying to look up via REST after receiving event\n"
                "conversation_token = event['data']['payload']['conversation_token']\n"
                "resp = requests.get(f'/2/dm_events/{conversation_token}', headers=auth)\n"
                "text = resp.json()['data']['text']  # KeyError! resp.json() == {}"
            ),
            "result": "{}",
            "error": "KeyError: 'data' — encrypted messages not exposed via REST endpoint",
        }

        # What the new code should do (correct)
        new_approach = {
            "code": (
                "encoded = event['data']['payload']['encoded_event']\n"
                "enc_key = event['data']['payload']['encrypted_conversation_key']\n"
                "plaintext = crypto.decrypt(encoded, enc_key)  # use your private keys\n"
                "# No REST lookup needed"
            ),
            "result": "Hello!",
            "error": None,
        }

        return {
            "incoming_event": event,
            "old_approach_broken": old_approach,
            "new_approach_correct": new_approach,
        }
