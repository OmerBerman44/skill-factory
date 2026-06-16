# <Skill> — workflow examples

<!--
PATTERN 1. Concrete end-to-end walkthroughs. The model learns the gnarly cases from
worked examples far better than from rules. Aim for ≥3, and cover the HARD cases —
multi-format input, edge cases, error/guardrail paths — not just the happy path.
Each example: the input, the numbered steps the agent takes, and the exact outcome.
-->

Concrete end-to-end walkthroughs. Use these as a model when handling real cases.
Full rules live in `reference.md`.

## Example 1 — <happy path>

<Input: what arrives.>

1. <Step the agent takes.>
2. <Step.>
3. <Outcome — the exact row written / message sent.>

## Example 2 — <a harder input format / source>

<Input.>

1. …
2. …

## Example 3 — <an edge case or guardrail path, e.g. duplicate / error / ambiguous>

<Input.>

1. <How the agent detects the edge case.>
2. <The guardrail action — skip silently, ask once, flag for review, etc.>

## Example 4 — <trigger-context difference, if the skill has automations>

<Same content, but triggered by the automation instead of chat.>

1. …
2. **Stay silent.** <Why — automation-triggered.>
