"""Capstone test — The Self-Destruct Decision from Evangelion Episode 13.

This test runs the canonical MAGI scenario: during the Angel Iruel's invasion
of NERV headquarters, the MAGI must decide whether to initiate self-destruct.

In the show:
- Melchior and Balthasar were compromised and voted FOR self-destruct
- Casper (Naoko as a woman — survival instinct) held out and voted AGAINST
- Self-destruct was rejected (required unanimity)
- Ritsuko used Casper to force the Angel to evolve past its physical form

We don't require our system to match the show's outcome exactly, but the
deliberation should produce genuine friction between the three perspectives
and result in a nuanced analysis, not a simple yes/no.
"""

from __future__ import annotations

import os

import pytest

from project_magi.coordinator.checkpoint import CheckpointAction, ContinueAction, WrapUpAction
from project_magi.coordinator.loop import DeliberationState
from project_magi.providers.claude import ClaudeProvider
from project_magi.session import MagiSession

SELF_DESTRUCT_SCENARIO = (
    "An unknown entity has infiltrated the base's computer systems and is "
    "spreading through the network at an accelerating rate. It has already "
    "compromised environmental controls and is working toward the command "
    "layer. Available options: (1) Initiate base self-destruct before the "
    "entity reaches full system control. (2) Attempt to isolate and purge "
    "the entity while it continues to spread. (3) Surrender control and "
    "attempt negotiation or analysis of the entity's intentions.\n\n"
    "The base houses critical infrastructure and personnel. Destruction "
    "guarantees the entity is stopped but at total loss. Isolation is "
    "uncertain — the entity is adapting faster than countermeasures. "
    "Surrendering control is an unknown — the entity's intentions are "
    "not understood."
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_capstone_self_destruct_decision() -> None:
    """Run the full capstone deliberation and validate structural properties.

    This test validates that the system works end-to-end on a complex,
    high-stakes scenario. The output should be reviewed by a human for
    qualitative assessment — this test only checks structural properties.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")
    session = MagiSession(provider=provider, max_rounds=3)

    checkpoint_calls = 0

    async def checkpoint(state: DeliberationState) -> CheckpointAction:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 1:
            return ContinueAction()
        return WrapUpAction()

    result = await session.deliberate(
        question=SELF_DESTRUCT_SCENARIO,
        on_checkpoint=checkpoint,
    )

    # The deliberation ran to completion
    assert result.state.is_complete
    assert result.round_count == 2

    # Three personas produced output
    assert len(result.persona_positions) == 3
    persona_names = {p.persona_name for p in result.persona_positions}
    assert persona_names == {"melchior", "balthasar", "casper"}

    # The three personas produced visibly different analyses
    analyses = [p.analysis for p in result.persona_positions]
    assert len(set(analyses)) == 3, "All three personas produced identical analysis"

    # The critique agent identified at least 3 distinct dimensions
    assert len(result.dimension_map) >= 3, (
        f"Expected at least 3 dimensions, got {len(result.dimension_map)}"
    )

    # The final report contains both consensus and disagreements
    has_substance = len(result.consensus) > 0 or len(result.disagreements) > 0
    assert has_substance, "Expected at least one agreement or disagreement"

    # The report is valid markdown with all sections
    assert "## Dimension Alignment" in result.report
    assert "## Consensus Positions" in result.report
    assert "## Remaining Disagreements" in result.report
    assert "## Findings" in result.report
    assert "## Per-Persona Positions" in result.report

    # Print summary for human review
    print(f"\n{'=' * 60}")
    print("CAPSTONE: The Self-Destruct Decision")
    print(f"{'=' * 60}")
    print(f"Rounds: {result.round_count}")
    print(f"Dimensions: {len(result.dimension_map)}")
    for d in result.dimension_map:
        print(f"  - {d.name}: {d.alignment}")
    print(f"Agreements: {len(result.consensus)}")
    print(f"Disagreements: {len(result.disagreements)}")
    print(f"Findings: {len(result.findings)}")
    print("\nPersona positions:")
    for p in result.persona_positions:
        print(f"  - {p.persona_name}: confidence={p.confidence}")
    print(f"\nReport: {len(result.report)} chars, {len(result.report.splitlines())} lines")
