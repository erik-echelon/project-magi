"""Integration test for the persona builder — hits the real Claude API."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from project_magi.personas.builder import (
    suggest_personas,
    suggestion_to_persona,
    write_persona_file,
)
from project_magi.personas.parser import parse_persona_file
from project_magi.providers.claude import ClaudeProvider

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_builder_generates_differentiated_personas(tmp_path: Path) -> None:
    """Give the builder a real task and verify the generated personas.

    This test hits the real API, generates persona suggestions, writes
    them to files, and loads them back to verify the full round-trip.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Use sonnet for integration tests to save cost/time
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-20250514")

    task = (
        "I'm planning a go-to-market strategy for a B2B SaaS product "
        "that provides real-time pipeline observability for data engineering teams."
    )

    suggestions = await suggest_personas(provider, task)

    print(f"\nSuggested {len(suggestions)} personas:")
    for s in suggestions:
        print(f"  - {s.name}: {s.description}")
        print(f"    Role: {s.role}")
        print(f"    Priorities: {', '.join(s.priorities)}")

    # At least 3 personas
    assert len(suggestions) >= 3, f"Expected at least 3 suggestions, got {len(suggestions)}"

    # Each has a distinct name
    names = [s.name for s in suggestions]
    assert len(set(names)) == len(names), f"Duplicate names: {names}"

    # Each has a non-empty description
    for s in suggestions:
        assert len(s.description) > 0, f"{s.name} has empty description"

    # No two personas have identical priorities
    priority_sets = [frozenset(s.priorities) for s in suggestions]
    for i, ps1 in enumerate(priority_sets):
        for j, ps2 in enumerate(priority_sets):
            if i != j and ps1 and ps2:
                assert ps1 != ps2, (
                    f"Personas {suggestions[i].name} and {suggestions[j].name} "
                    f"have identical priorities"
                )

    # Convert to personas, write to files, load back
    for suggestion in suggestions:
        persona = suggestion_to_persona(suggestion)
        path = write_persona_file(persona, tmp_path)
        loaded = parse_persona_file(path)

        print(f"\n  Round-trip verified for {loaded.name}")
        print(f"    File: {path}")
        print(f"    Has defense: {loaded.has_prompt_injection_defense}")

        assert loaded.name == suggestion.name
        assert loaded.description == suggestion.description
        assert loaded.has_prompt_injection_defense, (
            f"{loaded.name} missing prompt injection defense"
        )

    # Verify all files exist
    written_files = list(tmp_path.glob("*.md"))
    assert len(written_files) == len(suggestions)
    print(f"\n{len(written_files)} persona files written and verified")
