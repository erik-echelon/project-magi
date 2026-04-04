"""Persona definition, parsing, discovery, and building."""

from project_magi.personas.builder import (
    PersonaSuggestion,
    suggest_personas,
    suggestion_to_persona,
    write_persona_file,
)
from project_magi.personas.model import Persona
from project_magi.personas.parser import (
    PersonaDiscoveryResult,
    PersonaValidationError,
    discover_personas,
    parse_persona_file,
)

__all__ = [
    "Persona",
    "PersonaDiscoveryResult",
    "PersonaSuggestion",
    "PersonaValidationError",
    "discover_personas",
    "parse_persona_file",
    "suggest_personas",
    "suggestion_to_persona",
    "write_persona_file",
]
