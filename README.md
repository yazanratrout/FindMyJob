# FindMyJob

A local, single-user, human-in-the-loop pipeline that finds working-student
("Werkstudent") and related student positions in a chosen city, analyzes each
one, scores how well it fits your profile, and — on your explicit click — drafts
a tailored cover letter you download as a `.docx` and submit yourself.

It never scrapes sites that forbid it and never submits an application for you.
See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for the full
design and [`docs/CHANGELOG.md`](docs/CHANGELOG.md) for build progress.

## Status

Early build. Foundation (config, database, migrations, pipeline framework,
orchestrator, CLI, health API) is in place. Job sources, analysis, scoring,
cover letters and the web UI are being added checkpoint by checkpoint.

## Requirements

- Python 3.12+ (3.13 recommended)
- Node 20+ (only once the frontend lands)
- [`just`](https://github.com/casey/just) — optional but recommended
  (`brew install just`)

## Setup

```bash
git clone <this repo> && cd FindMyJob
cp .env.example .env          # then fill in ANTHROPIC_API_KEY etc.
python3 -m venv .venv
just setup                    # installs deps, migrates, seeds
# or without just:
#   .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pip install -e .
#   .venv/bin/python -m findmyjob db seed
```

Everything runs **inside `./.venv`**. Secrets live only in `.env`, which is
git-ignored.

## Common commands

| Command | Purpose |
|---|---|
| `just dev` | start the API on `127.0.0.1:8000` |
| `just run-pipeline` | run the daily pipeline once, now |
| `just test` | run the test suite |
| `just check` | lint + typecheck + tests (what CI runs) |
| `just doctor` | verify the installation and credentials |
| `just db-revision "msg"` | create a migration after changing models |
| `just db-reset` | drop everything and re-seed (destructive) |

## Layout

```
src/findmyjob/
  config.py          process configuration (env / .env)
  db.py              engine + sessions
  models/            SQLModel tables
  pipelines/         pipeline framework + orchestrator + concrete stages
  sources/           job-source connectors + company registry
  llm/               Claude client + prompt-backed helpers
  services/          non-pipeline business logic
  api/               FastAPI app + routes
  cli.py             `python -m findmyjob ...`
migrations/          Alembic
tests/               pytest
docs/                plan + changelog
data/                runtime data (git-ignored): db, documents, letters, models
frontend/            React UI (added later)
```

## Privacy

All data — your documents, the SQLite database, generated letters — stays on
your machine. The only outbound calls are to the job-source APIs you enable and
to the Anthropic API for analysis and cover letters. Bind address is
`127.0.0.1`.
