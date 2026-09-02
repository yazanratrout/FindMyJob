"""Command-line entry point: ``python -m findmyjob ...``"""

from __future__ import annotations

import argparse
import asyncio
import code
import sys

from findmyjob import __version__
from findmyjob.config import get_settings
from findmyjob.logging import configure_logging, get_logger

log = get_logger("cli")


# --------------------------------------------------------------------------- db
def cmd_db_upgrade(_args: argparse.Namespace) -> int:
    from findmyjob.db_migrate import upgrade_to_head

    upgrade_to_head()
    print("Database is at head.")
    return 0


def cmd_db_seed(_args: argparse.Namespace) -> int:
    from findmyjob.db import session_scope
    from findmyjob.db_migrate import upgrade_to_head
    from findmyjob.services.bootstrap import seed

    upgrade_to_head()  # ensure schema exists first
    with session_scope() as session:
        report = seed(session)
    print(
        f"Seed complete: settings_created={report.settings_created} "
        f"profile_created={report.profile_created} "
        f"companies_added={report.companies_added} companies_updated={report.companies_updated}"
    )
    return 0


def cmd_db_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        confirm = input("This DROPS ALL DATA. Type 'reset' to continue: ")
        if confirm.strip() != "reset":
            print("Aborted.")
            return 1
    from findmyjob.db import session_scope
    from findmyjob.services.bootstrap import reset_database

    reset_database(session_scope)
    print("Database reset.")
    return 0


# ---------------------------------------------------------------------- pipeline
def cmd_pipeline_run(args: argparse.Namespace) -> int:
    from findmyjob.models.enums import RunTrigger
    from findmyjob.pipelines.registry import build_default_orchestrator

    orchestrator = build_default_orchestrator(fetch_only=args.fetch_only, no_llm=args.no_llm)
    trigger = RunTrigger(args.trigger)
    run_id = asyncio.run(orchestrator.execute(trigger=trigger))
    print(f"Run {run_id} finished ({', '.join(orchestrator.pipeline_names)}).")
    return 0


def cmd_pipeline_list(_args: argparse.Namespace) -> int:
    from findmyjob.pipelines.registry import default_pipelines

    pipelines = default_pipelines()
    if not pipelines:
        print("No pipelines registered yet.")
        return 0
    for i, p in enumerate(pipelines):
        flag = " (critical)" if p.critical else ""
        print(f"{i:>2}. {p.name}{flag}")
    return 0


# ------------------------------------------------------------------------ doctor
def cmd_doctor(_args: argparse.Namespace) -> int:
    from findmyjob.services.doctor import run_doctor

    ok = run_doctor()
    return 0 if ok else 1


# ------------------------------------------------------------------------- shell
def cmd_shell(_args: argparse.Namespace) -> int:
    from findmyjob import models
    from findmyjob.db import session_scope

    banner = "FindMyJob shell. Available: models, session_scope, get_settings"
    code.interact(
        banner=banner,
        local={"models": models, "session_scope": session_scope, "get_settings": get_settings},
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="findmyjob", description="FindMyJob CLI")
    parser.add_argument("--version", action="version", version=f"findmyjob {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    db = sub.add_parser("db", help="database management").add_subparsers(
        dest="db_command", required=True
    )
    db.add_parser("upgrade", help="apply migrations").set_defaults(func=cmd_db_upgrade)
    db.add_parser("seed", help="create tables and seed defaults").set_defaults(func=cmd_db_seed)
    reset = db.add_parser("reset", help="DROP everything and re-seed")
    reset.add_argument("--yes", action="store_true", help="skip confirmation")
    reset.set_defaults(func=cmd_db_reset)

    pipe = sub.add_parser("pipeline", help="run the daily pipeline").add_subparsers(
        dest="pipeline_command", required=True
    )
    run = pipe.add_parser("run", help="run the full pipeline once")
    run.add_argument("--trigger", choices=["manual", "schedule"], default="manual")
    run.add_argument("--fetch-only", action="store_true", help="only ingest jobs")
    run.add_argument("--no-llm", action="store_true", help="skip analyze + judge")
    run.set_defaults(func=cmd_pipeline_run)
    pipe.add_parser("list", help="list registered pipelines").set_defaults(func=cmd_pipeline_list)

    sub.add_parser("doctor", help="check the installation").set_defaults(func=cmd_doctor)
    sub.add_parser("shell", help="interactive Python shell").set_defaults(func=cmd_shell)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except Exception:
        log.exception("cli.command_failed", command=getattr(args, "command", None))
        return 1
