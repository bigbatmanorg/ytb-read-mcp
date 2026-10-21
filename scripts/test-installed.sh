#!/usr/bin/env bash
# Build and execute the wheel outside the source tree.  uvx provides a fresh,
# isolated tool environment and avoids accidentally importing src/.
set -euo pipefail
cd "$(dirname "$0")/.."
uv build --wheel
wheel="$(find dist -maxdepth 1 -name 'ytb_read_mcp-*.whl' -print -quit)"
test -n "$wheel"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
(
  cd "$work"
  uvx --isolated --from "$OLDPWD/$wheel" ytb-read-mcp doctor > doctor.json
  uvx --isolated --from "$OLDPWD/$wheel" ytb-read-mcp test > test.json
  uv run python - <<'PY'
import json
assert json.load(open("doctor.json"))["stdio_ready"]
assert json.load(open("test.json"))["status"] == "passed"
PY
)
echo "Installed-wheel verification passed: $wheel"
