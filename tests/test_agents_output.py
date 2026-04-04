"""Tests for persona agent output schema and parsing."""

from __future__ import annotations

import json

from project_magi.agents.output import Finding, PersonaOutput, _clamp_confidence, _parse_findings


class TestFinding:
    def test_create(self) -> None:
        f = Finding(severity="critical", title="Bug", detail="It's broken")
        assert f.severity == "critical"
        assert f.title == "Bug"
        assert f.detail == "It's broken"


class TestPersonaOutputParse:
    def test_parses_valid_json(self) -> None:
        raw = json.dumps(
            {
                "analysis": "This is my analysis.",
                "confidence": 0.85,
                "findings": [
                    {"severity": "warning", "title": "Risk A", "detail": "Details about A"},
                    {"severity": "info", "title": "Note B", "detail": "Details about B"},
                ],
            }
        )

        output = PersonaOutput.parse("melchior", raw)

        assert output.persona_name == "melchior"
        assert output.analysis == "This is my analysis."
        assert output.confidence == 0.85
        assert len(output.findings) == 2
        assert output.findings[0].severity == "warning"
        assert output.findings[0].title == "Risk A"
        assert output.findings[1].severity == "info"
        assert output.raw_response == raw

    def test_parses_json_in_markdown_fence(self) -> None:
        raw = '```json\n{"analysis": "fenced", "confidence": 0.7, "findings": []}\n```'

        output = PersonaOutput.parse("test", raw)

        assert output.analysis == "fenced"
        assert output.confidence == 0.7

    def test_parses_json_in_plain_fence(self) -> None:
        raw = '```\n{"analysis": "plain fence", "confidence": 0.6, "findings": []}\n```'

        output = PersonaOutput.parse("test", raw)

        assert output.analysis == "plain fence"

    def test_fallback_on_no_json(self) -> None:
        raw = "Just a plain text response with no JSON structure at all."

        output = PersonaOutput.parse("test", raw)

        assert output.analysis == raw.strip()
        assert output.confidence == 0.5
        assert output.findings == []

    def test_fallback_on_invalid_json(self) -> None:
        raw = '{"analysis": broken json'

        output = PersonaOutput.parse("test", raw)

        assert output.confidence == 0.5

    def test_missing_analysis_field(self) -> None:
        raw = json.dumps({"confidence": 0.9, "findings": []})

        output = PersonaOutput.parse("test", raw)

        assert output.analysis == ""
        assert output.confidence == 0.9

    def test_missing_confidence_defaults(self) -> None:
        raw = json.dumps({"analysis": "No confidence", "findings": []})

        output = PersonaOutput.parse("test", raw)

        assert output.confidence == 0.5

    def test_confidence_clamped_high(self) -> None:
        raw = json.dumps({"analysis": "x", "confidence": 1.5, "findings": []})

        output = PersonaOutput.parse("test", raw)

        assert output.confidence == 1.0

    def test_confidence_clamped_low(self) -> None:
        raw = json.dumps({"analysis": "x", "confidence": -0.5, "findings": []})

        output = PersonaOutput.parse("test", raw)

        assert output.confidence == 0.0

    def test_findings_with_invalid_severity(self) -> None:
        raw = json.dumps(
            {
                "analysis": "x",
                "confidence": 0.5,
                "findings": [{"severity": "EXTREME", "title": "Bad", "detail": "d"}],
            }
        )

        output = PersonaOutput.parse("test", raw)

        assert output.findings[0].severity == "info"

    def test_findings_skip_empty_titles(self) -> None:
        raw = json.dumps(
            {
                "analysis": "x",
                "confidence": 0.5,
                "findings": [
                    {"severity": "warning", "title": "", "detail": "no title"},
                    {"severity": "info", "title": "Has title", "detail": "d"},
                ],
            }
        )

        output = PersonaOutput.parse("test", raw)

        assert len(output.findings) == 1
        assert output.findings[0].title == "Has title"


class TestClampConfidence:
    def test_normal(self) -> None:
        assert _clamp_confidence(0.5) == 0.5

    def test_string_number(self) -> None:
        assert _clamp_confidence("0.8") == 0.8

    def test_non_numeric(self) -> None:
        assert _clamp_confidence("not a number") == 0.5

    def test_none(self) -> None:
        assert _clamp_confidence(None) == 0.5


class TestParseFindings:
    def test_not_a_list(self) -> None:
        assert _parse_findings("not a list") == []

    def test_non_dict_items_skipped(self) -> None:
        assert _parse_findings(["not a dict", 42]) == []

    def test_valid_findings(self) -> None:
        findings = _parse_findings(
            [
                {"severity": "critical", "title": "A", "detail": "a"},
                {"severity": "warning", "title": "B", "detail": "b"},
            ]
        )
        assert len(findings) == 2
