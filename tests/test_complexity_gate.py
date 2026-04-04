"""Tests for the complexity gate."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from project_magi.coordinator.complexity_gate import (
    _parse_gate_response,
    should_deliberate,
)
from project_magi.providers.base import ProviderResponse


def _mock_provider(deliberate: bool, reason: str = "test") -> AsyncMock:
    mock = AsyncMock()
    mock.send_message.return_value = ProviderResponse(
        content=json.dumps({"deliberate": deliberate, "reason": reason}),
        model="claude-opus-4-6",
    )
    return mock


class TestShouldDeliberate:
    # Override phrases — should ALWAYS deliberate, no LLM call
    @pytest.mark.asyncio
    async def test_override_run_magi(self) -> None:
        provider = _mock_provider(False)  # LLM says no, but override wins
        result = await should_deliberate("Run MAGI on this: what is 2+2", provider)
        assert result is True
        provider.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_override_use_magi(self) -> None:
        provider = _mock_provider(False)
        result = await should_deliberate("Use MAGI to analyze this problem", provider)
        assert result is True
        provider.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_override_deliberate_on(self) -> None:
        provider = _mock_provider(False)
        result = await should_deliberate("Deliberate on whether we need tests", provider)
        assert result is True
        provider.send_message.assert_not_called()

    # LLM says deliberate
    @pytest.mark.asyncio
    async def test_llm_says_deliberate(self) -> None:
        provider = _mock_provider(True, "This involves trade-offs")
        result = await should_deliberate("Should we migrate to DynamoDB?", provider)
        assert result is True
        provider.send_message.assert_called_once()

    # LLM says skip
    @pytest.mark.asyncio
    async def test_llm_says_skip(self) -> None:
        provider = _mock_provider(False, "Simple factual question")
        result = await should_deliberate("What is 2+2?", provider)
        assert result is False
        provider.send_message.assert_called_once()

    # LLM call fails — default to deliberate
    @pytest.mark.asyncio
    async def test_llm_failure_defaults_to_deliberate(self) -> None:
        provider = AsyncMock()
        provider.send_message.side_effect = TimeoutError("API timeout")
        result = await should_deliberate("Some question", provider)
        assert result is True


class TestParseGateResponse:
    def test_parses_true(self) -> None:
        assert _parse_gate_response('{"deliberate": true, "reason": "complex"}') is True

    def test_parses_false(self) -> None:
        assert _parse_gate_response('{"deliberate": false, "reason": "trivial"}') is False

    def test_json_in_markdown_fence(self) -> None:
        raw = '```json\n{"deliberate": false, "reason": "simple"}\n```'
        assert _parse_gate_response(raw) is False

    def test_invalid_json_defaults_to_true(self) -> None:
        assert _parse_gate_response("not json at all") is True

    def test_missing_field_defaults_to_true(self) -> None:
        assert _parse_gate_response('{"reason": "no deliberate field"}') is True

    def test_empty_string_defaults_to_true(self) -> None:
        assert _parse_gate_response("") is True
