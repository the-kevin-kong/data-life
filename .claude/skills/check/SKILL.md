---
name: check
description: Run the data-life pre-PR quality gate — ruff lint + format, mypy strict, pytest — via `just check`. Use before proposing a commit or PR, or when asked to "run checks", "lint", "typecheck", "run the tests", or "make sure this passes CI".
---

# check — quality gate

Run the same gate CI runs, in order, and stop at the first failure.

## Steps

1. Run the whole gate:
   ```bash
   just check
   ```
   This is `just lint` (`uv run ruff check .` + `uv run ruff format --check .`) → `just typecheck`
   (`uv run mypy packages services apps`) → `just test` (`uv run pytest`).

2. If a stage fails, **stop** and report the shortest decisive output — the failing file:line and
   rule/error, not the whole log. Fix, then re-run `just check`.

3. To auto-fix formatting/lint first: `just fmt` (`ruff check --fix` + `ruff format`), then
   re-run `just check`.

## What CI enforces (match it)

- **ruff**: `line-length 100`, selects `E,F,I,UP,B,SIM,TID,RUF`. Tests may use `assert`.
- **mypy**: `strict`. For a third-party lib without stubs, add it to the
  `[[tool.mypy.overrides]] ignore_missing_imports` list in root `pyproject.toml` — do **not**
  scatter `# type: ignore`.
- **pytest**: pure-unit only, no network/GCP. `asyncio_mode = "auto"` (async tests need no
  decorator).

## Gotchas

- **ruff source of truth is `just lint`** (local/CI ruff from `uv.lock`). The pre-commit hook
  pin is kept in sync with it, so `uvx pre-commit run --all-files` and `just lint` agree — if they
  ever diverge, `just lint` wins and the pre-commit `rev` in `.pre-commit-config.yaml` should be
  bumped to the `uv run ruff --version`.
- **Pre-commit checks the staged blob**, not the working tree. `git add` your fixes before
  committing, or the hook re-flags the old content.
- Don't skip hooks (`--no-verify`) to get a commit through — fix the finding.
