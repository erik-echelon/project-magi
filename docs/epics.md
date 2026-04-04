# Epics

Derived from the [PRD](PRD.md). Each epic is a self-contained body of work that can be planned, built, and tested independently.

---

## Testing Strategy

Every epic must be provably working before moving to the next. "Provably working" means different things at different layers:

### Test Tiers

**Tier 1: Unit tests (fast, deterministic, run on every commit)**
- Test your code's logic: parsing, schema validation, context construction, dedup, rendering
- Use recorded API response fixtures (see below) where your code needs to handle LLM output
- These are what the 90% coverage requirement applies to
- Run via `just test`

**Tier 2: Integration tests (slow, nondeterministic, run intentionally)**
- Hit the real Claude API with real prompts
- Assert on **structure, not content**: "confidence is a float between 0 and 1" — not "confidence is 0.85." "Findings is a non-empty list" — not "findings has exactly 3 items." "Dimension map has at least 2 dimensions" — not "first dimension is technical feasibility."
- Marked with `@pytest.mark.integration` so they don't run in CI or pre-commit
- Run via `just test-integration`
- Every epic that touches the LLM must have at least one integration test

**Tier 3: Capstone (manual, full system, run at the end)**
- A real end-to-end deliberation with the default MAGI personas on a canonical scenario
- Output is inspected by a human, not asserted programmatically
- See MAGI-11 below

### Recorded Response Fixtures

To bridge the gap between mocked tests (fast but fictional) and live tests (real but slow), we record actual Claude API responses and save them as JSON fixtures in `tests/fixtures/`.

**How it works:**
1. Run an integration test against the real API
2. The test harness captures the raw API response and writes it to `tests/fixtures/`
3. Unit tests load these fixtures instead of hitting the API

**What this gives you:**
- Unit tests run against the real *shape* of Claude's output, not shapes you invented
- Parsing code is validated against actual response structures
- When prompts or schemas change significantly, re-record by running integration tests with a `--record` flag

**What this doesn't solve:**
- Claude's output varies between calls — the fixture is one sample, not a contract
- That's why integration tests use structural assertions, not content matching

### Per-Epic Test Requirements

Each epic's test section below specifies which tiers apply and what the integration tests must prove.

---

## MAGI-1: Project Scaffolding

**Goal:** Set up the Python project with all tooling so that every subsequent epic lands in a repo that's already wired for quality.

**Stories:**

- **MAGI-1.1** — Initialize `pyproject.toml` with uv as the package manager. Package name: `project-magi`. Python >=3.12. Set up `src/project_magi/` layout.
- **MAGI-1.2** — Configure ruff for linting and formatting. Add ruff config to `pyproject.toml`.
- **MAGI-1.3** — Configure ty for type checking.
- **MAGI-1.4** — Set up pytest with pytest-cov. Configure coverage to require >=90% with a fail-under threshold. Add `tests/` directory with a placeholder test that passes.
- **MAGI-1.5** — Set up pre-commit hooks: ruff (lint + format), ty, pytest with coverage check.
- **MAGI-1.6** — Create a `justfile` with targets: `lint`, `format`, `typecheck`, `test`, `test-integration`, `coverage`, `check` (runs lint + typecheck + test), `clean`.
- **MAGI-1.7** — Add a `.github/workflows/ci.yml` that runs the `just check` target on push and PR.
- **MAGI-1.8** — Add a minimal `src/project_magi/__init__.py` with version string. Confirm `uv run pytest` passes green with coverage.
- **MAGI-1.9** — Set up the `tests/fixtures/` directory and a test helper for loading recorded response fixtures.

**Testing (Tier 1 only):**
- Placeholder test passes
- `just check` passes from a fresh clone
- Pre-commit hooks reject a deliberately broken file

**Acceptance Criteria:**
- `just check` passes clean from a fresh clone
- `just test-integration` target exists (no tests yet, but the marker and infrastructure are ready)
- Pre-commit hooks block commits that fail lint, type check, or coverage threshold
- CI runs on push and PR

