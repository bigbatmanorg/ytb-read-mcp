#!/usr/bin/env bash
# Real YouTube verification.  This runner is intentionally opt-in: it sources
# local optional credentials without printing them and leaves a durable report.
set -euo pipefail
cd "$(dirname "$0")/.."

with_stt=0
with_media=0
with_jobs=0
with_http=0
for arg in "$@"; do
  case "$arg" in
    --with-stt) with_stt=1 ;;
    --with-media) with_media=1 ;;
    --with-jobs) with_jobs=1 ;;
    --with-http) with_http=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
run_id="$(date -u +%Y-%m-%dT%H%M%SZ)"
export YTB_E2E_RESULTS_DIR="test-results/$run_id"
export YTB_RUN_STT="$with_stt"
export YTB_RUN_MEDIA="$with_media"
export YTB_RUN_JOBS="$with_jobs"
export YTB_RUN_HTTP="$with_http"
mkdir -p "$YTB_E2E_RESULTS_DIR"
set +e
uv run pytest tests/e2e_live -v -s --junitxml="$YTB_E2E_RESULTS_DIR/junit.xml"
status=$?
set -e
uv run python - "$YTB_E2E_RESULTS_DIR" "$status" <<'PY'
import json, pathlib, sys
root, status = pathlib.Path(sys.argv[1]), int(sys.argv[2])
evidence = root / "live-evidence.json"
data = json.loads(evidence.read_text()) if evidence.exists() else {}
report = {"status": "PASS" if status == 0 else "FAIL", "exit_code": status,
          "kind": "real-mcp-stdio-youtube", "evidence": data,
          "optional_stt_requested": bool(int(__import__('os').environ['YTB_RUN_STT']))}
(root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
(root / "report.md").write_text(
    f"# Live verification\\n\\nStatus: **{report['status']}** (exit {status})\\n\\n"
    f"Real MCP calls: {len(data.get('calls', []))}. Evidence is in `live-evidence.json`; secrets are excluded.\\n",
    encoding="utf-8")
PY
exit "$status"
