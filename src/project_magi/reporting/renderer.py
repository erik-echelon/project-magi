"""Renders the final markdown report from a deliberation state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from project_magi.agents.critique import CritiqueOutput, DeduplicatedFinding
    from project_magi.agents.output import PersonaOutput
    from project_magi.coordinator.loop import DeliberationState


def render_report(
    state: DeliberationState,
    *,
    verbose: bool = False,
) -> str:
    """Render the final deliberation report as markdown.

    Args:
        state: The completed deliberation state.
        verbose: If True, include full reasoning chains. Default is concise.

    Returns:
        A markdown string containing the full report.
    """
    if not state.rounds:
        return "# MAGI Deliberation Report\n\nNo rounds completed.\n"

    last_round = state.rounds[-1]
    critique = last_round.critique
    persona_outputs = last_round.persona_result.outputs
    errors = last_round.persona_result.errors

    sections: list[str] = []

    # Header
    sections.append("# MAGI Deliberation Report")
    sections.append("")
    sections.append(f"**Question:** {state.question}")
    sections.append(f"**Rounds completed:** {state.round_count}")
    sections.append(f"**Stopped:** {_format_stop_reason(state.stopped_reason)}")
    if errors:
        lost = ", ".join(name for name, _ in errors)
        sections.append(f"**Degraded:** persona(s) lost: {lost}")
    sections.append("")

    # 1. Dimension alignment map
    sections.append(_render_dimensions(critique))

    # 2. Consensus positions
    sections.append(_render_agreements(critique))

    # 3. Remaining disagreements
    sections.append(_render_disagreements(critique))

    # 4. Deduplicated findings
    sections.append(_render_findings(critique.deduplicated_findings))

    # 5. Per-persona final position
    sections.append(_render_persona_positions(persona_outputs, verbose=verbose))

    return "\n".join(sections)


def _format_stop_reason(reason: str) -> str:
    match reason:
        case "wrap_up":
            return "Human chose to wrap up"
        case "max_rounds":
            return "Maximum rounds reached"
        case "no_quorum":
            return "Insufficient personas (fewer than 2 succeeded)"
        case _:
            return reason


def _render_dimensions(critique: CritiqueOutput) -> str:
    if not critique.dimensions:
        return "## Dimension Alignment\n\nNo dimensions identified.\n"

    lines = ["## Dimension Alignment", ""]
    lines.append("| Dimension | Alignment | Summary |")
    lines.append("|---|---|---|")

    for dim in critique.dimensions:
        # Escape pipes in summary text
        summary = dim.summary.replace("|", "\\|")
        lines.append(f"| {dim.name} | {dim.alignment} | {summary} |")

    lines.append("")
    return "\n".join(lines)


def _render_agreements(critique: CritiqueOutput) -> str:
    if not critique.agreements:
        return "## Consensus Positions\n\nNo consensus positions identified.\n"

    lines = ["## Consensus Positions", ""]

    for agreement in critique.agreements:
        persona_count = len(agreement.personas)
        persona_list = ", ".join(agreement.personas)
        lines.append(
            f"- **{persona_count}/{persona_count} personas agree:** "
            f"{agreement.point} ({persona_list})"
        )
        if agreement.note:
            lines.append(f"  - *{agreement.note}*")

    lines.append("")
    return "\n".join(lines)


def _render_disagreements(critique: CritiqueOutput) -> str:
    if not critique.disagreements:
        return "## Remaining Disagreements\n\nNo remaining disagreements.\n"

    lines = ["## Remaining Disagreements", ""]

    for disagreement in critique.disagreements:
        lines.append(f"**{disagreement.point}**")
        for persona_name, position in disagreement.sides.items():
            lines.append(f"- **{persona_name}:** {position}")
        lines.append("")

    return "\n".join(lines)


def _render_findings(findings: list[DeduplicatedFinding]) -> str:
    if not findings:
        return "## Findings\n\nNo findings reported.\n"

    lines = ["## Findings", ""]

    current_severity = ""
    for finding in findings:
        if finding.severity != current_severity:
            current_severity = finding.severity
            lines.append(f"### {current_severity.capitalize()}")
            lines.append("")

        sources = ", ".join(finding.sources)
        lines.append(f"- **{finding.title}** (raised by: {sources})")
        if finding.detail:
            lines.append(f"  - {finding.detail}")

    lines.append("")
    return "\n".join(lines)


def _render_persona_positions(
    outputs: list[PersonaOutput],
    *,
    verbose: bool = False,
) -> str:
    if not outputs:
        return "## Per-Persona Positions\n\nNo persona outputs available.\n"

    lines = ["## Per-Persona Positions", ""]

    for output in sorted(outputs, key=lambda o: o.persona_name):
        lines.append(f"### {output.persona_name.capitalize()}")
        lines.append(f"**Confidence:** {output.confidence}")
        lines.append("")

        if verbose:
            lines.append(output.analysis)
        else:
            # Concise: first paragraph or first 200 chars
            summary = _first_paragraph(output.analysis, max_chars=200)
            lines.append(summary)

        lines.append("")

    return "\n".join(lines)


def _first_paragraph(text: str, max_chars: int = 200) -> str:
    """Extract the first paragraph, truncating if needed."""
    # Split on double newline to get first paragraph
    paragraphs = text.split("\n\n")
    first = paragraphs[0].strip()

    if len(first) <= max_chars:
        return first

    # Truncate at word boundary
    truncated = first[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated + "..."
