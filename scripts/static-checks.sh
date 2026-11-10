#!/usr/bin/env bash
# Every check that reads the code without running it. CI and Claude Code's Stop hook run this.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run lint-imports
uv run vulture
uv run pylint src tests
