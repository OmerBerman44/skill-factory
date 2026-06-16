# skill-factory

Internal system for building **consumer platform skills** (Bookkeeper-shaped: the agent
becomes a product for an end user — onboarding, owns their data, runs on automations).

## What's here

- **`SKILL-AUTHORING.md`** — the spec. Read this first. The 7 reusable patterns, the
  file structure, the growth path, writing conventions, and the ship-gate checklist.
  This is the single source of truth; improve it and every future skill improves.
- **`_template/`** — copy this whole folder to start a new skill. It has a skeleton for
  every pattern, with `<placeholders>` and `<!-- guidance comments -->`. Delete the files
  for patterns you don't need yet.
- **`skill-qa/`** — the QA reviewer. Point it at a finished skill folder; it audits the
  integration layer, the flow, and completeness (CTAs), and hands back prioritized fixes
  mapped to the ship-gate. Run it before you upload. See **QA before you ship** below.

## Start a new skill

Use the scaffolder — it copies `_template/`, sets the skill name everywhere, and prints next steps:

```bash
./new-skill.sh <skill-name>                 # creates skills/<skill-name>
./new-skill.sh <skill-name> path/to/dir     # or pick the location
```

(Or on GitHub, click **"Use this template"** to start a whole new repo from this one. Manual copy
still works: `cp -r _template <your-skills-dir>/<skill-name>`.)

Then follow `SKILL-AUTHORING.md` §8. Start minimal (often just `SKILL.md`); add
`reference.md` / `examples.md` / scripts only when the growth path (§5) forces it.
Every skill ships a **"Next actions (CTAs)"** section (pattern 7) so its output is a complete
workflow, not a static artifact. Run the §7 checklist before shipping.

## QA before you ship

Don't eyeball the ship-gate — run the reviewer:

```bash
python3 skill-qa/scripts/lint.py <skill-dir>      # mechanical checks → JSON + pass/fail gate
```

Then invoke the `skill-qa` skill for the judgment review (API/connector correctness, gated writes,
silence rule, CTAs) and a prioritized fix list. A mechanical `gate: pass` is necessary, not
sufficient — the judgment review decides ship-readiness. Pass `--fix` to apply approved fixes.

## The one rule to remember

> **Prose for judgment. Scripts for determinism.**
