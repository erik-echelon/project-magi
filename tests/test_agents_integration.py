"""Integration tests for persona agents — hits the real Claude API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_magi.agents.runner import PersonaAgentRunner, run_persona_agents
from project_magi.personas.parser import discover_personas
from project_magi.providers.claude import ClaudeProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_personas_produce_differentiated_output() -> None:
    """Run all three default MAGI personas on the same prompt.

    Asserts structural properties of the output and that the three
    personas produce genuinely different analyses.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Load real personas from .claude/agents/
    agents_dir = Path.cwd() / ".claude" / "agents"
    discovery = discover_personas(agents_dir)
    personas = {p.name: p for p in discovery.personas}

    assert "melchior" in personas, "melchior persona not found"
    assert "balthasar" in personas, "balthasar persona not found"
    assert "casper" in personas, "casper persona not found"

    # Use sonnet for integration tests to save cost/time
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")

    runners = [
        PersonaAgentRunner(personas["melchior"], provider),
        PersonaAgentRunner(personas["balthasar"], provider),
        PersonaAgentRunner(personas["casper"], provider),
    ]

    question = "Should we rewrite this service in Rust?"

    result = await run_persona_agents(runners, question)

    # All three should succeed
    assert len(result.outputs) == 3, (
        f"Expected 3 outputs, got {len(result.outputs)}. Errors: {result.errors}"
    )
    assert len(result.errors) == 0
    assert not result.is_degraded
    assert result.has_quorum

    # Structural assertions on each output
    for output in result.outputs:
        print(f"\n--- {output.persona_name} ---")
        print(f"Confidence: {output.confidence}")
        print(f"Analysis length: {len(output.analysis)} chars")
        print(f"Findings: {len(output.findings)}")
        print(f"Analysis preview: {output.analysis[:200]}...")

        assert isinstance(output.analysis, str)
        assert len(output.analysis) > 0, f"{output.persona_name} returned empty analysis"
        assert isinstance(output.confidence, float)
        assert 0.0 <= output.confidence <= 1.0
        assert isinstance(output.findings, list)

    # Differentiation: the three analyses should not be identical
    analyses = [o.analysis for o in result.outputs]
    assert len(set(analyses)) == 3, "All three personas produced identical analysis"

    # Record responses as fixtures for downstream unit tests
    for output in result.outputs:
        fixture_data = {
            "persona_name": output.persona_name,
            "analysis": output.analysis,
            "confidence": output.confidence,
            "findings": [
                {"severity": f.severity, "title": f.title, "detail": f.detail}
                for f in output.findings
            ],
            "raw_response": output.raw_response,
        }
        fixture_path = FIXTURES_DIR / f"persona_output_{output.persona_name}.json"
        fixture_path.write_text(json.dumps(fixture_data, indent=2))
        print(f"\nRecorded fixture to {fixture_path}")
