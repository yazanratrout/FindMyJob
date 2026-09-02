# Pipelines

How the pipeline framework works, and what each concrete pipeline does. Rules
for adding/changing one: [`../rules/PIPELINE_RULES.md`](../rules/PIPELINE_RULES.md).

## The framework

Three pieces in `src/findmyjob/pipelines/`:

### `base.py` — the contract

- **`Pipeline`** (ABC): `name` (unique, stable), `critical` (bool),
  `should_run(ctx) -> bool`, `async run(ctx) -> PipelineResult`.
- **`PipelineResult`**: `status` (`OK` / `PARTIAL` / `FAILED` / `SKIPPED`),
  `stats: dict[str,int]`, `errors: list[PipelineError]`, timing. Helpers:
  `bump(key)`, `add_error(scope, exc)`, `finalize_status()` (OK→PARTIAL if any
  errors were recorded).
- **`PipelineError`**: `scope`, `message`, `exc_type`.

### `context.py` — what a pipeline receives

**`PipelineContext`**: `run_id`, `trigger`, `app_settings` (a detached snapshot
of the `AppSettings` row — safe to read across sessions), `logger` (bound with
`run_id`), `state` (scratch dict for hand-offs the DB shouldn't carry), and
`session()` — a transactional session context manager.

### `orchestrator.py` — the runner

`Orchestrator(pipelines).execute(trigger=...)`:

1. opens a `Run` row (`status=RUNNING`);
2. loads the settings snapshot, builds the `PipelineContext`;
3. for each pipeline, in order:
   - `should_run()` false → `SKIPPED`;
   - otherwise run it inside a try/except **crash barrier**, timed;
   - an uncaught exception becomes a `FAILED` result (the run does not die);
   - persist a `PipelineRun` row; roll `stats` up onto the `Run` as
     `"<pipeline>.<key>"`; append any errors to `Run.errors`;
   - if the result is `FAILED` **and** the pipeline is `critical`, stop.
4. close the `Run` (`COMPLETED`, or `FAILED` if a critical stage failed).

The orchestrator holds **no stage-specific logic**. The ordered list is built by
`registry.py::default_pipelines()` and nowhere else.

### `registry.py` — the sequence

`default_pipelines()` returns the ordered list. `build_default_orchestrator()`
wraps it. Add a pipeline here at the right position when its checkpoint lands.

---

## Concrete pipelines

Registered: `fetch` → `normalize` → `enrich` → `dedup` → `prefilter` →
`analyze` → `score` → `judge` → `decide`. `notify` lands in CP21.

| Pipeline | Module | CP | Critical | Status | Purpose |
|----------|--------|----|----------|--------|---------|
| `fetch` | `pipelines/fetch.py` | CP5 | yes | ✅ | Query allowlisted sources → `RawJob`s → `job` rows |
| `normalize` | `pipelines/normalize.py` | CP7 | no | ✅ | Company resolution, title/remote tidy-up |
| `enrich` | `pipelines/enrich.py` | CP7 | no | ✅ | Fetch full JD (robots-aware), JSON-LD merge |
| `dedup` | `pipelines/dedup.py` | CP8 | no | ✅ | Canonical-key + embedding dedup |
| `prefilter` | `pipelines/prefilter.py` | CP10 | no | ✅ | Cheap deterministic hard filters |
| `analyze` | `pipelines/analyze.py` | CP9 | no | ✅ | LLM structured extraction (cached) |
| `score` | `pipelines/score.py` | CP10 | no | ✅ | Analysis hard checks + weighted soft score |
| `judge` | `pipelines/judge.py` | CP11 | no | ✅ | LLM holistic fit, blend, decision |
| `decide` | `pipelines/decide.py` | CP11 | no | ✅ | Documents checklist |
| `notify` | `pipelines/notify.py` | CP21 | no | ⬜ | Morning digest |

### `fetch` (CP5, critical)

- **In:** `AppSettings` (via `build_source_query`) → a `SourceQuery`; every
  source enabled in `sources_enabled` and configured (credentials present).
- **Out:** new rows in `job` (idempotent upsert by `source_key` +
  `source_job_id`); existing postings get `last_seen_at` bumped.
- **Sources:** API connectors (Bundesagentur für Arbeit, Adzuna, Arbeitnow,
  The Muse — `sources/api/`), ATS connectors that fan out over the curated
  company registry (Greenhouse, Lever, Personio, SmartRecruiters, Ashby —
  `sources/ats/`), and a JSON-LD extractor for career pages with no known ATS
  (`sources/jsonld`, robots-aware). All rate-limited/retried by `HttpClient`;
  `build_sources` keeps only the ones enabled in `sources_enabled` and
  configured (credentials present, or ≥1 matching company).
- **Stats:** `sources_active`, `found`, `new`, `found.<source>`.
- **Failure:** a source that errors is recorded (`source:<key>`) and skipped;
  a malformed posting is recorded (`job:<source>:<id>`) and skipped. The stage
  returns `PARTIAL`, never aborts the run. Only an unexpected crash → `FAILED`
  (and, being critical, that aborts the run).

### `normalize` (CP7)

- **In:** jobs with `company_id IS NULL`.
- **Out:** `company_id` set (matching a registry row by normalized name, or a
  new inactive `origin=discovered` company); `normalized_title` backfilled;
  `is_remote` inferred from `location_raw`.
- **Stats:** `linked`, `companies_discovered`.
- Deterministic, no network. Idempotent (only touches unlinked jobs).

### `enrich` (CP7)

- **In:** active jobs whose `jd_text` is missing or under 400 chars (capped at
  200 per run).
- **Out:** `jd_text` + `jd_content_hash` replaced when the fetched content is
  longer; `lifecycle=dead` on 403/404/410.
- **How:** robots.txt-gated fetch via `HttpClient` → `trafilatura` main-content
  extraction + `JobPosting` JSON-LD merge (`services/enrich.enrich_url`).
- **Stats:** `fetched`, `enriched`, `dead`, `robots_blocked`.
- `EnrichPipeline(http_factory=…)` is injectable for tests.

### `dedup` (CP8)

- **In:** active jobs (all runs), oldest first.
- **Tier 2 — canonical key:** `normalized_company | normalized_title`. The
  earliest job with a key owns it; later jobs get `canonical_job_id = owner`.
- **Tier 3 — semantic:** embed `title + jd_text[:2000]` (`services/embeddings`,
  local `fastembed`), compare within the same company, link pairs with cosine
  ≥ 0.92. Vectors are stored in `job_embedding` and reused on later runs.
  Skipped entirely (stat `semantic_skipped`) if the model can't load.
- **Stats:** `linked_by_key`, `embedded`, `linked_by_embedding`.
- `DedupPipeline(embedder=…)` is injectable; tests pass a fake (no download).

Downstream pipelines (CP9+) only consider **canonical** jobs
(`canonical_job_id IS NULL`).

### `analyze` (CP9)

- **In:** canonical, active jobs with real `jd_text` and no `JobAnalysis` at the
  current `ANALYZER_VERSION` (capped at 120/run).
- **Out:** a `job_analysis` row — must/nice haves, skills, languages, weekly
  hours, contract type, salary, dates, enrollment/English-only/application
  method, documents requested, seniority, red flags, and a `source_snippets`
  provenance map (field → verbatim quote).
- **How:** `services/analyze.analyze_job` → `llm/analyzer.analyze_posting`
  (cheap model, JSON mode + repair). The LLM client's content-hash cache means
  the same posting seen on two sources costs one call.
- **Stats:** `analyzed`, `cache_hits`, `already_analyzed`, `skipped_thin_text`.
- `AnalyzePipeline(client_factory=…)` is injectable for tests.
- Runs *after* `prefilter` so deterministic rejects never reach the model.

### `prefilter` (CP10)

- **In:** canonical active jobs. **Out:** a per-run `JobScore` with
  `hard_pass` + `hard_failures` (recency, `blacklist:<kw>`, `location`);
  failures also set `decision=archived`. `analyze` skips these jobs.

### `score` (CP10)

- **In:** this run's `JobScore` rows that passed `prefilter` and now have a
  current `JobAnalysis`.
- **Out:** analysis hard checks may flip `hard_pass` off (`hours`,
  `language:<lang>`, `contract_type`, `job_type`); otherwise `soft_score` +
  `soft_breakdown` (8 components, each raw/weight/contribution), a provisional
  `final_score = soft_score` and `decision` via `bucket()`. `judge` (CP11)
  blends in the LLM holistic score.
- **Stats:** `scored`, `hard_failed_analysis`, `no_analysis`,
  `decision.<bucket>`.

### `judge` (CP11)

- **In:** this run's `JobScore` rows with `hard_pass` and
  `soft_score >= threshold_maybe - 10` (a clear reject isn't worth a smart call).
- **Out:** `llm_holistic`, `llm_rationale`, `missing_qualifications`,
  `strengths_to_highlight`; `final_score = blend*soft + (1-blend)*holistic`;
  `decision` re-bucketed. `llm/judge.judge_fit` (smart model).
- **Stats:** `judged`, `cache_hits`, `decision.<bucket>`.

### `decide` (CP11)

- **In:** every `JobScore` this run with an analysis.
- **Out:** `documents_needed` — a checklist (`doc_type`, `necessity`
  required/likely/optional, `reason`, `have`) from
  `services/documents_needed.compute_documents_needed`. Deterministic.
