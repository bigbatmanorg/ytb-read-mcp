#!/usr/bin/env bash
# Real image/network/persistence verification; requires a usable Docker daemon.
set -euo pipefail
cd "$(dirname "$0")/.."

image="ytb-read-mcp:e2e"
name="ytb-read-mcp-e2e-$$"
data_dir="$(mktemp -d)"
port="$(uv run python - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  rm -rf "$data_dir"
}
trap cleanup EXIT

docker build -t "$image" .
docker run -d --name "$name" -p "127.0.0.1:$port:8001" -v "$data_dir:/data" "$image" >/dev/null
export YTB_DOCKER_URL="http://127.0.0.1:$port/mcp"
uv run python - <<'PY'
import asyncio, os
from fastmcp import Client

async def main():
    url = os.environ["YTB_DOCKER_URL"]
    for _ in range(40):
        try:
            async with Client(url) as client:
                health = await client.call_tool("youtube_health", {})
                assert health.data["ffmpeg"] and health.data["sqlite_fts5"]
                info = await client.call_tool("youtube_video_info", {"video": "dQw4w9WgXcQ"})
                assert info.data["id"] == "dQw4w9WgXcQ"
                prepared = await client.call_tool("youtube_prepare_transcript", {"video": "dQw4w9WgXcQ"})
                assert prepared.data["available"]
                media = await client.call_tool("youtube_download", {"video": "dQw4w9WgXcQ", "mode": "audio"})
                assert media.data["bytes"] > 0 and media.data["path"].startswith("/data/")
                return
        except Exception:
            await asyncio.sleep(.5)
    raise RuntimeError("Docker MCP endpoint never became ready")

asyncio.run(main())
PY
docker restart "$name" >/dev/null
uv run python - <<'PY'
import asyncio, os
from fastmcp import Client

async def main():
    async with Client(os.environ["YTB_DOCKER_URL"]) as client:
        manifest = await client.call_tool("youtube_transcript_manifest", {"video": "dQw4w9WgXcQ"})
        assert manifest.data["segment_count"] > 0

asyncio.run(main())
PY
echo "Docker E2E passed: $image"
