"""Tests for MagiSession and MagiResult."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from project_magi.coordinator.checkpoint import (
    CheckpointAction,
    ContinueAction,
    WrapUpAction,
)
from project_magi.coordinator.loop import DeliberationState
from project_magi.personas.model import Persona
from project_magi.providers.base import Attachment, ProviderResponse
from project_magi.session import MagiSession, _resolve_attachments

if TYPE_CHECKING:
    from pathlib import Path


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
                {"severity": "info", "title": f"Finding from {name}", "detail": "d"}
                for name in [analysis[:10]]
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
    """Create a provider mock that handles persona + critique calls."""
    mock = AsyncMock()
    call_count = 0

    async def side_effect(**kwargs: object) -> ProviderResponse:
        nonlocal call_count
        call_count += 1
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


class TestMagiSessionInit:
    def test_with_explicit_personas(self) -> None:
        personas = [_make_persona("a"), _make_persona("b")]
        mock_provider = AsyncMock()
        session = MagiSession(personas=personas, provider=mock_provider)
        assert len(session.personas) == 2
        assert session.max_rounds == 3

    def test_loads_default_personas(self) -> None:
        mock_provider = AsyncMock()
        session = MagiSession(provider=mock_provider)
        # Should load from .claude/agents/
        names = {p.name for p in session.personas}
        assert "melchior" in names
        assert "balthasar" in names
        assert "casper" in names

    def test_custom_max_rounds(self) -> None:
        mock_provider = AsyncMock()
        session = MagiSession(
            personas=[_make_persona("a")],
            provider=mock_provider,
            max_rounds=5,
        )
        assert session.max_rounds == 5

    def test_loads_from_custom_dir(self, tmp_path: Path) -> None:
        # Write a persona to the custom dir
        (tmp_path / "test.md").write_text(
            '---\nname: custom\ndescription: "Custom persona"\n---\n\nBody.'
        )
        mock_provider = AsyncMock()
        session = MagiSession(personas_dir=tmp_path, provider=mock_provider)
        assert len(session.personas) == 1
        assert session.personas[0].name == "custom"


class TestDeliberate:
    @pytest.mark.asyncio
    async def test_single_round_returns_result(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider)

        async def wrap_up(state: DeliberationState) -> CheckpointAction:
            return WrapUpAction()

        result = await session.deliberate(
            question="Test question?",
            on_checkpoint=wrap_up,
        )

        assert result.round_count == 1
        assert result.state.is_complete
        assert result.state.stopped_reason == "wrap_up"

    @pytest.mark.asyncio
    async def test_two_rounds_then_wrap_up(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider)
        checkpoint_calls = 0

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            nonlocal checkpoint_calls
            checkpoint_calls += 1
            if checkpoint_calls == 1:
                return ContinueAction()
            return WrapUpAction()

        result = await session.deliberate(
            question="Test question?",
            on_checkpoint=checkpoint,
        )

        assert result.round_count == 2
        assert len(result.transcript) == 2

    @pytest.mark.asyncio
    async def test_no_checkpoint_runs_max_rounds(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider, max_rounds=2)

        result = await session.deliberate(question="Test question?")

        assert result.round_count == 2
        assert result.state.stopped_reason == "max_rounds"

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider)

        async def wrap_up(state: DeliberationState) -> CheckpointAction:
            return WrapUpAction()

        result = await session.deliberate(
            question="Test question?",
            on_checkpoint=wrap_up,
        )

        # All documented fields exist
        assert isinstance(result.consensus, list)
        assert isinstance(result.disagreements, list)
        assert isinstance(result.dimension_map, list)
        assert isinstance(result.findings, list)
        assert isinstance(result.persona_positions, list)
        assert isinstance(result.transcript, list)
        assert isinstance(result.report, str)
        assert result.state is not None

        # Dimension map has at least one entry (from mock)
        assert len(result.dimension_map) >= 1

        # Persona positions match the personas
        position_names = {p.persona_name for p in result.persona_positions}
        assert position_names == {"a", "b", "c"}

        # Each position has confidence and analysis
        for pos in result.persona_positions:
            assert isinstance(pos.confidence, float)
            assert isinstance(pos.analysis, str)

        # Report is non-empty markdown
        assert "## Dimension Alignment" in result.report

    @pytest.mark.asyncio
    async def test_checkpoint_callback_receives_state(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider)
        received_states: list[DeliberationState] = []

        async def checkpoint(state: DeliberationState) -> CheckpointAction:
            received_states.append(state)
            return WrapUpAction()

        await session.deliberate(
            question="Test question?",
            on_checkpoint=checkpoint,
        )

        assert len(received_states) == 1
        assert received_states[0].question == "Test question?"
        assert received_states[0].round_count == 1


class TestResolveAttachments:
    def test_none_returns_empty(self) -> None:
        assert _resolve_attachments(None) == []

    def test_empty_returns_empty(self) -> None:
        assert _resolve_attachments([]) == []

    def test_attachment_objects_passed_through(self) -> None:
        att = Attachment(media_type="text/plain", data=b"hello")
        result = _resolve_attachments([att])
        assert result == [att]

    def test_string_path_converted(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("content")
        result = _resolve_attachments([str(f)])
        assert len(result) == 1
        assert result[0].data == b"content"

    def test_path_object_converted(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("content")
        result = _resolve_attachments([f])
        assert len(result) == 1
        assert result[0].data == b"content"

    def test_mixed_types(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("file content")
        att = Attachment(media_type="text/plain", data=b"direct")
        result = _resolve_attachments([f, att])
        assert len(result) == 2


class TestMagiResultProperties:
    @pytest.mark.asyncio
    async def test_is_degraded_false_when_clean(self) -> None:
        provider = _make_mock_provider()
        personas = [_make_persona("a"), _make_persona("b"), _make_persona("c")]
        session = MagiSession(personas=personas, provider=provider)

        async def wrap_up(state: DeliberationState) -> CheckpointAction:
            return WrapUpAction()

        result = await session.deliberate(question="Test?", on_checkpoint=wrap_up)
        assert result.is_degraded is False
