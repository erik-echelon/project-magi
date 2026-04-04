"""Persona agent runner — executes persona agents and handles parallel coordination."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from project_magi.agents.output import PersonaOutput
from project_magi.providers.base import Attachment, Message

if TYPE_CHECKING:
    from project_magi.personas.model import Persona
    from project_magi.providers.base import Provider

logger = logging.getLogger(__name__)

OUTPUT_FORMAT_INSTRUCTIONS = """
Respond with a JSON object in this exact format (no markdown fences, just raw JSON):
{
  "analysis": "Your detailed analysis as a string (multiple paragraphs OK)",
  "confidence": 0.85,
  "findings": [
    {
      "severity": "critical | warning | info",
      "title": "Short finding title",
      "detail": "Full explanation"
    }
  ]
}

The confidence score should be between 0.0 and 1.0, reflecting how certain you are
in your overall assessment. The findings list should contain specific issues, risks,
or observations you identified, each classified by severity.
"""


def _build_round1_prompt(question: str) -> str:
    """Build the user-facing prompt for round 1."""
    return f"""\
## Question for Analysis

{question}

## Instructions

Analyze the above from your persona's perspective. Be specific and direct.
Produce your response as structured JSON.

{OUTPUT_FORMAT_INSTRUCTIONS}"""


def _build_round2_prompt(
    question: str,
    prior_output: PersonaOutput,
    critique_synthesis: str,
    human_feedback: str | None = None,
) -> str:
    """Build the user-facing prompt for round 2+."""
    parts = [
        "## Original Question\n",
        question,
        "\n\n## Your Prior Analysis\n",
        prior_output.analysis,
        "\n\n## Critique Synthesis\n",
        "The following is the critique agent's synthesis of all persona outputs "
        "from the previous round, including direct quotes from other personas:\n\n",
        critique_synthesis,
    ]

    if human_feedback:
        parts.extend(
            [
                "\n\n## Human Feedback\n",
                "The human reviewer provided this feedback:\n\n",
                human_feedback,
            ]
        )

    parts.extend(
        [
            "\n\n## Instructions\n",
            "Review the critique synthesis and any human feedback. Respond to the "
            "other personas' arguments. You may defend, revise, or sharpen your "
            "position. Be specific about where you agree, where you disagree, "
            "and why.\n\n",
            OUTPUT_FORMAT_INSTRUCTIONS,
        ]
    )

    return "".join(parts)


class PersonaAgentRunner:
    """Runs a single persona agent against a provider."""

    def __init__(self, persona: Persona, provider: Provider) -> None:
        self.persona = persona
        self.provider = provider

    async def run_round1(
        self,
        question: str,
        attachments: list[Attachment] | None = None,
    ) -> PersonaOutput:
        """Run the persona agent for round 1 (independent analysis)."""
        system_prompt = self.persona.system_prompt
        user_prompt = _build_round1_prompt(question)

        response = await self.provider.send_message(
            system_prompt=system_prompt,
            messages=[Message(role="user", content=user_prompt)],
            attachments=attachments,
        )

        return PersonaOutput.parse(self.persona.name, response.content)

    async def run_round2(
        self,
        question: str,
        prior_output: PersonaOutput,
        critique_synthesis: str,
        human_feedback: str | None = None,
        attachments: list[Attachment] | None = None,
    ) -> PersonaOutput:
        """Run the persona agent for round 2+ (response to critique)."""
        system_prompt = self.persona.system_prompt
        user_prompt = _build_round2_prompt(
            question=question,
            prior_output=prior_output,
            critique_synthesis=critique_synthesis,
            human_feedback=human_feedback,
        )

        response = await self.provider.send_message(
            system_prompt=system_prompt,
            messages=[Message(role="user", content=user_prompt)],
            attachments=attachments,
        )

        return PersonaOutput.parse(self.persona.name, response.content)


@dataclass
class PersonaAgentResult:
    """Result from running multiple persona agents in parallel."""

    outputs: list[PersonaOutput] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_degraded(self) -> bool:
        """True if any agents failed."""
        return len(self.errors) > 0

    @property
    def has_quorum(self) -> bool:
        """True if at least 2 agents succeeded."""
        return len(self.outputs) >= 2


async def run_persona_agents(
    runners: list[PersonaAgentRunner],
    question: str,
    attachments: list[Attachment] | None = None,
    *,
    prior_outputs: dict[str, PersonaOutput] | None = None,
    critique_synthesis: str | None = None,
    human_feedback: str | None = None,
) -> PersonaAgentResult:
    """Run multiple persona agents in parallel.

    For round 1: pass question and attachments only.
    For round 2+: also pass prior_outputs, critique_synthesis, and optionally human_feedback.

    Returns a PersonaAgentResult with successful outputs and any errors.
    Individual agent failures do not abort the group.
    """
    is_round1 = prior_outputs is None

    async def _run_one(runner: PersonaAgentRunner) -> PersonaOutput:
        if is_round1 or prior_outputs is None:
            return await runner.run_round1(question, attachments)
        prior = prior_outputs.get(runner.persona.name)
        if prior is None:
            msg = f"No prior output for {runner.persona.name}"
            raise ValueError(msg)
        return await runner.run_round2(
            question=question,
            prior_output=prior,
            critique_synthesis=critique_synthesis or "",
            human_feedback=human_feedback,
            attachments=attachments,
        )

    tasks = [asyncio.create_task(_run_one(r)) for r in runners]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    result = PersonaAgentResult()
    for runner, outcome in zip(runners, results, strict=True):
        if isinstance(outcome, BaseException):
            error_msg = f"{type(outcome).__name__}: {outcome}"
            logger.warning("Persona agent %s failed: %s", runner.persona.name, error_msg)
            result.errors.append((runner.persona.name, error_msg))
        else:
            result.outputs.append(outcome)

    return result
