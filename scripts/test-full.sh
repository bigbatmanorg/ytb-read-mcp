#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
require_all=0
for arg in "$@"; do
  [[ "$arg" == "--require-all" ]] && require_all=1 || { echo "Unknown option: $arg" >&2; exit 2; }
done
./scripts/check.sh
./scripts/test-installed.sh
if [[ "$require_all" == 1 ]]; then
  command -v docker >/dev/null || { echo "BLOCKED_CONFIGURATION: Docker is required by --require-all" >&2; exit 2; }
  [[ -f .env ]] || { echo "BLOCKED_CONFIGURATION: .env with STT settings is required by --require-all" >&2; exit 2; }
  ./scripts/test-live.sh --with-stt --with-media --with-jobs --with-http
  ./scripts/test-docker.sh
else
  ./scripts/test-live.sh
fi
