"""Integration tests for the Claude provider — hits the real API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_magi.providers.base import Message
from project_magi.providers.claude import ClaudeProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_claude_provider_real_api() -> None:
    """Send a real message to the Claude API and validate the response structure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    provider = ClaudeProvider(api_key=api_key)

    response = await provider.send_message(
        system_prompt="You are a helpful assistant. Reply in exactly one sentence.",
        messages=[Message(role="user", content="What is the capital of France?")],
    )

    # Structural assertions — not content assertions
    assert isinstance(response.content, str)
    assert len(response.content) > 0
    assert isinstance(response.model, str)
    assert len(response.model) > 0
    assert isinstance(response.input_tokens, int)
    assert response.input_tokens > 0
    assert isinstance(response.output_tokens, int)
    assert response.output_tokens > 0
    assert response.stop_reason in ("end_turn", "max_tokens", "stop_sequence")
    assert isinstance(response.raw, dict)
    assert "id" in response.raw

    # Record this response as a fixture for downstream unit tests
    fixture_path = FIXTURES_DIR / "claude_simple_response.json"
    fixture_path.write_text(json.dumps(response.raw, indent=2, default=str))
    print(f"\nRecorded fixture to {fixture_path}")
    print(f"Response content: {response.content}")
    print(f"Model: {response.model}")
    print(f"Tokens: {response.input_tokens} in / {response.output_tokens} out")
