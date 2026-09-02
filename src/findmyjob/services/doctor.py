"""``findmyjob doctor`` — sanity-check the installation."""

from __future__ import annotations

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


def _python_version() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 12)
    return Check("python >= 3.12", ok, f"{v.major}.{v.minor}.{v.micro}")


def _env_file() -> Check:
    path = REPO_ROOT / ".env"
    if path.exists():
        return Check(".env present", True, str(path))
    return Check(".env present", False, "copy .env.example to .env")


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


def _anthropic_key() -> Check:
    key = get_settings().anthropic_api_key
    return Check("ANTHROPIC_API_KEY set", bool(key), "required for analysis + cover letters")


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
            "ba": bool(s.ba_api_client_id and s.ba_api_client_secret),
            "adzuna": bool(s.adzuna_app_id and s.adzuna_app_key),
            "themuse": bool(s.themuse_api_key),
        }.items()
        if present
    ]
    # arbeitnow + public ATS endpoints need no credentials, so we're never at zero.
    return Check(
        "job source credentials",
        True,
        f"keyed: {', '.join(configured) or 'none'} (+ arbeitnow, ATS need no key)",
    )


def run_doctor() -> bool:
    checks = [
        _python_version(),
        _env_file(),
        _data_dirs(),
        _database(),
        _anthropic_key(),
        _company_seed(),
        _job_source_creds(),
    ]
    width = max(len(c.name) for c in checks)
    all_ok = True
    for c in checks:
        mark = "PASS" if c.ok else "FAIL"
        if not c.ok:
            all_ok = False
        print(f"  [{mark}] {c.name:<{width}}  {c.detail}")
    print("\nAll checks passed." if all_ok else "\nSome checks failed (see above).")
    return all_ok
