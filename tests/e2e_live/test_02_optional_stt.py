"""Real STT fallback.  Select explicitly with --with-stt so normal core runs stay bounded."""

from __future__ import annotations

import os
import sys

import pytest
from fastmcp import Client

from .conftest import call
from .sources import SOURCES


@pytest.mark.asyncio
async def test_real_configured_stt_fallback(client, evidence):
    if os.getenv("YTB_RUN_STT") != "1":
        pytest.skip("NOT_RUN: enable with scripts/test-live.sh --with-stt")
    if not os.getenv("STT_BASE_URL"):
        pytest.fail("BLOCKED_CONFIGURATION: STT_BASE_URL is required for requested STT verification")
    tracks = await call(client, evidence, "youtube_list_subtitles", {"video": SOURCES.stt_video})
    force_stt = bool(tracks["manual"] or tracks["automatic"])
    first = await call(
        client,
        evidence,
        "youtube_prepare_transcript",
        {"video": SOURCES.stt_video, "force_refresh": True, "force_stt": force_stt},
    )
    assert first["available"] and first["source"] == "stt" and first["segment_count"] > 0
    second = await call(
        client, evidence, "youtube_prepare_transcript", {"video": SOURCES.stt_video, "force_stt": force_stt}
    )
    assert second["content_hash"] == first["content_hash"]
    assert "stt_base_url" not in (first.get("provenance") or {})


@pytest.mark.asyncio
async def test_real_stt_multi_chunk_timestamps(tmp_path, evidence):
    """Several audio chunks must produce monotonic timestamps spanning the whole video."""
    if os.getenv("YTB_RUN_STT") != "1":
        pytest.skip("NOT_RUN: enable with scripts/test-live.sh --with-stt")
    env = {**os.environ, "YTB_DATA_DIR": str(tmp_path), "STT_CHUNK_SECONDS": "60"}
    config = {
        "mcpServers": {
            "youtube": {"command": sys.executable, "args": ["-m", "youtube_read_mcp.cli"], "env": env}
        }
    }
    async with Client(config) as stt_client:
        prepared = await call(
            stt_client,
            evidence,
            "youtube_prepare_transcript",
            {"video": SOURCES.caption_video, "force_stt": True},
        )
        assert prepared["available"] and prepared["source"] == "stt"
        duration = float(prepared["duration_seconds"])
        assert duration > 120, "fixture must span several 60 s chunks"
        page = await call(
            stt_client,
            evidence,
            "youtube_transcript_read",
            {"video": SOURCES.caption_video, "max_chars": 30000},
        )
    segments = page["segments"]
    starts = [float(s["start"]) for s in segments]
    assert starts == sorted(starts)
    assert float(segments[-1]["end"]) > duration * 0.6, "later chunks were not offset into the video"
    assert float(segments[-1]["end"]) <= duration + 5
