"""Complexity gate — decides whether a question warrants full deliberation."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from project_magi.providers.base import Message

if TYPE_CHECKING:
    from project_magi.providers.base import Provider

logger = logging.getLogger(__name__)

# Override phrases that force deliberation regardless — checked before the LLM call
_OVERRIDE_PHRASES = [
    "run magi",
    "use magi",
    "magi on this",
    "deliberate on",
    "full deliberation",
]

_GATE_SYSTEM_PROMPT = """\
You are a triage agent. Your only job is to decide whether a question requires \
multi-persona deliberation or can be answered directly.

Multi-persona deliberation is warranted when:
- There is genuine uncertainty about the right approach
- Multiple valid perspectives or trade-offs exist
- The consequences of a wrong decision are significant
- The question involves strategy, design, evaluation, or complex judgment

Direct answer is sufficient when:
- The question has a single, clear, factual answer
- It is a simple lookup, definition, or arithmetic
- There is no meaningful trade-off or judgment involved

Err on the side of deliberation — if you are unsure, choose deliberation.

Respond with ONLY a JSON object, no other text:
{"deliberate": true, "reason": "brief explanation"}
or
{"deliberate": false, "reason": "brief explanation"}
"""


async def should_deliberate(question: str, provider: Provider) -> bool:
    """Decide whether a question warrants full multi-persona deliberation.

    Returns True if the question should go through the full MAGI loop,
    False if it can be answered directly.

    Checks for explicit override phrases first (no LLM call needed),
    then asks the LLM to triage.
    """
    lower = question.lower().strip()

    # Check for explicit override — always deliberate
    for phrase in _OVERRIDE_PHRASES:
        if phrase in lower:
            logger.info("Complexity gate: override phrase detected, deliberating")
            return True

    # Ask the LLM to triage
    try:
        response = await provider.send_message(
            system_prompt=_GATE_SYSTEM_PROMPT,
            messages=[Message(role="user", content=question)],
        )
        result = _parse_gate_response(response.content)
        logger.info("Complexity gate: deliberate=%s", result)
        return result
    except Exception:
        # If the gate call fails, err on the side of deliberation
        logger.warning("Complexity gate failed, defaulting to deliberation", exc_info=True)
        return True


def _parse_gate_response(raw: str) -> bool:
    """Parse the gate LLM response. Defaults to True (deliberate) on any failure."""
    stripped = raw.strip()

    # Handle markdown fences
    if "```json" in stripped:
        start = stripped.index("```json") + len("```json")
        end = stripped.find("```", start)
        if end != -1:
            stripped = stripped[start:end].strip()
    elif stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3].strip()

    try:
        data = json.loads(stripped)
        return bool(data.get("deliberate", True))
    except (json.JSONDecodeError, AttributeError):
        return True
