"""Tests for the CLI entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_magi.cli import _resolve_file_args, main

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

    def test_file_flag_passes_attachments(self, tmp_path: Path) -> None:
        from project_magi.session import MagiSession

        pdf_file = tmp_path / "whitepaper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_result = self._make_mock_result()

        with (
            patch(
                "sys.argv",
                [
                    "magi",
                    "deliberate",
                    "Evaluate this",
                    "--auto",
                    "-f",
                    str(pdf_file),
                ],
            ),
            patch.object(MagiSession, "__init__", return_value=None),
            patch.object(
                MagiSession, "deliberate", new_callable=AsyncMock, return_value=mock_result
            ) as mock_deliberate,
        ):
            main()

            mock_deliberate.assert_called_once()
            call_args = mock_deliberate.call_args
            attachments = call_args.kwargs.get("attachments")
            assert attachments is not None
            assert len(attachments) == 1
            assert attachments[0] == pdf_file.resolve()

    def test_multiple_file_flags(self, tmp_path: Path) -> None:
        from project_magi.session import MagiSession

        file_a = tmp_path / "a.pdf"
        file_b = tmp_path / "b.txt"
        file_a.write_bytes(b"%PDF-1.4 fake")
        file_b.write_text("some text")

        mock_result = self._make_mock_result()

        with (
            patch(
                "sys.argv",
                [
                    "magi",
                    "deliberate",
                    "Evaluate",
                    "--auto",
                    "-f",
                    str(file_a),
                    "-f",
                    str(file_b),
                ],
            ),
            patch.object(MagiSession, "__init__", return_value=None),
            patch.object(
                MagiSession, "deliberate", new_callable=AsyncMock, return_value=mock_result
            ) as mock_deliberate,
        ):
            main()

            call_args = mock_deliberate.call_args
            attachments = call_args.kwargs.get("attachments")
            assert attachments is not None
            assert len(attachments) == 2

    def test_file_flag_missing_file_exits(self) -> None:
        with (
            pytest.raises(SystemExit),
            patch(
                "sys.argv",
                ["magi", "deliberate", "Test", "--auto", "-f", "/nonexistent/file.pdf"],
            ),
        ):
            main()


class TestResolveFileArgs:
    def test_resolves_existing_files(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"data")
        result = _resolve_file_args([str(f)])
        assert len(result) == 1
        assert result[0] == str(f.resolve())

    def test_empty_list(self) -> None:
        assert _resolve_file_args([]) == []

    def test_nonexistent_file_exits(self) -> None:
        with pytest.raises(SystemExit):
            _resolve_file_args(["/no/such/file.pdf"])
