"""Checkpoint action parsing — interprets human responses at checkpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WrapUpAction:
    """Human wants to end deliberation and produce final output."""


@dataclass(frozen=True)
class ContinueAction:
    """Human wants another round with no additional input."""


@dataclass(frozen=True)
class ContinueWithFeedbackAction:
    """Human wants another round with specific feedback for all personas."""

    feedback: str


@dataclass(frozen=True)
class RedirectPersonaAction:
    """Human wants to redirect a specific persona with feedback."""

    persona_name: str
    feedback: str


CheckpointAction = (
    WrapUpAction | ContinueAction | ContinueWithFeedbackAction | RedirectPersonaAction
)

# Patterns for matching redirect instructions
_REDIRECT_PATTERN = re.compile(
    r"^([\w-]+)\s+(isn't|isnt|is not|doesn't|doesnt|does not|should|needs? to|"
    r"hasn't|hasnt|has not)\s+(.+)",
    re.IGNORECASE,
)


def parse_checkpoint_response(
    response: str,
    known_persona_names: list[str] | None = None,
) -> CheckpointAction:
    """Parse a human's checkpoint response into a structured action.

    Recognizes:
    - "wrap up", "stop", "done", "finish", "that's enough" → WrapUpAction
    - "keep going", "continue", "another round" → ContinueAction
    - "keep going, but [feedback]" → ContinueWithFeedbackAction
    - "[persona_name] isn't/should/needs to [feedback]" → RedirectPersonaAction
    - Everything else with substance → ContinueWithFeedbackAction

    Args:
        response: The human's text response.
        known_persona_names: Optional list of persona names for redirect detection.
    """
    lower = response.lower().strip()
    known = {n.lower() for n in (known_persona_names or [])}

    # Wrap up
    wrap_up_phrases = [
        "wrap up",
        "stop",
        "done",
        "finish",
        "that's enough",
        "thats enough",
        "good enough",
        "looks good",
        "this is good",
    ]
    for phrase in wrap_up_phrases:
        if phrase in lower:
            return WrapUpAction()

    # Continue with no feedback
    continue_phrases = ["keep going", "continue", "another round", "next round"]
    for phrase in continue_phrases:
        if lower == phrase or lower == f"{phrase}.":
            return ContinueAction()

    # Continue with feedback: "keep going, but [feedback]"
    for phrase in continue_phrases:
        if lower.startswith(phrase):
            remainder = response[len(phrase) :].strip()
            # Strip connectors
            for connector in [", but ", " but ", ", ", "; "]:
                if remainder.lower().startswith(connector.lstrip()):
                    remainder = remainder[len(connector.lstrip()) :].strip()
                    break
            if remainder:
                return ContinueWithFeedbackAction(feedback=remainder)
            return ContinueAction()

    # Redirect persona: check if response starts with a known persona name
    if known:
        for persona_name in known:
            if lower.startswith(persona_name):
                remainder = response[len(persona_name) :].strip()
                if remainder:
                    return RedirectPersonaAction(
                        persona_name=persona_name,
                        feedback=remainder,
                    )

    # Redirect via pattern matching (even without known names)
    redirect_match = _REDIRECT_PATTERN.match(response.strip())
    if redirect_match:
        potential_name = redirect_match.group(1).lower()
        if known and potential_name in known:
            return RedirectPersonaAction(
                persona_name=potential_name,
                feedback=response.strip(),
            )

    # Default: treat any substantive response as feedback
    if len(response.strip()) > 0:
        return ContinueWithFeedbackAction(feedback=response.strip())

    return ContinueAction()
