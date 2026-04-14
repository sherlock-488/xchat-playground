"""Repro Pack: Legacy /2/dm_events endpoint stops returning new messages after E2EE.

Community report: Bots using the legacy DM Events endpoint
(GET /2/users/:id/direct_messages or similar) stop receiving new
messages after a conversation is "upgraded" to XChat E2EE.

The DM conversation still exists and messages are still being sent,
but the legacy endpoint returns an empty list or stops updating.

Root cause:
  XChat uses a new encrypted messaging stack. Once a conversation
  is upgraded to E2EE (either by the user enabling XChat or
  automatically based on platform settings), messages are no longer
  routed through the legacy DM infrastructure.

  The legacy dm_events endpoint was designed for unencrypted DMs
  and does not have access to E2EE message content.

Forum thread: https://devcommunity.x.com (search "dm_events stops updating")
"""

from __future__ import annotations


class LegacyDmStopsAfterE2eePack:
    title = "Legacy dm_events stops updating after E2EE upgrade"
    description = (
        "Reproduces the scenario where a bot using the legacy DM Events "
        "endpoint stops receiving messages after a conversation is "
        "upgraded to XChat E2EE."
    )
    forum_url = "https://devcommunity.x.com"

    def run(self, verbose: bool = False) -> dict:
        timeline = self._build_timeline()

        return {
            "reproduced": True,
            "summary": (
                "Legacy /2/dm_events (and related endpoints) stop returning "
                "new messages once a conversation is upgraded to XChat E2EE. "
                "This is by design — E2EE messages are only accessible via "
                "the Activity API with proper key material."
            ),
            "workaround": (
                "Migrate from legacy DM polling to XChat Activity Stream:\n\n"
                "1. Register a webhook or open a persistent stream:\n"
                "   GET /2/activity/stream  (Activity Stream)\n"
                "   — or — register a webhook via the developer portal\n\n"
                "2. Subscribe to chat events:\n"
                "   POST /2/activity/subscriptions\n"
                "   body: {event_type: 'chat.received', filter: {user_id: '...'}}\n\n"
                "3. Handle chat.received events and decrypt with your private keys\n\n"
                "4. Reply using POST /2/dm_conversations/:id/messages\n"
                "   (this endpoint still works for sending)\n\n"
                "See: playground simulate chat-received --help\n"
                "See: xchat-bot-python for the full login/unlock/subscribe/run flow"
            ),
            "affected_endpoints": [
                "GET /2/users/:id/direct_messages",
                "GET /2/dm_events",
                "GET /2/dm_conversations/:id/dm_events",
            ],
            "working_alternative": "X Activity API with chat.received subscription",
            "timeline": timeline if verbose else None,
        }

    def _build_timeline(self) -> list[dict]:
        return [
            {
                "time": "T+0",
                "event": "Bot starts polling GET /2/dm_events",
                "result": "Works — returns DM messages",
            },
            {
                "time": "T+1",
                "event": "User enables XChat / conversation upgraded to E2EE",
                "result": "Conversation now uses encrypted messaging stack",
            },
            {
                "time": "T+2",
                "event": "User sends a new message via XChat",
                "result": "Message delivered via XChat E2EE, NOT legacy DM infrastructure",
            },
            {
                "time": "T+3",
                "event": "Bot polls GET /2/dm_events",
                "result": "Returns empty [] or last pre-E2EE message — new messages missing",
            },
            {
                "time": "T+4",
                "event": "Bot checks X Activity Stream (chat.received subscription)",
                "result": "chat.received event arrives with data.payload.encoded_event",
            },
            {
                "time": "T+5",
                "event": "Bot decrypts message using private keys from state.json",
                "result": "Plaintext message content available — bot can respond",
            },
        ]
