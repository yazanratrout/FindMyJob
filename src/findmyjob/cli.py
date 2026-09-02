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


# ---------------------------------------------------------------------- schedule
def cmd_schedule_status(_args: argparse.Namespace) -> int:
    from findmyjob.db import session_scope
    from findmyjob.scheduler import next_fire_time
    from findmyjob.services.settings import get_app_settings

    with session_scope() as session:
        settings = get_app_settings(session)
        run_time, run_tz = settings.run_time, settings.run_timezone
    nxt = next_fire_time(run_time, run_tz)
    print(f"Daily run:   {run_time} {run_tz}")
    print(f"Next fire:   {nxt.isoformat() if nxt else 'n/a'}")
    print("Note: the in-process scheduler runs only while the API server is up.")
    return 0


# ------------------------------------------------------------------- maintenance
def cmd_maintenance_backup(_args: argparse.Namespace) -> int:
    from findmyjob.services.backup import backup

    path = backup()
    print(f"Backup written: {path}")
    return 0


def cmd_maintenance_prune(_args: argparse.Namespace) -> int:
    from findmyjob.db import session_scope
    from findmyjob.services.retention import prune

    with session_scope() as session:
        report = prune(session)
    print(f"Pruned {report.pruned} job(s).")
    return 0


# ---------------------------------------------------------------------- models
def cmd_models_fetch(_args: argparse.Namespace) -> int:
    from findmyjob.services.embeddings import get_embedder

    embedder = get_embedder()
    if embedder is None:
        print("Could not load the embedding model (offline?). Dedup will retry later.")
        return 1
    print(f"Embedding model ready: {embedder.model_version} ({embedder.dim} dims)")
    return 0


# --------------------------------------------------------------------- calibrate
def cmd_calibrate(args: argparse.Namespace) -> int:
    from findmyjob.db import session_scope
    from findmyjob.services.calibration import apply_report, build_report

    with session_scope() as session:
        report = build_report(session)
        print(
            f"Labelled jobs: {report.n_labeled} "
            f"({report.n_positive} positive / {report.n_negative} negative)"
        )
        if not report.ready:
            print(report.reason)
            return 0
        print(f"\n{'component':<18}{'corr':>8}{'weight':>10}{'suggested':>12}")
        for c in report.components:
            print(
                f"{c.name:<18}{c.correlation:>8.2f}"
                f"{c.current_weight:>10.1f}{c.suggested_weight:>12.1f}"
            )
        if report.judge_correlation is not None:
            print(f"\njudge score correlation: {report.judge_correlation:.2f}")
        print(
            f"blend_soft_ratio: {report.current_blend_soft_ratio} "
            f"-> {report.suggested_blend_soft_ratio}"
        )
        if args.apply:
            apply_report(session)
            print("\nApplied suggested weights to settings.")
        else:
            print("\nRe-run with --apply to write these weights to settings.")
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

    schedule = sub.add_parser("schedule", help="scheduling info").add_subparsers(
        dest="schedule_command", required=True
    )
    schedule.add_parser("status", help="show the configured daily run + next fire").set_defaults(
        func=cmd_schedule_status
    )

    maint = sub.add_parser("maintenance", help="database maintenance").add_subparsers(
        dest="maintenance_command", required=True
    )
    maint.add_parser("backup", help="write a SQLite backup").set_defaults(
        func=cmd_maintenance_backup
    )
    maint.add_parser("prune", help="delete old archived unreferenced jobs").set_defaults(
        func=cmd_maintenance_prune
    )

    models = sub.add_parser("models", help="local model management").add_subparsers(
        dest="models_command", required=True
    )
    models.add_parser("fetch", help="download the embedding model now").set_defaults(
        func=cmd_models_fetch
    )

    calibrate = sub.add_parser("calibrate", help="suggest score weights from your feedback")
    calibrate.add_argument("--apply", action="store_true", help="write the suggested weights")
    calibrate.set_defaults(func=cmd_calibrate)

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
