"""Diff two webhook handler responses for the same event stream."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from playground.replay.replayer import EventReplayer


async def diff_two_handlers(
    fixture_path: Path,
    baseline_url: str,
    candidate_url: str,
    consumer_secret: str | None = None,
) -> list[dict]:
    """Send the same events to two handlers and diff their responses.

    Returns a list of dicts with keys:
      - event_id: identifier for the event
      - event_type: event type string
      - baseline_response: response from baseline handler
      - candidate_response: response from candidate handler
      - identical: bool
      - diff: unified diff string (empty if identical)
    """
    baseline = EventReplayer(baseline_url, consumer_secret)
    candidate = EventReplayer(candidate_url, consumer_secret)

    baseline_results = await baseline.replay_file(fixture_path, delay=0)
    candidate_results = await candidate.replay_file(fixture_path, delay=0)

    results = []
    for i, (b, c) in enumerate(zip(baseline_results, candidate_results, strict=False)):
        b_text = json.dumps(
            {"status": b["status_code"], "body": b["response_body"]},
            indent=2,
        )
        c_text = json.dumps(
            {"status": c["status_code"], "body": c["response_body"]},
            indent=2,
        )
        identical = b_text == c_text
        diff = ""
        if not identical:
            diff = "\n".join(
                difflib.unified_diff(
                    b_text.splitlines(),
                    c_text.splitlines(),
                    fromfile="baseline",
                    tofile="candidate",
                    lineterm="",
                )
            )
        results.append(
            {
                "event_id": f"event_{i}",
                "event_type": b["event_type"],
                "baseline_response": b,
                "candidate_response": c,
                "identical": identical,
                "diff": diff,
            }
        )
    return results


def diff_responses(response_a: dict, response_b: dict) -> str:
    """Simple unified diff between two response dicts."""
    a_text = json.dumps(response_a, indent=2)
    b_text = json.dumps(response_b, indent=2)
    return "\n".join(
        difflib.unified_diff(
            a_text.splitlines(),
            b_text.splitlines(),
            fromfile="a",
            tofile="b",
            lineterm="",
        )
    )
