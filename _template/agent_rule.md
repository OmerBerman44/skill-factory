# <Skill> — agent rules

<!--
PATTERN 6. This file exists to stop the agent from re-implementing tested scripts.
Capable models "helpfully" rewrite a renderer/styler inline and get it subtly wrong.
Delete this file if the skill has no scripts.
-->

## Always check the skill before acting

For ANY <skill>-related task:
1. Read `<skill-name>/SKILL.md` first.
2. Follow the documented procedure exactly — do NOT write inline code that duplicates
   existing scripts.

## <Output type> requests specifically

When the user asks for <a report / dashboard image / styled sheet / etc.>:
- DO NOT write a new <matplotlib / batchUpdate / …> script inline.
- DO run `<skill-name>/scripts/<script>.py` with the correct args.
- <Where to get the args — sheet ID, token, etc.>

## Script exists, don't recreate it

- `<script_a>.py` — <what it produces>. Call it <when>.
- `<script_b>.py` — <what it produces>. Call it <when>.

If the output looks wrong, the fix is to **re-run the script** (it is idempotent), not to
issue manual inline calls.
