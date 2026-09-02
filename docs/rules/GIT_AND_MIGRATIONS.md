# Git & migrations

## Commits

- One commit per checkpoint (or per coherent sub-step of a large checkpoint).
- The commit includes: code + tests + docs updates (`CHANGELOG.md`,
  `PROGRESS.md`, affected explanation files, `README.md` if relevant).
- `just check` passes before committing.
- Message format:
  ```
  CPn: short summary

  - bullet of what changed
  - bullet of what changed

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
- PR descriptions (if ever used) end with:
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

## Never commit

- `.env` or any real secret.
- Anything under `data/` (db, uploaded documents, generated letters, model
  cache) — it is git-ignored; keep it that way.
- `.venv/`, caches, build artifacts.

Check with `git status` before `git add -A`. `git check-ignore .env data/…`
should confirm they're ignored.

## Migrations

Every change to a `models/` table requires a migration.

1. Make the model change.
2. Ensure the dev DB is current: `just db-upgrade`
3. Autogenerate: `just db-revision "short message"`
4. **Read the generated file** in `migrations/versions/`. Autogenerate misses
   some things (server defaults, column type changes on SQLite need
   `batch_alter_table` — already configured via `render_as_batch`). Fix by hand
   if needed.
5. Apply: `just db-upgrade`
6. `tests/test_migrations.py` must pass — it fails the build if the models and
   the migration head disagree.

- Never edit a migration that has already been committed and applied; add a new
  one.
- The initial migration may be regenerated freely *until it is committed*.
- Keep `alembic.ini`'s `sqlalchemy.url` blank — it's injected from
  `findmyjob.config` in `migrations/env.py`.
