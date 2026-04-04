"""Tests for MAGI-12: agent prompt hardening."""

from __future__ import annotations

import json
from pathlib import Path

from project_magi.agents.output import PersonaOutput, strip_zero_width
from project_magi.personas.parser import discover_personas


class TestStripZeroWidth:
    def test_strips_zero_width_space(self) -> None:
        assert strip_zero_width("hello\u200bworld") == "helloworld"

    def test_strips_zero_width_non_joiner(self) -> None:
        assert strip_zero_width("test\u200cvalue") == "testvalue"

    def test_strips_zero_width_joiner(self) -> None:
        assert strip_zero_width("test\u200dvalue") == "testvalue"

    def test_strips_bom(self) -> None:
        assert strip_zero_width("\ufeffhello") == "hello"

    def test_strips_word_joiner(self) -> None:
        assert strip_zero_width("test\u2060value") == "testvalue"

    def test_strips_multiple_types(self) -> None:
        text = "\u200b\u200c\u200d\ufeffhello\u2060world\u200b"
        assert strip_zero_width(text) == "helloworld"

    def test_preserves_normal_text(self) -> None:
        assert strip_zero_width("normal text here") == "normal text here"

    def test_empty_string(self) -> None:
        assert strip_zero_width("") == ""

    def test_only_zero_width_chars(self) -> None:
        assert strip_zero_width("\u200b\u200c\u200d") == ""

    def test_mixed_with_real_text(self) -> None:
        assert strip_zero_width("he\u200bll\u200co") == "hello"


class TestZeroWidthInFindingParsing:
    def test_finding_title_with_zero_width_stripped_to_empty_is_skipped(self) -> None:
        raw = json.dumps(
            {
                "analysis": "test",
                "confidence": 0.8,
                "findings": [
                    {
                        "severity": "warning",
                        "title": "\u200b\u200c\u200d",
                        "detail": "invisible title",
                    }
                ],
            }
        )

        output = PersonaOutput.parse("test", raw)
        assert len(output.findings) == 0

    def test_finding_title_with_zero_width_mixed_into_real_text(self) -> None:
        raw = json.dumps(
            {
                "analysis": "test",
                "confidence": 0.8,
                "findings": [
                    {
                        "severity": "critical",
                        "title": "Data\u200b Loss\u200c Risk",
                        "detail": "Some\u200b detail",
                    }
                ],
            }
        )

        output = PersonaOutput.parse("test", raw)
        assert len(output.findings) == 1
        assert output.findings[0].title == "Data Loss Risk"
        assert output.findings[0].detail == "Some detail"

    def test_analysis_text_has_zero_width_stripped(self) -> None:
        raw = json.dumps(
            {
                "analysis": "This\u200b is\u200c my\u200d analysis",
                "confidence": 0.8,
                "findings": [],
            }
        )

        output = PersonaOutput.parse("test", raw)
        assert output.analysis == "This is my analysis"


class TestDefaultPersonaNonOverlapDirectives:
    """Verify each default persona explicitly defers to the other two."""

    def _load_defaults(self) -> dict[str, str]:
        agents_dir = Path.cwd() / ".claude" / "agents"
        result = discover_personas(agents_dir)
        return {p.name: p.system_prompt for p in result.personas}

    def test_melchior_defers_to_balthasar(self) -> None:
        prompts = self._load_defaults()
        assert "balthasar" in prompts["melchior"].lower()
        assert "human impact" in prompts["melchior"].lower()

    def test_melchior_defers_to_casper(self) -> None:
        prompts = self._load_defaults()
        assert "casper" in prompts["melchior"].lower()
        assert "risk" in prompts["melchior"].lower() or "failure" in prompts["melchior"].lower()

    def test_balthasar_defers_to_melchior(self) -> None:
        prompts = self._load_defaults()
        assert "melchior" in prompts["balthasar"].lower()
        assert "technical" in prompts["balthasar"].lower()

    def test_balthasar_defers_to_casper(self) -> None:
        prompts = self._load_defaults()
        assert "casper" in prompts["balthasar"].lower()
        assert (
            "adversarial" in prompts["balthasar"].lower()
            or "failure" in prompts["balthasar"].lower()
            or "worst" in prompts["balthasar"].lower()
        )

    def test_casper_defers_to_melchior(self) -> None:
        prompts = self._load_defaults()
        assert "melchior" in prompts["casper"].lower()
        assert "technical" in prompts["casper"].lower() or "evidence" in prompts["casper"].lower()

    def test_casper_defers_to_balthasar(self) -> None:
        prompts = self._load_defaults()
        assert "balthasar" in prompts["casper"].lower()
        assert "human" in prompts["casper"].lower() or "welfare" in prompts["casper"].lower()

    def test_all_have_defer_section(self) -> None:
        prompts = self._load_defaults()
        for name, prompt in prompts.items():
            assert "What You Defer" in prompt, f"{name} missing 'What You Defer' section"


class TestDefaultPersonaConfidenceCalibration:
    """Verify each default persona includes confidence calibration guidance."""

    def _load_defaults(self) -> dict[str, str]:
        agents_dir = Path.cwd() / ".claude" / "agents"
        result = discover_personas(agents_dir)
        return {p.name: p.system_prompt for p in result.personas}

    def test_all_have_calibration_section(self) -> None:
        prompts = self._load_defaults()
        for name, prompt in prompts.items():
            assert "Confidence Calibration" in prompt, (
                f"{name} missing 'Confidence Calibration' section"
            )

    def test_all_have_numeric_ranges(self) -> None:
        prompts = self._load_defaults()
        for name, prompt in prompts.items():
            assert "0.9" in prompt, f"{name} missing 0.9 calibration"
            assert "0.7" in prompt, f"{name} missing 0.7 calibration"
            assert "0.5" in prompt, f"{name} missing 0.5 calibration"

    def test_calibration_consistent_across_personas(self) -> None:
        prompts = self._load_defaults()
        for name, prompt in prompts.items():
            assert "Virtually certain" in prompt, f"{name} missing 'Virtually certain' descriptor"
            assert "Genuinely uncertain" in prompt, (
                f"{name} missing 'Genuinely uncertain' descriptor"
            )