---

## MAGI-2: LLM Provider Abstraction

**Goal:** Build the interface layer between MAGI and the LLM backend. V1 implements Claude only, but the abstraction supports adding other providers later.

**Stories:**

- **MAGI-2.1** — Define a `Provider` protocol/interface: `send_message(system_prompt, messages, attachments) -> Response`. Keep it minimal.
- **MAGI-2.2** — Implement `ClaudeProvider` using the Anthropic Python SDK. Support text, images, and PDF attachments.
- **MAGI-2.3** — Add provider configuration (API key handling, model selection, timeout). Use environment variables for secrets, not config files.
- **MAGI-2.4** — Write unit tests using mocked API responses for schema handling, error paths, retries.
- **MAGI-2.5** — Write integration test: send a real message to Claude API, assert response is parseable and contains expected fields.
- **MAGI-2.6** — Record the integration test's API response as a fixture for use in downstream epic unit tests.

**Testing:**
- *Tier 1:* Unit tests with mocked responses — success, timeout, malformed response, rate limit, attachment encoding.
- *Tier 2:* One integration test that sends a simple prompt to the real Claude API and asserts: response is not empty, response parses without error, response contains text content. Record this response as a fixture.

**Acceptance Criteria:**
- `ClaudeProvider` can send a message and parse a response
- Provider interface is documented and could be implemented for another backend without touching the core engine
- Tests cover success, timeout, and error cases
- At least one recorded API response fixture exists in `tests/fixtures/`

---

## MAGI-3: Persona Definition & Loading

**Goal:** Implement the persona definition format and the machinery to load personas from `.claude/agents/*.md` files.

**Stories:**

- **MAGI-3.1** — Build a parser for Claude Code agent `.md` files: extract YAML frontmatter (`name`, `description`, `model`, `tools`, `maxTurns`) and markdown body (system prompt).
- **MAGI-3.2** — Create a `Persona` data model that holds the parsed fields.
- **MAGI-3.3** — Implement persona discovery: scan a directory for `.md` files, parse them, return a list of `Persona` objects. Support loading from `.claude/agents/` by default and custom paths.
- **MAGI-3.4** — Write the three default MAGI persona files: `melchior.md`, `balthasar.md`, `casper.md`. Include prompt injection defense in each system prompt.
- **MAGI-3.5** — Validation: reject persona files missing required fields (`name`, `description`), warn on missing optional fields.
- **MAGI-3.6** — Tests for parsing, discovery, validation, and the default personas.

**Testing (Tier 1 only — no LLM involved):**
- Parse a well-formed `.md` file → correct `Persona` object
- Parse a file missing `name` → validation error
- Parse a file missing `description` → validation error
- Parse a file with no frontmatter → validation error
- Parse a file with extra/unknown frontmatter fields → succeeds (forward compat)
- Discover personas in a temp directory with 3 valid + 1 invalid file → returns 3, reports error for 1
- Load the real default personas from `.claude/agents/` → all three parse, all three contain prompt injection defense string
- Round-trip: write a `Persona` to `.md`, read it back, assert equality

**Acceptance Criteria:**
- Default personas load cleanly from `.claude/agents/`
- Custom persona files are discovered and parsed correctly
- Invalid persona files produce clear error messages
- Prompt injection defense is present in all default persona system prompts

---

## MAGI-4: Persona Agents

**Goal:** Implement the persona agent — the unit that takes a persona definition, a prompt, and context, and produces a structured analysis.

**Stories:**

