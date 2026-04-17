"""Repro Pack: X Activity API webhook smoke test — first successful delivery.

A positive checklist for developers setting up X Activity API webhooks for
the first time. Walks through every requirement from the official docs.x.com
quickstart, using profile.update.bio as the recommended first event to test
(public event — no special OAuth scopes required for the monitored user).

Reference: X Activity API quickstart (docs.x.com)
"""

from __future__ import annotations

import os
import urllib.parse


class XAAWebhookSmokeTestPack:
    title = "X Activity API webhook smoke test (first delivery)"
    description = (
        "Step-by-step checklist to get your first real X Activity webhook "
        "delivery working. Uses profile.update.bio — a public event that "
        "requires no special OAuth scopes for the monitored user."
    )
    forum_url = "https://devcommunity.x.com"

    def run(self, verbose: bool = False) -> dict:
        steps = []

        # Step 1: Public HTTPS URL
        webhook_url = os.getenv("XCHAT_WEBHOOK_PUBLIC_URL", os.getenv("PLAYGROUND_WEBHOOK_URL", ""))
        has_https = webhook_url.startswith("https://") if webhook_url else False
        has_no_port = ":" not in urllib.parse.urlparse(webhook_url).netloc.split("@")[-1] if webhook_url else True
        url_ok = has_https and has_no_port
        steps.append({
            "step": 1,
            "name": "Webhook URL is public HTTPS without port",
            "description": (
                "X requires a publicly accessible HTTPS URL with no port number. "
                "localhost and 127.0.0.1 will not work for receiving real events. "
                "Use a tunnel (cloudflared, ngrok) for local development."
            ),
            "status": "pass" if url_ok else "warn",
            "detail": (
                f"Found: {webhook_url}" if webhook_url
                else "XCHAT_WEBHOOK_PUBLIC_URL not set — required for real webhook registration"
            ),
            "fix": (
                "Run: npx cloudflared tunnel --url http://localhost:7474\n"
                "Then set XCHAT_WEBHOOK_PUBLIC_URL=https://<your-tunnel>.trycloudflare.com"
            ) if not url_ok else None,
        })

        # Step 2: Consumer secret configured
        consumer_secret = os.getenv("CONSUMER_SECRET", "")
        steps.append({
            "step": 2,
            "name": "CONSUMER_SECRET is set",
            "description": (
                "Required for webhook HMAC-SHA256 signature verification. "
                "X signs every POST request with your app's Consumer Secret."
            ),
            "status": "pass" if consumer_secret else "fail",
            "detail": "Set" if consumer_secret else "Not set — webhook signature verification will fail",
            "fix": "Set CONSUMER_SECRET in .env — find it in X Developer Portal → your app → Keys and tokens",
        })

        # Step 3: CRC handler
        steps.append({
            "step": 3,
            "name": "Webhook handles GET CRC challenge",
            "description": (
                "X sends GET /webhook?crc_token=xxx before delivering any events. "
                "Your endpoint must respond with the correct HMAC-SHA256 hash. "
                "xchat-playground handles this automatically at GET /webhook."
            ),
            "status": "info",
            "detail": "playground serve handles CRC at GET /webhook automatically",
            "fix": None,
        })

        # Step 4: Register webhook
        steps.append({
            "step": 4,
            "name": "Register webhook with X",
            "description": (
                "POST /2/webhooks with your public URL. X will immediately send "
                "a CRC challenge to verify your endpoint is reachable."
            ),
            "status": "info",
            "detail": (
                "xchat-bot-starter-pro: xchat webhook register --url <your_url>\n"
                "xurl: xurl post /2/webhooks -d '{\"url\": \"<your_url>\"}'"
            ),
            "fix": None,
        })

        # Step 5: Create profile.update.bio subscription
        steps.append({
            "step": 5,
            "name": "Create profile.update.bio subscription",
            "description": (
                "profile.update.bio is a public event — no special OAuth scopes "
                "required for the monitored user. Ideal for first-time smoke testing. "
                "POST /2/activity/subscriptions with filter.user_id and event_type."
            ),
            "status": "info",
            "detail": (
                "xchat-bot-starter-pro: xchat subscriptions create "
                "--user-id <your_user_id> --event-type profile.update.bio\n"
                "xurl: xurl post /2/activity/subscriptions "
                "-d '{\"filter\": {\"user_id\": \"<id>\"}, \"event_type\": \"profile.update.bio\"}'"
            ),
            "fix": None,
        })

        # Step 6: Trigger event
        steps.append({
            "step": 6,
            "name": "Trigger the event",
            "description": (
                "Go to x.com and edit your bio. X will deliver a profile.update.bio "
                "event to your webhook within a few seconds."
            ),
            "status": "info",
            "detail": "Edit bio at https://x.com/settings/profile",
            "fix": None,
        })

        # Step 7: Webhook replay fallback
        steps.append({
            "step": 7,
            "name": "Use webhook replay if event was missed",
            "description": (
                "If your webhook was down when the event was delivered, use X's "
                "webhook replay to recover it. Replay covers the last 24 hours of "
                "delivered or attempted deliveries."
            ),
            "status": "info",
            "detail": (
                "POST /2/webhooks/replay with webhook_id, from_date, and to_date in the JSON body. "
                "Timestamps use 12-digit UTC format: yyyymmddhhmm (e.g. 202604170000). "
                "Rate limit: 100 requests per 15 minutes."
            ),
            "fix": None,
        })

        # Summary
        failures = [s for s in steps if s["status"] == "fail"]
        warnings = [s for s in steps if s["status"] == "warn"]

        summary_lines = [
            "X Activity API webhook smoke test checklist",
            "",
            "This pack walks you through the official docs.x.com quickstart requirements.",
            "Use profile.update.bio as your first real event — it's a public event",
            "that requires no OAuth scopes for the monitored user.",
            "",
        ]
        if not failures and not warnings:
            summary_lines.append("Environment looks ready. Follow steps 4-7 to complete setup.")
        else:
            if failures:
                summary_lines.append(f"{len(failures)} required item(s) missing — fix before proceeding.")
            if warnings:
                summary_lines.append(f"{len(warnings)} warning(s) — review before registering webhook.")

        return {
            "reproduced": True,
            "summary": "\n".join(summary_lines),
            "workaround": (
                "1. Expose local server: npx cloudflared tunnel --url http://localhost:7474\n"
                "2. Register webhook with the tunnel URL\n"
                "3. Create profile.update.bio subscription\n"
                "4. Edit your bio on X\n"
                "5. Watch events arrive in playground UI at /ui"
            ),
            "steps": steps if verbose else None,
        }
