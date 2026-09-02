# Progress

Living status of the build. Update this at the end of every checkpoint.
For the full spec see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md);
for what changed when, [`CHANGELOG.md`](./CHANGELOG.md).

**Last updated:** end of CP5
**Resume from:** CP6 — ATS connectors + company registry. Add
`sources/ats/{greenhouse,lever,personio,smartrecruiters,ashby}.py` (each fans
out over `company` rows with a matching `ats_type`), a `sources/jsonld.py`
`JobPosting` extractor for unknown-ATS career pages, and company CRUD endpoints
(`GET/POST/DELETE /api/companies`, `POST /api/companies/detect`). Append the ATS
sources to `ALL_SOURCE_CLASSES` in `sources/registry.py`. Honour `robots.txt`
for any HTML fetch (add a small robots cache in `services/http.py` or a helper).

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
| CP6 | ATS connectors + company registry | ⬜ todo |
| CP7 | Normalization & enrichment | ⬜ todo |
| CP8 | Deduplication | ⬜ todo |
| CP9 | LLM job analyzer | ⬜ todo |
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

Milestones: **M1 (CP0–CP4) complete** · **M2 (CP5–CP8) started** (CP5 done).

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
  critical-abort). Registered pipelines: `fetch` (CP5).
- **Job sources** (`sources/`): shared rate-limited/retrying `HttpClient`;
  `JobSource` contract; connectors for Bundesagentur für Arbeit, Adzuna,
  Arbeitnow, The Muse; registry that filters by enabled + configured.
  `fetch` pipeline persists new postings into `job` (idempotent).
- **LLM layer** (`llm/`): `LlmClient` (tier routing, content-hash cache,
  cost/token accounting, JSON mode + one repair retry, injectable network fn),
  prompt loader, `profile_parser`.
- **Services**: `bootstrap` (idempotent seed), `documents` (upload/validate/
  extract/store), `profile` (parse-merge with locked fields, skills),
  `settings` (read/update/validate + geocode), `geocode` (Nominatim + cache),
  `doctor`.
- **API** (`api/`): `/api/health`, `/api/documents*`, `/api/profile*`,
  `/api/settings*`, `/api/semester-terms*`.
- **CLI**: `findmyjob db upgrade|seed|reset`, `pipeline run|list`, `doctor`,
  `shell`.
- **Tests**: 63 passing. `ruff` + `mypy` clean.

## Known gaps / deferred

- No web UI yet (CP15+).
- No job sources yet (CP5+); orchestrator runs an empty sequence.
- Cost *budget enforcement* (stopping mid-run) is CP14; only per-call
  accounting exists.
- Image/scanned-PDF documents are stored but not OCR'd (CP3 vision fallback was
  descoped to a later pass; `parse_status = PENDING`).
- Geocoding hits Nominatim live; respect its 1 req/s policy when CP5 wiring
  triggers lookups in bulk (it won't — only on city change).

## How to resume

1. `just setup` (or `just db-upgrade && just db-seed`)
2. `just check` — confirm green baseline
3. Open `IMPLEMENTATION_PLAN.md` at the current checkpoint
4. Follow [`../rules/RULES.md`](../rules/RULES.md)
5. End the checkpoint: tests + `CHANGELOG.md` + this file + `README.md` + commit
