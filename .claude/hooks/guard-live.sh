#!/usr/bin/env bash
# Pre-hook: guard-live.sh
# Forces the permission popup for anything that changes what's live, so Tom
# approves each one in chat even when the command is otherwise auto-allowed
# (e.g. python3:* is on the allow list, which is how the TomBot DB got wiped
# without a prompt on 2026-09-24).
#
# ASK (popup):
#   git push                      -> Netlify build (costs money)
#   scripts/load_content_v3.py    -> wipes and reloads the LIVE TomBot DB
#   scripts/load_content*.py      -> any other loader variant
#   any command that names NILEDB_URL together with DELETE/TRUNCATE/DROP/
#   INSERT/UPDATE/ALTER            -> ad-hoc writes to the live DB
#
# Receives JSON on stdin: { "tool_name": "Bash", "tool_input": { "command": "..." } }
# Exit 0 = allow. To ask: exit 0 with a permissionDecision JSON on stdout.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(printf '%s\n' "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

[ -z "$COMMAND" ] && exit 0

ask() {
  python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask', 'permissionDecisionReason': sys.argv[1]}}))" "$1"
  exit 0
}

GIT_AT='(^|&&|\|\||;)\s*git\s+'

if printf '%s\n' "$COMMAND" | grep -qE "${GIT_AT}push\b"; then
  ask "git push triggers a Netlify build (costs money). Tom approves each push here."
fi

if printf '%s\n' "$COMMAND" | grep -qE 'load_content[A-Za-z0-9_]*\.py'; then
  ask "This wipes and reloads the LIVE TomBot database. Tom approves each reload here."
fi

if printf '%s\n' "$COMMAND" | grep -q 'NILEDB_URL' && printf '%s\n' "$COMMAND" | grep -qiE '\b(DELETE|TRUNCATE|DROP|INSERT|UPDATE|ALTER)\b'; then
  ask "This writes to the LIVE TomBot database. Tom approves each write here."
fi

exit 0
