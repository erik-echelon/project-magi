"""Persona agent execution, critique synthesis, and parallel coordination."""

from project_magi.agents.critique import (
    CritiqueOutput,
    DeduplicatedFinding,
    DimensionAlignment,
    deduplicate_findings,
    run_critique_agent,
)
from project_magi.agents.output import Finding, PersonaOutput
from project_magi.agents.runner import PersonaAgentRunner, run_persona_agents

__all__ = [
    "CritiqueOutput",
    "DeduplicatedFinding",
    "DimensionAlignment",
    "Finding",
    "PersonaAgentRunner",
    "PersonaOutput",
    "deduplicate_findings",
    "run_critique_agent",
    "run_persona_agents",
]
