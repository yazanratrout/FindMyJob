# Changelog

All notable build progress is recorded here, newest first. Entries are grouped
by the checkpoint (CP) from [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Unreleased

### Spec-conformance pass (post-CP25 audit)
A sweep of every checkpoint against the plan closed the remaining gaps:
- **Repost rule (CP8)** — `store_raw_job` now detects a posting last seen more
  than `repost_days` (21) ago reappearing while linked as a duplicate or no
  longer active: it is unlinked, re-activated, re-flagged first-seen this run
  and its stale `job_score` rows are dropped so it re-ranks from scratch.
- **JSON-LD merge in `enrich` (CP7)** — the `datePosted` / `baseSalary` hints
  the extractor already produced are now written back onto the job when it has
  no date / salary of its own.
- **`GET/PUT /api/sources` (CP5)** — a read model listing each connector with
  its enabled + credential-configured state; `PUT` toggles it (writes the same
  `sources_enabled` the wizard edits). `sources/registry.source_catalog`.
- **`pipeline run --source KEY --limit N` (CP12)** — narrow the fetch stage for
  debugging; threaded through `default_pipelines` / `build_default_orchestrator`.
- **Job-detail Analysis section (CP18)** — the drawer now renders the extracted
  must-haves / nice-to-haves, skills (required vs nice), languages, hours,
  contract, enrolment, start, deadline, apply method and red flags, with the
  analyzer's `source_snippets` shown as hover tooltips.
- **Dashboard filters (CP17)** — source, contract type, posted-within and
  has-salary filters alongside the existing bucket + search.
- **Notifications UI (CP21 decision)** — removed the vestigial e-mail / Telegram
  channel pickers from onboarding; replaced with a note that digests live in the
  Activity tab, plus a digest-size field.
- `data/.gitkeep` is tracked so the runtime dir exists on a fresh clone.
- 11 new tests (`test_repost`, `test_sources_route`, `test_registry`, JSON-LD
  enrich case). Documented deviations: token-overlap scoring instead of
  embeddings in `field_relevance` / `skills_match`; explicit source registry
  instead of subclass auto-discovery; plain bars instead of Recharts; scanned /
  image-only PDF OCR (Claude vision) is a planned enhancement, not in v1.

### CP25 — Calibration & feedback loop
- `job_feedback` table (one row per job: `verdict` up/down, `note`) + migration
  `4a07427937c2`; `services/feedback` upsert/clear helpers.
- `services/calibration`: labels each scored job from an explicit thumbs
  up/down (wins) or its tracker status (`applied`/`interview`/`offer` positive,
  `rejected`/`withdrawn` negative), Pearson-correlates every soft-score
  component with the outcome, and proposes a renormalised weight set
  (`weight * (1 + 0.6 * corr)`, clamped, summing to 100). The judge score is
  correlated too and nudges `blend_soft_ratio`. Needs ≥ 8 labelled jobs with
  ≥ 2 of each class before it will suggest anything.
- API: `PUT` / `DELETE /api/jobs/{id}/feedback`, `feedback` on the job detail,
  `GET /api/calibration`, `POST /api/calibration/apply` (writes `settings`).
- CLI: `findmyjob calibrate [--apply]`.
- Frontend: 👍/👎 control in the job drawer; a **Score calibration** panel in
  Settings (per-component correlation table + one-click apply).
- 12 new backend tests; ruff + mypy clean; `vite build` clean. No new deps
  (`numpy` already required by dedup).

### CP24 — Packaging & macOS deployment
- `findmyjob doctor` rewritten: Python/Node, `.env`, data dir, DB, **migrations
  at head**, `ANTHROPIC_API_KEY`, **web UI built**, **embedding model cached**,
  company seed, source keys — with a WARN vs FAIL distinction.
- `findmyjob models fetch` — download the `fastembed` model on demand.
- `just setup` now also fetches the model (non-fatal), builds the UI, runs
  `doctor`. New `just start` — migrate + serve API/UI without reload.
- README install walkthrough + `just` table updated.
- 3 new tests; ruff + mypy clean. No new deps.

### CP23 — Observability, retention, backup
- `services/retention.prune`: deletes canonical jobs (+ their score/analysis/
  embedding rows) that are old (`> retention_days`), archived or dead, and not
  referenced by an application or cover letter.
- `services/backup.backup`: SQLite online backup to
  `data/backups/findmyjob-<ts>.db` via the engine's connection, keeps the last
  14.
- Scheduler: nightly backup (03:30) + weekly prune (Sun 03:00) jobs, each
  crash-isolated.
- CLI: `findmyjob maintenance {backup,prune}`; `just backup` / `just prune`.
- Frontend: **Run detail drawer** on the Runs page — per-stage status / timing /
  stats, LLM usage, errors; live-polls while a run is in progress.
- **Fast/slow test split**: `slow` marker on the orchestrator integration
  modules; `just test` runs the fast subset (~125), `just test-all` (and
  `just check`) runs everything (~192).
- 3 new backend tests; ruff + mypy clean; `vite build` clean. No new deps.

### CP22 — Eligibility module (optional)
- `services/eligibility` (behind `eligibility_module_enabled`): `days_used`
  (non-EU 140/280 working-day ledger, clipped to the calendar year, half-days
  weighted 0.5), `gauge`, ledger CRUD (`add_entry` / `list_entries` /
  `delete_entry`), and `disqualifiers(job, analysis)` →
  `eligibility:non_eu_days_exhausted` / `eligibility:enrolment_ending`
  (within 60 days) / `eligibility:over_20h_in_term` (Werkstudent > 20 h during a
  lecture period).
- `score` pipeline merges eligibility disqualifiers into `hard_failures` when
  the module is on (stat `hard_failed_eligibility`).
- API: `GET /api/eligibility` (gauge), `GET/POST/DELETE /api/eligibility/entries`.
- Frontend: **Eligibility page** — working-day gauge + disclaimer, ledger table
  with add form, lecture-period editor; a conditional sidebar item shown only
  when the module is enabled.
- 9 new backend tests; ruff + mypy clean; `vite build` clean. No new deps, no
  migration (the `eligibility_entry` table has existed since CP1).

### CP21 — In-app run digests (no external notifications)
- Per the project owner's request, **no email / Telegram** — the digest lives in
  the web UI only.
- `models/digest.Digest` (per run: summary counts, top-N recommended items,
  warnings, `seen`); migration `0b10a2aa1e04`.
- `services/digest`: `build_digest` (idempotent per run — counts by decision,
  new jobs, follow-ups due, budget/error warnings), `list_digests`,
  `unseen_count`, `mark_seen` / `mark_all_seen`.
- `pipelines/notify.NotifyPipeline` — last stage, non-critical, builds the
  digest. Registered: `… → decide → notify`.
- API: `GET /api/digests`, `GET /api/digests/unseen-count`,
  `POST /api/digests/{id}/seen`, `POST /api/digests/seen`.
- Frontend: **Activity page** (per-run cards: status, counts, warnings, top job
  links into the drawer); sidebar "Activity" item with an unseen badge;
  visiting the page marks digests seen.
- 5 new backend tests; ruff + mypy clean; `vite build` clean. No new deps.

### CP20 — Application tracker
- `services/applications`: `get_or_create`, `update_application` (status →
  auto-stamps `applied_at`; ISO date parsing for `applied_at`/`follow_up_at`;
  outcome note; documents used), `follow_ups_due` (past `follow_up_at` +
  status applied/interview).
- API: `GET /api/applications`, `GET /api/applications/follow-ups`,
  `POST /api/applications`, `PUT /api/applications/{id}`.
- `JobDetail` now carries `application_id` / `application_status`.
- Frontend: Tracker page — a column per `ApplicationStatus`, per-card status
  select + follow-up date + notes; Dashboard shows a "follow-ups due" banner;
  job-detail drawer has a status control (creates the application on first use).
- 6 new backend tests; ruff + mypy clean; `vite build` clean. No new deps.
- **Milestone 5 complete.**

### CP19 — Cover letter generation + DOCX
- `llm/cover_letter`: `generate_cover_letter()` + prompt (posting-specific hook,
  evidence-backed claims, banned-phrase list, language/tone) + result schema
  (recipient, subject, salutation, paragraphs, closing, `claims_used`).
- `docx/render`: generates a DIN-5008-ish `docxtpl` template on first use,
  renders a letter to `data/letters/<job>/Cover letter <Company> vN.docx`.
- `services/cover_letters`: `generate` (resolve language, persist row, render,
  advance the `application` to `preparing`), `update` (validate + re-render +
  mark `user_edited`), `regenerate` (new version, instruction bypasses cache).
- API: `POST /api/jobs/{id}/cover-letter`, `GET /api/jobs/{id}/cover-letters`,
  `PUT /api/cover-letters/{id}`, `POST /api/cover-letters/{id}/regenerate`,
  `GET /api/cover-letters/{id}/docx`.
- `db`: `PRAGMA busy_timeout=5000` (scheduler + API can now write concurrently
  without spurious "database is locked").
- Frontend: `CoverLetterPanel` inside the job drawer — generate, edit paragraphs,
  a claims-used verification table, regenerate (with instruction), download
  `.docx` via an authenticated blob fetch. Drawer button is enabled.
- 6 new backend tests; ruff + mypy clean; `vite build` clean. No new deps.

### CP17 + CP18 — Dashboard job list + job detail
- Backend: `services/job_read` (`list_jobs` — canonical active jobs joined to
  their most-recent `JobScore` + analysis + company, ranked by `final_score`;
  bucket/source/search filters; "new since last completed run"),
  `bucket_counts`; `schemas/job` (`JobCard`, `JobDetail` with score breakdown,
  hard failures, rationale, documents checklist, raw analysis);
  `GET /api/jobs` + `GET /api/jobs/{id}`.
- Frontend: `useJobs` / `useJobDetail`; Dashboard replaced with ranked job
  rows (score ring, NEW badge, strengths/missing), bucket tabs + search;
  `JobDetailDrawer` slide-over — apply link, score-component bars, assessment,
  documents checklist (have / necessity / reason), full JD text. "Prepare cover
  letter" button is present but disabled until CP19.
- 4 new backend tests; ruff + mypy clean; `tsc` + `vite build` clean. No new deps.

### CP16 — Onboarding wizard UI
- `frontend/src/api/types.ts` + expanded `hooks.ts`: documents (upload/list/
  delete), profile (get/update/parse/skills), settings (get/update/suggest-
  keywords), semester terms.
- `frontend/src/onboarding/steps.tsx`: 8 step panels — Documents, Profile
  (parse + edit + locked-field hints), Where & what, Keywords (LLM suggest →
  move to allow/block), Limits (hours/language/contract + hard toggles,
  thresholds, weight sliders), Schedule & alerts (run time, notifications,
  cover-letter prefs, source toggles), Eligibility (non-EU day tracker toggle +
  lecture terms), Review.
- `onboarding/Wizard.tsx`: stepper with a shared settings draft; each step
  persists via `PUT /api/settings`; finish sets `onboarding_completed` and
  triggers the first run. `App.tsx` shows the wizard until onboarding is done.
- `pages/SettingsPage.tsx`: the same step panels stacked, re-editable any time.
- shared form controls (`components/form.tsx`): `Field`, `Select`, `Checkbox`,
  `TagInput`, `ChipToggle`.
- `tsc` + `vite build` clean. No new dependencies.

### CP15 — Frontend scaffold + auth
- **Backend auth**: `services/auth` (Argon2 via `argon2-cffi`, rehash-on-verify),
  `api/deps` (`require_auth`, session helpers), `api/routes/auth`
  (`GET /api/auth/status`, `POST /api/auth/{setup,login,logout}`).
  `SessionMiddleware` (signed cookie). Every `/api/*` router except `health` and
  `auth` is behind `require_auth`. Tests: `client` fixture authenticates;
  `unauth_client` for the auth flow.
- **Frontend** (`frontend/`): Vite + React 18 + TypeScript + Tailwind v4 +
  TanStack Query + React Router. `api/client.ts` + `api/hooks.ts`, minimal UI
  primitives, `Layout` (sidebar), `App` (auth gate → setup/login screens →
  routed shell). Placeholder Dashboard (health / spend / last run + "Run
  pipeline now") and Runs pages; Tracker/Settings stubs.
- `just frontend-{install,dev,build}`; `just setup` now builds the frontend;
  `api/app.py` serves `frontend/dist` at `/`.
- 6 new backend tests; ruff + mypy clean; frontend `tsc` + `vite build` clean.
  No new Python deps.

### CP14 — Cost controls
- `services/cost`: `current_month_cost_eur` (moved from `llm/client`),
  `remaining_budget_eur`, `budget_ok`, `mark_budget_exhausted`, `month_to_date`
  (total, remaining, per-purpose breakdown, linear month-end projection).
- Budget guard in `analyze` and `judge`: before each job, if
  `Settings.llm_monthly_budget_eur` would be exceeded, set
  `run.budget_exhausted=True`, bump `budget_exhausted`, stop — the rest is
  picked up on the next run (analyses/scores are per-run and resume cleanly).
- API: `GET /api/costs`.
- 7 new tests; ruff + mypy clean. No new dependencies.

### CP13 — Scheduler
- `findmyjob/scheduler.py`: `PipelineScheduler` (APScheduler `AsyncIOScheduler`
  with a `CronTrigger` from `AppSettings.run_time` / `run_timezone`,
  `misfire_grace_time=3600`, `coalesce`, `max_instances=1`). Started from the API
  lifespan (skipped in tests and when `APP_DISABLE_SCHEDULER=true`); a settings
  change to `run_time`/`run_timezone` reschedules it live (`maybe_reschedule`).
- `next_fire_time()` — compute the next run without a live scheduler (CLI).
- CLI: `findmyjob schedule status`.
- `deploy/*.plist.template` + `deploy/install-launchd.sh` + `just install-launchd`
  / `uninstall-launchd` — independent launchd fallback (daily + optional server).
- README scheduling section.
- 4 new tests; ruff + mypy clean. No new dependencies (APScheduler already
  declared; `apscheduler.*` added to the mypy ignore-missing-imports list).

### CP12 — Pipeline orchestrator wired + runs API
- `Orchestrator.open_run()` + `execute(run_id=…)` — open a run row, execute
  later (used for background triggering).
- `default_pipelines(fetch_only=…, no_llm=…)` + matching CLI flags
  (`findmyjob pipeline run --fetch-only --no-llm`).
- `services/runs`: `list_runs`, `run_detail` (stages + LLM usage summary),
  `start_background_run` (opens the run, runs the pipeline as an asyncio task).
- API: `GET /api/runs`, `GET /api/runs/{id}`, `POST /api/runs` (202, background),
  `GET /api/runs/{id}/events` (SSE progress, 1 s polling).
- Full 9-stage sequence registered: fetch → normalize → enrich → dedup →
  prefilter → analyze → score → judge → decide.
- Tests disable all job sources by default (`seeded_session`) so nothing hits a
  live API; `fetch` tests re-enable specific sources with respx.
- 7 new tests; ruff + mypy clean. No new dependencies.

### CP11 — Judge, blend, decision, documents
- `llm/judge`: `judge_fit()` + prompt + `JudgeResult` (holistic_fit 0-100,
  rationale, missing_qualifications, strengths_to_highlight, recommendation).
- `services/documents_needed.compute_documents_needed`: CV always; cover letter
  / transcript / references / portfolio from `documents_requested`; enrollment
  cert required if the posting demands enrolment, "likely" for
  Werkstudent/intern contracts; each entry flags whether the user has that doc.
- `services/profile.profile_summary_text` for the judge/cover-letter prompts.
- `pipelines/judge` (after `score`): only jobs with `hard_pass` and
  `soft_score >= threshold_maybe - 10`; writes holistic + rationale, sets
  `final_score = blend * soft + (1-blend) * holistic`, re-buckets `decision`.
- `pipelines/decide` (last): attaches the documents checklist to every scored
  job this run.
- 7 new tests; ruff + mypy clean. No new dependencies.

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