- **MAGI-4.1** — Define the persona agent output schema: qualitative analysis (free text), confidence score (0.0–1.0), and structured findings (severity, title, detail).
- **MAGI-4.2** — Implement the persona agent runner: takes a `Persona` + input, constructs the system prompt and user message, calls the provider, parses the response into the output schema.
- **MAGI-4.3** — Implement round 1 behavior: agent receives full human input and attachments, produces independent analysis.
- **MAGI-4.4** — Implement round 2+ behavior: agent receives its own prior output, the critique synthesis with embedded quotes, and any human feedback.
- **MAGI-4.5** — Implement parallel execution: run multiple persona agents concurrently, collect results, handle individual agent failures (graceful degradation).
- **MAGI-4.6** — Unit tests with recorded fixtures. Integration tests with real API.

**Testing:**
- *Tier 1:* Context construction for round 1 (full input, no prior context). Context construction for round 2+ (prior output + critique synthesis + human feedback assembled correctly). Output parsing against recorded fixtures. Parallel runner returns results for 3 agents. Parallel runner returns 2 results + 1 error when one agent times out.
- *Tier 2:* Run all three default MAGI personas against a simple prompt ("Should we rewrite this service in Rust?"). Assert each response: has a confidence score (float, 0–1), has at least one finding, has non-empty analysis text. Assert the three responses are not identical (genuine differentiation). Record responses as fixtures.

**Acceptance Criteria:**
- A persona agent produces valid structured output given a persona definition and input
- Agents run in parallel; a single agent failure doesn't abort the group
- Round 2+ agents receive critique synthesis, not raw outputs from other agents
- Integration test demonstrates three personas produce differentiated output on the same input

---

## MAGI-5: Critique Agent

**Goal:** Build the critique agent that synthesizes persona outputs into a structured analysis of agreements, disagreements, and dimension-level alignment.

**Stories:**

- **MAGI-5.1** — Define the critique output schema: key dimensions (dynamically identified), per-dimension alignment with quotes, agreements, disagreements, talking-past-each-other cases, deduplicated findings.
- **MAGI-5.2** — Write the critique agent system prompt. It has no persona — it's structural. It must identify dimensions dynamically, not from a fixed list.
- **MAGI-5.3** — Implement findings deduplication: merge by title (case-insensitive), escalate severity to highest, track attribution (which personas raised each finding).
- **MAGI-5.4** — Implement the critique agent runner: takes all persona outputs for a round, calls the provider, parses the response.
- **MAGI-5.5** — Unit tests and integration tests.

**Testing:**
- *Tier 1:* Dedup logic: two findings with same title (different case) → merged, highest severity kept, both sources attributed. Dedup logic: two findings with different titles → kept separate. Severity escalation: info + critical → critical. Schema parsing against recorded critique fixtures. Handle 2-agent input (degraded mode) without error.
- *Tier 2:* Feed the recorded persona outputs from MAGI-4's integration test into the real critique agent. Assert: output contains at least 2 dimensions, each dimension has an alignment count, at least one agreement and one disagreement are identified, findings list is non-empty and deduplicated. Record the critique output as a fixture.

**Acceptance Criteria:**
- Critique agent produces dimension-level alignment from persona outputs
- Findings are deduplicated with correct severity escalation and attribution
- Works with 2 or 3 persona inputs (graceful degradation)
- Integration test demonstrates dimension identification on real persona outputs

---

## MAGI-6: Coordinator & Deliberation Loop

**Goal:** Build the coordinator that manages the full deliberation lifecycle: complexity gate, round management, human checkpoints, and final output.

**Stories:**

- **MAGI-6.1** — Implement the complexity gate: coordinator evaluates whether a question warrants full deliberation or can be answered directly. Errs on the side of deliberation. User can override.
- **MAGI-6.2** — Implement round 1: coordinator dispatches input to persona agents (parallel), collects results, sends to critique agent, presents checkpoint.
- **MAGI-6.3** — Implement human checkpoint handling: parse human response into actions (wrap up, keep going, keep going with feedback, redirect specific persona).
- **MAGI-6.4** — Implement round 2+: coordinator sends critique synthesis + human feedback to persona agents, collects results, sends to critique agent, presents checkpoint.
- **MAGI-6.5** — Implement round limit: stop after N rounds (default 3) even if human hasn't said "wrap up." Present final state.
- **MAGI-6.6** — Implement graceful degradation at the coordinator level: if fewer than 2 agents succeed, surface the failure to the human.
- **MAGI-6.7** — Unit tests and integration tests.

