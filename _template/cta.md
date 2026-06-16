# <Skill> — next-action catalog (CTAs)

<!--
PATTERN 7. The full catalog of follow-up actions the skill can take after producing an output.
Only create this file when the CTA logic is rich (many actions, branching, per-policy behavior).
For most skills a short "Next actions" section in SKILL.md is enough — delete this file then.

The principle: a skill delivers a COMPLETE WORKFLOW, not a static artifact. Every output ends by
offering or triggering the next step. A CTA that contacts a person or changes data is a GATED
action — same consent model as any write (see reference.md § Confirmation protocol).
-->

The follow-up actions available after <the main output>. `SKILL.md` routes here. Each CTA lists the
connector it needs, whether it is **suggested** (offered, user picks) or **auto** (fires only within
an approved policy + kill switch), and what it does.

## Trigger map — which output offers which CTAs

| After this output | Offer / trigger | Kind |
|---|---|---|
| <e.g. the report is generated> | <Email to stakeholder>, <Update status>, <Set reminder> | suggested / auto |
| <e.g. a blocker is found> | <Slack the owner>, <Open a ticket> | suggested |

## The CTAs

### <CTA 1 — e.g. Email the report to stakeholders>
- **Connector:** <Gmail / Slack / …>.
- **Kind:** <suggested | auto (policy-gated)>.
- **Recipient/target:** <where it comes from — never guessed; skip + flag if missing>.
- **What it does:** <draft + send / post / write>. The agent drafts (judgment); the send is the action.
- **Gate:** <suggested → ask once; auto → only if the policy is approved and the kill switch is on>.
- **Log:** <if the action must not repeat, record it to <ledger/state> immediately after success>.

### <CTA 2 — e.g. Update the status in the system of record>
- **Connector:** <…>. **Kind:** gated write.
- **What it does:** <mark closed / set stage / flag>. Follows the **Confirmation protocol** — propose
  the exact change, get explicit consent, re-read, write one item, report.

### <CTA 3 — e.g. Set a reminder / install a follow-up automation>
- **Connector:** <automations / calendar>. **Kind:** <suggested | auto>.
- **What it does:** <"re-check in 7 days" / schedule the next run>. Store the returned id for self-heal.

## Policy & kill switch (for auto-CTAs)
<!-- Delete if the skill has no auto-triggered CTAs. Mirror the AR-reminder policy model. -->

- The user approves the auto-CTA policy **once** (which CTAs auto-fire, cadence, recipients). Until
  approved, every auto-CTA is downgraded to **suggested**.
- A single **kill switch** (`<cta_auto_enabled>`) disables all auto-CTAs instantly when off.
- Store policy + switch in <settings>; changing them is a normal settings edit.

## Automation-run behavior

When invoked by an automation (no user present):
- Fire **only** pre-approved auto-CTAs (policy on, kill switch on, recipient known).
- **Queue or surface** every suggested CTA in the output instead of sending it — never send blind.
- Respect the §<silence rule>: the data writes / sent actions ARE the notification.

## Guardrails

- **No connector for a CTA** → don't offer it. Never promise an action the skill can't perform.
- **Missing recipient/target** → skip that CTA and flag it; never guess an address or id.
- **Duplicate-send risk** → log every auto-CTA to state immediately; one send per item per stage.
- **Uncertain consent** → default to suggesting, not auto-firing.
