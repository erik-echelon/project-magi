# Project MAGI — development commands

set dotenv-load

# Run ruff linter and format check
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Run ruff formatter
format:
    uv run ruff format src/ tests/

# Run ty type checker
typecheck:
    uv run ty check

# Run unit tests with coverage
test:
    uv run pytest --cov --cov-report=term-missing --cov-fail-under=90 -m "not integration"

# Run integration tests (hits real API, costs tokens)
test-integration:
    uv run --env-file .env pytest -m integration -v || [ $? -eq 5 ]

# Show coverage report
coverage:
    uv run pytest --cov --cov-report=term-missing --cov-report=html -m "not integration"

# Run all checks (lint + typecheck + test)
check: lint typecheck test

# Clean build artifacts
clean:
    rm -rf .coverage htmlcov/ .pytest_cache/ .ruff_cache/ .ty_cache/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
