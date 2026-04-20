"""CLI entry point for running MAGI deliberations.

This module provides a command-line interface that Claude Code agents
can invoke via the Bash tool. It's the bridge between the agent .md
files and the Python library.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from project_magi.coordinator.checkpoint import CheckpointAction
    from project_magi.coordinator.loop import DeliberationState
    from project_magi.providers.base import Attachment


def main() -> None:
    """Run MAGI from the command line."""
    parser = argparse.ArgumentParser(description="MAGI deliberation engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # deliberate command
    delib_parser = subparsers.add_parser("deliberate", help="Run a deliberation")
    delib_parser.add_argument("question", help="The question to deliberate on")
    delib_parser.add_argument(
        "--file",
        "-f",
        action="append",
        default=[],
        help="Attach a file (PDF, image, or text). Can be repeated: -f a.pdf -f b.pdf",
    )
    delib_parser.add_argument(
        "--max-rounds", type=int, default=3, help="Maximum rounds (default: 3)"
    )
    delib_parser.add_argument(
        "--model",
        default=None,
        help="Model to use (default: claude-opus-4-6)",
    )
    delib_parser.add_argument(
        "--personas-dir",
        default=None,
        help="Directory to load personas from (default: .claude/agents/)",
    )
    delib_parser.add_argument("--output", "-o", default=None, help="Write report to this file")
    delib_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose report")
    delib_parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without checkpoints (auto-complete all rounds)",
    )

    # suggest-personas command
    suggest_parser = subparsers.add_parser(
        "suggest-personas", help="Generate persona suggestions for a task"
    )
    suggest_parser.add_argument("task", help="Task description")
    suggest_parser.add_argument(
        "--output-dir",
        default=None,
        help="Write persona .md files to this directory",
    )
    suggest_parser.add_argument(
        "--model",
        default=None,
        help="Model to use (default: claude-opus-4-6)",
    )

    args = parser.parse_args()

    if args.command == "deliberate":
        asyncio.run(_run_deliberate(args))
    elif args.command == "suggest-personas":
        asyncio.run(_run_suggest(args))


def _resolve_file_args(file_paths: list[str]) -> list[str]:
    """Validate file paths from --file arguments and return resolved paths."""
    resolved: list[str] = []
    for raw_path in file_paths:
        p = Path(raw_path)
        if not p.exists():
            print(f"Error: file not found: {p}", file=sys.stderr)
            sys.exit(1)
        resolved.append(str(p.resolve()))
    return resolved


async def _run_deliberate(args: argparse.Namespace) -> None:
    """Run a deliberation."""
    from project_magi.session import MagiSession

    file_paths = _resolve_file_args(args.file)

    session = MagiSession(
        personas_dir=args.personas_dir,
        max_rounds=args.max_rounds,
        model=args.model,
        verbose=args.verbose,
    )
    attachments: list[str | Path | Attachment] | None = (
        [Path(p) for p in file_paths] if file_paths else None
    )

    if args.auto:
        result = await session.deliberate(question=args.question, attachments=attachments)
    else:
        result = await session.deliberate(
            question=args.question,
            attachments=attachments,
            on_checkpoint=_interactive_checkpoint,
        )

    # Output the report
    print(result.report)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(result.report)
        print(f"\nReport written to {output_path}", file=sys.stderr)

    # Also output structured data as JSON to stderr for programmatic use
    summary = {
        "rounds": result.round_count,
        "stopped_reason": result.state.stopped_reason,
        "dimensions": len(result.dimension_map),
        "agreements": len(result.consensus),
        "disagreements": len(result.disagreements),
        "findings": len(result.findings),
        "personas": [
            {"name": p.persona_name, "confidence": p.confidence} for p in result.persona_positions
        ],
    }
    print(f"\n{json.dumps(summary, indent=2)}", file=sys.stderr)


async def _interactive_checkpoint(
    state: DeliberationState,
) -> CheckpointAction:
    """Interactive checkpoint for terminal use."""
    from project_magi.coordinator.checkpoint import parse_checkpoint_response

    critique = state.latest_critique
    if critique:
        print("\n" + "=" * 60, file=sys.stderr)
        print(f"CHECKPOINT — Round {state.round_count} complete", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        if critique.dimensions:
            print("\nDimensions:", file=sys.stderr)
            for d in critique.dimensions:
                print(f"  {d.name}: {d.alignment}", file=sys.stderr)

        if critique.agreements:
            print(f"\nAgreements: {len(critique.agreements)}", file=sys.stderr)
        if critique.disagreements:
            print(f"Disagreements: {len(critique.disagreements)}", file=sys.stderr)

        print(
            '\nOptions: "wrap up", "keep going", '
            '"keep going, but [feedback]", or give specific feedback',
            file=sys.stderr,
        )

    response = input("\n> ")
    persona_names = [o.persona_name for o in state.latest_persona_outputs.values()]
    return parse_checkpoint_response(response, known_persona_names=persona_names)


async def _run_suggest(args: argparse.Namespace) -> None:
    """Run persona suggestion."""
    from project_magi.personas.builder import (
        suggest_personas,
        suggestion_to_persona,
        write_persona_file,
    )
    from project_magi.providers.claude import ClaudeProvider

    provider = ClaudeProvider(model=args.model) if args.model else ClaudeProvider()

    suggestions = await suggest_personas(provider, args.task)

    if not suggestions:
        print("No personas suggested.", file=sys.stderr)
        sys.exit(1)

    print(f"Suggested {len(suggestions)} personas:\n")
    for s in suggestions:
        print(f"  {s.name}: {s.description}")
        print(f"    Role: {s.role}")
        if s.priorities:
            print(f"    Priorities: {', '.join(s.priorities)}")
        print()

    if args.output_dir:
        output_dir = Path(args.output_dir)
        for s in suggestions:
            persona = suggestion_to_persona(s)
            path = write_persona_file(persona, output_dir)
            print(f"  Wrote {path}", file=sys.stderr)
        print(
            f"\n{len(suggestions)} persona files written to {output_dir}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
