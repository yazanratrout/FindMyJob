# FindMyJob

A local, single-user, human-in-the-loop pipeline that finds working-student
("Werkstudent") and related student positions in a chosen city, analyzes each
posting, scores how well it fits your profile, and — on your explicit click —
drafts a tailored cover letter you download as a `.docx` and submit yourself.

- **Allowlist sourcing only.** Official / public APIs (Bundesagentur für Arbeit,
  Adzuna, Arbeitnow, The Muse) and public company ATS endpoints (Greenhouse,
  Lever, Personio, SmartRecruiters, Ashby). No LinkedIn / StepStone / Indeed
  scraping.
- **Automate before spending.** Deterministic filters, caching and heuristics
  run before any LLM call; model spend is capped by a monthly EUR budget.
- **Human-in-the-loop.** It recommends; you decide to apply, trigger and review
  the cover letter, and submit. It never applies for you.
- **Local & private.** SQLite + files on your machine, bound to `127.0.0.1`.
  The only outbound calls are to the job APIs you enable and the Anthropic API.

## Documentation

| Where | What |
|-------|------|
| [`docs/implementation/IMPLEMENTATION_PLAN.md`](docs/implementation/IMPLEMENTATION_PLAN.md) | Full spec + 25 build checkpoints |
| [`docs/implementation/PROGRESS.md`](docs/implementation/PROGRESS.md) | Current status / where the build is |
| [`docs/implementation/ARCHITECTURE.md`](docs/implementation/ARCHITECTURE.md) | System map |
| [`docs/implementation/PIPELINES.md`](docs/implementation/PIPELINES.md) | Pipeline framework & stages |
| [`docs/implementation/USER_GUIDE.md`](docs/implementation/USER_GUIDE.md) | Install & use |
| [`docs/rules/RULES.md`](docs/rules/RULES.md) | Engineering working agreement |

## Status

Early build — **Milestone 1 complete (CP0–CP4); Milestone 2 in progress (CP5
done).** Working today: configuration, database + migrations, the pipeline
framework and orchestrator, the LLM client (cache + cost accounting), document
upload + text extraction, LLM CV parsing into a structured profile, the settings
/ onboarding backend, and the **job-ingestion pipeline** — a `fetch` stage that
queries Bundesagentur für Arbeit, Adzuna, Arbeitnow and The Muse and stores new
postings. Next: ATS connectors (CP6), normalization/enrichment (CP7), dedup
(CP8). No web UI yet. See [`PROGRESS.md`](docs/implementation/PROGRESS.md).

## Requirements

- Python 3.12+ (3.13 recommended)
- Node 20+ (only once the frontend lands, CP15)
- [`just`](https://github.com/casey/just) — optional (`brew install just`)

## Setup

```bash
git clone <this repo> && cd FindMyJob
cp .env.example .env          # fill in ANTHROPIC_API_KEY, optional source keys
python3 -m venv .venv
just setup                    # install deps, migrate, seed
```

Without `just`:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip install -e .
.venv/bin/python -m findmyjob db seed
```

All code and tooling run **inside `./.venv`**. Secrets live only in `.env`
(git-ignored). User preferences are stored in the database, not in `.env`.

## Commands

| `just` | equivalent | purpose |
|--------|-----------|---------|
| `just dev` | `.venv/bin/python -m uvicorn findmyjob.api.app:app --reload` | start the API on `127.0.0.1:8000` |
| `just run-pipeline` | `.venv/bin/python -m findmyjob pipeline run` | run the daily pipeline once |
| `just test` | `.venv/bin/python -m pytest` | run tests |
| `just check` | ruff + mypy + pytest | full quality gate (run before committing) |
| `just doctor` | `.venv/bin/python -m findmyjob doctor` | verify the installation |
| `just db-upgrade` | `.venv/bin/python -m findmyjob db upgrade` | apply migrations |
| `just db-revision "msg"` | `.venv/bin/python -m alembic revision --autogenerate -m msg` | new migration after a model change |
| `just db-reset` | `.venv/bin/python -m findmyjob db reset` | drop & re-seed (destructive) |
| `just lock` | `pip freeze --exclude-editable > requirements.lock` | refresh the lock file |

## Repository layout

```text
src/findmyjob/      application package (see docs/implementation/ARCHITECTURE.md)
  config.py db.py normalize.py cli.py
  models/  schemas/  api/  pipelines/  llm/  sources/  services/
migrations/          Alembic
tests/               pytest
docs/                implementation plan, progress, architecture, rules
data/                git-ignored runtime data (db, documents, letters, logs)
frontend/            React UI (from CP15)
.env / .env.example  secrets (env only)
requirements*.txt    pinned deps + lock; requirements-dev.txt for tooling
justfile             task runner
```

## Contributing / continuing the build

Read [`docs/rules/RULES.md`](docs/rules/RULES.md) first. Build one checkpoint at
a time from the implementation plan; finish it (code + tests + docs + green
`just check`) before starting the next; keep
[`PROGRESS.md`](docs/implementation/PROGRESS.md) and
[`CHANGELOG.md`](docs/implementation/CHANGELOG.md) current in the same commit.

## License

MIT
