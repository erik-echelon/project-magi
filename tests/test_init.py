"""Basic tests to verify project setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

import project_magi
from tests.conftest import FIXTURES_DIR

if TYPE_CHECKING:
    from pathlib import Path


def test_version_exists() -> None:
    assert hasattr(project_magi, "__version__")
    assert isinstance(project_magi.__version__, str)
    assert len(project_magi.__version__) > 0


def test_version_is_semver() -> None:
    parts = project_magi.__version__.split(".")
    assert len(parts) == 3
    for part in parts:
        assert part.isdigit()


def test_fixtures_dir_exists() -> None:
    assert FIXTURES_DIR.exists()
    assert FIXTURES_DIR.is_dir()


def test_load_fixture_missing(fixtures_dir: Path) -> None:
    import pytest

    from tests.conftest import load_fixture

    with pytest.raises(FileNotFoundError, match="Fixture not found"):
        load_fixture("nonexistent.json")
