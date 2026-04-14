"""Event replayer — replay fixture files against a local webhook handler."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx


class EventReplayer:
    """Replay XChat event fixtures against a webhook handler URL.

    Supports both single JSON files and JSONL batch files.

    Usage:
        replayer = EventReplayer(target_url="http://127.0.0.1:7474/webhook")
        results = await replayer.replay_file(Path("fixtures/session.jsonl"))
    """

    def __init__(
        self,
        target_url: str = "http://127.0.0.1:7474/webhook",
        consumer_secret: str | None = None,
        timeout: float = 10.0,
    ):
        self.target_url = target_url
        self.consumer_secret = consumer_secret
        self.timeout = timeout

    async def replay_file(
        self,
        path: Path,
        delay: float = 0.1,
    ) -> list[dict]:
        """Replay all events from a fixture file.

        Supports:
          - .json   → single event dict
          - .jsonl  → one event per line
        """
        events = self._load_file(path)
        results = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for event in events:
                result = await self._send(client, event)
                results.append(result)
                if delay > 0:
                    await asyncio.sleep(delay)
        return results

    async def replay_event(self, event: dict) -> dict:
        """Replay a single event dict."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._send(client, event)

    # ── private ───────────────────────────────────────────────────────────────

    async def _send(self, client: httpx.AsyncClient, event: dict) -> dict:
        payload = json.dumps(event).encode()
        headers = {"Content-Type": "application/json"}

        if self.consumer_secret:
            from playground.webhook.signature import generate_signature
            headers["X-Signature-256"] = generate_signature(payload, self.consumer_secret)

        event_type = event.get("event_type", "unknown")
        try:
            response = await client.post(
                self.target_url,
                content=payload,
                headers=headers,
            )
            return {
                "event_type": event_type,
                "success": response.is_success,
                "status_code": response.status_code,
                "response_body": response.text[:500],
                "error": None,
            }
        except httpx.ConnectError as e:
            return {
                "event_type": event_type,
                "success": False,
                "status_code": None,
                "response_body": None,
                "error": f"Connection refused: {e}",
            }
        except Exception as e:
            return {
                "event_type": event_type,
                "success": False,
                "status_code": None,
                "response_body": None,
                "error": str(e),
            }

    def _load_file(self, path: Path) -> list[dict]:
        if not path.exists():
            raise FileNotFoundError(f"Fixture file not found: {path}")

        text = path.read_text()
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            data = json.loads(text)
            return [data] if isinstance(data, dict) else data
