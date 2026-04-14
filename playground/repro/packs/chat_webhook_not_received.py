"""Repro Pack: chat.received webhook not delivered.

Community report: Developers register a webhook endpoint and subscribe
to chat.received events, but the webhook is never called even though
messages are being sent.

Common causes:
  1. CRC challenge not handled correctly (endpoint not verified by X)
  2. Webhook URL is not publicly accessible (localhost won't work)
  3. Consumer secret mismatch between webhook registration and handler
  4. Subscription not created for the correct user / conversation
  5. Activity API tier doesn't include private events

Forum thread: https://devcommunity.x.com (search "chat webhook not received")
"""

from __future__ import annotations

import json


class ChatWebhookNotReceivedPack:
    title = "chat.received webhook not delivered"
    description = (
        "Simulates the scenario where chat.received events are sent "
        "but your webhook endpoint never receives them."
    )
    forum_url = "https://devcommunity.x.com"

    def run(self, verbose: bool = False) -> dict:
        steps = []

        # Step 1: Check CRC
        steps.append({
            "step": 1,
            "name": "CRC Challenge",
            "description": "X sends GET /webhook?crc_token=xxx before delivering events.",
            "what_goes_wrong": (
                "If your endpoint returns anything other than "
                '{"response_token": "sha256=<base64_hmac>"}, '
                "X marks it as unverified and stops delivering events."
            ),
            "how_to_debug": (
                "Run: playground webhook crc <token> --consumer-secret <secret>\n"
                "Then compare the output to what your handler returns."
            ),
            "simulation": self._simulate_crc_failure(),
        })

        # Step 2: Public URL
        steps.append({
            "step": 2,
            "name": "Public URL Required",
            "description": "X cannot reach http://localhost or http://127.0.0.1.",
            "what_goes_wrong": (
                "Your webhook must be at a publicly routable HTTPS URL. "
                "Localhost endpoints will silently fail registration."
            ),
            "how_to_debug": (
                "Use a tunnel: npx cloudflared tunnel --url http://localhost:7474\n"
                "Or: ngrok http 7474"
            ),
            "simulation": None,
        })

        # Step 3: Consumer secret mismatch
        steps.append({
            "step": 3,
            "name": "Consumer Secret Mismatch",
            "description": "Signature validation fails if secrets don't match.",
            "what_goes_wrong": (
                "If CONSUMER_SECRET in your handler differs from the one "
                "used to register the webhook, all incoming events will "
                "fail signature validation and return 403."
            ),
            "how_to_debug": (
                "Run: playground webhook verify '<payload>' '<X-Signature-256 value>'\n"
                "to check if your secret matches."
            ),
            "simulation": self._simulate_secret_mismatch(),
        })

        # Step 4: Subscription missing
        steps.append({
            "step": 4,
            "name": "Subscription Not Created",
            "description": "Webhook registered ≠ subscription created.",
            "what_goes_wrong": (
                "Registering a webhook URL is separate from subscribing a user "
                "to events. You must call POST /2/users/:id/activity/subscriptions "
                "with the correct event types after webhook registration."
            ),
            "how_to_debug": (
                "Check: GET /2/webhooks to see registered webhooks.\n"
                "Check: GET /2/users/:id/activity/subscriptions to see active subscriptions."
            ),
            "simulation": None,
        })

        return {
            "reproduced": True,
            "summary": (
                "chat.received webhook not delivered is almost always caused by one of: "
                "(1) CRC not handled, (2) localhost URL, (3) secret mismatch, "
                "(4) subscription not created."
            ),
            "workaround": (
                "1. Verify CRC with: playground webhook crc\n"
                "2. Use a tunnel (cloudflared/ngrok) for local testing\n"
                "3. Double-check CONSUMER_SECRET matches webhook registration\n"
                "4. Explicitly create subscription after webhook registration"
            ),
            "steps": steps if verbose else [s["name"] for s in steps],
        }

    def _simulate_crc_failure(self) -> dict:
        return {
            "description": "Handler returns wrong CRC response",
            "x_sends": "GET /webhook?crc_token=test_token_abc123",
            "correct_response": '{"response_token": "sha256=<hmac_of_token>"}',
            "wrong_responses": [
                '{"status": "ok"}',
                '"pong"',
                "200 OK (empty body)",
            ],
            "result": "X marks endpoint as unverified, stops delivering events",
        }

    def _simulate_secret_mismatch(self) -> dict:
        from playground.webhook.signature import generate_signature
        payload = b'{"event_type":"chat.received"}'
        correct_sig = generate_signature(payload, "correct_secret")
        wrong_sig = generate_signature(payload, "wrong_secret")
        return {
            "description": "Signature computed with wrong secret",
            "payload": payload.decode(),
            "correct_signature": correct_sig,
            "wrong_signature": wrong_sig,
            "result": "verify_signature() returns False → handler rejects event",
        }
