"""Tests for the deliberation loop."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from project_magi.coordinator.checkpoint import (
    CheckpointAction,
    ContinueAction,
    ContinueWithFeedbackAction,
    RedirectPersonaAction,
    WrapUpAction,
)
from project_magi.coordinator.loop import (
    DeliberationConfig,
    DeliberationState,
    run_deliberation,
)
from project_magi.personas.model import Persona
from project_magi.providers.base import ProviderResponse


def _make_persona(name: str) -> Persona:
    return Persona(
        name=name,
        description=f"Test persona {name}",
        system_prompt=f"You are {name}.",
    )


def _json_persona_response(analysis: str, confidence: float = 0.8) -> str:
    return json.dumps(
        {
            "analysis": analysis,
            "confidence": confidence,
            "findings": [
                {"severity": "info", "title": f"Finding from {analysis[:10]}", "detail": "d"}
            ],
        }
    )


def _json_critique_response() -> str:
    return json.dumps(
        {
            "dimensions": [
                {
                    "name": "Test Dimension",
                    "alignment": "2/3 aligned",
                    "summary": "Mostly agree",
                    "quotes": {},
                }
            ],
            "agreements": [{"point": "They agree on X", "personas": ["a", "b"]}],
            "disagreements": [{"point": "They disagree on Y", "sides": {"a": "yes", "c": "no"}}],
            "talking_past": [],
        }
    )


def _make_mock_provider() -> AsyncMock:
    """Create a provider that returns persona responses then critique responses.

    For a 3-persona round: calls 1-3 are persona agents, call 4 is critique.
    """
    mock = AsyncMock()
    call_count = 0

    async def side_effect(**kwargs: object) -> ProviderResponse:
        nonlocal call_count
        call_count += 1
        # Every 4th call is the critique agent (after 3 persona calls)
        if call_count % 4 == 0:
            return ProviderResponse(content=_json_critique_response(), model="claude-opus-4-6")
        names = ["a", "b", "c"]
        idx = (call_count - 1) % 4
        name = names[idx] if idx < len(names) else "unknown"
        return ProviderResponse(
            content=_json_persona_response(f"{name}'s analysis"),
            model="claude-opus-4-6",
        )

    mock.send_message.side_effect = side_effect
    return mock


class TestDeliberationLoop:
    @pytest.mark.asyncio
    async def test_single_round_wrap_up(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            return WrapUpAction()

        state = await run_deliberation(
            provider, personas, "Test question", on_checkpoint=checkpoint
        )

        assert state.is_complete
        assert state.stopped_reason == "wrap_up"
        assert state.round_count == 1
        assert len(state.rounds[0].persona_result.outputs) == 3
        assert state.rounds[0].critique.dimensions is not None

    @pytest.mark.asyncio
    async def test_two_rounds_then_wrap_up(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        checkpoint_calls = 0

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            nonlocal checkpoint_calls
            checkpoint_calls += 1
            if checkpoint_calls == 1:
                return ContinueAction()
            return WrapUpAction()

        state = await run_deliberation(
            provider, personas, "Test question", on_checkpoint=checkpoint
        )

        assert state.is_complete
        assert state.stopped_reason == "wrap_up"
        assert state.round_count == 2

    @pytest.mark.asyncio
    async def test_max_rounds_enforced(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]

        async def always_continue(state: DeliberationState) -> CheckpointAction:
            return ContinueAction()

        state = await run_deliberation(
            provider,
            personas,
            "Test question",
            config=DeliberationConfig(max_rounds=3),
            on_checkpoint=always_continue,
        )

        assert state.is_complete
        assert state.stopped_reason == "max_rounds"
        assert state.round_count == 3

    @pytest.mark.asyncio
    async def test_human_feedback_stored(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        checkpoint_calls = 0

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            nonlocal checkpoint_calls
            checkpoint_calls += 1
            if checkpoint_calls == 1:
                return ContinueWithFeedbackAction(feedback="Consider the budget")
            return WrapUpAction()

        state = await run_deliberation(
            provider, personas, "Test question", on_checkpoint=checkpoint
        )

        assert state.rounds[0].human_feedback == "Consider the budget"
        assert state.round_count == 2

    @pytest.mark.asyncio
    async def test_redirect_persona_stored(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        checkpoint_calls = 0

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            nonlocal checkpoint_calls
            checkpoint_calls += 1
            if checkpoint_calls == 1:
                return RedirectPersonaAction(persona_name="a", feedback="consider team impact")
            return WrapUpAction()

        state = await run_deliberation(
            provider, personas, "Test question", on_checkpoint=checkpoint
        )

        assert state.rounds[0].redirect_persona == "a"
        assert state.rounds[0].redirect_feedback == "consider team impact"
        assert "Feedback for a" in (state.rounds[0].human_feedback or "")

    @pytest.mark.asyncio
    async def test_no_checkpoint_runs_max_rounds(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]

        state = await run_deliberation(
            provider,
            personas,
            "Test question",
            config=DeliberationConfig(max_rounds=2),
        )

        assert state.is_complete
        assert state.stopped_reason == "max_rounds"
        assert state.round_count == 2

    @pytest.mark.asyncio
    async def test_no_quorum_stops_early(self) -> None:
        """If 2+ agents fail, deliberation stops with no_quorum."""
        mock = AsyncMock()
        call_count = 0

        async def side_effect(**kwargs: object) -> ProviderResponse:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise TimeoutError("Agent timed out")
            return ProviderResponse(
                content=_json_persona_response("survivor"),
                model="claude-opus-4-6",
            )

        mock.send_message.side_effect = side_effect

        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]

        state = await run_deliberation(mock, personas, "Test question")

        assert state.is_complete
        assert state.stopped_reason == "no_quorum"
        assert state.round_count == 1
        assert len(state.rounds[0].persona_result.errors) == 2

    @pytest.mark.asyncio
    async def test_one_agent_failure_continues(self) -> None:
        """If 1 agent fails but 2 succeed, deliberation continues."""
        mock = AsyncMock()
        call_count = 0

        async def side_effect(**kwargs: object) -> ProviderResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise TimeoutError("Agent b timed out")
            if call_count % 4 == 0:
                return ProviderResponse(content=_json_critique_response(), model="claude-opus-4-6")
            return ProviderResponse(
                content=_json_persona_response("analysis"),
                model="claude-opus-4-6",
            )

        mock.send_message.side_effect = side_effect

        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]

        async def wrap_up(state: DeliberationState) -> CheckpointAction:
            return WrapUpAction()

        state = await run_deliberation(mock, personas, "Test question", on_checkpoint=wrap_up)

        assert state.round_count == 1
        assert state.rounds[0].persona_result.is_degraded
        assert state.rounds[0].persona_result.has_quorum
        assert len(state.rounds[0].persona_result.outputs) == 2


class TestDeliberationState:
    def test_latest_critique_none_when_empty(self) -> None:
        state = DeliberationState(question="test")
        assert state.latest_critique is None

    def test_latest_persona_outputs_empty_when_no_rounds(self) -> None:
        state = DeliberationState(question="test")
        assert state.latest_persona_outputs == {}
