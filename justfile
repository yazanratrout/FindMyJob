# FindMyJob task runner.  Run `just` to list recipes.
# Requires: https://github.com/casey/just  (brew install just)
# Every recipe runs inside the project virtualenv at ./.venv

set dotenv-load := true

venv := ".venv"
py   := venv + "/bin/python"
pip  := venv + "/bin/pip"

default:
    @just --list

# ---- Setup -------------------------------------------------------------------

# Create the virtualenv and install all dependencies (runtime + dev).
setup:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install --upgrade pip
    {{pip}} install -r requirements-dev.txt
    {{pip}} install -e .
    -[ "$(uname)" = "Darwin" ] && chflags -R nohidden {{venv}}   # see `just fix-venv`
    {{py}} -m findmyjob db upgrade
    {{py}} -m findmyjob db seed
    -{{py}} -m findmyjob models fetch
    cd frontend && npm install && npm run build
    {{py}} -m findmyjob doctor
    @echo "Setup complete. Run 'just start' (or 'just dev' + 'just frontend-dev')."

# Freeze the currently installed packages into requirements.lock
lock:
    {{pip}} freeze --exclude-editable > requirements.lock

# macOS: clear the "hidden" flag on .venv. Python 3.13's site.py silently skips
# .pth files marked hidden, which breaks the editable install (ModuleNotFoundError:
# findmyjob). Some macOS tools set that flag on dot-directories.
fix-venv:
    chflags -R nohidden {{venv}}
    {{py}} -c "import findmyjob; print('ok:', findmyjob.__file__)"

# ---- Run -------------------------------------------------------------------

# Production-ish: migrate, then serve the API + built UI (no reload, scheduler on).
start:
    {{py}} -m findmyjob db upgrade
    {{py}} -m uvicorn findmyjob.api.app:app --host ${APP_HOST:-127.0.0.1} --port ${APP_PORT:-8000}

# Dev API server with autoreload (serves the built frontend too, if present).
dev:
    {{py}} -m uvicorn findmyjob.api.app:app --reload --host ${APP_HOST:-127.0.0.1} --port ${APP_PORT:-8000}

# ---- Frontend ------------------------------------------------------------

frontend-install:
    cd frontend && npm install

# Vite dev server on :5173, proxying /api to the backend.
frontend-dev:
    cd frontend && npm run dev

# Type-check + build into frontend/dist (served by the API in production).
frontend-build:
    cd frontend && npm run build

# Run the full daily pipeline once, now.
run-pipeline *ARGS:
    {{py}} -m findmyjob pipeline run {{ARGS}}

# Open a Python REPL with the app context loaded.
shell:
    {{py}} -m findmyjob shell

# ---- Database -------------------------------------------------------------

db-upgrade:
    {{py}} -m findmyjob db upgrade

db-revision MESSAGE:
    {{py}} -m alembic revision --autogenerate -m "{{MESSAGE}}"

db-seed:
    {{py}} -m findmyjob db seed

db-reset:
    {{py}} -m findmyjob db reset

# ---- Quality ------------------------------------------------------------

# Fast tests only (skips end-to-end orchestrator integration tests).
test *ARGS:
    {{py}} -m pytest -m "not slow" {{ARGS}}

# The whole suite, including the slow integration tests.
test-all *ARGS:
    {{py}} -m pytest {{ARGS}}

cov:
    {{py}} -m pytest --cov --cov-report=term-missing

lint:
    {{py}} -m ruff check src tests
    {{py}} -m ruff format --check src tests

fmt:
    {{py}} -m ruff check --fix src tests
    {{py}} -m ruff format src tests

typecheck:
    {{py}} -m mypy

# Run everything CI would run (full test suite).
check: lint typecheck test-all

# ---- Diagnostics -------------------------------------------------------

doctor:
    {{py}} -m findmyjob doctor

schedule-status:
    {{py}} -m findmyjob schedule status

backup:
    {{py}} -m findmyjob maintenance backup

prune:
    {{py}} -m findmyjob maintenance prune

# Suggest score weights from your feedback (pass --apply to write them).
calibrate *ARGS:
    {{py}} -m findmyjob calibrate {{ARGS}}

# ---- macOS deployment ------------------------------------------------

# Install the launchd daily-fallback job (add `--server` to also keep the API up).
install-launchd *ARGS:
    bash deploy/install-launchd.sh {{ARGS}}

uninstall-launchd:
    -launchctl unload ~/Library/LaunchAgents/com.findmyjob.daily.plist
    -launchctl unload ~/Library/LaunchAgents/com.findmyjob.server.plist
    -rm -f ~/Library/LaunchAgents/com.findmyjob.daily.plist ~/Library/LaunchAgents/com.findmyjob.server.plist
    @echo "launchd jobs removed"
