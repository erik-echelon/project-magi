"""Shared test configuration and fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


def load_fixture(name: str) -> dict:
    """Load a JSON fixture by name from tests/fixtures/."""
    path = FIXTURES_DIR / name
    if not path.exists():
        msg = f"Fixture not found: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text())
