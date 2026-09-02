# Working rules

The agreement for how work on FindMyJob is done. Read this before starting a
checkpoint. Every rule here is a hard requirement, not a preference.

Companion documents in this folder:

- [`CODING_STANDARDS.md`](./CODING_STANDARDS.md) — style, typing, structure, tests
- [`DEPENDENCIES.md`](./DEPENDENCIES.md) — the "add it before you import it" rule
- [`GIT_AND_MIGRATIONS.md`](./GIT_AND_MIGRATIONS.md) — commits, secrets, schema changes
- [`PIPELINE_RULES.md`](./PIPELINE_RULES.md) — adding or changing a pipeline safely

---

## 1. Pipelines are independent

- Every processing stage is its own module under `src/findmyjob/pipelines/`,
  implementing the `Pipeline` contract from `pipelines/base.py`.
- A pipeline may read and write the database. It **must not import another
  pipeline** or depend on another pipeline's in-memory state.
- A pipeline must be replaceable in isolation: rewriting or removing one cannot
  break the others.
- A pipeline is individually robust: catch per-item errors, record them in
  `PipelineResult.errors`, keep going, return `PARTIAL`. Only raise when the
  whole stage is meaningless.
- A pipeline is idempotent: running it twice over the same data must not
  double-write.

## 2. One orchestrator

- `pipelines/orchestrator.py` is the only component that knows the whole
  sequence. It owns the `Run` lifecycle, the per-stage crash barrier, timing,
  `PipelineRun` records and stat roll-up.
- The ordered pipeline list lives **only** in `pipelines/registry.py`.
- The orchestrator never contains stage-specific logic.

## 3. Cheap before expensive

- Deterministic filters, cache lookups and heuristics run before any LLM call.
- Never send something to the model that a rule could have decided.
- Every LLM call goes through `llm/client.py`: content-hash cache, token/cost
  accounting, monthly EUR budget. No direct `anthropic` calls elsewhere.

## 4. Clean repository

- `src/` layout. One concern per module. Public functions are typed and, where
  non-obvious, have a docstring. Modules have a one-paragraph docstring.
- `ruff check`, `ruff format --check` and `mypy` are clean before every commit.
- Every checkpoint adds tests. `just check` passes before every commit.
- Follow the structure in the implementation plan §2.3.

## 5. Secrets only in `.env`

- API keys, passwords, tokens: read from the environment / `.env` only.
- `.env` is git-ignored; `.env.example` documents every key with a placeholder.
- User preferences (city, keywords, weights, schedule) are **not** secrets —
  they live in the `app_settings` table.
- Nothing under `data/` is ever committed.

## 6. Reproducible environment

- All code and tooling run inside `./.venv`.
- `requirements.txt` (pinned minimums) + `requirements.lock` (exact, via
  `pip freeze`) + `requirements-dev.txt`. Keep the lock file current.

## 7. Add a dependency before you import it

See [`DEPENDENCIES.md`](./DEPENDENCIES.md). In short: if you're about to
`import` something that isn't already declared, stop, add it to the right
requirements file with a minimum version, reinstall, refresh the lock file,
then write the code.

## 8. Keep the docs current

After every checkpoint, in the same commit:

- add a `CHANGELOG.md` entry (what changed, which CP);
- update `PROGRESS.md` (status, what's next, new gaps);
- update any explanation file in `docs/implementation/` the change affects
  (`PIPELINES.md`, `ARCHITECTURE.md`, `USER_GUIDE.md`, …);
- update the top-level `README.md` if the user-facing picture changed.

## 9. Scope discipline

- Build one checkpoint at a time, in order. Finish it (code + tests + docs +
  green `just check` + commit) before starting the next.
- Don't scaffold things a later checkpoint owns unless the plan says to.
- Never add job sources that forbid automated access (LinkedIn, StepStone,
  Indeed, Xing, Glassdoor). Allowlist only — see the plan §4.

## 10. Human-in-the-loop stays

The pipeline recommends; the user decides to apply, triggers the cover letter,
reviews it, and submits. No automated application submission, ever.
