# CLAUDE.md

## Project

Project MAGI is a multi-persona AI deliberation engine inspired by Evangelion's MAGI supercomputer. Multiple AI personas independently analyze a question, then deliberate across rounds with a critique agent synthesizing agreements and disagreements.

See `docs/philosophy.md` for design philosophy, `docs/PRD.md` for product requirements, `docs/user-guide.md` for usage documentation.

## Setup

```bash
uv sync --dev
uv run pre-commit install
```

Create a `.env` file with `ANTHROPIC_API_KEY=sk-ant-...` for integration tests and CLI usage.

## Development Commands

All tasks are in the `justfile`:

```bash
just check            # Run lint + typecheck + test (the CI gate)
just lint             # Ruff linter + format check
just format           # Ruff formatter
just typecheck        # ty type checker
just test             # Unit tests with coverage (90% threshold)
just test-integration # Integration tests (hits real API, costs tokens)
just coverage         # Coverage report with HTML output
just clean            # Remove build artifacts
```

## Project Structure

```
src/project_magi/
├── __init__.py           # Public API: MagiSession, MagiResult
├── session.py            # MagiSession facade
├── cli.py                # CLI entry point (magi command)
├── agents/
│   ├── output.py         # PersonaOutput, Finding schemas
│   ├── runner.py         # Persona agent runner, parallel execution
│   └── critique.py       # Critique agent, findings dedup
├── coordinator/
│   ├── checkpoint.py     # Checkpoint action parsing
│   ├── complexity_gate.py # LLM-based triage
│   └── loop.py           # Deliberation loop orchestration
├── personas/
│   ├── model.py          # Persona data model
│   ├── parser.py         # .md file parser, discovery
│   └── builder.py        # Persona suggestion generator
├── providers/
│   ├── base.py           # Provider protocol, Message, Attachment
│   └── claude.py         # ClaudeProvider (Anthropic SDK)
└── reporting/
    └── renderer.py       # Markdown report renderer

.claude/agents/           # Claude Code agent definitions
├── melchior.md           # The Scientist persona
├── balthasar.md          # The Mother persona
├── casper.md             # The Woman persona
├── magi.md               # Main deliberation skill
└── magi-builder.md       # Persona builder skill

tests/                    # pytest
tests/fixtures/           # Recorded API response fixtures
docs/                     # Philosophy, PRD, epics, user guide, capstone
```

## Testing

- **Unit tests:** `just test` — 256 tests, 90% coverage required, runs on every commit
- **Integration tests:** `just test-integration` — 7 tests hitting real Claude API, marked with `@pytest.mark.integration`
- **Recorded fixtures** in `tests/fixtures/` bridge unit and integration testing
- Default model for library: `claude-opus-4-6`. Integration tests use `claude-sonnet-4-20250514` to save cost.
