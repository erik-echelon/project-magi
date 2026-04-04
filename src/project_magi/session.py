"""MagiSession — the public API for running deliberations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from project_magi.agents.critique import (
    CritiqueOutput,
    DeduplicatedFinding,
    DimensionAlignment,
)
from project_magi.coordinator.loop import (
    DeliberationConfig,
    DeliberationRound,
    DeliberationState,
    run_deliberation,
)
from project_magi.personas.parser import discover_personas
from project_magi.providers.base import Attachment
from project_magi.providers.claude import ClaudeProvider
from project_magi.reporting.renderer import render_report

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from project_magi.agents.critique import Agreement, Disagreement
    from project_magi.coordinator.checkpoint import CheckpointAction
    from project_magi.personas.model import Persona
    from project_magi.providers.base import Provider


@dataclass(frozen=True)
class PersonaPosition:
    """A persona's final position at the end of deliberation."""

    persona_name: str
    confidence: float
    analysis: str


@dataclass(frozen=True)
class MagiResult:
    """Result of a MAGI deliberation.

    This is the primary output object — it contains everything a consumer
    needs to render, display, or further process the deliberation.
    """

    consensus: list[Agreement]
    disagreements: list[Disagreement]
    dimension_map: list[DimensionAlignment]
    findings: list[DeduplicatedFinding]
    persona_positions: list[PersonaPosition]
    transcript: list[DeliberationRound]
    report: str
    state: DeliberationState

    @property
    def round_count(self) -> int:
        return len(self.transcript)

    @property
    def is_degraded(self) -> bool:
        return any(r.persona_result.is_degraded for r in self.transcript)


class MagiSession:
    """A MAGI deliberation session.

    This is the main entry point for the library. Create a session with
    personas and provider configuration, then call deliberate() with a
    question.

    Example::

        session = MagiSession(
            personas=[melchior, balthasar, casper],
            max_rounds=3,
        )
        result = await session.deliberate(
            question="Should we prioritize the API rewrite?",
            on_checkpoint=my_callback,
        )
    """

    def __init__(
        self,
        *,
        personas: list[Persona] | None = None,
        personas_dir: Path | str | None = None,
        max_rounds: int = 3,
        provider: Provider | None = None,
        model: str | None = None,
        api_key: str | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize a MAGI session.

        Args:
            personas: Explicit list of Persona objects. If None, loads from
                personas_dir or the default .claude/agents/ directory.
            personas_dir: Directory to load personas from. Defaults to
                .claude/agents/ relative to cwd.
            max_rounds: Maximum deliberation rounds (default 3).
            provider: An LLM provider instance. If None, creates a
                ClaudeProvider with the given model and api_key.
            model: Model name for the auto-created provider.
            api_key: API key for the auto-created provider.
            verbose: If True, generate verbose reports (default False).
        """
        # Load personas
        if personas is not None:
            self.personas = personas
        else:
            dir_path = Path(personas_dir) if personas_dir else None
            discovery = discover_personas(dir_path)
            if discovery.errors:
                for path, error in discovery.errors:
                    import logging

                    logging.getLogger(__name__).warning(
                        "Skipping invalid persona %s: %s", path, error
                    )
            self.personas = discovery.personas

        # Set up provider
        if provider is not None:
            self.provider = provider
        elif model and api_key:
            self.provider = ClaudeProvider(model=model, api_key=api_key)
        elif model:
            self.provider = ClaudeProvider(model=model)
        elif api_key:
            self.provider = ClaudeProvider(api_key=api_key)
        else:
            self.provider = ClaudeProvider()

        self.max_rounds = max_rounds
        self.verbose = verbose

    async def deliberate(
        self,
        question: str,
        attachments: list[str | Path | Attachment] | None = None,
        *,
        on_checkpoint: Callable[[DeliberationState], Awaitable[CheckpointAction]] | None = None,
    ) -> MagiResult:
        """Run a full deliberation on the given question.

        Args:
            question: The question to deliberate on.
            attachments: Optional list of file paths (str/Path) or
                Attachment objects.
            on_checkpoint: Async callback invoked after each round.
                Receives the current state and returns a CheckpointAction.
                If None, runs for max_rounds automatically.

        Returns:
            A MagiResult with all deliberation outputs.
        """
        resolved_attachments = _resolve_attachments(attachments)

        state = await run_deliberation(
            provider=self.provider,
            personas=self.personas,
            question=question,
            attachments=resolved_attachments or None,
            config=DeliberationConfig(max_rounds=self.max_rounds),
            on_checkpoint=on_checkpoint,
        )

        return _build_result(state, verbose=self.verbose)


def _resolve_attachments(
    attachments: list[str | Path | Attachment] | None,
) -> list[Attachment]:
    """Convert a mix of file paths and Attachment objects to Attachment list."""
    if not attachments:
        return []

    result: list[Attachment] = []
    for item in attachments:
        if isinstance(item, Attachment):
            result.append(item)
        else:
            result.append(Attachment.from_path(item))
    return result


def _build_result(state: DeliberationState, *, verbose: bool = False) -> MagiResult:
    """Convert a completed DeliberationState into a MagiResult."""
    # Extract final round data
    last_critique = state.latest_critique or CritiqueOutput()
    last_outputs = list(state.latest_persona_outputs.values())

    # Build persona positions
    positions = [
        PersonaPosition(
            persona_name=o.persona_name,
            confidence=o.confidence,
            analysis=o.analysis,
        )
        for o in sorted(last_outputs, key=lambda o: o.persona_name)
    ]

    # Render the report
    report = render_report(state, verbose=verbose)

    return MagiResult(
        consensus=list(last_critique.agreements),
        disagreements=list(last_critique.disagreements),
        dimension_map=list(last_critique.dimensions),
        findings=list(last_critique.deduplicated_findings),
        persona_positions=positions,
        transcript=list(state.rounds),
        report=report,
        state=state,
    )
