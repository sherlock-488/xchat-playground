# Replay Lab

Record real events, scrub PII, and replay them against your handler.

## Why replay?

- Reproduce bugs without waiting for real events
- Test your handler against edge cases
- Share reproducible bug reports without exposing user data
- A/B test two versions of your handler on the same event stream

## Recording events

```python
from playground.replay.recorder import EventRecorder
from pathlib import Path

recorder = EventRecorder(
    output_path=Path("recordings/session.jsonl"),
    scrub_pii=True,  # Replace real user IDs with FAKE_USER_001, etc.
)

# In your webhook handler:
async def handle_event(event: dict):
    recorder.record(event)
    # ... your existing logic

# Save at the end of your session:
recorder.save()
```

## Replaying fixtures

```bash
# Replay a fixture file against your handler
uv run playground replay run recordings/session.jsonl \
  --target http://127.0.0.1:8080/webhook

# Replay with delay between events (simulate real timing)
uv run playground replay run recordings/session.jsonl --delay 0.5
```

## Diffing two handlers

```bash
# Compare old vs new handler on the same events
uv run playground replay diff recordings/session.jsonl \
  --baseline-url http://127.0.0.1:8080/webhook \
  --candidate-url http://127.0.0.1:8081/webhook
```

## PII scrubbing

The recorder automatically replaces:
- `sender_id`, `recipient_id`, `for_user_id`, `participant_ids` → `FAKE_USER_001`, etc.
- Bearer tokens in strings
- Long numeric IDs (likely real user IDs)

IDs are replaced **consistently**: the same real ID always maps to the same fake ID within a session.

## Fixture formats

- `.json` — single event dict
- `.jsonl` — one event per line (batch)

Generate fixtures without recording real events:

```bash
uv run playground simulate batch --count 50 --output fixtures/batch.jsonl
```
