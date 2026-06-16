"""
Skill QA — mechanical lint (deterministic, READ-ONLY)

PATTERN 2. The reviewer agent CALLS this for the mechanical checks; it never eyeballs them
(see agent_rule.md). This script does the deterministic part of a skill review: parse the skill's
files and report the facts that are exact and repeatable — frontmatter validity, file presence,
size budget, agent_rule coverage, `# VERIFY` counts, and whether the skill ships a CTA (Pattern 7).
The agent reasons over this JSON and does the *judgment* review (API correctness, gated writes,
flow) per reference.md.

Contract:
  - READ-ONLY. Never modifies the target skill. Only reads files.
  - Idempotent: same skill folder -> same output.
  - Reads the skill path from argv. Fails loudly with a clear message if it's missing/invalid.
  - The mechanical `gate` is "fail" iff there is >=1 BLOCKER finding. A "pass" here is necessary,
    not sufficient — the agent's judgment review still decides ship-readiness.

Usage:
  python3 lint.py <skill_path>
    skill_path — path to the skill folder (the one containing SKILL.md).

Output: a single JSON object on stdout:
  {
    "skill":   "<folder name>",
    "files":   { "SKILL.md": true, "reference.md": ..., "scripts": ["a.py", ...] },
    "findings":[ {id, severity, check, file, detail, rule} ],
    "counts":  { "blocker": n, "warn": n, "nit": n, "info": n, "verify_markers": n },
    "gate":    "pass" | "fail"
  }
"""

import os
import re
import sys
import json
from pathlib import Path

SEV_BLOCKER = "blocker"
SEV_WARN = "warn"
SEV_NIT = "nit"
SEV_INFO = "info"

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECRET = re.compile(
    r"""(token|secret|api[_-]?key|apikey|password|passwd|bearer)\s*[:=]\s*['"][^'"]{12,}['"]""",
    re.IGNORECASE,
)

SIDECARS = ["reference.md", "examples.md", "agent_rule.md", "onboarding.md", "cta.md"]


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── ARGS ──────────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    fail("usage: lint.py <skill_path>")

SKILL_DIR = Path(sys.argv[1]).expanduser()
if not SKILL_DIR.is_dir():
    fail(f"not a directory: {SKILL_DIR}")

SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_NAME = SKILL_DIR.resolve().name

findings = []


def add(id_, severity, check, detail, rule, file=""):
    findings.append({
        "id": id_, "severity": severity, "check": check,
        "file": file, "detail": detail, "rule": rule,
    })


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# ── FILE INVENTORY ────────────────────────────────────────────────────────────
scripts_dir = SKILL_DIR / "scripts"
script_files = sorted(p.name for p in scripts_dir.glob("*.py")) if scripts_dir.is_dir() else []
files = {"SKILL.md": SKILL_MD.exists()}
for s in SIDECARS:
    files[s] = (SKILL_DIR / s).exists()
files["scripts"] = script_files


