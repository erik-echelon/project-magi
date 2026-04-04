"""Tests for the CLI entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_magi.cli import main

if TYPE_CHECKING:
    from pathlib import Path


class TestCLIArgParsing:
    def test_deliberate_requires_question(self) -> None:
        with pytest.raises(SystemExit), patch("sys.argv", ["magi", "deliberate"]):
            main()

    def test_suggest_requires_task(self) -> None:
        with pytest.raises(SystemExit), patch("sys.argv", ["magi", "suggest-personas"]):
            main()

    def test_no_command_fails(self) -> None:
        with pytest.raises(SystemExit), patch("sys.argv", ["magi"]):
            main()


class TestCLIDeliberateExecution:
    def _make_mock_result(self) -> MagicMock:
        mock_result = MagicMock()
        mock_result.report = "# Test Report\n\nTest content."
        mock_result.round_count = 1
        mock_result.state.stopped_reason = "max_rounds"
        mock_result.dimension_map = []
        mock_result.consensus = []
        mock_result.disagreements = []
        mock_result.findings = []
        mock_result.persona_positions = []
        return mock_result

    def test_auto_mode_runs_without_checkpoint(self) -> None:
        from project_magi.session import MagiSession

        mock_result = self._make_mock_result()

        with (
            patch("sys.argv", ["magi", "deliberate", "Test question?", "--auto"]),
            patch.object(MagiSession, "__init__", return_value=None),
            patch.object(
                MagiSession, "deliberate", new_callable=AsyncMock, return_value=mock_result
            ) as mock_deliberate,
        ):
            main()

            mock_deliberate.assert_called_once()
            # --auto means on_checkpoint should not be passed
            call_kwargs = mock_deliberate.call_args
            assert call_kwargs.kwargs.get("on_checkpoint") is None

    def test_output_flag_writes_file(self, tmp_path: Path) -> None:
        from project_magi.session import MagiSession

        output_file = tmp_path / "report.md"
        mock_result = self._make_mock_result()
        mock_result.report = "# Test Report\n\nReport content here."

        with (
            patch(
                "sys.argv",
                ["magi", "deliberate", "Test?", "--auto", "-o", str(output_file)],
            ),
            patch.object(MagiSession, "__init__", return_value=None),
            patch.object(
                MagiSession, "deliberate", new_callable=AsyncMock, return_value=mock_result
            ),
        ):
            main()

        assert output_file.exists()
        assert "Report content here" in output_file.read_text()

    def test_interactive_mode_passes_checkpoint(self) -> None:
        from project_magi.session import MagiSession

        mock_result = self._make_mock_result()

        with (
            patch("sys.argv", ["magi", "deliberate", "Test question?"]),
            patch.object(MagiSession, "__init__", return_value=None),
            patch.object(
                MagiSession, "deliberate", new_callable=AsyncMock, return_value=mock_result
            ) as mock_deliberate,
        ):
            main()

            mock_deliberate.assert_called_once()
            call_kwargs = mock_deliberate.call_args
            assert call_kwargs.kwargs.get("on_checkpoint") is not None
