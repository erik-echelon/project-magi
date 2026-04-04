"""Tests for the critique agent — dedup logic, parsing, and runner."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from project_magi.agents.critique import (
    CritiqueOutput,
    _build_critique_prompt,
    _higher_severity,
    deduplicate_findings,
    run_critique_agent,
)
from project_magi.agents.output import Finding, PersonaOutput
from project_magi.providers.base import ProviderResponse


class TestDeduplicateFindings:
    def test_two_findings_same_title_merged(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="melchior",
                analysis="a",
                confidence=0.8,
                findings=[Finding(severity="warning", title="Data Loss Risk", detail="short")],
            ),
            PersonaOutput(
                persona_name="casper",
                analysis="b",
                confidence=0.7,
                findings=[
                    Finding(
                        severity="critical", title="data loss risk", detail="much longer detail"
                    )
                ],
            ),
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 1
        assert result[0].title == "Data Loss Risk"  # keeps first seen casing
        assert result[0].severity == "critical"  # escalated
        assert "melchior" in result[0].sources
        assert "casper" in result[0].sources
        assert result[0].detail == "much longer detail"  # keeps longer

    def test_two_findings_different_titles_kept_separate(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="melchior",
                analysis="a",
                confidence=0.8,
                findings=[Finding(severity="warning", title="Risk A", detail="a")],
            ),
            PersonaOutput(
                persona_name="casper",
                analysis="b",
                confidence=0.7,
                findings=[Finding(severity="info", title="Risk B", detail="b")],
            ),
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 2
        titles = {f.title for f in result}
        assert titles == {"Risk A", "Risk B"}

    def test_severity_escalation_info_to_critical(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="a",
                analysis="a",
                confidence=0.5,
                findings=[Finding(severity="info", title="Issue", detail="d")],
            ),
            PersonaOutput(
                persona_name="b",
                analysis="b",
                confidence=0.5,
                findings=[Finding(severity="critical", title="issue", detail="d")],
            ),
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 1
        assert result[0].severity == "critical"

    def test_sorted_by_severity(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="a",
                analysis="a",
                confidence=0.5,
                findings=[
                    Finding(severity="info", title="Low", detail="d"),
                    Finding(severity="critical", title="High", detail="d"),
                    Finding(severity="warning", title="Mid", detail="d"),
                ],
            ),
        ]

        result = deduplicate_findings(outputs)

        assert [f.severity for f in result] == ["critical", "warning", "info"]

    def test_empty_title_skipped(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="a",
                analysis="a",
                confidence=0.5,
                findings=[Finding(severity="info", title="", detail="d")],
            ),
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 0

    def test_no_findings(self) -> None:
        outputs = [
            PersonaOutput(persona_name="a", analysis="a", confidence=0.5),
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 0

    def test_three_personas_same_finding(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name=name,
                analysis="a",
                confidence=0.5,
                findings=[Finding(severity="warning", title="Shared Issue", detail="d")],
            )
            for name in ["melchior", "balthasar", "casper"]
        ]

        result = deduplicate_findings(outputs)

        assert len(result) == 1
        assert len(result[0].sources) == 3


class TestHigherSeverity:
    def test_critical_wins(self) -> None:
        assert _higher_severity("info", "critical") == "critical"
        assert _higher_severity("critical", "info") == "critical"

    def test_warning_beats_info(self) -> None:
        assert _higher_severity("info", "warning") == "warning"

    def test_same_returns_first(self) -> None:
        assert _higher_severity("warning", "warning") == "warning"


class TestCritiqueOutputParse:
    def test_parses_valid_json(self) -> None:
        raw = json.dumps(
            {
                "dimensions": [
                    {
                        "name": "Technical Feasibility",
                        "alignment": "2/3 aligned",
                        "summary": "Most agree it's feasible",
                        "quotes": {"melchior": "It's technically sound"},
                    }
                ],
                "agreements": [
                    {"point": "Migration is risky", "personas": ["balthasar", "casper"]}
                ],
                "disagreements": [
                    {
                        "point": "Timeline",
                        "sides": {"melchior": "3 months", "casper": "6 months minimum"},
                    }
                ],
                "talking_past": [
                    {
                        "description": "Melchior focuses on perf, Balthasar on team",
                        "personas_involved": ["melchior", "balthasar"],
                    }
                ],
            }
        )

        output = CritiqueOutput.parse(raw)

        assert len(output.dimensions) == 1
        assert output.dimensions[0].name == "Technical Feasibility"
        assert output.dimensions[0].alignment == "2/3 aligned"
        assert "melchior" in output.dimensions[0].quotes

        assert len(output.agreements) == 1
        assert output.agreements[0].point == "Migration is risky"

        assert len(output.disagreements) == 1
        assert "melchior" in output.disagreements[0].sides

        assert len(output.talking_past) == 1

    def test_parses_json_in_fence(self) -> None:
        raw_json = json.dumps(
            {
                "dimensions": [],
                "agreements": [],
                "disagreements": [],
                "talking_past": [],
            }
        )
        raw = f"```json\n{raw_json}\n```"
        output = CritiqueOutput.parse(raw)
        assert output.dimensions == []

    def test_fallback_on_no_json(self) -> None:
        output = CritiqueOutput.parse("Just plain text, no JSON")
        assert output.dimensions == []
        assert output.raw_response == "Just plain text, no JSON"

    def test_fallback_on_invalid_json(self) -> None:
        output = CritiqueOutput.parse('{"dimensions": broken}')
        assert output.dimensions == []

    def test_missing_fields_default_to_empty(self) -> None:
        output = CritiqueOutput.parse('{"dimensions": []}')
        assert output.agreements == []
        assert output.disagreements == []
        assert output.talking_past == []


class TestBuildCritiquePrompt:
    def test_includes_all_persona_outputs(self) -> None:
        outputs = [
            PersonaOutput(
                persona_name="melchior",
                analysis="Technical analysis here",
                confidence=0.9,
                findings=[Finding(severity="warning", title="Risk", detail="detail")],
            ),
            PersonaOutput(
                persona_name="casper",
                analysis="Risk analysis here",
                confidence=0.7,
            ),
        ]

        prompt = _build_critique_prompt(outputs)

        assert "melchior" in prompt
        assert "casper" in prompt
        assert "Technical analysis here" in prompt
        assert "Risk analysis here" in prompt
        assert "0.9" in prompt
        assert "0.7" in prompt
        assert "[warning] Risk" in prompt

    def test_handles_no_findings(self) -> None:
        outputs = [
            PersonaOutput(persona_name="test", analysis="analysis", confidence=0.5),
        ]

        prompt = _build_critique_prompt(outputs)

        assert "test" in prompt
        assert "analysis" in prompt


class TestRunCritiqueAgent:
    @pytest.mark.asyncio
    async def test_runs_and_returns_critique_with_deduped_findings(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.send_message.return_value = ProviderResponse(
            content=json.dumps(
                {
                    "dimensions": [
                        {
                            "name": "Scope",
                            "alignment": "2/3 aligned",
                            "summary": "Most agree scope is too broad",
                            "quotes": {},
                        }
                    ],
                    "agreements": [{"point": "Too broad", "personas": ["a", "b"]}],
                    "disagreements": [],
                    "talking_past": [],
                }
            ),
            model="claude-opus-4-6",
        )

        persona_outputs = [
            PersonaOutput(
                persona_name="a",
                analysis="analysis a",
                confidence=0.8,
                findings=[Finding(severity="warning", title="Scope Creep", detail="d")],
            ),
            PersonaOutput(
                persona_name="b",
                analysis="analysis b",
                confidence=0.7,
                findings=[Finding(severity="critical", title="scope creep", detail="longer d")],
            ),
        ]

        result = await run_critique_agent(mock_provider, persona_outputs)

        # LLM-produced synthesis
        assert len(result.dimensions) == 1
        assert result.dimensions[0].name == "Scope"
        assert len(result.agreements) == 1

        # Deterministic dedup
        assert len(result.deduplicated_findings) == 1
        assert result.deduplicated_findings[0].severity == "critical"
        assert "a" in result.deduplicated_findings[0].sources
        assert "b" in result.deduplicated_findings[0].sources

    @pytest.mark.asyncio
    async def test_works_with_two_persona_inputs_degraded(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.send_message.return_value = ProviderResponse(
            content=json.dumps(
                {
                    "dimensions": [
                        {"name": "D1", "alignment": "2/2", "summary": "s", "quotes": {}}
                    ],
                    "agreements": [],
                    "disagreements": [],
                    "talking_past": [],
                }
            ),
            model="claude-opus-4-6",
        )

        persona_outputs = [
            PersonaOutput(persona_name="a", analysis="a", confidence=0.8),
            PersonaOutput(persona_name="b", analysis="b", confidence=0.7),
        ]

        result = await run_critique_agent(mock_provider, persona_outputs)

        assert len(result.dimensions) == 1
        assert result.dimensions[0].alignment == "2/2"

    @pytest.mark.asyncio
    async def test_uses_critique_system_prompt(self) -> None:
        from project_magi.agents.critique import CRITIQUE_SYSTEM_PROMPT

        mock_provider = AsyncMock()
        empty_critique = json.dumps(
            {
                "dimensions": [],
                "agreements": [],
                "disagreements": [],
                "talking_past": [],
            }
        )
        mock_provider.send_message.return_value = ProviderResponse(
            content=empty_critique,
            model="claude-opus-4-6",
        )

        await run_critique_agent(
            mock_provider,
            [PersonaOutput(persona_name="a", analysis="a", confidence=0.5)],
        )

        call_kwargs = mock_provider.send_message.call_args.kwargs
        assert call_kwargs["system_prompt"] == CRITIQUE_SYSTEM_PROMPT
