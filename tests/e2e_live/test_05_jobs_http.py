"""Real worker process, durable jobs, and HTTP transport."""

from __future__ import annotations

import asyncio
import os
import socket
import sys
from pathlib import Path

import pytest
from fastmcp import Client

from .conftest import call
from .sources import SOURCES


async def _worker_once(data_dir: str) -> None:
    env = {**os.environ, "YTB_DATA_DIR": data_dir}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "youtube_read_mcp.cli",
        "worker",
        "--once",
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert await asyncio.wait_for(process.wait(), 240) == 0


async def _worker_restart_recovery(data_dir: str, calls: int) -> None:
    env = {**os.environ, "YTB_DATA_DIR": data_dir}
    worker = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "youtube_read_mcp.cli",
        "worker",
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.sleep(0.25)
    worker.terminate()
    await asyncio.wait_for(worker.wait(), 20)
    for _ in range(calls):
        await _worker_once(data_dir)


@pytest.mark.asyncio
async def test_real_worker_jobs_sync_and_cancel(client, evidence):
    if os.getenv("YTB_RUN_JOBS") != "1":
        pytest.skip("NOT_RUN: enable with scripts/test-live.sh --with-jobs")
    sync_one = await call(client, evidence, "youtube_sync_source", {"source": SOURCES.channel, "limit": 2})
    assert sync_one["scanned"] > 0 and sync_one["new_video_ids"]
    sync_two = await call(client, evidence, "youtube_sync_source", {"source": SOURCES.channel, "limit": 2})
    assert not sync_two["new_video_ids"]
    videos = [SOURCES.caption_video, "9bZkp7q19f0", "Mph1H5u3yeA"]
    job = await call(client, evidence, "youtube_batch_prepare", {"videos": videos})
    assert job["total"] == 3 and job["state"] == "queued"
    for _ in videos:
        await _worker_once(evidence["data_dir"])
    completed = await call(client, evidence, "youtube_job_status", {"job_id": job["id"]})
    assert completed["state"] in {"completed", "partial"} and completed["completed"] >= 1

    recovery = await call(client, evidence, "youtube_batch_prepare", {"videos": videos})
    await _worker_restart_recovery(evidence["data_dir"], len(videos))
    recovered = await call(client, evidence, "youtube_job_status", {"job_id": recovery["id"]})
    assert recovered["state"] in {"completed", "partial", "failed"}
    assert all(item["state"] != "running" for item in recovered["items"])
    queued = await call(client, evidence, "youtube_batch_prepare", {"videos": videos})
    cancelled = await call(client, evidence, "youtube_job_cancel", {"job_id": queued["id"]})
    assert cancelled["state"] == "cancelled" and all(x["state"] == "cancelled" for x in cancelled["items"])

    # Two independent server processes share this data directory.  The file
    # lock in transcript preparation must serialize their real cache writes.
    config = {
        "mcpServers": {
            "youtube": {
                "command": sys.executable,
                "args": ["-m", "youtube_read_mcp.cli"],
                "env": {**os.environ, "YTB_DATA_DIR": evidence["data_dir"]},
            }
        }
    }
    async with Client(config) as first, Client(config) as second:
        one, two = await asyncio.gather(
            first.call_tool(
                "youtube_prepare_transcript", {"video": SOURCES.caption_video, "force_refresh": True}
            ),
            second.call_tool(
                "youtube_prepare_transcript", {"video": SOURCES.caption_video, "force_refresh": True}
            ),
        )
    assert one.data["available"] and two.data["available"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_real_http_transport(client, evidence):
    if os.getenv("YTB_RUN_HTTP") != "1":
        pytest.skip("NOT_RUN: enable with scripts/test-live.sh --with-http")
    port = _free_port()
    data_dir = Path(evidence["data_dir"]) / "http"
    env = {**os.environ, "YTB_DATA_DIR": str(data_dir)}
    server = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "youtube_read_mcp.cli",
        "serve",
        "--transport",
        "http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                async with Client(f"http://127.0.0.1:{port}/mcp") as http_client:
                    health = await http_client.call_tool("youtube_health", {})
                    assert health.data["stdio_ready"]
                    info = await http_client.call_tool("youtube_video_info", {"video": SOURCES.video})
                    assert info.data["id"] == SOURCES.video
                    return
            except Exception:
                await asyncio.sleep(0.5)
        raise AssertionError("HTTP MCP server did not become ready")
    finally:
        server.terminate()
        await asyncio.wait_for(server.wait(), 20)
