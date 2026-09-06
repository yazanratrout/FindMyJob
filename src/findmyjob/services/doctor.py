"""``findmyjob doctor`` — sanity-check the installation."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from sqlalchemy import text

from findmyjob.config import REPO_ROOT, get_settings
from findmyjob.db import get_engine


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    #: a failed warn-check prints WARN and does not fail `doctor`
    warn: bool = False


def _python_version() -> Check:
    v = sys.version_info
    return Check("python >= 3.12", (v.major, v.minor) >= (3, 12), f"{v.major}.{v.minor}.{v.micro}")


def _node() -> Check:
    node = shutil.which("node")
    return Check("node available", bool(node), node or "needed to build the web UI", warn=True)


def _env_file() -> Check:
    path = REPO_ROOT / ".env"
    return Check(
        ".env present",
        path.exists(),
        str(path) if path.exists() else "copy .env.example to .env",
    )


def _data_dirs() -> Check:
    settings = get_settings()
    try:
        settings.ensure_dirs()
        probe = settings.data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return Check("data dir writable", True, str(settings.data_dir))
    except OSError as exc:
        return Check("data dir writable", False, str(exc))


def _database() -> Check:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return Check("database reachable", True, get_settings().database_url)
    except Exception as exc:
        return Check("database reachable", False, str(exc))


def _migrations() -> Check:
    try:
        import logging

        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        from findmyjob.db_migrate import alembic_config

        logging.getLogger("alembic").setLevel(logging.WARNING)

        cfg = alembic_config()
        head = ScriptDirectory.from_config(cfg).get_current_head()
        with get_engine().connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        at_head = current == head
        detail = str(head) if at_head else f"current={current} head={head} — run `just db-upgrade`"
        return Check("migrations at head", at_head, detail)
    except Exception as exc:
        return Check("migrations at head", False, str(exc))


def _anthropic_key() -> Check:
    settings = get_settings()
    if settings.llm_offline:
        return Check("LLM configured", True, "LLM_OFFLINE=true - using canned responses")
    if settings.llm_provider == "openai":
        ok = bool(settings.llm_openai_base_url)
        detail = (
            f"OpenAI-compatible: {settings.llm_openai_base_url}"
            if ok
            else "LLM_PROVIDER=openai but LLM_OPENAI_BASE_URL is not set"
        )
        return Check("LLM configured", ok, detail)
    key = settings.anthropic_api_key
    return Check("LLM configured", bool(key), "ANTHROPIC_API_KEY - required for analysis + letters")


def _frontend_built() -> Check:
    index = REPO_ROOT / "frontend" / "dist" / "index.html"
    return Check(
        "web UI built",
        index.exists(),
        str(index.parent) if index.exists() else "run `just frontend-build`",
        warn=True,
    )


def _embedding_model() -> Check:
    models_dir = get_settings().models_dir
    cached = models_dir.exists() and any(models_dir.iterdir())
    return Check(
        "embedding model cached",
        cached,
        str(models_dir)
        if cached
        else "run `findmyjob models fetch` (dedup will otherwise download it)",
        warn=True,
    )


def _company_seed() -> Check:
    try:
        from findmyjob.services.bootstrap import _load_company_seed

        n = len(_load_company_seed())
        return Check("company seed loads", n > 0, f"{n} companies")
    except Exception as exc:
        return Check("company seed loads", False, str(exc))


def _job_source_creds() -> Check:
    s = get_settings()
    configured = [
        name
        for name, present in {
            "ba": True,  # public API key, no registration
            "adzuna": bool(s.adzuna_app_id and s.adzuna_app_key),
            "themuse": bool(s.themuse_api_key),
        }.items()
        if present
    ]
    return Check(
        "job sources reachable",
        True,
        f"keyed: {', '.join(configured)} (+ arbeitnow, ATS need no key)",
        warn=True,
    )


def run_doctor() -> bool:
    checks = [
        _python_version(),
        _node(),
        _env_file(),
        _data_dirs(),
        _database(),
        _migrations(),
        _anthropic_key(),
        _frontend_built(),
        _embedding_model(),
        _company_seed(),
        _job_source_creds(),
    ]
    width = max(len(c.name) for c in checks)
    failed = False
    for c in checks:
        if c.ok:
            mark = "PASS"
        elif c.warn:
            mark = "WARN"
        else:
            mark = "FAIL"
            failed = True
        print(f"  [{mark}] {c.name:<{width}}  {c.detail}")
    print("\nAll checks passed." if not failed else "\nSome checks failed (see above).")
    return not failed
