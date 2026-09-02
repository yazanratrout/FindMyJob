# Progress

Living status of the build. Update this at the end of every checkpoint.
For the full spec see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md);
for what changed when, [`CHANGELOG.md`](./CHANGELOG.md).

**Last updated:** end of CP25 — **all 25 checkpoints complete.**
**Resume from:** nothing outstanding. The build is done: Milestones 1-7 all
shipped. Future work is maintenance / the deferred items below (frontend tests,
OCR fallback, the repost rule, an optional logistic re-ranker at ≥ 40 labels).

---

## Checkpoint status

| CP | Title | Status |
|----|-------|--------|
| CP0 | Repo scaffold & tooling | ✅ done |
| CP1 | Config, DB, migrations | ✅ done |
| CP2 | Document intake & storage | ✅ done |
| CP3 | Profile builder (LLM) | ✅ done |
| CP4 | Settings & onboarding backend | ✅ done |
| CP5 | Source framework + API connectors | ✅ done |
| CP6 | ATS connectors + company registry | ✅ done |
| CP7 | Normalization & enrichment | ✅ done |
| CP8 | Deduplication | ✅ done |
| CP9 | LLM job analyzer | ✅ done |
| CP10 | Scoring engine | ✅ done |
| CP11 | Judge, blend, decision, documents | ✅ done |
| CP12 | Pipeline orchestrator (wire it all) | ✅ done |
| CP13 | Scheduler | ✅ done |
| CP14 | Cost controls | ✅ done |
| CP15 | Frontend scaffold, auth, API client | ✅ done |
| CP16 | Onboarding wizard UI | ✅ done |
| CP17 | Dashboard UI | ✅ done |
| CP18 | Job detail UI | ✅ done |
| CP19 | Cover letter generation + DOCX | ✅ done |
| CP20 | Application tracker | ✅ done |
| CP21 | In-app run digests | ✅ done |
| CP22 | Eligibility module | ✅ done |
| CP23 | Observability, retention, backup | ✅ done |
| CP24 | Packaging & macOS deployment | ✅ done |
| CP25 | Calibration & feedback loop | ✅ done |

Milestones: **M1 (CP0–CP4) complete** · **M2 (CP5–CP8) complete** · **M3 (CP9–CP12) complete** · **M4 (CP13–CP14) complete** · **M5 (CP15–CP20) complete** · **M6 (CP21–CP24) complete** · **M7 (CP25) complete**.

---

## What exists today

- **Config** (`config.py`): env/`.env`-backed, derived `database_url`, runtime
  dirs. Cached singleton.
- **Database** (`db.py`, `models/`): SQLite + FK/WAL, full schema, Alembic
  migrations, drift-guard test. Tables: profile, profile_skill, document,
  app_settings, company, semester_term, run, pipeline_run, llm_call,
  llm_cache_entry, geocode_cache, job (+embedding/analysis/score), application,
  cover_letter, eligibility_entry, app_auth.
- **Pipeline framework** (`pipelines/`): `Pipeline`, `PipelineContext`,
  `PipelineResult`, `Orchestrator` (crash-isolated, timed, stat roll-up,
  critical-abort). Registered pipelines: `fetch` → `normalize` → `enrich` → `dedup` → `prefilter` → `analyze` → `score` → `judge` → `decide` → `notify` (full sequence).
- **Job sources** (`sources/`): shared rate-limited/retrying `HttpClient`;
  `JobSource` contract; API connectors (Bundesagentur für Arbeit, Adzuna,
  Arbeitnow, The Muse); ATS connectors (Greenhouse, Lever, Personio,
  SmartRecruiters, Ashby) + a JSON-LD career-page extractor (robots-aware);
  registry filters by enabled + configured. `fetch` pipeline persists new
  postings into `job` (idempotent).
- **Company registry** (`services/companies`): CRUD, ATS auto-detect,
  `company_refs` for the connectors. API at `/api/companies*`.
- **Ingestion pipelines**: `normalize` (company resolution), `enrich` (full-JD
  fetch, robots-aware), `dedup` (canonical-key + local-embedding tiers,
  `services/embeddings`, vectors in `job_embedding`).
- **LLM layer** (`llm/`): `LlmClient` (tier routing, content-hash cache,
  cost/token accounting, JSON mode + one repair retry, injectable network fn),
  prompt loader, `profile_parser`, `keyword_suggest`, `analyzer`.
- **Services**: `bootstrap`, `documents`, `profile`, `settings`, `geocode`,
  `semester`, `companies`, `jobs`, `enrich`, `embeddings`, `analyze`, `doctor`.
- **Intelligence pipelines**: `prefilter`, `analyze`, `score`, `judge` (LLM
  holistic + blend), `decide` (documents checklist). `services/scoring`,
  `services/jobscore`, `services/documents_needed`, `services/analyze`,
  `llm/analyzer`, `llm/judge`.
- **Cover letters** (`llm/cover_letter`, `docx/render`, `services/cover_letters`,
  `/api/…cover-letter…`): LLM draft with claims-used, DOCX render, versions.
- **Runs API + background trigger** (`services/runs`, `/api/runs*`): list,
  detail (stages + LLM usage), `POST` to trigger, SSE progress stream.
- **Scheduler** (`scheduler.py`): in-process APScheduler daily run from settings,
  reschedules live; launchd fallback in `deploy/`. `findmyjob schedule status`.
- **Cost controls** (`services/cost`, `/api/costs`): month-to-date spend,
  per-purpose breakdown, monthly-budget guard that stops `analyze`/`judge`.
- **Auth** (`services/auth`, `api/deps`, `/api/auth/*`): Argon2 passphrase,
  signed session cookie; all `/api/*` except `health` + `auth` are guarded.
- **API** (`api/`): `/api/{health,auth,documents,profile,settings,semester-terms,
  companies,runs,costs,jobs,cover-letters,applications,digests,eligibility}`.
- **Frontend** (`frontend/`): auth, onboarding wizard, Settings, ranked dashboard,
  job-detail drawer, application tracker, Activity (digests + badge), Eligibility
  (conditional), **Runs list + run-detail drawer**.
- **CLI**: `findmyjob db …`, `pipeline run|list`, `schedule status`,
  `maintenance backup|prune`, `models fetch`, `calibrate [--apply]`,
  `doctor` (11 checks), `shell`.
- **Maintenance**: nightly SQLite backup + weekly retention prune, scheduled and
  as CLI (`services/backup`, `services/retention`).
- **Calibration** (`services/feedback`, `services/calibration`, `/api/calibration`,
  `/api/jobs/{id}/feedback`): thumbs up/down + tracker outcomes → per-component
  correlations → one-click weight adjustment. Settings panel + drawer control.
- **Tests**: ~207 passing (backend; `just test` fast subset, `just test-all` all).
  `ruff` + `mypy` clean; `vite build` clean.

## Known gaps / deferred

- No frontend tests yet.
- Image/scanned-PDF documents are stored but not OCR'd (CP3 vision fallback
  deferred; `parse_status = PENDING`).
- The repost rule (a long-gone posting reappearing counts as new) is not yet
  implemented - `dedup` currently always links by canonical key.
- Calibration is correlation-based only; the optional per-user logistic
  re-ranker at ≥ 40 labelled jobs (CP25 stretch goal) is not built.

## How to resume

1. `just setup` (or `just db-upgrade && just db-seed`)
2. `just check` — confirm green baseline
3. Open `IMPLEMENTATION_PLAN.md` at the current checkpoint
4. Follow [`../rules/RULES.md`](../rules/RULES.md)
5. End the checkpoint: tests + `CHANGELOG.md` + this file + `README.md` + commit
