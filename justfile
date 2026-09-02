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
    {{py}} -m findmyjob db upgrade
    {{py}} -m findmyjob db seed
    @echo "Setup complete. Run 'just dev' to start the API."

# Freeze the currently installed packages into requirements.lock
lock:
    {{pip}} freeze --exclude-editable > requirements.lock

# ---- Run -------------------------------------------------------------------

# Start the API server (serves the built frontend too, if present).
dev:
    {{py}} -m uvicorn findmyjob.api.app:app --reload --host ${APP_HOST:-127.0.0.1} --port ${APP_PORT:-8000}

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

test *ARGS:
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

# Run everything CI would run.
check: lint typecheck test

# ---- Diagnostics -------------------------------------------------------

doctor:
    {{py}} -m findmyjob doctor

schedule-status:
    {{py}} -m findmyjob schedule status

# ---- macOS deployment ------------------------------------------------

# Install the launchd daily-fallback job (add `--server` to also keep the API up).
install-launchd *ARGS:
    bash deploy/install-launchd.sh {{ARGS}}

uninstall-launchd:
    -launchctl unload ~/Library/LaunchAgents/com.findmyjob.daily.plist
    -launchctl unload ~/Library/LaunchAgents/com.findmyjob.server.plist
    -rm -f ~/Library/LaunchAgents/com.findmyjob.daily.plist ~/Library/LaunchAgents/com.findmyjob.server.plist
    @echo "launchd jobs removed"
