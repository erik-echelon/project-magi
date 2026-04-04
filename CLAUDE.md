# CLAUDE.md

## Project

Project MAGI is a multi-persona AI deliberation engine. See `docs/philosophy.md` for the design philosophy and `docs/PRD.md` for the full product requirements.

## Setup

```bash
uv sync --dev
uv run pre-commit install
```

## Development Commands

All tasks are in the `justfile`:

```bash
just check            # Run lint + typecheck + test (the CI gate)
just lint             # Ruff linter
just format           # Ruff formatter
just typecheck        # ty type checker
just test             # Unit tests with coverage (90% threshold)
just test-integration # Integration tests (hits real API)
just coverage         # Coverage report with HTML output
just clean            # Remove build artifacts
```

## Project Structure

```
src/project_magi/     # Main package (src layout)
tests/                # Tests (pytest)
tests/fixtures/       # Recorded API response fixtures for unit tests
docs/                 # Philosophy, PRD, epics
.claude/agents/       # Claude Code agent definitions (personas, coordinator, etc.)
```

## Key Architecture

- **Personas** are defined as Claude Code agent `.md` files in `.claude/agents/`
- The system has four agent roles: coordinator, persona agents, critique agent, persona builder
- The core engine is a Python library; the Claude Code skill is a thin consumer
- See `docs/epics.md` for the implementation plan

## Testing

- Unit tests: `just test` (90% coverage required, runs on every commit)
- Integration tests: `just test-integration` (hits real Claude API, marked with `@pytest.mark.integration`)
- Recorded API fixtures in `tests/fixtures/` bridge unit and integration testing
