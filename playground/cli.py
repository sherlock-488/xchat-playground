"""CLI entry point for xchat-playground."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Load .env as early as possible so all commands see env vars
load_dotenv()

app = typer.Typer(
    name="playground",
    help="xchat-playground — local simulator & replay lab for XChat bots",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# ── Sub-apps ──────────────────────────────────────────────────────────────────

simulate_app = typer.Typer(help="Generate XChat event fixtures")
webhook_app = typer.Typer(help="Webhook CRC & signature tools")
replay_app = typer.Typer(help="Record, replay, and diff events")
crypto_app = typer.Typer(help="Decrypt XChat messages (stub or real-key)")
repro_app = typer.Typer(help="Run known-bug repro packs")

app.add_typer(simulate_app, name="simulate")
app.add_typer(webhook_app, name="webhook")
app.add_typer(replay_app, name="replay")
app.add_typer(crypto_app, name="crypto")
app.add_typer(repro_app, name="repro")


# ── serve ─────────────────────────────────────────────────────────────────────


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(7474, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
):
    """Start the local webhook server + web UI at http://localhost:7474"""
    import uvicorn

    console.print(
        Panel(
            f"[bold green]xchat-playground[/] server starting\n"
            f"  Web UI  → [link]http://{host}:{port}/ui[/link]\n"
            f"  Webhook → [link]http://{host}:{port}/webhook[/link]\n"
            f"  API     → [link]http://{host}:{port}/docs[/link]\n\n"
            "[dim]Tip: expose publicly with: npx cloudflared tunnel --url "
            f"http://localhost:{port}[/dim]",
            title="🧪 xchat-playground",
            border_style="green",
        )
    )

    uvicorn.run(
        "playground.webhook.server:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
        log_level="info",
    )


# ── doctor ────────────────────────────────────────────────────────────────────


