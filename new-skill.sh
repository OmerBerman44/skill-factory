#!/usr/bin/env bash
#
# new-skill.sh — scaffold a new platform skill from _template.
#
# Usage:
#   ./new-skill.sh <skill-name> [target-dir]
#
#   <skill-name>  kebab-case id for the skill (e.g. weekly-sales-report). Becomes the
#                 folder name and the `name:` in SKILL.md frontmatter.
#   [target-dir]  where to create it. Default: skills/<skill-name> inside this repo.
#
# What it does:
#   - copies _template/ to the new skill folder
#   - replaces the <skill-name> placeholder throughout with your name
#   - prints the next steps (which sidecars to keep, how to QA before shipping)
#
# It does NOT fill in the prose placeholders (<Skill Title>, <intent>, …) — that's the
# authoring work. Follow SKILL-AUTHORING.md §8.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$REPO_ROOT/_template"

die() { echo "error: $*" >&2; exit 1; }

[[ $# -ge 1 ]] || die "usage: ./new-skill.sh <skill-name> [target-dir]"

NAME="$1"
[[ "$NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || \
  die "skill name must be kebab-case (lowercase, digits, single hyphens): got '$NAME'"

TARGET="${2:-$REPO_ROOT/skills/$NAME}"
[[ -e "$TARGET" ]] && die "target already exists: $TARGET"
[[ -d "$TEMPLATE" ]] || die "template not found at $TEMPLATE"

echo "→ scaffolding '$NAME' at $TARGET"
mkdir -p "$(dirname "$TARGET")"
cp -r "$TEMPLATE" "$TARGET"
find "$TARGET" -name '.DS_Store' -delete   # don't propagate macOS junk into new skills

# Replace the literal <skill-name> placeholder (paths + frontmatter) with the real name.
# Use perl for portable in-place edit (BSD vs GNU sed differ on -i).
find "$TARGET" -type f \( -name '*.md' -o -name '*.py' \) -print0 \
  | xargs -0 perl -pi -e "s/<skill-name>/$NAME/g"

echo "✓ created:"
find "$TARGET" -type f | sed "s|$REPO_ROOT/||" | sort | sed 's/^/    /'

cat <<EOF

next steps:
  1. Edit $TARGET/SKILL.md — fill the description (with trigger phrases), critical rules,
     workflow, and the "Next actions (CTAs)" section. Delete sidecars you don't need yet.
  2. Add reference.md / examples.md / scripts only when the growth path (SKILL-AUTHORING.md §5) forces it.
  3. QA before shipping:
       python3 "$REPO_ROOT/skill-qa/scripts/lint.py" "$TARGET"
     then run the skill-qa skill for the judgment review + ship-gate.

The one rule: prose for judgment, scripts for determinism.
EOF
