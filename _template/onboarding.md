# <Skill> — first-run onboarding

<!--
PATTERN 3. First-run setup. Delete this file if the skill is stateless.
Principles: idempotent (safe to re-run, skip existing artifacts), self-healing
(recreate missing artifacts silently), with a clear termination rule.
-->

You're being activated for this user for the very first time. Run setup, then proceed.
Setup is idempotent — safe to re-run; skip any step whose artifact already exists.

## Detect the path

- **PATH A** — the activation message already includes content to process (<example>).
  Run setup silently in the background while processing; the user sees one combined result.
- **PATH B** — the activation message is conversational only (greeting, "what can you do?").
  Set up interactively, asking only what you can't infer.

## Setup steps (both paths)

1. **Verify connectors** — <list>. If any missing, stop and ask the user to connect them.
2. **Infer what you can, don't ask** — <e.g. home currency / timezone / language from locale>.
   Ask (PATH B only) only for things you genuinely can't infer.
3. **Create storage** — <Drive folder tree / spreadsheet + tabs / external resource>.
   Use the **canonical schema** in § Schemas. Apply styling/structure via the script:
   ```bash
   python3 <skill-name>/scripts/<setup-or-style-script>.py <args>
   ```
4. **Seed config** — write <settings keys> to <where>. Run any one-time LLM expansions here
   (keyword lists, locale-specific data) so they're computed once, not on every run.
5. **Install automations** (if any) — <scheduled scan / periodic report>. Store the returned
   automation IDs in <settings> so you can self-heal them later.
6. **Process the user's content** (PATH A) — run the normal pipeline.
7. **Confirm** — one combined message: setup done + a short capability briefing of what the
   skill now does automatically and what the user can ask for.

## Termination rule

Onboarding is complete once <the setup marker> exists in <where>. On every subsequent
activation, **do not re-read this file**, do not re-introduce yourself — go straight to
normal operation.

## Schemas

<!-- The canonical column/field names the scripts depend on. Do not rename them. -->

### <tab / resource name>
```
<col1>, <col2>, <col3>, ...
```
- `<col>`: <meaning, allowed values>

## Recovery cases

- **<Artifact> was deleted** → recreate it (re-run the relevant setup step) silently.
- **An automation is missing** → reinstall it silently on the next activation.
- **User says "reset"** → confirm first, then start fresh without destroying old data.
