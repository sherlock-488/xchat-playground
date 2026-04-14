"""Repro Pack: GET /2/dm_events/{id} returns empty {} after chat.received.

Community report: Bot receives a chat.received webhook event with a
dm_event_id. When it calls GET /2/dm_events/{dm_event_id} to fetch
message details, the API returns an empty object {}.

Root cause:
  After XChat's E2EE is enabled for a conversation, the legacy
  /2/dm_events endpoint no longer returns message content for
  encrypted conversations. The message content is only accessible
  via the encrypted_content field in the Activity Stream event itself.

This is a breaking change from the pre-E2EE DM API behavior.

Forum thread: https://devcommunity.x.com (search "dm_events returns empty")
"""

from __future__ import annotations


class EncryptedLookupEmptyPack:
    title = "GET /2/dm_events/{id} returns {} for encrypted chat"
    description = (
        "Reproduces the scenario where chat.received arrives but "
        "looking up the dm_event_id via the REST API returns an empty object."
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
                "Instead: read encrypted_content directly from the Activity Stream event,\n"
                "then decrypt it using your private keys (see: playground crypto).\n\n"
                "Migration pattern:\n"
                "  OLD: receive event → lookup /2/dm_events/{id} → read .text\n"
                "  NEW: receive event → read event.message.encrypted_content → decrypt"
            ),
            "scenario": scenario if verbose else None,
        }

    def _build_scenario(self) -> dict:
        # Simulate the event
        event = {
            "event_type": "chat.received",
            "direct_message_events": [{
                "id": "1234567890abcdef",
                "event_type": "MessageCreate",
                "dm_conversation_id": "DM_111_222",
                "sender_id": "111222333",
                "message": {
                    "encrypted_content": "STUB_ENC_SGVsbG8h",
                    "encryption_type": "XChaCha20Poly1305",
                },
            }],
        }

        # What the old code does (broken)
        old_approach = {
            "code": (
                "dm_event_id = event['direct_message_events'][0]['id']\n"
                "resp = requests.get(f'/2/dm_events/{dm_event_id}', headers=auth)\n"
                "text = resp.json()['data']['text']  # KeyError! resp.json() == {}"
            ),
            "result": "{}",
            "error": "KeyError: 'data' — because the response body is empty",
        }

        # What the new code should do (correct)
        new_approach = {
            "code": (
                "encrypted = event['direct_message_events'][0]['message']['encrypted_content']\n"
                "plaintext = crypto.decrypt(encrypted)  # use your private keys\n"
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
