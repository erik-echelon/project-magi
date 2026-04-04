"""Tests for the persona builder."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from project_magi.personas.builder import (
    PersonaSuggestion,
    _parse_suggestions,
    suggest_personas,
    suggestion_to_persona,
    write_persona_file,
)
from project_magi.personas.model import PROMPT_INJECTION_DEFENSE, Persona
from project_magi.personas.parser import parse_persona_file
from project_magi.providers.base import ProviderResponse

if TYPE_CHECKING:
    from pathlib import Path


SAMPLE_SUGGESTIONS_JSON = json.dumps(
    [
        {
            "name": "cfo",
            "description": "Evaluates through financial discipline and ROI",
            "role": "Chief Financial Officer",
            "system_prompt": ("You are the CFO persona.\n\n" + PROMPT_INJECTION_DEFENSE),
            "priorities": ["Unit economics", "Budget impact", "ROI timeline"],
        },
        {
            "name": "head-of-sales",
            "description": "Evaluates through pipeline reality and competitive positioning",
            "role": "Head of Sales",
            "system_prompt": ("You are the Head of Sales persona.\n\n" + PROMPT_INJECTION_DEFENSE),
            "priorities": ["Pipeline impact", "Win rate", "Competitive position"],
        },
        {
            "name": "cto",
            "description": "Evaluates through technical debt and scalability",
            "role": "Chief Technology Officer",
            "system_prompt": ("You are the CTO persona.\n\n" + PROMPT_INJECTION_DEFENSE),
            "priorities": ["Technical debt", "Scalability", "Integration burden"],
        },
    ]
)


class TestParseSuggestions:
    def test_parses_valid_json(self) -> None:
        suggestions = _parse_suggestions(SAMPLE_SUGGESTIONS_JSON)
        assert len(suggestions) == 3
        assert suggestions[0].name == "cfo"
        assert suggestions[1].name == "head-of-sales"
        assert suggestions[2].name == "cto"

    def test_parses_json_in_fence(self) -> None:
        raw = f"```json\n{SAMPLE_SUGGESTIONS_JSON}\n```"
        suggestions = _parse_suggestions(raw)
        assert len(suggestions) == 3

    def test_empty_on_no_json(self) -> None:
        assert _parse_suggestions("Just plain text") == []

    def test_empty_on_invalid_json(self) -> None:
        assert _parse_suggestions("[{invalid}]") == []

    def test_empty_on_non_list(self) -> None:
        assert _parse_suggestions('{"not": "a list"}') == []

    def test_skips_items_without_name(self) -> None:
        raw = json.dumps([{"description": "no name here"}])
        assert _parse_suggestions(raw) == []

    def test_skips_items_without_description(self) -> None:
        raw = json.dumps([{"name": "no-desc"}])
        assert _parse_suggestions(raw) == []

    def test_adds_prompt_injection_defense_if_missing(self) -> None:
        raw = json.dumps(
            [
                {
                    "name": "test",
                    "description": "Test persona",
                    "role": "Tester",
                    "system_prompt": "You are a test persona. No defense here.",
                    "priorities": [],
                }
            ]
        )
        suggestions = _parse_suggestions(raw)
        assert len(suggestions) == 1
        assert PROMPT_INJECTION_DEFENSE in suggestions[0].system_prompt

    def test_keeps_defense_if_already_present(self) -> None:
        raw = json.dumps(
            [
                {
                    "name": "test",
                    "description": "Test persona",
                    "system_prompt": f"You are a test persona.\n\n{PROMPT_INJECTION_DEFENSE}",
                }
            ]
        )
        suggestions = _parse_suggestions(raw)
        # Should not be duplicated
        count = suggestions[0].system_prompt.count(PROMPT_INJECTION_DEFENSE)
        assert count == 1

    def test_name_lowercased(self) -> None:
        raw = json.dumps(
            [
                {
                    "name": "CFO",
                    "description": "Test",
                    "system_prompt": "x",
                }
            ]
        )
        suggestions = _parse_suggestions(raw)
        assert suggestions[0].name == "cfo"

    def test_priorities_not_a_list(self) -> None:
        raw = json.dumps(
            [
                {
                    "name": "test",
                    "description": "Test",
                    "system_prompt": "x",
                    "priorities": "not a list",
                }
            ]
        )
        suggestions = _parse_suggestions(raw)
        assert suggestions[0].priorities == []


class TestSuggestPersonas:
    @pytest.mark.asyncio
    async def test_calls_provider(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.send_message.return_value = ProviderResponse(
            content=SAMPLE_SUGGESTIONS_JSON,
            model="claude-opus-4-6",
        )

        suggestions = await suggest_personas(mock_provider, "Planning a go-to-market strategy")

        assert len(suggestions) == 3
        mock_provider.send_message.assert_called_once()

        # Verify system prompt is the builder prompt
        from project_magi.personas.builder import BUILDER_SYSTEM_PROMPT

        call_kwargs = mock_provider.send_message.call_args.kwargs
        assert call_kwargs["system_prompt"] == BUILDER_SYSTEM_PROMPT
        assert "go-to-market" in call_kwargs["messages"][0].content


class TestSuggestionToPersona:
    def test_converts_with_defaults(self) -> None:
        suggestion = PersonaSuggestion(
            name="cfo",
            description="Financial lens",
            role="CFO",
            system_prompt="You are the CFO.",
            priorities=["ROI", "Budget"],
        )

        persona = suggestion_to_persona(suggestion)

        assert persona.name == "cfo"
        assert persona.description == "Financial lens"
        assert persona.system_prompt == "You are the CFO."
        assert persona.model == "opus"
        assert persona.tools == ["Read", "Grep", "Glob"]

    def test_custom_model_and_tools(self) -> None:
        suggestion = PersonaSuggestion(
            name="test",
            description="Test",
            role="Test",
            system_prompt="x",
            priorities=[],
        )

        persona = suggestion_to_persona(suggestion, model="sonnet", tools=["Read", "Write"])

        assert persona.model == "sonnet"
        assert persona.tools == ["Read", "Write"]


class TestWritePersonaFile:
    def test_writes_valid_md_file(self, tmp_path: Path) -> None:
        persona = Persona(
            name="test-persona",
            description="A test persona",
            system_prompt=f"You are a test persona.\n\n{PROMPT_INJECTION_DEFENSE}",
            model="opus",
            tools=["Read", "Grep"],
        )

        path = write_persona_file(persona, tmp_path)

        assert path.exists()
        assert path.name == "test-persona.md"
        assert path.parent == tmp_path

    def test_written_file_parseable_by_loader(self, tmp_path: Path) -> None:
        persona = Persona(
            name="roundtrip",
            description="Round-trip test",
            system_prompt=f"You are a round-trip test.\n\n{PROMPT_INJECTION_DEFENSE}",
            model="opus",
            tools=["Read", "Grep", "Glob"],
        )

        path = write_persona_file(persona, tmp_path)
        loaded = parse_persona_file(path)

        assert loaded.name == persona.name
        assert loaded.description == persona.description
        assert loaded.system_prompt == persona.system_prompt
        assert loaded.model == persona.model
        assert loaded.tools == persona.tools

    def test_written_file_has_defense(self, tmp_path: Path) -> None:
        persona = Persona(
            name="defended",
            description="Has defense",
            system_prompt=f"Body.\n\n{PROMPT_INJECTION_DEFENSE}",
        )

        path = write_persona_file(persona, tmp_path)
        loaded = parse_persona_file(path)

        assert loaded.has_prompt_injection_defense

    def test_creates_directory_if_needed(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "dir"
        persona = Persona(name="test", description="Test", system_prompt="x")

        path = write_persona_file(persona, nested)

        assert path.exists()
        assert nested.exists()


class TestFullRoundTrip:
    """End-to-end: parse suggestions → convert to persona → write file → load back."""

    def test_suggestion_to_file_to_loaded_persona(self, tmp_path: Path) -> None:
        suggestions = _parse_suggestions(SAMPLE_SUGGESTIONS_JSON)

        for suggestion in suggestions:
            persona = suggestion_to_persona(suggestion)
            path = write_persona_file(persona, tmp_path)
            loaded = parse_persona_file(path)

            assert loaded.name == suggestion.name
            assert loaded.description == suggestion.description
            assert loaded.has_prompt_injection_defense
            assert loaded.model == "opus"
            assert loaded.tools == ["Read", "Grep", "Glob"]
