"""Parser and discovery for persona .md files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from project_magi.personas.model import Persona

logger = logging.getLogger(__name__)

# Regex to extract YAML frontmatter between --- delimiters
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


class PersonaValidationError(Exception):
    """Raised when a persona file fails validation."""


def parse_persona_file(path: Path) -> Persona:
    """Parse a Claude Code agent .md file into a Persona object.

    The file must have YAML frontmatter delimited by --- lines,
    followed by a markdown body that becomes the system prompt.

    Required frontmatter fields: name, description.
    Optional fields: model, tools, maxTurns (and any others, stored in extra_fields).

    Raises:
        PersonaValidationError: If the file is missing frontmatter or required fields.
    """
    text = path.read_text(encoding="utf-8")
    return parse_persona_string(text, source=str(path))


def parse_persona_string(text: str, source: str = "<string>") -> Persona:
    """Parse a persona from a raw markdown string.

    Args:
        text: The full markdown content (frontmatter + body).
        source: A label for error messages (e.g. the file path).

    Returns:
        A Persona object.

    Raises:
        PersonaValidationError: If the content is missing frontmatter or required fields.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        msg = f"{source}: No YAML frontmatter found (expected --- delimiters)"
        raise PersonaValidationError(msg)

    frontmatter_str, body = match.group(1), match.group(2)

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        msg = f"{source}: Invalid YAML in frontmatter: {e}"
        raise PersonaValidationError(msg) from e

    if not isinstance(frontmatter, dict):
        msg = f"{source}: Frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"
        raise PersonaValidationError(msg)

    # Validate required fields
    name = frontmatter.get("name")
    if not name:
        msg = f"{source}: Missing required field 'name'"
        raise PersonaValidationError(msg)

    description = frontmatter.get("description")
    if not description:
        msg = f"{source}: Missing required field 'description'"
        raise PersonaValidationError(msg)

    # Extract optional fields
    model = str(frontmatter.get("model", ""))
    tools_raw = frontmatter.get("tools", "")
    if isinstance(tools_raw, str) and tools_raw:
        tools = [t.strip() for t in tools_raw.split(",")]
    elif isinstance(tools_raw, list):
        tools = [str(t) for t in tools_raw]
    else:
        tools = []

    max_turns_raw = frontmatter.get("maxTurns")
    max_turns = int(max_turns_raw) if max_turns_raw is not None else None

    # Collect any extra fields not explicitly handled
    known_keys = {"name", "description", "model", "tools", "maxTurns"}
    extra_fields = {k: v for k, v in frontmatter.items() if k not in known_keys}

    system_prompt = body.strip()

    return Persona(
        name=str(name),
        description=str(description),
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        max_turns=max_turns,
        extra_fields=extra_fields,
    )


@dataclass
class PersonaDiscoveryResult:
    """Result of scanning a directory for persona files."""

    personas: list[Persona] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


# MAGI system agent filenames that should not be loaded as deliberation personas
_SYSTEM_AGENT_NAMES = frozenset(
    {
        "magi",
        "magi-builder",
        "magi-coordinator",
    }
)


def discover_personas(
    directory: Path | None = None,
    *,
    exclude_system_agents: bool = True,
) -> PersonaDiscoveryResult:
    """Scan a directory for persona .md files and parse them.

    Args:
        directory: The directory to scan. Defaults to .claude/agents/ relative
                   to the current working directory.
        exclude_system_agents: If True (default), excludes MAGI system agents
            (magi.md, magi-builder.md, magi-coordinator.md) from the results.
            Set to False to load all .md files.

    Returns:
        A PersonaDiscoveryResult with successfully parsed personas and any errors.
    """
    if directory is None:
        directory = Path.cwd() / ".claude" / "agents"

    result = PersonaDiscoveryResult()

    if not directory.exists():
        logger.warning("Persona directory does not exist: %s", directory)
        return result

    for md_file in sorted(directory.glob("*.md")):
        # Skip system agents when loading deliberation personas
        if exclude_system_agents and md_file.stem in _SYSTEM_AGENT_NAMES:
            continue

        try:
            persona = parse_persona_file(md_file)
            result.personas.append(persona)
        except PersonaValidationError as e:
            result.errors.append((md_file, str(e)))
            logger.warning("Skipping invalid persona file: %s", e)

    return result
