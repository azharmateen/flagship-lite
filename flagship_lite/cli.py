"""CLI: flagship-lite init, list, toggle, eval, stale, serve."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click
import yaml

from .flags import Flag
from .loader import load_flags, save_flags, find_flags_file, FlagLoadError


SAMPLE_FLAGS = {
    "flags": [
        {
            "name": "new_checkout",
            "description": "New checkout flow with improved UX",
            "enabled": True,
            "rollout_percentage": 25.0,
            "environments": ["staging", "production"],
            "tags": ["frontend", "checkout"],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "name": "dark_mode",
            "description": "Enable dark mode toggle in settings",
            "enabled": True,
            "targeting_rules": [
                {"attribute": "email", "operator": "ends_with", "value": "@beta-testers.com"}
            ],
            "tags": ["frontend", "ui"],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "name": "legacy_api",
            "description": "Keep legacy API endpoints active",
            "enabled": False,
            "tags": ["backend", "deprecated"],
            "created_at": "2025-01-15T00:00:00",
            "updated_at": "2025-01-15T00:00:00",
        },
    ]
}


@click.group()
@click.version_option(version="0.1.0", prog_name="flagship-lite")
def cli():
    """Feature flags that live in your repo."""
    pass


@cli.command()
@click.option("--path", "-p", default="flags.yaml", help="Path for flags file")
def init(path):
    """Initialize a new flags.yaml file with example flags.

    Example: flagship-lite init
    """
    flags_path = Path(path)
    if flags_path.exists():
        click.secho(f"File already exists: {flags_path}", fg="yellow")
        if not click.confirm("Overwrite?"):
            return

    content = yaml.dump(SAMPLE_FLAGS, default_flow_style=False, sort_keys=False)
    flags_path.write_text(content, encoding="utf-8")
    click.secho(f"Created {flags_path} with {len(SAMPLE_FLAGS['flags'])} example flags", fg="green")


@cli.command("list")
@click.option("--file", "-f", "flags_file", default=None, help="Flags file path")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_flags(flags_file, as_json):
    """List all feature flags.

    Example: flagship-lite list
    """
    try:
        flags = load_flags(flags_file)
    except FlagLoadError as e:
        click.secho(str(e), fg="red")
        sys.exit(1)

    if as_json:
        import json
        click.echo(json.dumps([f.to_dict() for f in flags], indent=2))
        return

    if not flags:
        click.echo("No flags defined.")
        return

    for flag in flags:
        status = click.style("ON ", fg="green") if flag.enabled else click.style("OFF", fg="red")
        pct = f" ({flag.rollout_percentage}%)" if flag.rollout_percentage < 100 else ""
        envs = f" [{', '.join(flag.environments)}]" if flag.environments else ""
        rules = f" ({len(flag.targeting_rules)} rules)" if flag.targeting_rules else ""
        click.echo(f"  {status} {flag.name}{pct}{envs}{rules}")
        if flag.description:
            click.echo(f"       {flag.description}")


@cli.command()
@click.argument("flag_name")
@click.option("--file", "-f", "flags_file", default=None, help="Flags file path")
def toggle(flag_name, flags_file):
    """Toggle a flag on/off.

    Example: flagship-lite toggle new_checkout
    """
    try:
        flags = load_flags(flags_file)
    except FlagLoadError as e:
        click.secho(str(e), fg="red")
        sys.exit(1)

    target = None
    for f in flags:
        if f.name == flag_name:
            target = f
            break

    if target is None:
        click.secho(f"Flag '{flag_name}' not found", fg="red")
        sys.exit(1)

    target.enabled = not target.enabled
    target.updated_at = datetime.utcnow().isoformat()
    save_flags(flags, flags_file)

    status = "enabled" if target.enabled else "disabled"
    color = "green" if target.enabled else "red"
    click.secho(f"Flag '{flag_name}' is now {status}", fg=color)


@cli.command("eval")
@click.argument("flag_name")
@click.option("--user-id", "-u", default=None, help="User ID for evaluation")
@click.option("--email", "-e", default=None, help="User email")
@click.option("--env", "environment", default=None, help="Environment name")
@click.option("--file", "-f", "flags_file", default=None, help="Flags file path")
def eval_flag(flag_name, user_id, email, environment, flags_file):
    """Evaluate a flag for a given context.

    Example: flagship-lite eval new_checkout --user-id 123 --env production
    """
    try:
        flags = load_flags(flags_file)
    except FlagLoadError as e:
        click.secho(str(e), fg="red")
        sys.exit(1)

    from .evaluator import evaluate_flag
    context = {}
    if user_id:
        context["user_id"] = user_id
    if email:
        context["email"] = email
    if environment:
        context["environment"] = environment

    enabled, reason = evaluate_flag(flag_name, context, flags)

    if enabled:
        click.secho(f"ENABLED: {reason}", fg="green")
    else:
        click.secho(f"DISABLED: {reason}", fg="red")


@cli.command()
@click.option("--max-age", default=90, help="Max age in days before a flag is considered stale")
@click.option("--search-dir", "-d", default=".", help="Directory to search for code references")
@click.option("--file", "-f", "flags_file", default=None, help="Flags file path")
def stale(max_age, search_dir, flags_file):
    """Find stale flags that may be safe to remove.

    Example: flagship-lite stale --max-age 60
    """
    try:
        flags = load_flags(flags_file)
    except FlagLoadError as e:
        click.secho(str(e), fg="red")
        sys.exit(1)

    from .stale_detector import detect_stale
    reports = detect_stale(flags, max_age_days=max_age, search_dir=search_dir)

    if not reports:
        click.secho("No stale flags detected!", fg="green")
        return

    click.secho(f"\nFound {len(reports)} stale flag(s):\n", fg="yellow")
    for report in reports:
        color = {"high": "red", "medium": "yellow", "low": "blue"}.get(report.severity, "white")
        click.secho(f"  [{report.severity.upper()}] ", fg=color, nl=False)
        click.echo(f"{report.flag_name}: {report.reason}")
        if report.details:
            click.echo(f"           {report.details}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Server host")
@click.option("--port", "-p", default=8100, help="Server port")
@click.option("--file", "-f", "flags_file", default="flags.yaml", help="Flags file path")
def serve(host, port, flags_file):
    """Start the flag evaluation HTTP server.

    Example: flagship-lite serve --port 8100
    """
    from .server import create_app
    import uvicorn

    click.echo(f"Starting flagship-lite server at http://{host}:{port}")
    click.echo(f"  Flags file: {flags_file}")
    click.echo(f"  Docs: http://{host}:{port}/docs")

    app = create_app(flags_file)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
