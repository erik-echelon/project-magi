# Repo Audit: project-magi

**Date**: 2026-04-04
**Branch**: main
**Commit**: b891fb4
**Python version detected**: >=3.12 (running on 3.13.2)
**Package manager detected**: uv

## Codebase Summary

### Purpose
Multi-persona AI deliberation engine inspired by the MAGI supercomputer from Neon Genesis Evangelion. Multiple AI personas independently analyze questions, then deliberate across rounds with a critique agent synthesizing agreements and disagreements.

### Structure
```
project-magi/
├── src/project_magi/        # Main package (src layout)
│   ├── __init__.py           # Version string only
│   └── py.typed              # PEP 561 marker
├── tests/
│   ├── conftest.py           # Fixture loader helper
│   ├── test_init.py          # 4 placeholder tests
│   └── fixtures/             # Empty (with .gitkeep)
├── docs/
│   ├── philosophy.md
│   ├── PRD.md
│   └── epics.md
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── pyproject.toml
├── justfile
├── uv.lock
├── LICENSE
└── README.md
```

### Entry Points
None yet. The package is scaffolding only — no CLI entrypoints, no `__main__.py`, no scripts.

### Dependencies
0 runtime deps, 6 dev deps:
- pytest >=8.0 (installed: 9.0.2)
- pytest-cov >=6.0 (installed: 7.1.0)
- pytest-asyncio >=0.24 (installed: 1.3.0)
- pre-commit >=4.0 (installed: 4.5.1)
- ruff >=0.11 (installed: 0.15.9)
- ty >=0.0.1a7 (installed: 0.0.28)

No runtime dependencies yet. All dependencies are current.

### Test Coverage
Framework: pytest. 4 tests. 100% coverage (only 1 statement in the package so far). Coverage fail-under set to 90%.

### Infrastructure
None. No Docker, no cloud config, no deployment infrastructure. This is expected at the scaffolding stage.

## Modernization Checklist

### Package Management
- ✅ Uses uv as package manager
- ✅ `pyproject.toml` as single source of truth (no `setup.py` / `setup.cfg`)
- ✅ Has `uv.lock` lockfile
- ✅ No bare `requirements.txt`
- ✅ Dev dependencies separated via `[dependency-groups]`

### Python Version
- ✅ Python >=3.12 specified in `requires-python`
- ❌ No `.python-version` file present
- ✅ Version pinned in `pyproject.toml`

### Linting / Formatting
- ✅ `ruff` installed and configured
- ⚠️ `ruff format` available via `just format` but not included in `just check`
- ✅ No redundant linters
- ✅ Ruff config in `pyproject.toml`

### Type Checking
- ✅ `ty` installed and configured
- ✅ Type check command in CI (via `just check` → `just typecheck`)
- ✅ `py.typed` marker present
- ✅ Key module has type annotations

### Testing
- ✅ `pytest` is the test runner
- ✅ `pytest` config in `pyproject.toml`
- ✅ Tests exist (4 tests)
- ✅ Coverage reporting configured with fail-under=90

### Task Runner
- ✅ `justfile` present with: `lint`, `format`, `typecheck`, `test`, `test-integration`, `coverage`, `check`, `clean`
- ✅ All common tasks documented in one place

### CI/CD
- ✅ GitHub Actions present
- ⚠️ CI runs lint + typecheck + test but does not pin a specific Python version — relies on ubuntu-latest default
- ⚠️ CI does not run `ruff format --check` (formatting violations won't be caught)

### Code Quality
- ✅ No committed secrets or hardcoded credentials
- ✅ `.gitignore` covers `.venv`, `__pycache__`, `*.pyc`, `.env`, `dist/`, `*.egg-info/`, `.ruff_cache/`, `.ty_cache/`
- ✅ No debug `print()` statements

### Claude Code / AI Tooling
- ❌ No `CLAUDE.md` present
- N/A `.claude/commands/` (no commands yet, appropriate at this stage)

### Documentation
- ✅ `README.md` explains purpose and philosophy
- ⚠️ `README.md` does not include install instructions or how to run tests
- ❌ No changelog or version history

## Priority Recommendations

**High** (blocks development workflow or CI reliability):
1. Add `CLAUDE.md` with: project purpose, install instructions (`uv sync --dev`), how to run tests (`just check`), architecture notes, and pointer to docs/
2. Add Python version to CI workflow (e.g., `uv python install 3.12` or use `setup-python` action) so CI doesn't silently drift
3. Add `ruff format --check` to `just check` so formatting is enforced in CI, not just in pre-commit

**Medium** (important for consistency):
4. Add `.python-version` file (e.g., `3.12`) so uv and other tools pick up the expected version
5. Add install/development instructions to `README.md` ("How to install", "How to run tests")
6. The pre-commit ruff hook rev (`v0.11.13`) is behind the installed ruff (`0.15.9`) — update the rev to stay in sync

**Low** (nice to have):
7. Add a `CHANGELOG.md` — even a minimal "## 0.1.0 - Scaffolding" entry establishes the convention
8. Consider adding `"ANN"` (flake8-annotations) to ruff lint selects to enforce type annotations as the codebase grows

## Open Questions
- The `conftest.py` imports `json` and `pathlib` at module level without `TYPE_CHECKING` guards, while `test_init.py` uses `TYPE_CHECKING` for `Path`. This inconsistency is harmless but worth deciding on a convention early — should test helpers use `TYPE_CHECKING` guards or not?
