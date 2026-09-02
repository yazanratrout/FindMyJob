# Changelog

All notable build progress is recorded here, newest first. Entries are grouped
by the checkpoint (CP) from [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Unreleased

### CP10 — Scoring engine
- `services/scoring` (pure functions): `cheap_hard_checks` (recency, blocked
  keywords, location — EN/DE city aliases), `analysis_hard_checks` (hours /
  language / contract, each gated by its hard toggle; full-time always fails
  `job_type`), `compute_soft_score` (skills_match, field_relevance, language_fit,
  hours_fit, seniority_fit, recency, salary_fit, company_affinity — weights from
  `AppSettings.weights`; breakdown records raw/weight/contribution), `bucket`.
- `services/jobscore`: per-run `JobScore` upsert + profile facts
  (`profile_skill_names`, `profile_language_levels`, `company_affinity`).
- `pipelines/prefilter` (before `analyze`): cheap hard filters → `JobScore`
  with `hard_pass`/`hard_failures`; `analyze` now skips prefilter rejects.
- `pipelines/score` (after `analyze`): analysis hard checks, then soft score +
  provisional `final_score`/`decision` (judge blend comes in CP11).
- `normalize`: shared `city_tokens` / `location_mentions_city` (ATS connectors
  now reuse them).
- Sequence: fetch → normalize → enrich → dedup → prefilter → analyze → score.
- 17 new tests (117 total); ruff + mypy clean. No new dependencies.

### CP9 — LLM job analyzer
- `llm/analyzer`: `analyze_posting()` + prompt + `JobAnalysisResult` schema
  (must/nice haves, skills, languages+CEFR, weekly hours + basis, contract type,
  salary, dates, enrollment/English-only/application-method, documents
  requested, seniority, red flags, and a `source_snippets` provenance map).
  `ANALYZER_VERSION` constant invalidates cached analyses on prompt change.
- `services/analyze`: `analyze_job()` — skip if a current-version `JobAnalysis`
  exists or the text is too thin; otherwise call the analyzer and persist.
- `pipelines/analyze` (non-critical): canonical + active jobs with real text and
  no current analysis, capped at 120/run. Identical postings across sources hit
  the LLM client cache (one call). `client_factory` injectable for tests.
- Registered after `dedup` (CP10 will insert `prefilter` before it).
- 5 new tests (100 total); ruff + mypy clean. No new dependencies.

### CP8 — Deduplication
- `services/embeddings`: lazy local `fastembed` embedder
  (`intfloat/multilingual-e5-small`, cached in `data/models/`); degrades to
  `None` when unavailable so the run still works. `cosine_matrix` + blob codec.
- `pipelines/dedup` (non-critical): tier 2 canonical key
  (`normalized_company | normalized_title`) links later duplicates to the
  earliest job via `job.canonical_job_id`; tier 3 embeds `title + jd_text`,
  compares within the same company, links pairs with cosine ≥ 0.92. Vectors
  persist in `job_embedding` and are reused across runs. Embedder is injectable
  for tests (no model download).
- Registered after `enrich`: fetch → normalize → enrich → dedup.
- 5 new tests (95 total); ruff + mypy clean. No new dependencies.

### CP7 — Normalization & enrichment
- `pipelines/normalize` (non-critical): links each job to a `company` row by
  normalized name, creating an inactive `origin=discovered` company when new;
  backfills `normalized_title`; sets `is_remote` from location text.
  `services/jobs.resolve_company`.
- `pipelines/enrich` (non-critical): for active jobs with thin `jd_text`,
  fetches the posting URL (robots-aware, rate-limited), extracts main content
  with `trafilatura` and merges `JobPosting` JSON-LD; marks 403/404/410 links
  `lifecycle=dead`. `services/enrich.enrich_url`.
- `FetchPipeline` / `EnrichPipeline` take an injectable `http_factory` for tests.
- Both registered in `pipelines/registry` after `fetch`.
- 7 new tests; ruff + mypy clean. No new dependencies (`trafilatura` already
  declared).

### CP6 — ATS connectors + company registry
- `sources/ats/`: Greenhouse, Lever, Personio (XML), SmartRecruiters, Ashby —
  each fans out over `CompanyRef`s with a matching `ats_type`, maps to `RawJob`,
  and filters to student-suitable roles + the target city (with EN/DE city
  aliases) + recency.
- `sources/jsonld`: extracts schema.org `JobPosting` data from career pages of
  companies with no known ATS; `sources/robots` gates those fetches by
  `robots.txt`.
- `services/companies`: CRUD, `company_refs` (queryable companies only),
  `detect_ats` (URL pattern + HTML fallback).
- API: `GET/POST/PUT/DELETE /api/companies`, `POST /api/companies/detect`.
- `sources/registry.build_sources` now also builds the ATS + JSON-LD sources
  from the company list; `pipelines/fetch` loads `company_refs` and passes them.
- `normalize._strip_accents` → public `normalize.fold_accents`.
- 20 new tests (83 total); ruff + mypy clean. No new dependencies.

### CP5 — Source framework + API connectors
- `services/http.HttpClient`: shared async client — per-host min-interval rate
  limiting, retry/backoff on 429/5xx/transport errors (tenacity), stable UA.
- `sources/base`: `JobSource` contract, `SourceQuery`, `RawJob`.
- `sources/_parsing`: datetime/unix parsing, HTML→text, keyword & recency
  filters.
- Connectors (`sources/api/`): Bundesagentur für Arbeit (fixed public API key),
  Adzuna (needs `ADZUNA_*`), Arbeitnow (keyless, client-side filter), The Muse
  (optional key). Each maps to `RawJob`, paginates with a hard cap, translates
  job types to the source's vocabulary.
- `sources/registry`: `build_sources` (enabled + configured filter),
  `build_source_query` (from `AppSettings`).
- `services/jobs.store_raw_job`: idempotent upsert into `job` by
  `(source_key, source_job_id)` with `normalized_title` + content hash.
- `pipelines/fetch.FetchPipeline` (critical): queries every active source,
  stores new postings, contains per-source and per-posting failures. Registered
  in `pipelines/registry`.
- 20 new tests (all sources `respx`-mocked; 63 total); ruff + mypy clean.
- No new dependencies (tenacity/httpx/selectolax/python-dateutil already declared).

### Docs restructure
- `docs/` split into `docs/implementation/` (plan, progress, changelog,
  architecture, pipelines, user guide) and `docs/rules/` (working agreement,
  coding standards, dependency rule, git/migrations, pipeline rules).
- Added the engineering working agreement (plan §7) and the "add a dependency
  before you import it" rule.
- Top-level `README.md` rewritten to reflect current state and doc layout.

### CP4 — Settings & onboarding backend
- `services/settings`: read/update the singleton `AppSettings`, whitelist of
  writable fields, validation (threshold order, blend ratio, known sources,
  run-time format), re-geocode when the city changes.
- `services/geocode` + `models/geo.GeocodeCache`: best-effort Nominatim
  city→coords lookup, cached in the DB, injectable for tests, never fatal.
- `services/semester` + API: CRUD for lecture-period terms; `is_in_lecture_period`.
- `llm/keyword_suggest` + prompt: grouped keyword candidates
  (core / adjacent / tools / likely_noise) from fields + titles + CV skills.
- API: `GET/PUT /api/settings`, `POST /api/settings/suggest-keywords`,
  `GET/POST/DELETE /api/semester-terms`.
- migration `de033880e991`; 12 new tests (51 total); ruff + mypy clean.

### CP3 — Profile builder (LLM)
- `llm/client`: Claude wrapper — tier routing, content-hash response cache
  (`llm_cache_entry`), token/cost accounting to `llm_call`, JSON mode with one
  repair retry + schema validation; network call injectable for tests.
- `llm/prompts` loader + `profile_parser` prompt/schema.
- `services/profile`: merge parsed data into the profile, honour user-locked
  fields, preserve manual skills; `update_profile` / `set_skills`.
- API: `GET/PUT /api/profile`, `POST /api/profile/parse`, `PUT /api/profile/skills`.
- migration `ed1f59245c48`.

### CP2 — Document intake & storage
- `services/documents`: validate (type + 15 MB cap), store per-profile on disk,
  extract a text layer (`pdfplumber` / `python-docx` / plain); never fail the
  upload over extraction.
- `services/text_extract`: mime dispatch; images left `PENDING`.
- `services/profile`: singleton profile accessor.
- API: `POST/GET/DELETE /api/documents`, `GET /api/documents/{id}/file`.

### CP1 — Config, DB, migrations
- `findmyjob.config.Settings`: environment/`.env`-backed process config with a
  derived `database_url` and runtime directory helpers; cached singleton.
- `findmyjob.db`: SQLite engine with FK + WAL pragmas, `session_scope`,
  FastAPI `get_session`, `create_all` / `drop_all` (FK-safe).
- Full SQLModel schema (`findmyjob.models`): profile, skills, documents,
  app settings, companies, semester terms, runs, pipeline runs, LLM calls,
  jobs, embeddings, analyses, scores, applications, cover letters,
  eligibility ledger, auth.
- Alembic wired (`migrations/`, `db_migrate.upgrade_to_head`); initial
  autogenerated revision. `tests/test_migrations.py` fails the build if models
  drift from migrations.
- `findmyjob.services.bootstrap.seed`: idempotent creation of the singleton
  settings + profile rows and sync of `sources/companies.yaml` (30 Munich
  employers). Seed-managed companies refresh; user companies are never touched.

### CP0 — Repo scaffold & tooling
- `src/findmyjob` package layout; `pyproject.toml` (ruff + mypy + pytest),
  `requirements.txt` / `requirements-dev.txt`, `.env.example`, `.gitignore`,
  `justfile` task runner.
- Structured logging (`structlog`): pretty console + rotating JSON file.
- Pipeline framework: `Pipeline` base class, `PipelineContext`, `PipelineResult`,
  and an `Orchestrator` that runs pipelines in order with per-stage crash
  isolation, timing, `PipelineRun` records and run-level stat roll-up. Critical
  pipelines abort the run; non-critical failures are contained.
- `findmyjob` CLI: `db upgrade|seed|reset`, `pipeline run|list`, `doctor`,
  `shell`.
- FastAPI app factory with `/api/health`, lifespan that migrates + seeds,
  dev CORS, and optional static frontend mount.
- `findmyjob doctor` installation check.