def emit_and_exit():
    counts = {SEV_BLOCKER: 0, SEV_WARN: 0, SEV_NIT: 0, SEV_INFO: 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    counts["verify_markers"] = VERIFY_COUNT
    gate = "fail" if counts[SEV_BLOCKER] > 0 else "pass"
    print(json.dumps({
        "skill": SKILL_NAME,
        "files": files,
        "findings": findings,
        "counts": counts,
        "gate": gate,
    }, indent=2))
    sys.exit(0)


VERIFY_COUNT = 0

# SKILL.md must exist — hard stop (everything else depends on it).
if not SKILL_MD.exists():
    add("skill_md_missing", SEV_BLOCKER, "structure",
        "No SKILL.md in the skill folder — the only required file is absent.",
        "SKILL-AUTHORING.md §3", "SKILL.md")
    emit_and_exit()

skill_text = read(SKILL_MD)
skill_lower = skill_text.lower()


# ── FRONTMATTER ───────────────────────────────────────────────────────────────
def parse_frontmatter(text):
    """Naive YAML-frontmatter parse (top-level scalar keys only). No external deps."""
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        km = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if km:
            fm[km.group(1).strip()] = km.group(2).strip().strip('"').strip("'")
    return fm


fm = parse_frontmatter(skill_text)
if fm is None:
    add("frontmatter_missing", SEV_BLOCKER, "discovery",
        "SKILL.md has no YAML frontmatter (--- name/description ---). It won't load.",
        "SKILL-AUTHORING.md §4", "SKILL.md")
    emit_and_exit()

name = fm.get("name", "")
desc = fm.get("description", "")

if not name:
    add("name_missing", SEV_BLOCKER, "discovery", "Frontmatter has no `name`.",
        "SKILL-AUTHORING.md §4", "SKILL.md")
else:
    if not KEBAB.match(name):
        add("name_not_kebab", SEV_BLOCKER, "discovery",
            f"`name: {name}` is not kebab-case (^[a-z0-9]+(-[a-z0-9]+)*$).",
            "SKILL-AUTHORING.md §4 / §7", "SKILL.md")
    if name != SKILL_NAME:
        add("name_folder_mismatch", SEV_BLOCKER, "discovery",
            f"`name: {name}` does not match the folder name `{SKILL_NAME}`.",
            "SKILL-AUTHORING.md §7", "SKILL.md")

if not desc:
    add("description_missing", SEV_BLOCKER, "discovery",
        "Frontmatter has no `description` — the entire discovery surface is empty.",
        "SKILL-AUTHORING.md §4", "SKILL.md")
else:
    if len(desc) < 40:
        add("description_too_short", SEV_WARN, "discovery",
            f"`description` is only {len(desc)} chars — likely missing scope/input/triggers.",
            "SKILL-AUTHORING.md §4", "SKILL.md")
    if not re.search(r"use when|triggers on|trigger", desc, re.IGNORECASE):
        add("description_no_triggers", SEV_WARN, "discovery",
            "`description` has no explicit trigger phrases ('Use when …' / 'Triggers on …'). "
            "The agent may never fire the skill.",
            "SKILL-AUTHORING.md §4", "SKILL.md")


# ── SIZE BUDGET (progressive disclosure) ──────────────────────────────────────
line_count = skill_text.count("\n") + 1
if line_count > 220 or len(skill_text) > 15000:
    add("skill_md_too_large", SEV_WARN, "structure",
        f"SKILL.md is {line_count} lines / {len(skill_text)} chars — it's loaded on every "
        "activation. Route heavy detail into reference.md / examples.md.",
        "SKILL-AUTHORING.md §3", "SKILL.md")


# ── CRITICAL RULES BLOCK ──────────────────────────────────────────────────────
if "critical rule" not in skill_lower:
    add("critical_rules_missing", SEV_WARN, "flow",
        "No 'Critical rules' block found in SKILL.md (3–5 non-negotiable invariants expected).",
        "SKILL-AUTHORING.md §6 (pattern 5)", "SKILL.md")
elif "these rules win" not in skill_lower:
    add("critical_rules_no_winclause", SEV_WARN, "flow",
        "Critical-rules block present but missing the '…these rules win.' conflict clause.",
        "SKILL-AUTHORING.md §6 (pattern 5)", "SKILL.md")


# ── OUT OF SCOPE ──────────────────────────────────────────────────────────────
if "out of scope" not in skill_lower:
    add("out_of_scope_missing", SEV_WARN, "flow",
        "No 'Out of scope' section — without it the skill may improvise into the wrong product.",
        "SKILL-AUTHORING.md §6 (scope hygiene)", "SKILL.md")


# ── PATTERN 7 — CTAs / COMPLETE WORKFLOW ──────────────────────────────────────
has_cta_section = bool(re.search(r"next action|\bcta", skill_lower))
has_cta_file = files.get("cta.md", False)
if not has_cta_section and not has_cta_file:
    add("cta_section_missing", SEV_BLOCKER, "cta",
        "No 'Next actions (CTAs)' section in SKILL.md and no cta.md — the output dead-ends "
        "on a static artifact instead of delivering a complete workflow. Add follow-up actions "
        "(email a stakeholder, update a status, set a reminder). If the output genuinely has no "
        "follow-up (rare), the author must consciously accept this.",
        "SKILL-AUTHORING.md §6 (pattern 7) / §7 Value", "SKILL.md")


# ── AUTOMATION → SILENCE RULE ─────────────────────────────────────────────────
ref_text = read(SKILL_DIR / "reference.md")
combined = skill_lower + "\n" + ref_text.lower()
mentions_automation = bool(re.search(r"\b(automation|scheduled|schedule|cron|daily run|monthly run)\b", combined))
has_silence = bool(re.search(r"silence|stay silent|never (send|message|notify)|no chat message", combined))
if mentions_automation and not has_silence:
    add("silence_rule_missing", SEV_WARN, "flow",
        "Skill mentions an automation/schedule but no silence rule found. State explicitly: "
        "'when automation-triggered, NEVER message the user.'",
        "SKILL-AUTHORING.md §6 (pattern 4)", "SKILL.md")


# ── ONBOARDING TERMINATION RULE ───────────────────────────────────────────────
if files.get("onboarding.md", False):
    onb = read(SKILL_DIR / "onboarding.md").lower()
    if not re.search(r"terminat|complete once|onboarding is complete|once .* exists", onb):
        add("onboarding_no_termination", SEV_WARN, "flow",
            "onboarding.md has no clear termination rule — the skill may re-onboard forever.",
            "SKILL-AUTHORING.md §6 (pattern 3)", "onboarding.md")
    if not re.search(r"self-heal|recreate|silently recreate|missing artifact", onb):
        add("onboarding_not_self_healing", SEV_NIT, "flow",
            "onboarding.md doesn't describe self-healing (recreate a deleted artifact silently).",
            "SKILL-AUTHORING.md §6 (pattern 3)", "onboarding.md")


# ── SCRIPTS ↔ AGENT_RULE COVERAGE + SECRETS + VERIFY ──────────────────────────
agent_rule_text = read(SKILL_DIR / "agent_rule.md")
if script_files and not files.get("agent_rule.md", False):
    add("agent_rule_missing", SEV_WARN, "flow",
        f"{len(script_files)} script(s) present but no agent_rule.md 'don't recreate' guard — "
        "the model will helpfully rewrite a tested script and get it subtly wrong.",
        "SKILL-AUTHORING.md §6 (pattern 6)", "agent_rule.md")

for s in script_files:
    src = read(scripts_dir / s)
    # Count real `# VERIFY` comments; ignore backtick-quoted mentions in docstrings/prose.
    VERIFY_COUNT += len(re.findall(r"(?<!`)#\s*VERIFY", src))

    # script not named in the guard
    if files.get("agent_rule.md", False) and s not in agent_rule_text:
        add("script_not_guarded", SEV_WARN, "flow",
            f"`{s}` is not mentioned in agent_rule.md — add a 'don't recreate it' entry.",
            "SKILL-AUTHORING.md §6 (pattern 6)", f"scripts/{s}")

    # possible hardcoded secret (heuristic; the agent confirms)
    for i, line in enumerate(src.splitlines(), 1):
        if "os.environ" in line or "getenv" in line:
            continue
        if SECRET.search(line):
            add("possible_hardcoded_secret", SEV_WARN, "integration",
                f"`{s}:{i}` looks like a hardcoded secret/token. Read it from env instead "
                "(confirm — may be a placeholder).",
                "SKILL-AUTHORING.md §6 (script contract)", f"scripts/{s}")

    # reads inputs from env/args at all?
    if "requests" in src and "os.environ" not in src and "getenv" not in src and "sys.argv" not in src:
        add("script_no_external_inputs", SEV_NIT, "integration",
            f"`{s}` makes HTTP calls but reads no args/env — verify it isn't hardcoding inputs.",
            "SKILL-AUTHORING.md §6 (script contract)", f"scripts/{s}")

emit_and_exit()
