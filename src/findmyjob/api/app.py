"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from findmyjob import __version__
from findmyjob.config import REPO_ROOT, get_settings
from findmyjob.db import create_all, session_scope
from findmyjob.db_migrate import upgrade_to_head
from findmyjob.logging import configure_logging, get_logger
from findmyjob.services.bootstrap import seed

log = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    settings.ensure_dirs()
    if settings.app_env == "test":
        create_all()
    else:
        upgrade_to_head()
    with session_scope() as session:
        seed(session)

    scheduler = None
    if settings.app_env != "test" and not settings.disable_scheduler:
        from findmyjob.scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.start()
        log.info("api.scheduler_started", next_fire=str(scheduler.next_run_time()))

    log.info("api.startup", env=settings.app_env)
    yield
    if scheduler is not None:
        scheduler.shutdown()
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FindMyJob",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=settings.is_production,
    )

    if not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    from findmyjob.api.deps import require_auth
    from findmyjob.api.routes import (
        auth,
        companies,
        costs,
        documents,
        health,
        profile,
        runs,
    )
    from findmyjob.api.routes import settings as settings_routes

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")

    guarded = [Depends(require_auth)]
    app.include_router(documents.router, prefix="/api", dependencies=guarded)
    app.include_router(profile.router, prefix="/api", dependencies=guarded)
    app.include_router(settings_routes.router, prefix="/api", dependencies=guarded)
    app.include_router(companies.router, prefix="/api", dependencies=guarded)
    app.include_router(runs.router, prefix="/api", dependencies=guarded)
    app.include_router(costs.router, prefix="/api", dependencies=guarded)

    frontend_dist = REPO_ROOT / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
