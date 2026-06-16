# <Skill> — operating reference

<!--
PATTERN 1. The full rules. SKILL.md routes here once onboarding is complete.
Only create this file when the rules outgrow SKILL.md. Organize by the stages of
the skill's pipeline — one ## section per stage.
-->

The full rules for <the skill's pipeline stages>. `SKILL.md` routes here.

## <Stage 1 — e.g. Input capture / Extraction>

<How content is fetched/parsed. The priority chain when multiple sources exist.
The fuzzy judgment the LLM makes here. RTL/multi-language/edge handling.>

## <Stage 2 — e.g. Classification / Categorization>

<The taxonomy or decision rules. In-session memory. The fallback funnel
(known → LLM knowledge → web search → flag for review).>

## <Stage 3 — Deduplication / validation>

<Checks to run before writing, in order. What counts as a duplicate. What to do on a hit
depending on trigger context (silent skip vs. ask the user).>

## Storage

<The data layout — tabs/columns/folders. Where originals go. Naming conventions.
Reference the canonical schema in onboarding.md; don't duplicate it, point to it.>

## <Output — Dashboard / report / styling>

**Owned by `scripts/<script>.py`.** Never produce this inline. Always call:
```bash
python3 <skill-name>/scripts/<script>.py <args>
```
<What the script computes/writes, so the design is auditable — but this is documentation,
NOT an instruction for the agent to execute by hand.>

## <Operations — automations, reminders, recaps>

<Schedules. What each automated run does. The silence rule (cross-reference SKILL.md).
Self-heal behavior for missing automations.>

## Language / localization
<!-- Delete if single-language. -->

<How languages are stored, auto-expanded, and which user-facing text is translated.>

## Guardrails

The realistic failure modes and exactly what to do for each. Organize by category:

### <Category — e.g. Input quality>
- **<Failure mode>** → <action / message to user>.
- **<Failure mode>** → <action>.

### <Category — e.g. Storage / system>
- **<Failure mode>** → <action>.

### <Category — e.g. Visual / output>
- **<Symptom>** → <usually: re-run the script, never inline fixes>.
