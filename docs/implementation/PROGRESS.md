# Progress

Living status of the build. Update this at the end of every checkpoint.
For the full spec see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md);
for what changed when, [`CHANGELOG.md`](./CHANGELOG.md).

**Last updated:** end of CP9
**Resume from:** CP10 — Scoring engine. Build `services/scoring.py`: the hard
filters (`prefilter` — location/hours/language/contract/job-type/recency/
blacklist, each gated by its hard toggle in settings) and the weighted soft
score (skills_match, field_relevance, language_fit, hours_fit, seniority_fit,
recency, salary_fit, company_affinity; weights from `AppSettings.weights`).
Add a `prefilter` pipeline (before `analyze` in the sequence) writing a
`JobScore` with `hard_pass`/`hard_failures`, and a `score` pipeline (after
`analyze`) filling `soft_score`/`soft_breakdown`. Table-driven tests are the
priority here. `field_relevance` reuses `services/embeddings`.

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
| CP10 | Scoring engine | ⬜ todo |
| CP11 | Judge, blend, decision, documents | ⬜ todo |
| CP12 | Pipeline orchestrator (wire it all) | ⬜ todo |
| CP13 | Scheduler | ⬜ todo |
| CP14 | Cost controls | ⬜ todo (client-side accounting partly done in CP3) |
| CP15 | Frontend scaffold, auth, API client | ⬜ todo |
| CP16 | Onboarding wizard UI | ⬜ todo |
| CP17 | Dashboard UI | ⬜ todo |
| CP18 | Job detail UI | ⬜ todo |
| CP19 | Cover letter generation + DOCX | ⬜ todo |
| CP20 | Application tracker | ⬜ todo |
| CP21 | Notifications (digest) | ⬜ todo |
| CP22 | Eligibility module | ⬜ todo |
| CP23 | Observability, retention, backup | ⬜ todo |
| CP24 | Packaging & macOS deployment | ⬜ todo |
| CP25 | Calibration & feedback loop | ⬜ todo |

Milestones: **M1 (CP0–CP4) complete** · **M2 (CP5–CP8) complete** · **M3 (CP9–CP12) started** (CP9 done).

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
  critical-abort). Registered pipelines: `fetch` → `normalize` → `enrich` → `dedup` → `analyze`.
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
- **Analyze pipeline** (`analyze`): LLM structured extraction into `job_analysis`
  (cached, versioned, capped per run).
- **API** (`api/`): `/api/health`, `/api/documents*`, `/api/profile*`,
  `/api/settings*`, `/api/semester-terms*`, `/api/companies*`.
- **CLI**: `findmyjob db upgrade|seed|reset`, `pipeline run|list`, `doctor`,
  `shell`.
- **Tests**: 100 passing (suite ~7 min; a fast marker is planned in CP23). `ruff` + `mypy` clean.

## Known gaps / deferred

- No web UI yet (CP15+).
- No scoring / judge / cover-letter pipelines yet (CP10–CP11); the run stops
  after `analyze`.
- Cost *budget enforcement* (stopping mid-run) is CP14; only per-call
  accounting exists.
- Image/scanned-PDF documents are stored but not OCR'd (CP3 vision fallback
  deferred; `parse_status = PENDING`).
- `dedup` embedding model downloads on first real run; tests inject a fake.
  Consider adding the download to `just setup` (CP24).
- The repost rule (a long-gone posting reappearing counts as new) is not yet
  implemented — `dedup` currently always links by canonical key.
- Full test suite ~7 min (trafilatura import + per-test DB reset); split fast/slow
  in CP23.

## How to resume

1. `just setup` (or `just db-upgrade && just db-seed`)
2. `just check` — confirm green baseline
3. Open `IMPLEMENTATION_PLAN.md` at the current checkpoint
4. Follow [`../rules/RULES.md`](../rules/RULES.md)
5. End the checkpoint: tests + `CHANGELOG.md` + this file + `README.md` + commit
