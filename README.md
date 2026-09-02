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

**Milestones 1–5 complete (CP0–CP20): the app is end-to-end usable.** The
backend runs the full pipeline on a schedule within an LLM budget; the React app
has passphrase auth, an onboarding wizard, a re-editable settings page, a ranked
job dashboard with a detail drawer (score breakdown, assessment, documents
checklist, original posting), **LLM cover-letter generation → editable → `.docx`
download**, and an **application tracker** board. Remaining: digest
notifications, the eligibility module, observability, and macOS packaging
(CP21–24). `findmyjob pipeline run` (or `POST /api/runs`, or the daily
scheduler) executes:
`fetch` (Bundesagentur für Arbeit, Adzuna, Arbeitnow, The Muse + the public ATS
boards of curated employers) → `normalize` → `enrich` (robots-aware) → `dedup`
(canonical-key + local embeddings) → `prefilter` (cheap hard filters) →
`analyze` (LLM extraction) → `score` (hard checks + weighted soft score) →
`judge` (LLM holistic fit, blended) → `decide` (documents checklist). Plus the
config / profile / company / settings / runs / costs REST API, an in-process
daily scheduler, and a monthly LLM-budget guard. **Next: the React web UI
(CP15+).** No UI yet — use the API at `/api/docs`. See
[`PROGRESS.md`](docs/implementation/PROGRESS.md).

## Requirements

- Python 3.12+ (3.13 recommended)
- Node 20+ (for the web UI)
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
| `just schedule-status` | `.venv/bin/python -m findmyjob schedule status` | show the daily run time + next fire |
| `just install-launchd` | renders + loads the launchd fallback job | keep the daily run going when the server is down |

## Scheduling

While the API server runs, an in-process scheduler fires the full pipeline every
day at the time set in Settings (`run_time` / `run_timezone`, default
`10:00 Europe/Berlin`); a missed run (laptop asleep) fires once on wake within a
1-hour grace window. Changing the time in the UI reschedules it live.

For a run even when the server is down, install the independent `launchd`
fallback (`just install-launchd`, add `--server` to also keep the API up). The
pipeline is idempotent, so a double run costs almost nothing.

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
