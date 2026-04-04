"""Tests for persona definition, parsing, and discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from project_magi.personas.model import PROMPT_INJECTION_DEFENSE, Persona
from project_magi.personas.parser import (
    PersonaValidationError,
    discover_personas,
    parse_persona_file,
    parse_persona_string,
)

if TYPE_CHECKING:
    from pathlib import Path


VALID_PERSONA_MD = """\
---
name: test-persona
description: "A test persona for unit tests"
model: sonnet
tools: Read, Grep, Glob
maxTurns: 10
---

You are a test persona. Be helpful.
"""


class TestParsePersonaString:
    def test_parses_well_formed_file(self) -> None:
        persona = parse_persona_string(VALID_PERSONA_MD)

        assert persona.name == "test-persona"
        assert persona.description == "A test persona for unit tests"
        assert persona.model == "sonnet"
        assert persona.tools == ["Read", "Grep", "Glob"]
        assert persona.max_turns == 10
        assert persona.system_prompt == "You are a test persona. Be helpful."

    def test_missing_frontmatter_raises(self) -> None:
        with pytest.raises(PersonaValidationError, match="No YAML frontmatter found"):
            parse_persona_string("Just some markdown without frontmatter.")

    def test_missing_name_raises(self) -> None:
        md = """\
---
description: "Has description but no name"
---

Body text.
"""
        with pytest.raises(PersonaValidationError, match="Missing required field 'name'"):
            parse_persona_string(md)

    def test_missing_description_raises(self) -> None:
        md = """\
---
name: no-desc
---

Body text.
"""
        with pytest.raises(PersonaValidationError, match="Missing required field 'description'"):
            parse_persona_string(md)

    def test_no_frontmatter_delimiters(self) -> None:
        with pytest.raises(PersonaValidationError, match="No YAML frontmatter found"):
            parse_persona_string("name: foo\ndescription: bar\n\nBody.")

    def test_invalid_yaml_raises(self) -> None:
        md = """\
