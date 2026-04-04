"""Integration test for the full deliberation loop — hits the real Claude API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_magi.coordinator.checkpoint import CheckpointAction, WrapUpAction
from project_magi.coordinator.loop import (
    DeliberationConfig,
    DeliberationState,
    run_deliberation,
)
from project_magi.personas.parser import discover_personas
from project_magi.providers.claude import ClaudeProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_one_round_deliberation() -> None:
    """Run a complete 1-round deliberation with real API calls.

    This is the first end-to-end integration test: load real personas,
    run them in parallel, run the critique agent, and verify the full
    state is populated.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Load real personas
    agents_dir = Path.cwd() / ".claude" / "agents"
    discovery = discover_personas(agents_dir)
    personas = [p for p in discovery.personas if p.name in ("melchior", "balthasar", "casper")]
    assert len(personas) == 3

    # Use sonnet for integration tests to save cost/time
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")

    async def auto_wrap_up(state: DeliberationState) -> CheckpointAction:
        return WrapUpAction()

    state = await run_deliberation(
        provider,
        personas,
        "Should we adopt a microservices architecture for our monolithic e-commerce platform?",
        config=DeliberationConfig(max_rounds=3),
        on_checkpoint=auto_wrap_up,
    )

    # Verify completion
    assert state.is_complete
    assert state.stopped_reason == "wrap_up"
    assert state.round_count == 1

    # Verify persona outputs
    round1 = state.rounds[0]
    persona_names = {o.persona_name for o in round1.persona_result.outputs}
    print(f"\nPersonas that produced output: {persona_names}")
    assert len(round1.persona_result.outputs) == 3, (
        f"Expected 3 outputs, got {len(round1.persona_result.outputs)}. "
        f"Errors: {round1.persona_result.errors}"
    )
    assert len(round1.persona_result.errors) == 0

    for output in round1.persona_result.outputs:
        print(f"\n--- {output.persona_name} ---")
        print(f"Confidence: {output.confidence}")
        print(f"Analysis length: {len(output.analysis)} chars")
        print(f"Findings: {len(output.findings)}")
        assert len(output.analysis) > 0
        assert 0.0 <= output.confidence <= 1.0

    # Verify critique
    critique = round1.critique
    print(f"\nDimensions: {len(critique.dimensions)}")
    for d in critique.dimensions:
        print(f"  - {d.name}: {d.alignment}")
    print(f"Agreements: {len(critique.agreements)}")
    print(f"Disagreements: {len(critique.disagreements)}")
    print(f"Deduplicated findings: {len(critique.deduplicated_findings)}")

    assert len(critique.dimensions) >= 2
    assert len(critique.agreements) >= 1 or len(critique.disagreements) >= 1

    # Record the full deliberation state as a fixture
    fixture_data = {
        "question": state.question,
        "round_count": state.round_count,
        "stopped_reason": state.stopped_reason,
        "persona_outputs": [
            {
                "persona_name": o.persona_name,
                "confidence": o.confidence,
                "analysis_length": len(o.analysis),
                "findings_count": len(o.findings),
            }
            for o in round1.persona_result.outputs
        ],
        "critique_summary": {
            "dimensions": len(critique.dimensions),
            "agreements": len(critique.agreements),
            "disagreements": len(critique.disagreements),
            "deduplicated_findings": len(critique.deduplicated_findings),
        },
    }
    fixture_path = FIXTURES_DIR / "deliberation_1round.json"
    fixture_path.write_text(json.dumps(fixture_data, indent=2))
    print(f"\nRecorded fixture to {fixture_path}")
