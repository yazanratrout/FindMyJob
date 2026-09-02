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

Registered so far: **`fetch`** (CP5). The rest are added per checkpoint.

| Pipeline | Module | CP | Critical | Status | Purpose |
|----------|--------|----|----------|--------|---------|
| `fetch` | `pipelines/fetch.py` | CP5 | yes | ✅ | Query allowlisted sources → `RawJob`s → `job` rows |
| `normalize` | `pipelines/normalize.py` | CP7 | no | ⬜ | Canonical shape, company resolution |
| `enrich` | `pipelines/enrich.py` | CP7 | no | ⬜ | Fetch full JD (robots-aware), JSON-LD merge |
| `dedup` | `pipelines/dedup.py` | CP8 | no | ⬜ | Exact / canonical-key / embedding dedup |
| `prefilter` | `pipelines/prefilter.py` | CP10 | no | ⬜ | Deterministic hard filters before any LLM |
| `analyze` | `pipelines/analyze.py` | CP9 | no | ⬜ | LLM structured extraction (cached) |
| `score` | `pipelines/score.py` | CP10 | no | ⬜ | Deterministic soft score + weights |
| `judge` | `pipelines/judge.py` | CP11 | no | ⬜ | LLM holistic fit, blend, decision |
| `decide` | `pipelines/decide.py` | CP11 | no | ⬜ | Bucket + documents checklist |
| `notify` | `pipelines/notify.py` | CP21 | no | ⬜ | Morning digest |

### `fetch` (CP5, critical)

- **In:** `AppSettings` (via `build_source_query`) → a `SourceQuery`; every
  source enabled in `sources_enabled` and configured (credentials present).
- **Out:** new rows in `job` (idempotent upsert by `source_key` +
  `source_job_id`); existing postings get `last_seen_at` bumped.
- **Sources:** Bundesagentur für Arbeit, Adzuna, Arbeitnow, The Muse
  (`sources/api/`). Each is rate-limited and retried by the shared `HttpClient`.
- **Stats:** `sources_active`, `found`, `new`, `found.<source>`.
- **Failure:** a source that errors is recorded (`source:<key>`) and skipped;
  a malformed posting is recorded (`job:<source>:<id>`) and skipped. The stage
  returns `PARTIAL`, never aborts the run. Only an unexpected crash → `FAILED`
  (and, being critical, that aborts the run).

Later pipelines pick up from `job`: `normalize` resolves companies, `enrich`
fills missing descriptions, `dedup` links duplicates.
