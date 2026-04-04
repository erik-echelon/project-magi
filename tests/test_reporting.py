"""Tests for the final output renderer."""

from __future__ import annotations

import json
from pathlib import Path

from project_magi.agents.critique import (
    Agreement,
    CritiqueOutput,
    DeduplicatedFinding,
    DimensionAlignment,
    Disagreement,
)
from project_magi.agents.output import Finding, PersonaOutput
from project_magi.agents.runner import PersonaAgentResult
from project_magi.coordinator.loop import DeliberationRound, DeliberationState
from project_magi.reporting.renderer import _first_paragraph, render_report

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_state(
    *,
    question: str = "Test question?",
    persona_outputs: list[PersonaOutput] | None = None,
    critique: CritiqueOutput | None = None,
    errors: list[tuple[str, str]] | None = None,
    stopped_reason: str = "wrap_up",
    round_count: int = 1,
) -> DeliberationState:
    """Build a minimal deliberation state for testing."""
    if persona_outputs is None:
        persona_outputs = [
            PersonaOutput(
                persona_name="melchior",
                analysis="Technical analysis paragraph one.\n\nParagraph two with more detail.",
                confidence=0.85,
                findings=[Finding(severity="warning", title="Risk A", detail="Detail A")],
            ),
            PersonaOutput(
                persona_name="balthasar",
                analysis="Human impact analysis. This affects the team significantly.",
                confidence=0.7,
                findings=[Finding(severity="info", title="Note B", detail="Detail B")],
            ),
            PersonaOutput(
                persona_name="casper",
                analysis="Risk analysis. Multiple failure modes identified.",
                confidence=0.9,
                findings=[Finding(severity="critical", title="Major Risk", detail="Detail C")],
            ),
        ]

    if critique is None:
        critique = CritiqueOutput(
            dimensions=[
                DimensionAlignment(
                    name="Technical Feasibility",
                    alignment="3/3 aligned",
                    summary="All agree it's feasible",
                    quotes={"melchior": "technically sound"},
                ),
                DimensionAlignment(
                    name="Risk Level",
                    alignment="1/3 aligned",
                    summary="Casper sees high risk, others moderate",
                    quotes={"casper": "failure modes are severe"},
                ),
            ],
            agreements=[
                Agreement(
                    point="The approach is technically feasible",
                    personas=["melchior", "balthasar", "casper"],
                    note="Genuine agreement on core feasibility",
                ),
            ],
            disagreements=[
                Disagreement(
                    point="Acceptable risk level",
                    sides={
                        "melchior": "Risk is manageable",
                        "casper": "Risk is unacceptable without mitigation",
                    },
                ),
            ],
            deduplicated_findings=[
                DeduplicatedFinding(
                    severity="critical",
                    title="Major Risk",
                    detail="Detail C",
                    sources=["casper"],
                ),
                DeduplicatedFinding(
                    severity="warning",
                    title="Risk A",
                    detail="Detail A",
                    sources=["melchior"],
                ),
                DeduplicatedFinding(
                    severity="info",
                    title="Note B",
                    detail="Detail B",
                    sources=["balthasar"],
                ),
            ],
        )

    persona_result = PersonaAgentResult(
        outputs=persona_outputs,
        errors=errors or [],
    )

    state = DeliberationState(question=question)
    for i in range(round_count):
        state.rounds.append(
            DeliberationRound(
                round_number=i + 1,
                persona_result=persona_result,
                critique=critique,
            )
        )
    state.is_complete = True
    state.stopped_reason = stopped_reason

    return state


class TestRenderReport:
    def test_contains_all_five_sections(self) -> None:
        state = _make_state()
        report = render_report(state)

        assert "## Dimension Alignment" in report
        assert "## Consensus Positions" in report
        assert "## Remaining Disagreements" in report
        assert "## Findings" in report
        assert "## Per-Persona Positions" in report

    def test_sections_in_correct_order(self) -> None:
        state = _make_state()
        report = render_report(state)

        dim_pos = report.index("## Dimension Alignment")
        consensus_pos = report.index("## Consensus Positions")
        disagree_pos = report.index("## Remaining Disagreements")
        findings_pos = report.index("## Findings")
        persona_pos = report.index("## Per-Persona Positions")

        assert dim_pos < consensus_pos < disagree_pos < findings_pos < persona_pos

    def test_header_contains_question(self) -> None:
        state = _make_state(question="Should we rewrite in Rust?")
        report = render_report(state)
        assert "Should we rewrite in Rust?" in report

    def test_header_contains_round_count(self) -> None:
        state = _make_state(round_count=3)
        report = render_report(state)
        assert "**Rounds completed:** 3" in report

    def test_header_contains_stop_reason(self) -> None:
        state = _make_state(stopped_reason="wrap_up")
        report = render_report(state)
        assert "Human chose to wrap up" in report

    def test_header_shows_max_rounds(self) -> None:
        state = _make_state(stopped_reason="max_rounds")
        report = render_report(state)
        assert "Maximum rounds reached" in report