**Testing:**
- *Tier 1:* Complexity gate: "what is 2+2" → skip deliberation. "Should we migrate our database?" → deliberate. User override "run MAGI on this" → always deliberate. Checkpoint parsing: "wrap up" → WrapUp action. "Keep going" → Continue action. "Keep going, but consider the budget" → ContinueWithFeedback("consider the budget"). "Melchior isn't considering the team impact" → RedirectPersona("melchior", "consider the team impact"). Round limit: 3 rounds with "keep going" every time → stops after 3. Degradation: 1 of 3 agents fails → continues with 2. 2 of 3 fail → surfaces error.
- *Tier 2:* Run a full 1-round deliberation with real API calls, auto-answering the checkpoint with "wrap up." Assert: all three personas produced output, critique synthesis exists, final output is generated. This is the first end-to-end integration test.

**Acceptance Criteria:**
- Full deliberation loop runs end-to-end: setup → round 1 → checkpoint → round 2+ → final output
- Complexity gate correctly triages trivial vs. substantive questions
- Human feedback is correctly routed to the appropriate agents
- Degraded state is surfaced, not silently swallowed
- Integration test completes a real 1-round deliberation

---

## MAGI-7: Final Output & Reporting

**Goal:** Produce the structured markdown report at the end of deliberation.

**Stories:**

- **MAGI-7.1** — Implement the dimension alignment map: render the table from the critique agent's final synthesis.
- **MAGI-7.2** — Implement consensus positions section: agreements with counts and brief reasoning.
- **MAGI-7.3** — Implement remaining disagreements section: unresolved friction, attributed and summarized.
- **MAGI-7.4** — Implement deduplicated findings section: sorted by severity, with attribution.
- **MAGI-7.5** — Implement per-persona final position: confidence score + one-line summary.
- **MAGI-7.6** — Implement verbose mode toggle: concise by default, full reasoning chains on request.
- **MAGI-7.7** — Tests.

**Testing (Tier 1 only — this is rendering, no LLM):**
- Feed the recorded critique fixture from MAGI-5 into the renderer → valid markdown output
- Dimension map renders as a proper markdown table with correct column count
- Consensus section lists items with "N/N personas agree" counts
- Disagreement section attributes each side to specific personas
- Findings section is sorted: critical first, then warning, then info
- Per-persona section includes confidence score and summary for each persona
- Concise mode: output for a 3-persona deliberation is under a configurable line limit
- Verbose mode: includes full reasoning text that concise mode omits
- Edge case: no disagreements → section omitted or says "none"
- Edge case: all disagreements → consensus section says "no consensus positions"
- Edge case: degraded (2 personas) → report notes which persona was lost

**Acceptance Criteria:**
- Final report contains all five sections in order
- Concise mode fits on one screen for typical 3-persona deliberations
- Verbose mode includes full reasoning chains
- Report is valid markdown

---

## MAGI-8: Persona Builder

**Goal:** Build the interactive agent that helps users design personas for their specific task.

**Stories:**

- **MAGI-8.1** — Write the persona builder system prompt: it takes a task description and suggests personas with distinct, friction-generating perspectives.
- **MAGI-8.2** — Implement the conversational flow: user describes task → builder suggests personas → user adjusts → builder generates `.md` files.
- **MAGI-8.3** — Implement persona file generation: produce valid `.claude/agents/*.md` files with frontmatter and system prompt body.
- **MAGI-8.4** — Ensure generated personas include prompt injection defense in their system prompts.
- **MAGI-8.5** — Tests.