---
name: [invalid yaml
---

Body.
"""
        with pytest.raises(PersonaValidationError, match="Invalid YAML"):
            parse_persona_string(md)

    def test_frontmatter_not_a_mapping_raises(self) -> None:
        md = """\
---
- just a list
- not a mapping
---

Body.
"""
        with pytest.raises(PersonaValidationError, match="must be a YAML mapping"):
            parse_persona_string(md)

    def test_extra_fields_preserved(self) -> None:
        md = """\
---
name: extra
description: "Has extra fields"
customField: hello
anotherOne: 42
---

Body.
"""
        persona = parse_persona_string(md)
        assert persona.extra_fields["customField"] == "hello"
        assert persona.extra_fields["anotherOne"] == 42
        assert persona.name == "extra"

    def test_tools_as_list(self) -> None:
        md = """\
---
name: list-tools
description: "Tools as YAML list"
tools:
  - Read
  - Write
---

Body.
"""
        persona = parse_persona_string(md)
        assert persona.tools == ["Read", "Write"]

    def test_no_tools(self) -> None:
        md = """\
---
name: no-tools
description: "No tools specified"
---

Body.
"""
        persona = parse_persona_string(md)
        assert persona.tools == []

    def test_no_model(self) -> None:
        md = """\
---
name: no-model
description: "No model specified"
---

Body.
"""
        persona = parse_persona_string(md)
        assert persona.model == ""

    def test_no_max_turns(self) -> None:
        md = """\
---
name: no-turns
description: "No maxTurns"
---

Body.
"""
        persona = parse_persona_string(md)
        assert persona.max_turns is None

    def test_multiline_body(self) -> None:
        md = """\
---
name: multi
description: "Multiline body"
---

Line one.

## Section

- bullet
- bullet
"""
        persona = parse_persona_string(md)
        assert "Line one." in persona.system_prompt
        assert "## Section" in persona.system_prompt
        assert "- bullet" in persona.system_prompt

    def test_source_in_error_message(self) -> None:
        with pytest.raises(PersonaValidationError, match=r"my-file\.md"):
            parse_persona_string("no frontmatter", source="my-file.md")


class TestParsePersonaFile:
    def test_parses_from_path(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text(VALID_PERSONA_MD)

        persona = parse_persona_file(f)
        assert persona.name == "test-persona"

    def test_error_includes_path(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.md"
        f.write_text("no frontmatter here")

        with pytest.raises(PersonaValidationError, match=r"bad\.md"):
            parse_persona_file(f)


class TestDiscoverPersonas:
    def test_discovers_valid_files(self, tmp_path: Path) -> None:
        for name in ["a.md", "b.md", "c.md"]:
            (tmp_path / name).write_text(
                f'---\nname: {name[0]}\ndescription: "Persona {name[0]}"\n---\n\nBody.'
            )

        result = discover_personas(tmp_path)
        assert len(result.personas) == 3
        assert len(result.errors) == 0

    def test_reports_invalid_files(self, tmp_path: Path) -> None:
        # 3 valid
        for name in ["a.md", "b.md", "c.md"]:
            (tmp_path / name).write_text(
                f'---\nname: {name[0]}\ndescription: "Persona {name[0]}"\n---\n\nBody.'
            )
        # 1 invalid
        (tmp_path / "bad.md").write_text("no frontmatter")

        result = discover_personas(tmp_path)
        assert len(result.personas) == 3
        assert len(result.errors) == 1
        assert "bad.md" in str(result.errors[0][0])

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = discover_personas(tmp_path)
        assert len(result.personas) == 0
        assert len(result.errors) == 0

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        result = discover_personas(tmp_path / "does_not_exist")
        assert len(result.personas) == 0
        assert len(result.errors) == 0

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "valid.md").write_text('---\nname: valid\ndescription: "Valid"\n---\n\nBody.')
        (tmp_path / "not-a-persona.txt").write_text("just text")
        (tmp_path / "also-not.yaml").write_text("key: value")

        result = discover_personas(tmp_path)
        assert len(result.personas) == 1

    def test_sorted_by_filename(self, tmp_path: Path) -> None:
        for name in ["z.md", "a.md", "m.md"]:
            (tmp_path / name).write_text(
                f'---\nname: {name[0]}\ndescription: "Persona {name[0]}"\n---\n\nBody.'
            )

        result = discover_personas(tmp_path)
        names = [p.name for p in result.personas]
        assert names == ["a", "m", "z"]

    def test_excludes_system_agents_by_default(self, tmp_path: Path) -> None:
        for name in ["melchior.md", "magi.md", "magi-builder.md", "magi-coordinator.md"]:
            stem = name.replace(".md", "")
            (tmp_path / name).write_text(
                f'---\nname: {stem}\ndescription: "Agent {stem}"\n---\n\nBody.'
            )

        result = discover_personas(tmp_path)
        names = {p.name for p in result.personas}
        assert "melchior" in names
        assert "magi" not in names
        assert "magi-builder" not in names
        assert "magi-coordinator" not in names

    def test_include_system_agents_when_requested(self, tmp_path: Path) -> None:
        for name in ["melchior.md", "magi.md"]:
            stem = name.replace(".md", "")
            (tmp_path / name).write_text(
                f'---\nname: {stem}\ndescription: "Agent {stem}"\n---\n\nBody.'
            )

        result = discover_personas(tmp_path, exclude_system_agents=False)
        names = {p.name for p in result.personas}
        assert "melchior" in names
        assert "magi" in names


class TestDefaultPersonas:
    """Tests that load the real default personas from .claude/agents/."""

    def test_default_personas_load(self) -> None:
        from pathlib import Path

        agents_dir = Path.cwd() / ".claude" / "agents"
        result = discover_personas(agents_dir)

        assert len(result.errors) == 0, f"Errors loading default personas: {result.errors}"
        names = {p.name for p in result.personas}
        assert "melchior" in names
        assert "balthasar" in names
        assert "casper" in names

    def test_melchior_has_required_fields(self) -> None:
        from pathlib import Path

        persona = parse_persona_file(Path.cwd() / ".claude" / "agents" / "melchior.md")
        assert persona.name == "melchior"
        assert len(persona.description) > 0
        assert len(persona.system_prompt) > 0
        assert persona.model == "opus"

    def test_balthasar_has_required_fields(self) -> None:
        from pathlib import Path

        persona = parse_persona_file(Path.cwd() / ".claude" / "agents" / "balthasar.md")
        assert persona.name == "balthasar"
        assert len(persona.description) > 0
        assert len(persona.system_prompt) > 0

    def test_casper_has_required_fields(self) -> None:
        from pathlib import Path

        persona = parse_persona_file(Path.cwd() / ".claude" / "agents" / "casper.md")
        assert persona.name == "casper"
        assert len(persona.description) > 0
        assert len(persona.system_prompt) > 0

    def test_all_default_personas_have_prompt_injection_defense(self) -> None:
        from pathlib import Path

        agents_dir = Path.cwd() / ".claude" / "agents"
        result = discover_personas(agents_dir)

        for persona in result.personas:
            if persona.name in ("melchior", "balthasar", "casper"):
                assert persona.has_prompt_injection_defense, (
                    f"{persona.name} is missing prompt injection defense"
                )

    def test_all_default_personas_contain_defense_string(self) -> None:
        from pathlib import Path

        agents_dir = Path.cwd() / ".claude" / "agents"
        result = discover_personas(agents_dir)

        for persona in result.personas:
            if persona.name in ("melchior", "balthasar", "casper"):
                assert PROMPT_INJECTION_DEFENSE in persona.system_prompt


class TestPersonaModel:
    def test_frozen(self) -> None:
        persona = Persona(name="test", description="test", system_prompt="test")
        with pytest.raises(AttributeError):
            setattr(persona, "name", "other")  # noqa: B010

    def test_has_prompt_injection_defense_true(self) -> None:
        persona = Persona(
            name="test",
            description="test",
            system_prompt=f"Before. {PROMPT_INJECTION_DEFENSE} After.",
        )
        assert persona.has_prompt_injection_defense is True

    def test_has_prompt_injection_defense_false(self) -> None:
        persona = Persona(
            name="test",
            description="test",
            system_prompt="No defense here.",
        )
        assert persona.has_prompt_injection_defense is False


class TestPersonaRoundTrip:
    def test_write_and_read_back(self, tmp_path: Path) -> None:
        original = Persona(
            name="roundtrip",
            description="A round-trip test persona",
            system_prompt="You are a round-trip test persona.",
            model="sonnet",
            tools=["Read", "Grep"],
            max_turns=5,
        )

        md_path = tmp_path / "roundtrip.md"
        md_path.write_text(original.to_markdown())

        loaded = parse_persona_file(md_path)

        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.system_prompt == original.system_prompt
        assert loaded.model == original.model
        assert loaded.tools == original.tools
        assert loaded.max_turns == original.max_turns

    def test_write_minimal_and_read_back(self, tmp_path: Path) -> None:
        original = Persona(
            name="minimal",
            description="Minimal persona",
            system_prompt="Just a body.",
        )

        md_path = tmp_path / "minimal.md"
        md_path.write_text(original.to_markdown())

        loaded = parse_persona_file(md_path)

        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.system_prompt == original.system_prompt
        assert loaded.tools == []
        assert loaded.max_turns is None
