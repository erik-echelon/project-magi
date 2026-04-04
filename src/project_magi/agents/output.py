"""Persona agent output schema."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)

VALID_SEVERITIES = frozenset({"critical", "warning", "info"})

# Zero-width and invisible Unicode characters that LLMs sometimes produce
_ZERO_WIDTH_RE = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u2061\u2062\u2063\u2064\u180e]"
)


def strip_zero_width(text: str) -> str:
    """Remove zero-width and invisible Unicode characters from text."""
    return _ZERO_WIDTH_RE.sub("", text)


@dataclass(frozen=True)
class Finding:
    """A single finding from a persona agent's analysis."""

    severity: str  # "critical", "warning", or "info"
    title: str
    detail: str


@dataclass(frozen=True)
class PersonaOutput:
    """Structured output from a persona agent for one round."""

    persona_name: str
    analysis: str
    confidence: float
    findings: list[Finding] = field(default_factory=list)
    raw_response: str = ""

    @classmethod
    def parse(cls, persona_name: str, raw_text: str) -> PersonaOutput:
        """Parse a persona agent's raw response into structured output.

        The agent is prompted to respond in JSON. This method extracts the
        JSON block (tolerating markdown fences) and parses it.

        If parsing fails, falls back to treating the entire response as
        unstructured analysis with default confidence.
        """
        json_str = _extract_json(raw_text)
        if json_str is None:
            logger.warning(
                "Persona %s did not return valid JSON, treating as unstructured analysis",
                persona_name,
            )
            return cls(
                persona_name=persona_name,
                analysis=raw_text.strip(),
                confidence=0.5,
                raw_response=raw_text,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(
                "Persona %s returned invalid JSON, treating as unstructured analysis",
                persona_name,
            )
            return cls(
                persona_name=persona_name,
                analysis=raw_text.strip(),
                confidence=0.5,
                raw_response=raw_text,
            )

        analysis = strip_zero_width(str(data.get("analysis", "")))
        confidence = _clamp_confidence(data.get("confidence", 0.5))
        findings = _parse_findings(data.get("findings", []))

        return cls(
            persona_name=persona_name,
            analysis=analysis,
            confidence=confidence,
            findings=findings,
            raw_response=raw_text,
        )


def _extract_json(text: str) -> str | None:
    """Extract a JSON block from text, handling markdown code fences."""
    stripped = text.strip()

    # Try to find a ```json ... ``` block
    if "```json" in stripped:
        start = stripped.index("```json") + len("```json")
        end = stripped.find("```", start)
        if end != -1:
            return stripped[start:end].strip()

    # Try to find a ``` ... ``` block
    if stripped.startswith("```") and stripped.endswith("```"):
        inner = stripped[3:]
        end = inner.rfind("```")
        if end > 0:
            return inner[:end].strip()

    # Try the whole thing as JSON (starts with { or [)
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    return None


def _clamp_confidence(value: float | int | str | object) -> float:
    """Clamp a confidence value to [0.0, 1.0]."""
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return 0.5
    return 0.5


def _parse_findings(raw_findings: object) -> list[Finding]:
    """Parse a list of finding dicts into Finding objects."""
    if not isinstance(raw_findings, list):
        return []

    findings: list[Finding] = []
    for raw_item in raw_findings:
        if not isinstance(raw_item, dict):
            continue
        item = cast("dict[str, Any]", raw_item)
        severity = str(item.get("severity") or "info").lower()
        if severity not in VALID_SEVERITIES:
            severity = "info"
        title = strip_zero_width(str(item.get("title") or ""))
        detail = strip_zero_width(str(item.get("detail") or ""))
        if title:
            findings.append(Finding(severity=severity, title=title, detail=detail))

    return findings