class TestDimensionAlignment:
    def test_renders_as_markdown_table(self) -> None:
        state = _make_state()
        report = render_report(state)

        assert "| Dimension | Alignment | Summary |" in report
        assert "|---|---|---|" in report
        assert "| Technical Feasibility | 3/3 aligned |" in report
        assert "| Risk Level | 1/3 aligned |" in report

    def test_correct_column_count(self) -> None:
        state = _make_state()
        report = render_report(state)

        for line in report.split("\n"):
            if line.startswith("| ") and "---" not in line and "Dimension" not in line:
                # Data rows should have exactly 4 pipes (3 columns)
                assert line.count("|") == 4, f"Wrong column count: {line}"

    def test_no_dimensions(self) -> None:
        state = _make_state(critique=CritiqueOutput())
        report = render_report(state)
        assert "No dimensions identified" in report


class TestConsensusPositions:
    def test_shows_agreement_counts(self) -> None:
        state = _make_state()
        report = render_report(state)
        assert "3/3 personas agree" in report

    def test_no_agreements(self) -> None:
        critique = CritiqueOutput(
            disagreements=[Disagreement(point="Everything", sides={"a": "yes", "b": "no"})],
        )
        state = _make_state(critique=critique)
        report = render_report(state)
        assert "No consensus positions identified" in report


class TestDisagreements:
    def test_attributes_sides(self) -> None:
        state = _make_state()
        report = render_report(state)
        assert "**melchior:**" in report
        assert "**casper:**" in report
        assert "Risk is manageable" in report
        assert "Risk is unacceptable" in report

    def test_no_disagreements(self) -> None:
        critique = CritiqueOutput(
            agreements=[Agreement(point="Everything", personas=["a", "b"])],
        )
        state = _make_state(critique=critique)
        report = render_report(state)
        assert "No remaining disagreements" in report


class TestFindings:
    def test_sorted_by_severity(self) -> None:
        state = _make_state()
        report = render_report(state)

        critical_pos = report.index("### Critical")
        warning_pos = report.index("### Warning")
        info_pos = report.index("### Info")

        assert critical_pos < warning_pos < info_pos

    def test_shows_attribution(self) -> None:
        state = _make_state()
        report = render_report(state)
        assert "(raised by: casper)" in report
        assert "(raised by: melchior)" in report

    def test_no_findings(self) -> None:
        critique = CritiqueOutput()
        state = _make_state(critique=critique)
        report = render_report(state)
        assert "No findings reported" in report


class TestPersonaPositions:
    def test_includes_confidence(self) -> None:
        state = _make_state()
        report = render_report(state)
        assert "**Confidence:** 0.85" in report
        assert "**Confidence:** 0.7" in report
        assert "**Confidence:** 0.9" in report

    def test_concise_mode_truncates(self) -> None:
        long_analysis = "A" * 300 + "\n\nSecond paragraph."
        outputs = [PersonaOutput(persona_name="test", analysis=long_analysis, confidence=0.5)]
        state = _make_state(persona_outputs=outputs, critique=CritiqueOutput())
        report = render_report(state, verbose=False)

        # Should not contain full 300-char first paragraph
        assert "A" * 300 not in report
        assert "..." in report

    def test_verbose_mode_includes_full_analysis(self) -> None:
        long_analysis = "A" * 300 + "\n\nSecond paragraph with more detail."
        outputs = [PersonaOutput(persona_name="test", analysis=long_analysis, confidence=0.5)]
        state = _make_state(persona_outputs=outputs, critique=CritiqueOutput())
        report = render_report(state, verbose=True)

        assert "A" * 300 in report
        assert "Second paragraph with more detail." in report

    def test_no_outputs(self) -> None:
        state = _make_state(persona_outputs=[], critique=CritiqueOutput())
        report = render_report(state)
        assert "No persona outputs available" in report


