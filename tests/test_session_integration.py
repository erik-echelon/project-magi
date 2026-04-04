"""Integration test for MagiSession — full end-to-end with real API."""

from __future__ import annotations

import os

import pytest

from project_magi.coordinator.checkpoint import CheckpointAction, ContinueAction, WrapUpAction
from project_magi.coordinator.loop import DeliberationState
from project_magi.providers.claude import ClaudeProvider
from project_magi.session import MagiSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_two_round_deliberation() -> None:
    """Run a complete 2-round deliberation via MagiSession.

    This is the full end-to-end test: load default personas, run 2 rounds
    with real API calls, verify all result fields are populated.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Use sonnet for integration tests to save cost/time
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")

    # Load default personas from .claude/agents/
    session = MagiSession(provider=provider, max_rounds=3)

    # Verify defaults loaded
    persona_names = {p.name for p in session.personas}
    assert "melchior" in persona_names
    assert "balthasar" in persona_names
    assert "casper" in persona_names

    checkpoint_calls = 0

    async def checkpoint(state: DeliberationState) -> CheckpointAction:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        print(f"\n--- Checkpoint {checkpoint_calls} (round {state.round_count}) ---")
        critique = state.latest_critique
        if critique:
            print(f"Dimensions: {len(critique.dimensions)}")
            print(f"Agreements: {len(critique.agreements)}")
            print(f"Disagreements: {len(critique.disagreements)}")
        if checkpoint_calls == 1:
            return ContinueAction()
        return WrapUpAction()

    result = await session.deliberate(
        question=(
            "Should we adopt a microservices architecture for our monolithic e-commerce platform?"
        ),
        on_checkpoint=checkpoint,
    )

    # Verify structure
    print(f"\nRounds: {result.round_count}")
    print(f"Stopped: {result.state.stopped_reason}")
    print(f"Degraded: {result.is_degraded}")

    assert result.round_count == 2
    assert result.state.stopped_reason == "wrap_up"
    assert checkpoint_calls == 2

    # result.consensus or result.disagreements should be non-empty
    assert len(result.consensus) > 0 or len(result.disagreements) > 0, (
        "Expected at least one agreement or disagreement"
    )

    # Dimension map
    print(f"\nDimension map: {len(result.dimension_map)} dimensions")
    for d in result.dimension_map:
        print(f"  - {d.name}: {d.alignment}")
    assert len(result.dimension_map) >= 2

    # Persona positions
    print(f"\nPersona positions: {len(result.persona_positions)}")
    for p in result.persona_positions:
        print(f"  - {p.persona_name}: confidence={p.confidence}")
    assert len(result.persona_positions) == 3

    # Transcript
    assert len(result.transcript) == 2

    # Findings
    print(f"\nFindings: {len(result.findings)}")
    assert isinstance(result.findings, list)

    # Report
    assert "## Dimension Alignment" in result.report
    assert "## Per-Persona Positions" in result.report
    print(f"\nReport length: {len(result.report)} chars, {len(result.report.splitlines())} lines")
