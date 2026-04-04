"""Deliberation loop — orchestrates the full multi-round process."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from project_magi.agents.critique import CritiqueOutput, run_critique_agent
from project_magi.agents.runner import (
    PersonaAgentResult,
    PersonaAgentRunner,
    run_persona_agents,
)

if TYPE_CHECKING:
    from project_magi.agents.output import PersonaOutput
    from project_magi.coordinator.checkpoint import CheckpointAction
    from project_magi.personas.model import Persona
    from project_magi.providers.base import Attachment, Provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliberationConfig:
    """Configuration for a deliberation session."""

    max_rounds: int = 3


@dataclass
class DeliberationRound:
    """The result of a single round of deliberation."""

    round_number: int
    persona_result: PersonaAgentResult
    critique: CritiqueOutput
    human_feedback: str | None = None
    redirect_persona: str | None = None
    redirect_feedback: str | None = None


@dataclass
class DeliberationState:
    """Full state of a deliberation, accumulated across rounds."""

    question: str
    rounds: list[DeliberationRound] = field(default_factory=list)
    is_complete: bool = False
    stopped_reason: str = ""  # "wrap_up", "max_rounds", "no_quorum"

    @property
    def latest_critique(self) -> CritiqueOutput | None:
        if not self.rounds:
            return None
        return self.rounds[-1].critique

    @property
    def latest_persona_outputs(self) -> dict[str, PersonaOutput]:
        if not self.rounds:
            return {}
        return {o.persona_name: o for o in self.rounds[-1].persona_result.outputs}

    @property
    def round_count(self) -> int:
        return len(self.rounds)


# Type alias for the checkpoint callback
CheckpointCallback = Callable[[DeliberationState], Awaitable["CheckpointAction"]]


async def run_deliberation(
    provider: Provider,
    personas: list[Persona],
    question: str,
    attachments: list[Attachment] | None = None,
    *,
    config: DeliberationConfig | None = None,
    on_checkpoint: CheckpointCallback | None = None,
) -> DeliberationState:
    """Run the full deliberation loop.

    Args:
        provider: The LLM provider to use.
        personas: List of personas to run.
        question: The human's question.
        attachments: Optional attachments.
        config: Deliberation configuration (max rounds, etc.).
        on_checkpoint: Async callback invoked after each round. Receives the
            current state and returns a CheckpointAction. If None, the loop
            runs for max_rounds and wraps up automatically.

    Returns:
        The final DeliberationState with all rounds.
    """
    from project_magi.coordinator.checkpoint import (
        ContinueAction,
        ContinueWithFeedbackAction,
        RedirectPersonaAction,
        WrapUpAction,
    )

    cfg = config or DeliberationConfig()
    state = DeliberationState(question=question)

    runners = [PersonaAgentRunner(p, provider) for p in personas]

    for round_num in range(1, cfg.max_rounds + 1):
        logger.info("Starting round %d", round_num)

        # Run persona agents
        if round_num == 1:
            persona_result = await run_persona_agents(runners, question, attachments)
        else:
            prev_round = state.rounds[-1]
            persona_result = await run_persona_agents(
                runners,
                question,
                attachments,
                prior_outputs=state.latest_persona_outputs,
                critique_synthesis=prev_round.critique.raw_response,
                human_feedback=prev_round.human_feedback,
            )

        # Check quorum
        if not persona_result.has_quorum:
            logger.warning(
                "Round %d: fewer than 2 agents succeeded. Stopping.",
                round_num,
            )
            state.rounds.append(
                DeliberationRound(
                    round_number=round_num,
                    persona_result=persona_result,
                    critique=CritiqueOutput(),
                )
            )
            state.is_complete = True
            state.stopped_reason = "no_quorum"
            return state

        # Run critique agent
        critique = await run_critique_agent(provider, persona_result.outputs)

        round_data = DeliberationRound(
            round_number=round_num,
            persona_result=persona_result,
            critique=critique,
        )
        state.rounds.append(round_data)

        # Last round — no checkpoint, just wrap up
        if round_num == cfg.max_rounds:
            state.is_complete = True
            state.stopped_reason = "max_rounds"
            return state

        # Human checkpoint
        if on_checkpoint is not None:
            action = await on_checkpoint(state)

            if isinstance(action, WrapUpAction):
                state.is_complete = True
                state.stopped_reason = "wrap_up"
                return state
            elif isinstance(action, ContinueAction):
                pass
            elif isinstance(action, ContinueWithFeedbackAction):
                round_data.human_feedback = action.feedback
            elif isinstance(action, RedirectPersonaAction):
                round_data.redirect_persona = action.persona_name
                round_data.redirect_feedback = action.feedback
                # Route redirect as human feedback so the targeted persona sees it
                round_data.human_feedback = (
                    f"[Feedback for {action.persona_name}]: {action.feedback}"
                )
        # If no callback, continue automatically

    state.is_complete = True
    state.stopped_reason = "max_rounds"
    return state
