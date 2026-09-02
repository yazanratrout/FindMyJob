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

_None yet._ The registry returns an empty list; a run currently opens and closes
a `Run` with no work. Pipelines are added from CP5 onward:

| Pipeline | Module | CP | Critical | Purpose |
|----------|--------|----|----------|---------|
| `fetch` | `pipelines/fetch.py` | CP5 | yes | Query allowlisted sources → `RawJob`s → `job` rows |
| `normalize` | `pipelines/normalize.py` | CP7 | no | Canonical shape, company resolution |
| `enrich` | `pipelines/enrich.py` | CP7 | no | Fetch full JD (robots-aware), JSON-LD merge |
| `dedup` | `pipelines/dedup.py` | CP8 | no | Exact / canonical-key / embedding dedup |
| `prefilter` | `pipelines/prefilter.py` | CP10 | no | Deterministic hard filters before any LLM |
| `analyze` | `pipelines/analyze.py` | CP9 | no | LLM structured extraction (cached) |
| `score` | `pipelines/score.py` | CP10 | no | Deterministic soft score + weights |
| `judge` | `pipelines/judge.py` | CP11 | no | LLM holistic fit, blend, decision |
| `decide` | `pipelines/decide.py` | CP11 | no | Bucket + documents checklist |
| `notify` | `pipelines/notify.py` | CP21 | no | Morning digest |

This table is updated as each pipeline is implemented, with a subsection
describing its inputs, outputs, stats and failure modes.
