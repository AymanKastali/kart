#!/usr/bin/env bash
# After Claude edits a Python file: format it, then hand any lint or type error straight back.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // empty')
[[ "$file" == *.py ]] || exit 0
cd "$CLAUDE_PROJECT_DIR"

uv run --quiet ruff format --quiet "$file"
if ! problems=$(uv run --quiet ruff check --output-format concise "$file" 2>&1 && uv run --quiet ty check 2>&1); then
    echo "$problems" >&2
    exit 2
fi