@app.command()
def doctor():
    """Check your local environment is ready for XChat bot development."""
    import shutil
    import subprocess

    checks = []

    # Python version
    v = sys.version_info
    ok = v >= (3, 10)
    checks.append(("Python ≥ 3.10", ok, f"{v.major}.{v.minor}.{v.micro}"))

    # uv
    uv_path = shutil.which("uv")
    checks.append(("uv installed", bool(uv_path), uv_path or "not found"))

    # xurl
    xurl_path = shutil.which("xurl")
    checks.append(
        (
            "xurl installed",
            bool(xurl_path),
            xurl_path or "not found — see https://github.com/xdevplatform/xurl",
        )
    )

    # .env file
    env_exists = Path(".env").exists()
    checks.append(
        (
            ".env file",
            env_exists,
            ".env found" if env_exists else "missing — copy .env.example",
        )
    )

    # state.json (xchat-bot-python key material)
    state_exists = Path("state.json").exists()
    checks.append(
        (
            "state.json",
            state_exists,
            "found" if state_exists else "not present (needed for real-key crypto)",
        )
    )

    # state.json not committed
    if state_exists:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "state.json"],
            capture_output=True,
        )
        ignored = result.returncode == 0
        checks.append(
            (
                "state.json in .gitignore",
                ignored,
                "✓ safe" if ignored else "⚠️  ADD state.json TO .gitignore NOW",
            )
        )

    table = Table(title="Environment Check", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    all_ok = True
    for name, ok, detail in checks:
        status = "[green]✓ pass[/]" if ok else "[red]✗ fail[/]"
        if not ok:
            all_ok = False
        table.add_row(name, status, str(detail))

    console.print(table)

    if all_ok:
        console.print("\n[bold green]All checks passed! You're ready to build.[/]")
    else:
        console.print(
            "\n[bold yellow]Some checks failed. Fix the issues above before running live tests.[/]"
        )
        raise typer.Exit(1)


# ── simulate commands ─────────────────────────────────────────────────────────


@simulate_app.command("chat-received")
def simulate_chat_received(
    sender_id: str = typer.Option("111222333", help="Sender user ID"),
    recipient_id: str = typer.Option("444555666", help="Recipient user ID"),
    conversation_id: str = typer.Option(
        None, help="Conversation ID (auto-generated if omitted)"
    ),
    encrypted: bool = typer.Option(True, help="Include stub encrypted payload"),
    schema: str = typer.Option(
        "demo",
        help=(
            "Fixture schema: 'demo' (flat, for teaching) or 'official' "
            "(XAA envelope, mirrors xchat-bot-python — chat.received only)"
        ),
    ),
    strict_official: bool = typer.Option(
        False,
        "--strict-official",
        help="With --schema official: strip _schema/_note metadata for a clean XAA envelope",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save to file"),
    pretty: bool = typer.Option(True, help="Pretty-print JSON"),
):
    """Generate a chat.received event fixture.

    Use --schema official to produce the real X Activity API envelope:
      {"data": {"event_type": "chat.received", "payload": {...}}}

    Add --strict-official to strip simulator metadata (_schema, _note) for a
    clean envelope suitable for contract testing or feeding to other tools.
    """
    from playground.simulator.events import EventSimulator, EventType

    sim = EventSimulator()
    event = sim.generate(
        EventType.CHAT_RECEIVED,
        sender_id=sender_id,
        recipient_id=recipient_id,
        conversation_id=conversation_id,
        encrypted=encrypted,
        schema=schema,
        strict=strict_official,
    )
    _output_json(event, output, pretty)


@simulate_app.command("chat-sent")
def simulate_chat_sent(
    sender_id: str = typer.Option("444555666", help="Sender user ID"),
    recipient_id: str = typer.Option("111222333", help="Recipient user ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save to file"),
):
    """Generate a chat.sent event fixture."""
    from playground.simulator.events import EventSimulator, EventType

    sim = EventSimulator()
    event = sim.generate(
        EventType.CHAT_SENT, sender_id=sender_id, recipient_id=recipient_id
    )
    _output_json(event, output, pretty=True)


@simulate_app.command("conversation-join")
def simulate_conversation_join(
    user_id: str = typer.Option("111222333", help="User ID joining"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save to file"),
):
    """Generate a chat.conversation_join event fixture."""
    from playground.simulator.events import EventSimulator, EventType

    sim = EventSimulator()
    event = sim.generate(EventType.CONVERSATION_JOIN, user_id=user_id)
    _output_json(event, output, pretty=True)


@simulate_app.command("batch")
def simulate_batch(
    count: int = typer.Option(5, help="Number of events to generate"),
    event_type: str = typer.Option("chat.received", help="Event type"),
    schema: str = typer.Option(
        "demo",
        help=(
            "Fixture schema: 'demo' (flat) or 'official' "
            "(XAA envelope, chat.received only)"
        ),
    ),
    output: Path = typer.Option(Path("fixtures/batch.jsonl"), "--output", "-o"),
):
    """Generate a batch of events and save as JSONL."""
    from playground.simulator.events import EventSimulator, EventType

    type_map = {
        "chat.received": EventType.CHAT_RECEIVED,
        "chat.sent": EventType.CHAT_SENT,
        "chat.conversation_join": EventType.CONVERSATION_JOIN,
    }
    et = type_map.get(event_type, EventType.CHAT_RECEIVED)
    sim = EventSimulator()

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("w") as f:
            for _ in range(count):
                event = sim.generate(et, schema=schema)
                f.write(json.dumps(event) + "\n")
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from e

    console.print(
        f"[green]✓[/] Wrote {count} {schema}-schema events to [bold]{output}[/]"
    )


# ── webhook commands ──────────────────────────────────────────────────────────


@webhook_app.command("crc")
def webhook_crc(
    crc_token: str = typer.Argument(..., help="CRC token from X"),
    consumer_secret: str = typer.Option(
        None, envvar="CONSUMER_SECRET", help="Your app's consumer secret"
    ),
):
    """Compute the CRC challenge response for a given token."""
    from playground.webhook.crc import compute_crc_response

    if not consumer_secret:
        console.print(
            "[red]Error:[/] CONSUMER_SECRET not set. Pass --consumer-secret or set env var."
        )
        raise typer.Exit(1)

    response = compute_crc_response(crc_token, consumer_secret)
    console.print(
        Panel(
            f"[bold]CRC Token:[/]    {crc_token}\n"
            f"[bold]Response:[/]     {response['response_token']}\n\n"
            "[dim]Return this JSON body to X:[/dim]\n"
            f"[green]{json.dumps(response, indent=2)}[/green]",
            title="CRC Challenge Response",
        )
    )


@webhook_app.command("verify")
def webhook_verify(
    payload: str = typer.Argument(..., help="Raw request body"),
    signature: str = typer.Argument(
        ...,
        help="x-twitter-webhooks-signature header value (or legacy X-Signature-256)",
    ),
    consumer_secret: str = typer.Option(None, envvar="CONSUMER_SECRET"),
):
    """Verify a webhook payload signature."""
    from playground.webhook.signature import verify_signature

    if not consumer_secret:
        console.print(
            "[red]Error:[/] CONSUMER_SECRET not set. Pass --consumer-secret or set in .env"
        )
        raise typer.Exit(1)

    valid = verify_signature(payload.encode(), signature, consumer_secret)
    if valid:
        console.print("[bold green]✓ Signature valid[/]")
    else:
        console.print("[bold red]✗ Signature INVALID[/]")
        raise typer.Exit(1)


# ── replay commands ───────────────────────────────────────────────────────────


@replay_app.command("run")
def replay_run(
    fixture: Path = typer.Argument(..., help="Path to event fixture JSON or JSONL"),
    target: str = typer.Option(
        "http://127.0.0.1:7474/webhook", help="Handler URL to replay against"
    ),
    delay: float = typer.Option(0.1, help="Delay between events (seconds)"),
):
    """Replay a fixture file against a local webhook handler."""
    import asyncio

    from playground.replay.replayer import EventReplayer

    async def _run():
        replayer = EventReplayer(target_url=target)
        results = await replayer.replay_file(fixture, delay=delay)
        for r in results:
            status = "[green]✓[/]" if r["success"] else "[red]✗[/]"
            console.print(f"  {status} {r['event_type']} → HTTP {r['status_code']}")
        console.print(f"\n[bold]Total: {len(results)} events replayed[/]")

    asyncio.run(_run())


@replay_app.command("diff")
def replay_diff(
    fixture: Path = typer.Argument(..., help="Path to event fixture"),
    baseline_url: str = typer.Option(..., help="Baseline handler URL"),
    candidate_url: str = typer.Option(..., help="Candidate handler URL"),
):
    """Diff responses from two handlers for the same events."""
    import asyncio

    from playground.replay.diff import diff_two_handlers

    async def _run():
        results = await diff_two_handlers(fixture, baseline_url, candidate_url)
        for r in results:
            if r["identical"]:
                console.print(f"  [green]=[/] {r['event_id']} — responses identical")
            else:
                console.print(f"  [yellow]≠[/] {r['event_id']} — DIFF:")
                console.print(Syntax(r["diff"], "diff", theme="monokai"))

    asyncio.run(_run())


@replay_app.command("export")
def replay_export(
    server: str = typer.Option("http://127.0.0.1:7474", help="playground server URL"),
    output: Path = typer.Option(Path("recordings/export.jsonl"), "--output", "-o"),
    limit: int = typer.Option(200, help="Max events to export"),
    no_scrub: bool = typer.Option(
        False, "--no-scrub", help="Disable PII scrubbing (use with caution)"
    ),
    include_demo: bool = typer.Option(
        False, "--include-demo", help="Include injected demo events"
    ),
):
    """Export events from the running playground server as a scrubbed JSONL file.

    The exported file can be replayed with: playground replay run <file>

    PII scrubbing is ON by default — real user IDs are replaced with FAKE_USER_xxx.
    """
    import httpx

    scrub = not no_scrub
    skip_demo = not include_demo
    url = f"{server}/api/events/export?limit={limit}&scrub_pii={str(scrub).lower()}&skip_demo={str(skip_demo).lower()}"

    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
    except httpx.ConnectError as err:
        console.print(
            f"[red]Error:[/] Cannot connect to {server}. Is the server running?"
        )
        console.print("[dim]Start it with: playground serve[/dim]")
        raise typer.Exit(1) from err
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error:[/] Server returned {e.response.status_code}")
        raise typer.Exit(1) from e

    content = r.text
    event_count = len([line for line in content.splitlines() if line.strip()])

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)

    console.print(
        Panel(
            f"[bold green]✓ Exported {event_count} events[/]\n\n"
            f"[bold]Output:[/]  {output}\n"
            f"[bold]Scrubbed:[/] {'yes — real IDs replaced with FAKE_USER_xxx' if scrub else '[yellow]NO — real IDs preserved[/yellow]'}\n\n"
            "[dim]Replay with: playground replay run {output}[/dim]",
            title="Replay Export",
            border_style="green",
        )
    )


# ── crypto commands ───────────────────────────────────────────────────────────


@crypto_app.command("stub")
def crypto_stub(
    payload: str = typer.Argument(
        ..., help="Encrypted payload (or 'STUB_*' fixture value)"
    ),
):
    """Decrypt using stub mode (returns plaintext fixture, no real keys needed)."""
    from playground.crypto.stub import StubCrypto

    result = StubCrypto().decrypt(payload)
    console.print(
        Panel(
            f"[bold]Input:[/]  {payload}\n"
            f"[bold]Output:[/] [green]{result['plaintext']}[/green]\n\n"
            "[dim]Mode: STUB — no real keys used[/dim]",
            title="Crypto Sandbox (Stub Mode)",
        )
    )


@crypto_app.command("real")
def crypto_real(
    encoded_event: str = typer.Argument(
        ..., help="data.payload.encoded_event value from XChat Activity Stream event"
    ),
    enc_key: str = typer.Option(
        None,
        "--enc-key",
        help="data.payload.encrypted_conversation_key (optional)",
    ),
    state_file: Path = typer.Option(
        Path("state.json"), help="Path to state.json from xchat-bot-python"
    ),
):
    """Decrypt using real private keys from state.json."""
    from playground.crypto.real import RealCrypto

    if not state_file.exists():
        console.print(
            f"[red]Error:[/] {state_file} not found. Run xchat-bot-python login first."
        )
        raise typer.Exit(1)

    crypto = RealCrypto(state_file)
    result = crypto.decrypt(encoded_event, enc_key)
    console.print(
        Panel(
            f"[bold]Plaintext:[/] [green]{result['plaintext']}[/green]\n"
            f"[bold]Key used:[/]  {result['key_id']}",
            title="Crypto Sandbox (Real-Key Mode)",
        )
    )


# ── repro commands ────────────────────────────────────────────────────────────


@repro_app.command("list")
def repro_list():
    """List all available repro packs."""
    from playground.repro.registry import list_packs

    packs = list_packs()
    table = Table(
        title="Available Repro Packs", show_header=True, header_style="bold cyan"
    )
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Forum Thread", style="dim")

    for p in packs:
        table.add_row(p["id"], p["title"], p.get("forum_url", "—"))

    console.print(table)


@repro_app.command("run")
def repro_run(
    pack_id: str = typer.Argument(
        ..., help="Repro pack ID (from 'playground repro list')"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run a repro pack to reproduce a known XChat API bug."""
    from playground.repro.registry import run_pack

    console.print(f"[bold]Running repro pack:[/] {pack_id}\n")
    result = run_pack(pack_id, verbose=verbose)

    if result["reproduced"]:
        console.print(
            Panel(
                f"[bold yellow]Bug reproduced![/]\n\n"
                f"[bold]Summary:[/] {result['summary']}\n\n"
                f"[bold]Workaround:[/]\n{result['workaround']}",
                title=f"Repro: {pack_id}",
                border_style="yellow",
            )
        )
    else:
        console.print(
            f"[green]Could not reproduce[/] — {result.get('reason', 'no details')}"
        )


@repro_app.command("check")
def repro_check(
    pack_id: str = typer.Argument(
        ..., help="Repro pack ID (from 'playground repro list')"
    ),
    webhook_url: str = typer.Option(
        None, "--webhook-url", "-u", help="Your webhook URL to validate"
    ),
):
    """Run the semi-automatic environment checker for a repro pack.

    Example: playground repro check chat-webhook-not-received --webhook-url https://yourbot.example.com/webhook
    """
    from playground.repro.registry import check_pack

    console.print(f"[bold]Checking environment for:[/] {pack_id}\n")
    try:
        kwargs = {}
        if webhook_url:
            kwargs["webhook_url"] = webhook_url
        result = check_pack(pack_id, **kwargs)
    except AttributeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from e
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from e

    table = Table(
        title=f"Environment Check: {pack_id}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    for item in result["checks"]:
        status = item["status"]
        if status == "pass":
            status_str = "[green]✓ pass[/]"
        elif status == "fail":
            status_str = "[red]✗ fail[/]"
        elif status == "warn":
            status_str = "[yellow]⚠ warn[/]"
        else:
            status_str = "[dim]– skip[/]"

        detail = item["detail"]
        if "fix" in item:
            detail += f"\n  [dim]Fix: {item['fix']}[/dim]"
        table.add_row(item["check"], status_str, detail)

    console.print(table)

    overall = result["overall"]
    if overall == "pass":
        console.print(f"\n[bold green]{result['summary']}[/]")
    elif overall == "fail":
        console.print(f"\n[bold red]{result['summary']}[/]")
        raise typer.Exit(1)
    else:
        console.print(f"\n[bold yellow]{result['summary']}[/]")


# ── helpers ───────────────────────────────────────────────────────────────────


def _output_json(data: dict, output: Path | None, pretty: bool = True) -> None:
    text = json.dumps(data, indent=2 if pretty else None)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
        console.print(f"[green]✓[/] Saved to [bold]{output}[/]")
    else:
        console.print(Syntax(text, "json", theme="monokai"))


if __name__ == "__main__":
    app()
