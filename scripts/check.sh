#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --extra dev
uv run python -m compileall -q src
uv run pytest -q
uv run ytb-read-mcp test
uv run ytb-read-mcp doctor
printf '\nAll deterministic checks passed. Live YouTube access is not covered.\n'