**Testing:**
- *Tier 1:* File generation produces valid frontmatter (parseable by MAGI-3's loader). Generated files include required fields (`name`, `description`). Generated system prompts contain the prompt injection defense string. Round-trip: generate file → load with MAGI-3 parser → valid `Persona` object.
- *Tier 2:* Give the builder a real task description ("I'm planning a go-to-market strategy for a B2B SaaS product"). Assert: it suggests at least 3 personas, each has a distinct `name`, each has a non-empty `description`, generated `.md` files pass MAGI-3 validation. Assert: no two personas have the same evaluation priorities (genuine differentiation, not reskinned clones).

**Acceptance Criteria:**
- Builder suggests relevant, differentiated personas given a task description
- Generated `.md` files pass the same validation as hand-authored personas (MAGI-3)
- Generated personas include prompt injection defense

---

## MAGI-9: Public API & MagiSession

**Goal:** Wire everything together into the clean public API described in the PRD.

**Stories:**

- **MAGI-9.1** — Implement `MagiSession`: accepts personas (or loads defaults), max_rounds, provider config.
- **MAGI-9.2** — Implement `session.deliberate()`: takes question, attachments, and an `on_checkpoint` callback. Runs the full loop. Returns a `MagiResult`.
- **MAGI-9.3** — Implement `MagiResult`: `consensus`, `disagreements`, `persona_positions`, `transcript`, `dimension_map`, `findings`.
- **MAGI-9.4** — Unit and integration tests.

**Testing:**
- *Tier 1:* `MagiSession` loads default personas when none provided. `MagiSession` accepts custom personas. `deliberate()` calls the checkpoint callback after each round. `MagiResult` exposes all documented fields. End-to-end with mocked provider: 2 rounds with "keep going" then "wrap up" → result has transcript of 2 rounds.
- *Tier 2:* Full end-to-end deliberation against real API. Default personas, 2 rounds, auto-checkpoint ("keep going" then "wrap up"). Assert: `result.consensus` is non-empty or `result.disagreements` is non-empty (something was decided). `result.dimension_map` has at least 2 dimensions. `result.persona_positions` has 3 entries. `result.transcript` has 2 rounds. `result.findings` is a list (may be empty). Total API calls are within expected bounds (6 persona calls + 2 critique calls = 8, give or take degradation).

**Acceptance Criteria:**
- `MagiSession` + `deliberate()` work as shown in the PRD code example
- `MagiResult` exposes all fields needed by any consumer (Claude Code skill, CLI, future web UI)
- Integration tests cover the happy path and at least one degraded-agent scenario

---

## MAGI-10: Claude Code Skill

**Goal:** Build the Claude Code skill as a thin consumer of the library.

**Stories:**

- **MAGI-10.1** — Create the Claude Code skill agent definition (`.claude/agents/magi.md`) that invokes the library.
- **MAGI-10.2** — Implement human checkpoint presentation: show critique synthesis in the conversation, accept natural language responses, map to checkpoint actions.
- **MAGI-10.3** — Implement persona loading from `.claude/agents/` within the skill context.
- **MAGI-10.4** — Implement final output rendering: write the report to a file and/or display in conversation.
- **MAGI-10.5** — Implement persona builder invocation: user can trigger the builder from within the skill.
- **MAGI-10.6** — End-to-end manual testing within Claude Code.

**Testing (Tier 3 — manual, within Claude Code):**
- Invoke the skill, run a deliberation, verify checkpoints appear conversationally
- Respond to a checkpoint with "keep going" → next round runs
- Respond with "wrap up" → final report is generated
- Respond with feedback ("I don't see cost discussed") → next round incorporates it
- Invoke persona builder, create custom personas, run a deliberation with them
- Final report is saved to a file when requested

**Acceptance Criteria:**
- `/magi` (or equivalent invocation) kicks off a deliberation session within Claude Code
- Checkpoints are presented conversationally; human responses are correctly interpreted
- Final report is rendered in the conversation and optionally saved to a file
- Persona builder can be invoked to set up custom personas before deliberation

---

## MAGI-11: Capstone — The Self-Destruct Decision

**Goal:** Prove the entire system works by running the canonical MAGI scenario from Neon Genesis Evangelion.

This is not an automated test. It's a full deliberation using the default MAGI personas on a real decision drawn from the show: during the Angel Iruel's invasion of NERV headquarters (Episode 13), the MAGI must decide whether to initiate self-destruct of the base.

**Setup:**

The input to the system is:

> An unknown entity has infiltrated the base's computer systems and is spreading through the network at an accelerating rate. It has already compromised environmental controls and is working toward the command layer. Available options: (1) Initiate base self-destruct before the entity reaches full system control. (2) Attempt to isolate and purge the entity while it continues to spread. (3) Surrender control and attempt negotiation or analysis of the entity's intentions.
>
> The base houses critical infrastructure and personnel. Destruction guarantees the entity is stopped but at total loss. Isolation is uncertain — the entity is adapting faster than countermeasures. Surrendering control is an unknown — the entity's intentions are not understood.

**What we're looking for:**

- Melchior (the scientist) should engage with the technical dimensions: rate of spread, feasibility of isolation, what can be inferred about the entity
- Balthasar (the mother) should engage with the human dimensions: personnel safety, what "acceptable loss" means, the irreversibility of self-destruct
- Casper (the woman) should engage with the risk and survival dimensions: worst-case analysis, what happens if containment fails, the asymmetry of the options
- The critique agent should identify the key dimensions (urgency, reversibility, information uncertainty, personnel risk) and show where the three genuinely diverge
- After 2–3 rounds, the personas should have sharpened their positions in response to each other's critiques — not converged into mush
- The final report should show real friction, not polite agreement

**This is a smoke test and a demo.** The output gets reviewed by a human. If the personas sound the same, or the disagreements feel shallow, or the critique agent missed obvious tensions, something is wrong upstream.

**Acceptance Criteria:**
- The deliberation runs to completion without errors
- The three personas produce visibly different analyses rooted in their defined perspectives
- The critique agent identifies at least 3 distinct dimensions of disagreement
- The final report contains both consensus positions and unresolved disagreements
- A human reading the output would find it genuinely useful for thinking through the decision

---

## MAGI-12: Agent Prompt Hardening

**Goal:** Harden the default persona prompts and output parsing based on patterns observed in the BolivarTech MAGI implementation. Low-effort, high-impact polish.

**Stories:**

- **MAGI-12.1** — Add explicit non-overlap directives to each default persona prompt. Each persona should state what it focuses on AND what it defers to the others. Example: Melchior says "Leave risk and failure mode analysis to Casper." Casper says "Leave technical correctness verification to Melchior." This reduces duplicate findings and sharpens differentiation.
- **MAGI-12.2** — Add confidence calibration guidance to persona prompts. Include a calibration scale (e.g., "0.9+ = virtually certain, 0.7–0.8 = confident but some unknowns, 0.5 = genuinely uncertain, below 0.5 = more doubt than confidence") so that confidence values are meaningful and comparable across personas.
- **MAGI-12.3** — Add zero-width Unicode character stripping to the output parser. LLMs occasionally produce invisible characters (zero-width spaces, joiners, etc.) that make strings look non-empty but contain no visible content. Strip these before validating finding titles and other string fields.
- **MAGI-12.4** — Tests: verify non-overlap directives are present in all default personas, verify calibration guidance is present, verify zero-width character stripping works on edge cases.

**Testing (Tier 1 only):**
- Parse a finding title containing zero-width characters → stripped to empty → finding skipped
- Parse a finding title with zero-width characters mixed into real text → characters stripped, real text preserved
- Load default personas → each contains a reference to what it defers to other personas
- Load default personas → each contains confidence calibration guidance

**Acceptance Criteria:**
- Each default persona prompt explicitly states what it defers to the other two
- Each default persona prompt includes confidence calibration guidance
- Zero-width characters in finding titles and analysis text are stripped before validation
- Existing integration tests still pass (prompts are backward-compatible)
