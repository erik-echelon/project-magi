"""Tests for persona agent runner and parallel execution."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from project_magi.agents.output import PersonaOutput
from project_magi.agents.runner import (
    PersonaAgentRunner,
    _build_round1_prompt,
    _build_round2_prompt,
    run_persona_agents,
)
from project_magi.personas.model import Persona
from project_magi.providers.base import Attachment, ProviderResponse


def _make_persona(name: str = "test-persona") -> Persona:
    return Persona(
        name=name,
        description=f"Test persona {name}",
        system_prompt=f"You are {name}.",
    )


def _make_json_response(
    analysis: str = "Test analysis",
    confidence: float = 0.8,
    findings: list[dict[str, str]] | None = None,
) -> str:
    return json.dumps(
        {
            "analysis": analysis,
            "confidence": confidence,
            "findings": findings or [],
        }
    )


def _make_provider_response(content: str) -> ProviderResponse:
    return ProviderResponse(
        content=content,
        model="claude-opus-4-6",
        input_tokens=100,
        output_tokens=50,
    )


class TestBuildRound1Prompt:
    def test_contains_question(self) -> None:
        prompt = _build_round1_prompt("Should we use Rust?")
        assert "Should we use Rust?" in prompt

    def test_contains_json_instructions(self) -> None:
        prompt = _build_round1_prompt("test")
        assert '"analysis"' in prompt
        assert '"confidence"' in prompt
        assert '"findings"' in prompt


class TestBuildRound2Prompt:
    def test_contains_original_question(self) -> None:
        prior = PersonaOutput(persona_name="test", analysis="Prior analysis", confidence=0.8)
        prompt = _build_round2_prompt("Original question", prior, "Critique text")
        assert "Original question" in prompt

    def test_contains_prior_analysis(self) -> None:
        prior = PersonaOutput(persona_name="test", analysis="My previous take", confidence=0.8)
        prompt = _build_round2_prompt("q", prior, "critique")
        assert "My previous take" in prompt

    def test_contains_critique_synthesis(self) -> None:
        prior = PersonaOutput(persona_name="test", analysis="a", confidence=0.8)
        prompt = _build_round2_prompt("q", prior, "The critique says X disagrees with Y")
        assert "The critique says X disagrees with Y" in prompt

    def test_contains_human_feedback_when_provided(self) -> None:
        prior = PersonaOutput(persona_name="test", analysis="a", confidence=0.8)
        prompt = _build_round2_prompt("q", prior, "critique", human_feedback="Consider cost")
        assert "Consider cost" in prompt
        assert "Human Feedback" in prompt

    def test_no_human_feedback_section_when_none(self) -> None:
        prior = PersonaOutput(persona_name="test", analysis="a", confidence=0.8)
        prompt = _build_round2_prompt("q", prior, "critique", human_feedback=None)
        assert "Human Feedback" not in prompt


class TestPersonaAgentRunner:
    @pytest.fixture
    def mock_provider(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_run_round1(self, mock_provider: AsyncMock) -> None:
        persona = _make_persona("melchior")
        mock_provider.send_message.return_value = _make_provider_response(
            _make_json_response(analysis="Technical analysis", confidence=0.9)
        )

        runner = PersonaAgentRunner(persona, mock_provider)
        output = await runner.run_round1("Should we use Rust?")

        assert output.persona_name == "melchior"
        assert output.analysis == "Technical analysis"
        assert output.confidence == 0.9

        # Verify provider was called with correct system prompt
        call_args = mock_provider.send_message.call_args
        assert call_args.kwargs["system_prompt"] == "You are melchior."
        assert len(call_args.kwargs["messages"]) == 1
        assert call_args.kwargs["messages"][0].role == "user"

    @pytest.mark.asyncio
    async def test_round1_with_attachments(self, mock_provider: AsyncMock) -> None:
        persona = _make_persona()
        mock_provider.send_message.return_value = _make_provider_response(_make_json_response())

        att = Attachment(media_type="image/png", data=b"\x89PNG", filename="img.png")
        runner = PersonaAgentRunner(persona, mock_provider)
        await runner.run_round1("Describe this", attachments=[att])

        call_args = mock_provider.send_message.call_args
        assert call_args.kwargs["attachments"] == [att]

    @pytest.mark.asyncio
    async def test_run_round2(self, mock_provider: AsyncMock) -> None:
        persona = _make_persona("casper")
        mock_provider.send_message.return_value = _make_provider_response(
            _make_json_response(analysis="Revised position", confidence=0.75)
        )

        prior = PersonaOutput(persona_name="casper", analysis="Initial take", confidence=0.8)

        runner = PersonaAgentRunner(persona, mock_provider)
        output = await runner.run_round2(
            question="Should we use Rust?",
            prior_output=prior,
            critique_synthesis="Melchior disagrees on performance claims.",
            human_feedback="Also consider hiring difficulty.",
        )

        assert output.persona_name == "casper"
        assert output.analysis == "Revised position"
        assert output.confidence == 0.75

        # Verify the prompt contains all context
        user_content = mock_provider.send_message.call_args.kwargs["messages"][0].content
        assert "Should we use Rust?" in user_content
        assert "Initial take" in user_content
        assert "Melchior disagrees" in user_content
        assert "hiring difficulty" in user_content

    @pytest.mark.asyncio
    async def test_handles_non_json_response(self, mock_provider: AsyncMock) -> None:
        persona = _make_persona()
        mock_provider.send_message.return_value = _make_provider_response(
            "Just plain text, not JSON"
        )

        runner = PersonaAgentRunner(persona, mock_provider)
        output = await runner.run_round1("test")

        assert output.analysis == "Just plain text, not JSON"
        assert output.confidence == 0.5


class TestRunPersonaAgents:
    def _make_runner(self, name: str, response: str, *, fail: bool = False) -> PersonaAgentRunner:
        persona = _make_persona(name)
        mock_provider = AsyncMock()
        if fail:
            mock_provider.send_message.side_effect = TimeoutError("Agent timed out")
        else:
            mock_provider.send_message.return_value = _make_provider_response(response)
        return PersonaAgentRunner(persona, mock_provider)

    @pytest.mark.asyncio
    async def test_parallel_all_succeed(self) -> None:
        runners = [
            self._make_runner("a", _make_json_response(analysis="A's take")),
            self._make_runner("b", _make_json_response(analysis="B's take")),
            self._make_runner("c", _make_json_response(analysis="C's take")),
        ]

        result = await run_persona_agents(runners, "test question")

        assert len(result.outputs) == 3
        assert len(result.errors) == 0
        assert not result.is_degraded
        assert result.has_quorum
        names = {o.persona_name for o in result.outputs}
        assert names == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_one_failure_graceful_degradation(self) -> None:
        runners = [
            self._make_runner("a", _make_json_response(analysis="A's take")),
            self._make_runner("b", "", fail=True),
            self._make_runner("c", _make_json_response(analysis="C's take")),
        ]

        result = await run_persona_agents(runners, "test question")

        assert len(result.outputs) == 2
        assert len(result.errors) == 1
        assert result.errors[0][0] == "b"
        assert "TimeoutError" in result.errors[0][1]
        assert result.is_degraded
        assert result.has_quorum

    @pytest.mark.asyncio
    async def test_two_failures_no_quorum(self) -> None:
        runners = [
            self._make_runner("a", _make_json_response(analysis="A's take")),
            self._make_runner("b", "", fail=True),
            self._make_runner("c", "", fail=True),
        ]

        result = await run_persona_agents(runners, "test question")

        assert len(result.outputs) == 1
        assert len(result.errors) == 2
        assert result.is_degraded
        assert not result.has_quorum

    @pytest.mark.asyncio
    async def test_round2_passes_prior_outputs(self) -> None:
        persona_a = _make_persona("a")
        mock_provider_a = AsyncMock()
        mock_provider_a.send_message.return_value = _make_provider_response(
            _make_json_response(analysis="A round 2")
        )
        runner_a = PersonaAgentRunner(persona_a, mock_provider_a)

        prior_outputs = {
            "a": PersonaOutput(persona_name="a", analysis="A round 1", confidence=0.8),
        }

        result = await run_persona_agents(
            [runner_a],
            "test question",
            prior_outputs=prior_outputs,
            critique_synthesis="Critique text here",
            human_feedback="Consider X",
        )

        assert len(result.outputs) == 1
        assert result.outputs[0].analysis == "A round 2"

        # Verify the prompt was constructed with round 2 context
        user_content = mock_provider_a.send_message.call_args.kwargs["messages"][0].content
        assert "A round 1" in user_content
        assert "Critique text here" in user_content
        assert "Consider X" in user_content

    @pytest.mark.asyncio
    async def test_round2_missing_prior_output_errors(self) -> None:
        runner = self._make_runner("a", _make_json_response())

        result = await run_persona_agents(
            [runner],
            "test",
            prior_outputs={},  # no prior for "a"
            critique_synthesis="critique",
        )

        assert len(result.outputs) == 0
        assert len(result.errors) == 1
        assert "No prior output" in result.errors[0][1]
