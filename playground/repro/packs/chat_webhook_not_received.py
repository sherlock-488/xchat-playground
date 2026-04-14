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

import os
import urllib.parse


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
                "to events. You must call POST /2/activity/subscriptions "
                "with the correct event types after webhook registration."
            ),
            "how_to_debug": (
                "Check: GET /2/webhooks to see registered webhooks.\n"
                "Check: GET /2/activity/subscriptions to see active subscriptions."
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

    def check(self, webhook_url: str | None = None) -> dict:
        """Semi-automatic environment checker.

        Runs local checks that don't require network access to X's API.
        Pass webhook_url to also validate the URL format.

        Returns a checklist dict with pass/fail/warn for each item.
        """
        results = []

        # Check 1: CONSUMER_SECRET is set
        secret = os.getenv("CONSUMER_SECRET", "")
        if secret:
            results.append({
                "check": "CONSUMER_SECRET set",
                "status": "pass",
                "detail": f"Secret is set ({len(secret)} chars)",
            })
        else:
            results.append({
                "check": "CONSUMER_SECRET set",
                "status": "fail",
                "detail": "CONSUMER_SECRET is empty. Set it in .env or environment.",
                "fix": "Copy .env.example to .env and fill in your Consumer Secret",
            })

        # Check 2: CRC response format (simulate locally)
        if secret:
            from playground.webhook.crc import compute_crc_response
            test_token = "check_token_12345"
            resp = compute_crc_response(test_token, secret)
            rt = resp.get("response_token", "")
            if rt.startswith("sha256=") and len(rt) > 10:
                results.append({
                    "check": "CRC response format",
                    "status": "pass",
                    "detail": "compute_crc_response() returns valid sha256= token",
                })
            else:
                results.append({
                    "check": "CRC response format",
                    "status": "fail",
                    "detail": f"Unexpected CRC response: {rt!r}",
                })
        else:
            results.append({
                "check": "CRC response format",
                "status": "skip",
                "detail": "Skipped — CONSUMER_SECRET not set",
            })

        # Check 3: Webhook URL not localhost
        if webhook_url:
            parsed = urllib.parse.urlparse(webhook_url)
            host = parsed.hostname or ""
            is_local = host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
            is_https = parsed.scheme == "https"

            if is_local:
                results.append({
                    "check": "Webhook URL not localhost",
                    "status": "fail",
                    "detail": f"URL {webhook_url!r} is a localhost address — X cannot reach it.",
                    "fix": "Use a tunnel: npx cloudflared tunnel --url http://localhost:7474",
                })
            else:
                results.append({
                    "check": "Webhook URL not localhost",
                    "status": "pass",
                    "detail": f"URL host {host!r} is not localhost",
                })

            if not is_https and not is_local:
                results.append({
                    "check": "Webhook URL uses HTTPS",
                    "status": "warn",
                    "detail": "X requires HTTPS for production webhook URLs.",
                    "fix": "Ensure your tunnel or server provides TLS",
                })
            elif is_https:
                results.append({
                    "check": "Webhook URL uses HTTPS",
                    "status": "pass",
                    "detail": "URL uses HTTPS",
                })
        else:
            results.append({
                "check": "Webhook URL not localhost",
                "status": "skip",
                "detail": "Pass webhook_url= to check URL format",
            })

        # Check 4: .env file exists
        from pathlib import Path
        env_exists = Path(".env").exists()
        results.append({
            "check": ".env file present",
            "status": "pass" if env_exists else "warn",
            "detail": ".env found" if env_exists else ".env missing — using environment variables only",
        })

        # Summary
        statuses = [r["status"] for r in results]
        all_pass = all(s in ("pass", "skip") for s in statuses)
        has_fail = "fail" in statuses

        return {
            "checks": results,
            "overall": "pass" if all_pass else ("fail" if has_fail else "warn"),
            "summary": (
                "All checks passed — your local config looks correct."
                if all_pass else
                "Some checks failed — see 'checks' for details and fixes."
            ),
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
