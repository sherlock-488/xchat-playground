# Contributing to xchat-playground

Thank you for helping make XChat bot development easier! 🧪

## Ways to contribute

- **Add a Repro Pack** — found a new XChat API bug? Document it as a preset
- **Improve fixtures** — better example events, edge cases, error payloads
- **Fix a bug** — check the [issue tracker](../../issues)
- **Improve docs** — clearer explanations, more examples, translations
- **Add tests** — more coverage is always welcome

## Getting started (10 minutes)

```bash
# 1. Fork & clone
git clone https://github.com/sherlock-488/xchat-playground
cd xchat-playground

# 2. Install dependencies
pip install uv
uv sync --extra dev

# 3. Run tests to verify everything works
uv run pytest

# 4. Start the server
uv run playground serve
```

## Development workflow

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --tb=short -v

# Lint
uv run ruff check playground/ tests/
uv run ruff format --check playground/ tests/

# Auto-fix lint issues
uv run ruff check --fix playground/ tests/
uv run ruff format playground/ tests/
```

## Adding a Repro Pack

Repro packs are the most valuable contribution. They document real bugs from the community.

1. Create `playground/repro/packs/your_issue_name.py`:

```python
class YourIssuePack:
    title = "Short description of the bug"
    description = "One sentence explaining what happens."
    forum_url = "https://devcommunity.x.com/..."  # link to forum thread if exists

    def run(self, verbose: bool = False) -> dict:
        return {
            "reproduced": True,
            "summary": "What the bug is",
            "workaround": "How to fix it",
            # Add verbose details if verbose=True
        }
```

2. Register it in `playground/repro/registry.py`:

```python
from playground.repro.packs.your_issue_name import YourIssuePack

class ReproRegistry:
    _packs = {
        # ... existing packs ...
        "your-issue-name": YourIssuePack,
    }
```

3. Add a test in `tests/` if possible.

4. Open a PR with title: `[repro] Add pack: your-issue-description`

## Pull request checklist

- [ ] Tests pass (`uv run pytest`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] New code has tests where practical
- [ ] `state.json` is NOT included in the PR
- [ ] No real user IDs or API keys in fixtures

## Issue labels

| Label | Meaning |
|-------|---------|
| `good first issue` | Great for new contributors |
| `repro-pack` | New bug repro pack needed |
| `simulator` | Event simulator improvements |
| `webhook` | CRC/signature/server issues |
| `replay` | Record/replay/diff improvements |
| `crypto` | Decryption sandbox |
| `docs` | Documentation improvements |
| `ci` | CI/CD improvements |

## Code style

- Python 3.10+ type hints encouraged
- `ruff` for linting and formatting (config in `pyproject.toml`)
- Docstrings on public functions
- Keep functions small and focused

## Questions?

Open a [discussion](../../discussions) or ask in the [X Developer Forum](https://devcommunity.x.com).
