# Pipeline rules

How to add or change a pipeline without breaking the rest of the system. See
[`../implementation/PIPELINES.md`](../implementation/PIPELINES.md) for how the
framework works and what each existing pipeline does.

## The contract

A pipeline subclasses `findmyjob.pipelines.base.Pipeline`:

```python
class MyPipeline(Pipeline):
    name = "my-stage"          # unique, stable, kebab-case
    critical = False           # True => a FAILED result aborts the whole run

    def should_run(self, ctx: PipelineContext) -> bool:
        return ctx.app_settings.some_toggle       # optional; default True

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()                        # status OK by default
        with ctx.session() as session:
            for item in self._load(session):
                try:
                    self._process(item, session)
                    res.bump("processed")
                except Exception as exc:
                    res.add_error(f"item:{item.id}", exc)
        res.finalize_status()                       # OK -> PARTIAL if errors
        return res
```

## Rules

1. **No cross-pipeline imports.** Need something another stage produced? Read it
   from the database. Need to share a helper? Put it in `services/` or a plain
   module, not in a pipeline.
2. **Isolate per-item failure.** One bad job/source/row must not stop the stage.
   Catch, record via `res.add_error(...)`, continue.
3. **Raise only for stage-wide failure** (e.g. a required config missing). The
   orchestrator turns an uncaught exception into a `FAILED` result; that aborts
   the run only if `critical = True`.
4. **Idempotent.** Guard writes so a re-run doesn't duplicate. Use natural keys,
   `ON CONFLICT`-style checks, or "already processed this run" checks.
5. **Cheap before expensive.** Inside the pipeline, filter deterministically
   before calling `llm/`. If the stage is LLM-heavy, check the budget
   (`services/cost.py`, from CP14) and stop cleanly when exhausted — set a stat
   and let the next run continue.
6. **Own transaction scope.** Use `ctx.session()` (commits on success, rolls
   back on error). Keep transactions short.
7. **Report stats.** `res.bump("<countable>")` for everything the run summary
   and digest will want: `found`, `new`, `duplicates`, `analyzed`,
   `recommended`, …
8. **Register in one place.** Add the pipeline to the ordered list in
   `pipelines/registry.py::default_pipelines()` at the correct position. Nothing
   else changes.
9. **Test it in isolation.** Construct the pipeline, build a `PipelineContext`
   (or use the orchestrator test helpers), seed the DB with inputs, assert the
   outputs and the `PipelineResult`. Mock network and LLM.
10. **Document it.** Add a section to `docs/implementation/PIPELINES.md`.

## Execution order (target)

```
fetch → normalize → enrich → dedup → prefilter → analyze → score → judge
      → decide → notify
```

`fetch` is `critical` (no jobs, nothing to do). The rest are non-critical: a
failure is contained and the run still completes with whatever got through.
