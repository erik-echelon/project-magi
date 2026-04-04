"""Integration test for the critique agent — hits the real Claude API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_magi.agents.critique import run_critique_agent
from project_magi.agents.output import Finding, PersonaOutput
from project_magi.providers.claude import ClaudeProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_persona_output(name: str) -> PersonaOutput:
    """Load a recorded persona output fixture."""
    path = FIXTURES_DIR / f"persona_output_{name}.json"
    data = json.loads(path.read_text())
    return PersonaOutput(
        persona_name=data["persona_name"],
        analysis=data["analysis"],
        confidence=data["confidence"],
        findings=[
            Finding(severity=f["severity"], title=f["title"], detail=f["detail"])
            for f in data["findings"]
        ],
        raw_response=data.get("raw_response", ""),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_critique_agent_on_real_persona_outputs() -> None:
    """Feed recorded persona outputs into the real critique agent.

    Uses the persona output fixtures from MAGI-4's integration test.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Load the recorded persona outputs from Epic 4
    melchior = _load_persona_output("melchior")
    balthasar = _load_persona_output("balthasar")
    casper = _load_persona_output("casper")

    # Use sonnet for integration tests to save cost/time
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")

    result = await run_critique_agent(provider, [melchior, balthasar, casper])

    # Structural assertions
    print(f"\nDimensions: {len(result.dimensions)}")
    for d in result.dimensions:
        print(f"  - {d.name}: {d.alignment} — {d.summary}")

    print(f"\nAgreements: {len(result.agreements)}")
    for a in result.agreements:
        print(f"  - {a.point} ({', '.join(a.personas)})")

    print(f"\nDisagreements: {len(result.disagreements)}")
    for d in result.disagreements:
        print(f"  - {d.point}")

    print(f"\nTalking past: {len(result.talking_past)}")

    print(f"\nDeduplicated findings: {len(result.deduplicated_findings)}")
    for f in result.deduplicated_findings:
        print(f"  - [{f.severity}] {f.title} (sources: {', '.join(f.sources)})")

    # At least 2 dimensions identified
    assert len(result.dimensions) >= 2, (
        f"Expected at least 2 dimensions, got {len(result.dimensions)}"
    )

    # Each dimension has an alignment value
    for dim in result.dimensions:
        assert dim.name, "Dimension has empty name"
        assert dim.alignment, f"Dimension '{dim.name}' has empty alignment"

    # At least one agreement and one disagreement
    assert len(result.agreements) >= 1, "Expected at least 1 agreement"
    assert len(result.disagreements) >= 1, "Expected at least 1 disagreement"

    # Deduplicated findings are non-empty (the persona outputs had findings)
    assert len(result.deduplicated_findings) > 0, "Expected deduplicated findings"

    # Findings are sorted by severity (critical first)
    severities = [f.severity for f in result.deduplicated_findings]
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    severity_ranks = [severity_order.get(s, 3) for s in severities]
    assert severity_ranks == sorted(severity_ranks), "Findings not sorted by severity"

    # Record the critique output as a fixture
    fixture_data = {
        "dimensions": [
            {
                "name": d.name,
                "alignment": d.alignment,
                "summary": d.summary,
                "quotes": d.quotes,
            }
            for d in result.dimensions
        ],
        "agreements": [
            {"point": a.point, "personas": a.personas, "note": a.note} for a in result.agreements
        ],
        "disagreements": [{"point": d.point, "sides": d.sides} for d in result.disagreements],
        "talking_past": [
            {"description": t.description, "personas_involved": t.personas_involved}
            for t in result.talking_past
        ],
        "deduplicated_findings": [
            {
                "severity": f.severity,
                "title": f.title,
                "detail": f.detail,
                "sources": f.sources,
            }
            for f in result.deduplicated_findings
        ],
        "raw_response": result.raw_response,
    }
    fixture_path = FIXTURES_DIR / "critique_output.json"
    fixture_path.write_text(json.dumps(fixture_data, indent=2))
    print(f"\nRecorded critique fixture to {fixture_path}")
