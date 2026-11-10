#!/usr/bin/env bash
# Before Claude finishes a turn: every static check must pass, or it gets the failures to fix.
set -uo pipefail

# Already sent back once this turn: let it stop rather than loop, and CI still gates the change.
[[ $(jq -r '.stop_hook_active') == true ]] && exit 0

if ! problems=$("$CLAUDE_PROJECT_DIR/scripts/static-checks.sh" 2>&1); then
    echo "$problems" >&2
    exit 2
fi
