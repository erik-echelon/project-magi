"""Critique agent — synthesizes persona outputs into structured analysis."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from project_magi.providers.base import Message

if TYPE_CHECKING:
    from project_magi.agents.output import PersonaOutput
    from project_magi.providers.base import Provider

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}

CRITIQUE_SYSTEM_PROMPT = """\
You are the MAGI critique agent. You have no persona, no perspective of your own, \
and no opinion on the substance of the question. Your job is purely structural: \
analyze the outputs from multiple persona agents and produce a synthesis.

You must:
1. Identify the KEY DIMENSIONS of the question — the important axes along which \
the personas' analyses can be compared. These dimensions emerge from what the \
personas actually addressed, not from a predetermined list.
2. For each dimension, report ALIGNMENT: which personas agree and which diverge. \
Include direct quotes from the personas to support your characterization.
3. Identify AGREEMENTS: positions where personas genuinely converge (not just \
superficially using similar language with different reasoning).
4. Identify DISAGREEMENTS: positions where personas genuinely diverge. Quote \
each side directly.
5. Identify TALKING PAST EACH OTHER: cases where personas are addressing \
different aspects of the question and not actually engaging with each other's \
arguments.

You are not an arbiter. You do not judge which persona is right. You map the \
landscape of agreement and disagreement so that the next round of deliberation \
(and the human reviewer) can see clearly where the friction is.

Respond with a JSON object in this exact format (no markdown fences, just raw JSON):
{
  "dimensions": [
    {
      "name": "Dimension name",
      "alignment": "3/3 aligned | 2/3 aligned | 1/3 aligned | no alignment",
      "summary": "Brief description of where personas stand",
      "quotes": {
        "persona_name": "Direct quote from that persona's analysis"
      }
    }
  ],
  "agreements": [
    {
      "point": "What they agree on",
      "personas": ["persona1", "persona2"],
      "note": "Optional: why this is genuine agreement, not superficial"
    }
  ],
  "disagreements": [
    {
      "point": "What they disagree about",
      "sides": {
        "persona1": "Their position (with quote)",
        "persona2": "Their position (with quote)"
      }
    }
  ],
  "talking_past": [
    {
      "description": "How the personas are missing each other's points",
      "personas_involved": ["persona1", "persona2"]
    }
  ]
}
"""


def _build_critique_prompt(persona_outputs: list[PersonaOutput]) -> str:
    """Build the user prompt for the critique agent."""
    parts = ["## Persona Outputs for This Round\n"]

    for output in persona_outputs:
        parts.append(f"### {output.persona_name}")
        parts.append(f"**Confidence:** {output.confidence}")
        parts.append(f"**Analysis:**\n{output.analysis}")
        if output.findings:
            parts.append("**Findings:**")
            for f in output.findings:
                parts.append(f"- [{f.severity}] {f.title}: {f.detail}")
        parts.append("")

    parts.append(
        "Analyze these outputs and produce the structured synthesis as described "
        "in your instructions."
    )

    return "\n".join(parts)


@dataclass(frozen=True)
class DimensionAlignment:
    """One dimension of alignment from the critique synthesis."""

    name: str
    alignment: str  # e.g. "3/3 aligned", "2/3 aligned"
    summary: str
    quotes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Agreement:
    """A point of agreement identified by the critique agent."""

    point: str
    personas: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(frozen=True)
class Disagreement:
    """A point of disagreement identified by the critique agent."""

    point: str
    sides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TalkingPast:
    """A case where personas are talking past each other."""

    description: str
    personas_involved: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeduplicatedFinding:
    """A finding that has been deduplicated across personas."""

    severity: str
    title: str
    detail: str
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CritiqueOutput:
    """Full output from the critique agent."""

    dimensions: list[DimensionAlignment] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)
    disagreements: list[Disagreement] = field(default_factory=list)
    talking_past: list[TalkingPast] = field(default_factory=list)
    deduplicated_findings: list[DeduplicatedFinding] = field(default_factory=list)
    raw_response: str = ""

    @classmethod
    def parse(cls, raw_text: str) -> CritiqueOutput:
        """Parse the critique agent's raw response into structured output."""
        json_str = _extract_json(raw_text)
        if json_str is None:
            logger.warning("Critique agent did not return valid JSON")
            return cls(raw_response=raw_text)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Critique agent returned invalid JSON")
            return cls(raw_response=raw_text)

        dimensions = _parse_dimensions(data.get("dimensions", []))
        agreements = _parse_agreements(data.get("agreements", []))
        disagreements = _parse_disagreements(data.get("disagreements", []))
        talking_past = _parse_talking_past(data.get("talking_past", []))

        return cls(
            dimensions=dimensions,
            agreements=agreements,
            disagreements=disagreements,
            talking_past=talking_past,
            raw_response=raw_text,
        )


