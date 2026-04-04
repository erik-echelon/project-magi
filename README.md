# Project MAGI

> *"Understanding each other one hundred percent is impossible. Of course, that's why we spend so much time trying to understand ourselves and others. That's what makes life so interesting."* — Kaji Ryoji

Multi-persona AI deliberation engine. Inspired by the MAGI supercomputer from Neon Genesis Evangelion.

## The Idea

In Evangelion, NERV's MAGI supercomputer is three systems, each imprinted with a different facet of Dr. Naoko Akagi's personality: MELCHIOR (the scientist), BALTHASAR (the mother), and CASPAR (the woman). Decisions are resolved by majority vote — the three don't have to agree, and often don't. The whole point is that no single aspect of human judgment gets to run the show alone.

Project MAGI does the same thing for your work. You define a set of personas with different roles and priorities. They independently analyze your question, then deliberate across multiple rounds — critiquing each other, responding to disagreements, and sharpening their positions. A critique agent maps where they agree and where they don't. After each round, you see the state of the deliberation and decide whether to keep going, redirect, or wrap up. The output is a structured report of what converged and what didn't.

## Why Bother?

Evangelion's recurring theme is the Hedgehog's Dilemma (borrowed from Schopenhauer): hedgehogs need each other's warmth in winter, but their quills make closeness painful. So they cycle between freezing alone and hurting each other. The show argues that understanding another mind is painful and always incomplete, but the alternative is worse.

Working with a single AI has the same problem. One perspective gives you one reading of a document, one shape for a research plan, one draft of a deliverable. It feels complete because it's articulate and confident, but it's not. The gaps are invisible from the inside. MAGI makes those gaps visible by forcing genuinely different perspectives to confront each other, and by pulling the human into the loop when the friction needs a tiebreaker or a gut check. The value isn't in any single perspective. It's in the friction between them.

At the end of the series, Shinji is offered Instrumentality: dissolve all human consciousness into one unified whole, no more misunderstanding, no more pain. He turns it down. Separate minds that struggle to understand each other are better than one mind that never has to. MAGI takes the same position. It doesn't blend perspectives into an average. It keeps them separate, lets them argue, and reports what survived.

## Quick Start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/erik-echelon/project-magi.git
cd project-magi
uv sync --dev
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Run a deliberation:

```bash
uv run --env-file .env magi deliberate "Should we adopt microservices?" --auto
```

See the [User Guide](docs/user-guide.md) for full documentation.

## Using as a Library

```python
import asyncio
from project_magi import MagiSession

async def main():
    session = MagiSession(max_rounds=3)
    result = await session.deliberate(
        question="Should we prioritize the API rewrite or onboarding?",
    )
    print(result.report)

asyncio.run(main())
```

## Documentation

- **[User Guide](docs/user-guide.md)** — installation, CLI reference, library API, custom personas, report format
- **[Philosophy](docs/philosophy.md)** — the design principles behind MAGI
- **[PRD](docs/PRD.md)** — full product requirements
- **[Capstone](docs/capstone.md)** — the self-destruct scenario from Evangelion Episode 13, run through our system

## Development

```bash
just check            # Lint + typecheck + test (the CI gate)
just test             # Unit tests with 90% coverage threshold
just test-integration # Integration tests (hits real Claude API)
just format           # Auto-format with ruff
```

See [CLAUDE.md](CLAUDE.md) for the full development workflow.

## License

MIT
