# Architecture

A condensed map of the system. Full design and rationale:
[`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Shape

Single-user, local, `127.0.0.1` only. A FastAPI backend serves a React UI and
exposes a REST API. A scheduler (and a `launchd` fallback) runs the daily
pipeline. Everything persists to one SQLite file; documents and generated
letters are plain files under `data/`.

```
React UI ──REST──> FastAPI ──> services / llm / sources
                      │              │
                 scheduler ──> Orchestrator ──> pipelines ──> SQLite + files
```

## Layers (dependencies point downward only)

```
api/         HTTP routes: validate input, call a service, shape output
  │
services/    business logic that isn't a pipeline stage
  │          (documents, profile, settings, geocode, bootstrap, doctor, cost…)
  │
pipelines/   the daily job: framework + concrete stages + orchestrator
llm/         Claude client (cache, cost, JSON mode) + prompt-backed helpers
sources/     job-source connectors + company registry (allowlist only)
  │
models/      SQLModel tables (no ORM relationships — explicit queries)
  │
db.py        engine, sessions, pragmas          config.py   env / .env
```

Pipelines may call `services/`, `llm/`, `sources/`. **Pipelines never import
each other.** `api/` contains no business logic.

## Package layout

```
src/findmyjob/
  config.py            process config (env / .env), derived paths + db URL
  logging.py           structlog: pretty console + rotating JSON file
  db.py                engine (FK + WAL), session_scope, get_session
  db_migrate.py        programmatic Alembic upgrade
  normalize.py         company/title normalization, slugify
  cli.py / __main__.py `python -m findmyjob ...`

  models/              one module per aggregate; __init__ re-exports for metadata
  schemas/             Pydantic request/response models for the API
  api/
    app.py             app factory, lifespan (migrate + seed), CORS, static mount
    routes/            health, documents, profile, settings, …
  pipelines/
    base.py context.py orchestrator.py registry.py   (framework)
    fetch.py normalize.py … (concrete stages, added per checkpoint)
  llm/
    client.py          Claude wrapper
    prompts/           *.md templates + load_prompt()
    profile_parser.py  (analyzer.py, judge.py, cover_letter.py added later)
  sources/
    base.py            JobSource / SourceQuery / RawJob (CP5)
    companies.yaml     seed employer registry
    api/  ats/          connectors (CP5 / CP6)
  services/            documents, profile, settings, geocode, bootstrap, doctor,
                       feedback, calibration, retention, backup, digest, ...
migrations/            Alembic env + versions
tests/                 pytest; conftest gives each test an isolated DB
data/                  git-ignored runtime: findmyjob.db, documents/, letters/, models/, logs/, backups/
frontend/             React UI (CP15+)
```

## Data model (current tables)

- **Profile**: `profile`, `profile_skill`, `document` — the single user, their
  skills, their uploaded files (+ extracted text + parse status).
- **Config**: `app_settings` (singleton, all user preferences), `company`
  (employer registry), `semester_term` (lecture periods), `geocode_cache`.
- **Runs**: `run` (one orchestrator execution), `pipeline_run` (per-stage
  result), `llm_call` (per model call: tokens, cost, cache hit),
  `llm_cache_entry` (content-hash → response).
- **Jobs**: `job` (+ `canonical_job_id` self-link for dedup), `job_embedding`,
  `job_analysis` (LLM extraction, versioned), `job_score` (hard/soft/final +
  decision + documents checklist).
- **Application**: `application` (status tracker), `cover_letter` (generated
  drafts + claims-used + docx path).
- **Eligibility**: `eligibility_entry` (non-EU working-day ledger).
- **Feedback**: `job_feedback` (one thumbs up/down per job, feeds calibration).
- **Auth**: `app_auth` (Argon2 passphrase hash).

## Request/pipeline flow

- **API request**: route → service → models/db → response schema.
- **Daily run**: scheduler → `Orchestrator.execute()` → each pipeline
  (`fetch → … → notify`) reading/writing the DB → `Run` closed → digest sent.
  Details per stage in [`PIPELINES.md`](./PIPELINES.md).

## Key decisions

- **Sync DB inside async pipelines.** SQLite + single user; simplicity wins.
- **No ORM relationships.** Explicit `select()` avoids lazy-load surprises
  across the session boundaries pipelines cross.
- **LLM behind one client.** Caching, cost, budget and testability in one place.
- **Allowlist sourcing.** Only official/public APIs and permitted feeds.
- **Local-first.** No cloud dependency; `launchd` runs it on a Mac.
