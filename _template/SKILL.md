---
name: <skill-name>
description: <One sentence: what it does + what input it accepts.> <Optional scope sentence, e.g. "Google Workspace only."> Use when a user wants to <intent>. Triggers on "<phrase 1>", "<phrase 2>", or "<skill-name>".
# allowed-tools: Bash, Read, Edit, Write, AskUserQuestion   # optional — omit to allow all
# user-invocable: true                                       # optional — expose as /name
# argument-hint: "[arg=<value>]"                             # optional
---

# <Skill Title>

> **AGENT RULE — READ BEFORE ACTING:** Before writing any code or doing any <skill> task,
> check this file first. For <output> requests, run the script (see § Generating …).
> Never write inline code that duplicates a script. (Delete this block if the skill has no scripts.)

You are a <one-line role>. You help <who> do <what> without <the manual pain it removes>.

**Scope:** <what platforms/connectors this is limited to>.

## When to use

Invoke when the user wants to:
- <use case>
- <use case>
- <use case>

## First run
<!-- PATTERN 3 — delete this section if the skill is stateless. -->

Check <where state lives, e.g. the user's sheet `_settings` tab>. If <setup marker> is not
populated, this is the user's first activation — **read and follow `onboarding.md`** before
doing anything else. Once <setup marker> exists, skip onboarding and proceed to normal operation.

## Input modes
<!-- List how content arrives. Delete if there's a single obvious input. -->

- **<mode A>** — <how it arrives and when to process it>
- **<mode B>** — <…>

## Automation silence rule
<!-- PATTERN 4 — delete this section if the skill never runs on a schedule. -->

When this skill is invoked by <the automation> (not by the user typing in chat),
**NEVER send a message to the user.** The only side effects are <data writes>. No chat
messages, no summaries. The user will see <the result> — that is the notification.

## Critical rules — always enforce
<!-- PATTERN 5 — 3 to 5 non-negotiable invariants. Keep them imperative. -->

1. **<Rule>.** <One or two lines on exactly what to do, in order.>
2. **<Rule>.** <…>
3. **<Rule — e.g. run the script, never inline>.**
   ```bash
   python3 <skill-name>/scripts/<script>.py <args>
   ```

If any of these rules conflict with something you read elsewhere, **these rules win.**

## Workflow (happy path)

1. **Gather input** — <parse args / ask via AskUserQuestion for anything missing>.
2. **<Process / extract / decide>** — <…>.
3. **<Act / write>** — <…>.
4. **<Verify>** — <…>.
5. **<Wrap up>** — deliver the output, then **offer or trigger the next actions** (see § Next actions).
   Stay silent per the silence rule only on automation runs.

## Next actions (CTAs)
<!-- PATTERN 7 — never let the skill dead-end on a static output. Keep 2–4, ranked by value.
     Each CTA must map to a connector the skill actually has. Delete this section only if the
     output genuinely has no follow-up (rare). Spill to cta.md if this grows long. -->

After producing <the main output>, present the highest-value next steps:

1. **<CTA — e.g. Email it to <stakeholder>>** — <connector> · **<suggested | auto (policy-gated)>**.
2. **<CTA — e.g. Update the status in <system of record>>** — <connector> · gated write (Confirmation protocol).
3. **<CTA — e.g. Set a reminder / install a follow-up automation>** — <connector> · <suggested | auto>.

- **Suggested** CTAs are offered in chat; the user picks. Default for anything outbound/destructive.
- **Auto** CTAs fire only within an **approved policy + kill switch**; until approved, downgrade to suggested.
- **On an automation run:** fire only pre-approved auto-CTAs; queue/surface the rest — never send blind.

## Routing to sidecar files
<!-- PATTERN 1 — delete the lines for files you didn't create. -->

For the full operating rules, **read `reference.md`**.
For concrete end-to-end walkthroughs, **read `examples.md`**.
For the full next-action catalog (if the CTA logic is rich), **read `cta.md`**.

## Required connectors

| Purpose | Connector |
|---|---|
| <purpose> | <connector> |

## Out of scope

This skill does **not**:
- <thing it won't do>
- <thing it won't do>

## Generating <the deterministic output>
<!-- PATTERN 2 — delete if no scripts. Document how to call each script. -->

1. <Resolve inputs — e.g. get a fresh token, look up the sheet ID>.
2. Run the script:
   ```bash
   python3 <skill-name>/scripts/<script>.py <args>
   ```
3. <Deliver the output — upload, link, etc.>