class TestDegradedMode:
    def test_shows_lost_persona(self) -> None:
        state = _make_state(
            persona_outputs=[
                PersonaOutput(persona_name="melchior", analysis="a", confidence=0.8),
                PersonaOutput(persona_name="casper", analysis="b", confidence=0.7),
            ],
            errors=[("balthasar", "TimeoutError: timed out")],
            critique=CritiqueOutput(),
        )
        report = render_report(state)
        assert "Degraded" in report
        assert "balthasar" in report


class TestNoRounds:
    def test_empty_state(self) -> None:
        state = DeliberationState(question="test")
        report = render_report(state)
        assert "No rounds completed" in report


class TestFirstParagraph:
    def test_short_text(self) -> None:
        assert _first_paragraph("Short text.") == "Short text."

    def test_multi_paragraph(self) -> None:
        text = "First paragraph.\n\nSecond paragraph."
        assert _first_paragraph(text) == "First paragraph."

    def test_truncation(self) -> None:
        text = "Word " * 100
        result = _first_paragraph(text, max_chars=50)
        assert len(result) <= 55  # 50 + room for "..."
        assert result.endswith("...")


class TestWithRecordedFixtures:
    """Test rendering with real recorded data from previous epics."""

    def test_renders_from_real_critique_fixture(self) -> None:
        fixture = json.loads((FIXTURES_DIR / "critique_output.json").read_text())

        # Reconstruct CritiqueOutput from fixture
        critique = CritiqueOutput(
            dimensions=[
                DimensionAlignment(
                    name=d["name"],
                    alignment=d["alignment"],
                    summary=d["summary"],
                    quotes=d.get("quotes", {}),
                )
                for d in fixture["dimensions"]
            ],
            agreements=[
                Agreement(
                    point=a["point"],
                    personas=a.get("personas", []),
                    note=a.get("note", ""),
                )
                for a in fixture["agreements"]
            ],
            disagreements=[
                Disagreement(point=d["point"], sides=d.get("sides", {}))
                for d in fixture["disagreements"]
            ],
            deduplicated_findings=[
                DeduplicatedFinding(
                    severity=f["severity"],
                    title=f["title"],
                    detail=f["detail"],
                    sources=f["sources"],
                )
                for f in fixture["deduplicated_findings"]
            ],
        )

        # Load real persona outputs
        persona_outputs = []
        for name in ["melchior", "balthasar", "casper"]:
            pdata = json.loads((FIXTURES_DIR / f"persona_output_{name}.json").read_text())
            persona_outputs.append(
                PersonaOutput(
                    persona_name=pdata["persona_name"],
                    analysis=pdata["analysis"],
                    confidence=pdata["confidence"],
                    findings=[
                        Finding(
                            severity=f["severity"],
                            title=f["title"],
                            detail=f["detail"],
                        )
                        for f in pdata["findings"]
                    ],
                )
            )

        state = _make_state(
            question="Should we rewrite this service in Rust?",
            persona_outputs=persona_outputs,
            critique=critique,
        )
        report = render_report(state)

        # Verify it's valid markdown with all sections
        assert "## Dimension Alignment" in report
        assert "## Consensus Positions" in report
        assert "## Remaining Disagreements" in report
        assert "## Findings" in report
        assert "## Per-Persona Positions" in report

        # Verify real content appears
        assert "Should we rewrite this service in Rust?" in report
        assert "melchior" in report.lower()
        assert "balthasar" in report.lower()
        assert "casper" in report.lower()

        # Verify it's reasonable length in concise mode
        line_count = len(report.split("\n"))
        print(f"Concise report: {line_count} lines")
        assert line_count < 200, f"Concise report too long: {line_count} lines"

    def test_verbose_mode_longer_than_concise(self) -> None:
        """Verbose should include more content than concise."""
        # Use a simple state with long analysis
        outputs = [
            PersonaOutput(
                persona_name="test",
                analysis="First paragraph.\n\n" + "Detailed reasoning. " * 50,
                confidence=0.8,
            ),
        ]
        state = _make_state(persona_outputs=outputs, critique=CritiqueOutput())

        concise = render_report(state, verbose=False)
        verbose = render_report(state, verbose=True)

        assert len(verbose) > len(concise)
