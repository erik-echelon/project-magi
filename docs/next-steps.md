# Next Steps

What's next for Project MAGI after V1.

## Synthesis Agent

A new agent type that takes the completed deliberation and produces a concrete, actionable write-up of the consensus — not a report of who said what, but a unified document that reads like it was written by one voice, with call-outs for unresolved disagreements.

Available only on request ("synthesize this" or a `--synthesize` flag). The deliberation report remains the primary output. The synthesis is a second pass for cases where the user needs a document they can hand to someone else, not just a decision map they use themselves.

The synthesis agent:
- Writes in a single voice, not per-persona
- Integrates the consensus positions into coherent recommendations
- Flags disagreements as call-out boxes or footnotes, not as the main structure
- Preserves attribution for contested points ("Note: this recommendation is disputed by Casper, who argues...")
- Can be tuned for audience: executive summary, technical brief, team memo

This is distinct from the critique agent (which maps the landscape) and the report renderer (which presents the raw deliberation). The synthesis agent makes a judgment about what the deliberation concluded — which is exactly why it should be opt-in, not automatic. Making that judgment is a form of editorial authority that the thin coordinator deliberately avoids.

## Multi-Model Support

The provider abstraction is in place. Adding GPT and Gemini backends requires implementing the `Provider` protocol — `send_message(system_prompt, messages, attachments) -> ProviderResponse`. No changes to the core engine.

The interesting design question: should different personas use different models? A Claude persona and a Gemini persona aren't just playing different characters — they actually are different cognitive architectures. That's more philosophically honest than the current setup where differentiation comes entirely from system prompts.

Implementation: add `OpenAIProvider` and `GeminiProvider`, allow per-persona model override in the `.md` frontmatter, update `PersonaAgentRunner` to select provider per persona.

## Additional Example Scenarios

### From Evangelion

**The Instrumentality Vote** — Should humanity merge into a single consciousness? Melchior evaluates the technical implications (what happens to individual cognition?), Balthasar evaluates the human cost (what is lost when individuals cease to exist?), Casper evaluates the risks (what if it can't be reversed? what if the merged consciousness is worse?). This is the ultimate MAGI question — the show's thesis statement as a deliberation.

**The Eva Unit-03 Decision** — An Eva has been taken over by an Angel. The pilot (a child) is inside. Options: destroy the Eva (killing the pilot), attempt to extract the pilot under fire, or let the Angel proceed. This forces a direct collision between Melchior's tactical analysis, Balthasar's refusal to sacrifice a child, and Casper's worst-case assessment of what happens if the Angel isn't stopped.

**SEELE's Hacking Attempt** — From End of Evangelion. SEELE attempts to hack the MAGI remotely to force a specific outcome. This could test the system's prompt injection defenses in a narrative context — how do the personas respond when the scenario itself contains manipulative framing?

### Beyond Evangelion

**Startup Pivot Decision** — A startup has runway for 8 months. The product has some traction but isn't growing. Options: double down on the current product, pivot to an adjacent market, or try to get acquired. Custom personas: CEO, CTO, Head of Sales, lead investor.

**Clinical Trial Ethics** — A promising drug shows strong results in Phase 2 but with a concerning side effect in a subpopulation. Options: proceed to Phase 3 as planned, modify the protocol to exclude the subpopulation, or delay for additional safety studies. Custom personas: chief medical officer, patient advocate, regulatory affairs lead, biostatistician.

**Infrastructure Migration Under Load** — A high-traffic service needs to migrate from a legacy database to a new one. The system handles payments. Options: big-bang migration over a maintenance window, gradual dual-write migration, or build a new service alongside the old one. This is a pure engineering deliberation where Melchior, Balthasar, and Casper each have strong, different takes.

Each of these could be written up as a narrative document like the capstone (`docs/capstone.md`), including the scenario, what the personas found, and what the friction revealed.

## Persistent Deliberation History

Save deliberation states to disk so they can be resumed, compared, or referenced later. This enables:
- Resuming an interrupted deliberation
- Comparing how the same question was analyzed at different times or with different personas
- Building a library of past deliberations for organizational learning

## Real-Time Streaming

Stream persona outputs as they're generated rather than waiting for all agents to complete. This would make the interactive mode feel more responsive, especially with Opus (which is slower than Sonnet).

## Web UI

A browser-based interface for running deliberations without the terminal. The library API (`MagiSession.deliberate()`) already supports this — the web UI would be another consumer, like the CLI. Checkpoints would be presented as interactive cards rather than terminal prompts.

## Slack / Teams Integration

A bot that runs MAGI deliberations in a channel. Someone posts a question, the bot runs the personas, and posts the report as a thread. Checkpoints could be interactive messages with buttons.
