# Dependency rule

**Whenever a library is about to be used and it is not already installed, add it
to the requirements file first.**

This is a hard rule. Code must never import a package that is only
transitively available (pulled in as someone else's dependency) — that breaks
the moment the intermediate package drops it.

## The procedure

Before writing an `import` for a package that is not already in
`requirements.txt` or `requirements-dev.txt`:

1. Decide which file it belongs in:
   - **`requirements.txt`** — needed at runtime by the app or pipelines.
   - **`requirements-dev.txt`** — only needed for tests, linting, type stubs,
     or local tooling.
2. Add a line with a **minimum version** (`package>=X.Y`), grouped under the
   right comment heading, kept alphabetical within the group.
3. Reinstall: `.venv/bin/pip install -r requirements-dev.txt`
4. Refresh the lock file: `just lock`
   (`.venv/bin/pip freeze --exclude-editable > requirements.lock`)
5. Only now write the code that imports it.
6. Mention the new dependency in the checkpoint's `CHANGELOG.md` entry.

## Choosing a version

- Pick the lowest version that has the API you need (so the range stays wide).
- No upper bound unless a known-bad major release exists.
- Prefer packages that don't drag heavy transitive trees. Example: this project
  uses `fastembed` (ONNX, small) instead of `sentence-transformers` (PyTorch,
  ~800 MB) for embeddings.

## Type stubs

If `mypy` reports missing stubs for a new runtime package, either add the stub
package to `requirements-dev.txt` (`types-<pkg>`) or add the module to the
`ignore_missing_imports` override list in `pyproject.toml` `[tool.mypy]`.

## Never

- Never `pip install` something without adding it to a requirements file.
- Never import a package "because it's already in the venv" without checking it
  is declared.
- Never leave `requirements.lock` stale after adding a dependency.
