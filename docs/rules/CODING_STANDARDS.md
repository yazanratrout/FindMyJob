# Coding standards

## Language & tooling

- Python 3.12+ (3.13 in dev). `from __future__ import annotations` in every
  module.
- `ruff` for lint + format (config in `pyproject.toml`). `mypy` for types.
- `just check` = `ruff check` + `ruff format --check` + `mypy` + `pytest`. It
  must pass before every commit.

## Structure

- `src/findmyjob/` package layout. One concern per module.
- Layers and their direction of dependency (never import upward):
  ```
  api/  ->  services/  ->  {llm/, sources/, pipelines/}  ->  models/  ->  db.py, config.py
  ```
- `pipelines/` may use `services/`, `llm/`, `sources/`. Pipelines never import
  each other.
- No business logic in `api/` route handlers — they validate input, call a
  service, shape the response.

## Models

- SQLModel tables in `models/`. No ORM `Relationship` fields — use explicit
  `select()` queries. This keeps behaviour predictable across the session
  boundaries that pipelines cross.
- JSON-shaped columns are `list`/`dict` with `sa_column=Column(JSON)` and a
  `default_factory`.
- Timestamps via `TimestampMixin`. Store naive UTC (`models.base.utcnow`).
- Every model change → a reviewed Alembic migration (see
  [`GIT_AND_MIGRATIONS.md`](./GIT_AND_MIGRATIONS.md)).

## Typing

- Public functions and methods have typed parameters and return types.
- Prefer `X | None` over `Optional[X]`; `list`/`dict` over `List`/`Dict`.
- `sqlmodel.col(Model.field)` in `where` / `order_by` to keep mypy happy.
- Avoid `# type: ignore` except at genuine third-party boundaries; annotate why.

## Errors

- Services raise typed exceptions (`ValueError` subclasses or domain errors).
- Route handlers translate those into `HTTPException` with a useful `detail`.
- Pipelines catch per-item errors and record them; they do not crash the run.
- `llm/client.py` raises `LlmError` for any model failure.

## Logging

- `structlog` via `findmyjob.logging.get_logger(name)`.
- Event names are `dotted.lower_snake` (`pipeline.done`, `documents.saved`).
- Bind context (`run_id`, `pipeline`, ids) rather than formatting into strings.
- No secrets or full document text in logs.

## Tests

- `pytest`, one test module per source area. Fixtures in `tests/conftest.py`
  give every test a fresh, isolated SQLite schema.
- The LLM network call is injected (`LlmClient(api_fn=...)`) — tests never hit
  the network. Use `tests/fakes.py`.
- HTTP calls to job sources are mocked with `respx`.
- Deterministic logic (scoring, dedup, normalization) gets table-driven tests.
- A checkpoint isn't done until its behaviour is covered.

## Comments

- Module docstring: what this file is for, one paragraph.
- Docstrings on non-obvious public functions. Skip them for self-evident ones.
- Comments explain *why*, not *what*.