def _extract_json(text: str) -> str | None:
    """Extract JSON from text, handling markdown fences."""
    stripped = text.strip()

    if "```json" in stripped:
        start = stripped.index("```json") + len("```json")
        end = stripped.find("```", start)
        if end != -1:
            return stripped[start:end].strip()

    if stripped.startswith("```") and stripped.endswith("```"):
        inner = stripped[3:]
        end = inner.rfind("```")
        if end > 0:
            return inner[:end].strip()

    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    return None


def _parse_dimensions(raw: object) -> list[DimensionAlignment]:
    if not isinstance(raw, list):
        return []
    result: list[DimensionAlignment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        d = cast("dict[str, Any]", item)
        result.append(
            DimensionAlignment(
                name=str(d.get("name") or ""),
                alignment=str(d.get("alignment") or ""),
                summary=str(d.get("summary") or ""),
                quotes=_parse_str_dict(d.get("quotes")),
            )
        )
    return result


def _parse_agreements(raw: object) -> list[Agreement]:
    if not isinstance(raw, list):
        return []
    result: list[Agreement] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        d = cast("dict[str, Any]", item)
        result.append(
            Agreement(
                point=str(d.get("point") or ""),
                personas=_parse_str_list(d.get("personas")),
                note=str(d.get("note") or ""),
            )
        )
    return result


def _parse_disagreements(raw: object) -> list[Disagreement]:
    if not isinstance(raw, list):
        return []
    result: list[Disagreement] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        d = cast("dict[str, Any]", item)
        result.append(
            Disagreement(
                point=str(d.get("point") or ""),
                sides=_parse_str_dict(d.get("sides")),
            )
        )
    return result


def _parse_talking_past(raw: object) -> list[TalkingPast]:
    if not isinstance(raw, list):
        return []
    result: list[TalkingPast] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        d = cast("dict[str, Any]", item)
        result.append(
            TalkingPast(
                description=str(d.get("description") or ""),
                personas_involved=_parse_str_list(d.get("personas_involved")),
            )
        )
    return result


def _parse_str_dict(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _parse_str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def deduplicate_findings(
    persona_outputs: list[PersonaOutput],
) -> list[DeduplicatedFinding]:
    """Deduplicate findings across persona outputs.

    Merges findings with the same title (case-insensitive), escalates
    severity to the highest level, and tracks which personas raised each.
    """
    merged: dict[str, DeduplicatedFinding] = {}

    for output in persona_outputs:
        for finding in output.findings:
            key = finding.title.lower().strip()
            if not key:
                continue

            if key in merged:
                existing = merged[key]
                # Escalate severity
                new_severity = _higher_severity(existing.severity, finding.severity)
                # Merge detail (keep longer)
                new_detail = (
                    finding.detail
                    if len(finding.detail) > len(existing.detail)
                    else existing.detail
                )
                merged[key] = DeduplicatedFinding(
                    severity=new_severity,
                    title=existing.title,
                    detail=new_detail,
                    sources=[*existing.sources, output.persona_name],
                )
            else:
                merged[key] = DeduplicatedFinding(
                    severity=finding.severity,
                    title=finding.title,
                    detail=finding.detail,
                    sources=[output.persona_name],
                )

    # Sort by severity (critical first)
    return sorted(
        merged.values(),
        key=lambda f: SEVERITY_RANK.get(f.severity, 0),
        reverse=True,
    )


def _higher_severity(a: str, b: str) -> str:
    """Return the higher severity of two severity levels."""
    rank_a = SEVERITY_RANK.get(a, 0)
    rank_b = SEVERITY_RANK.get(b, 0)
    return a if rank_a >= rank_b else b


async def run_critique_agent(
    provider: Provider,
    persona_outputs: list[PersonaOutput],
) -> CritiqueOutput:
    """Run the critique agent on a list of persona outputs.

    Returns a CritiqueOutput with the synthesis, plus deduplicated findings
    computed separately (not by the LLM).
    """
    user_prompt = _build_critique_prompt(persona_outputs)

    response = await provider.send_message(
        system_prompt=CRITIQUE_SYSTEM_PROMPT,
        messages=[Message(role="user", content=user_prompt)],
    )

    critique = CritiqueOutput.parse(response.content)

    # Add deduplicated findings (computed deterministically, not by the LLM)
    deduped = deduplicate_findings(persona_outputs)

    return CritiqueOutput(
        dimensions=critique.dimensions,
        agreements=critique.agreements,
        disagreements=critique.disagreements,
        talking_past=critique.talking_past,
        deduplicated_findings=deduped,
        raw_response=response.content,
    )
