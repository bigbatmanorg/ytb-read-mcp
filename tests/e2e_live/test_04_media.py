"""Actual YouTube media/FFmpeg tests; enabled explicitly to limit routine load."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from .conftest import call
from .sources import SOURCES


def probe(path: str) -> dict:
    return json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]
        )
    )


@pytest.mark.asyncio
async def test_real_download_frames_and_clip(client, evidence):
    if os.getenv("YTB_RUN_MEDIA") != "1":
        pytest.skip("NOT_RUN: enable with scripts/test-live.sh --with-media")
    formats = await call(client, evidence, "youtube_media_formats", {"video": SOURCES.media_video})
    assert formats["formats"] and any(x.get("format_id") for x in formats["formats"])
    audio = await call(client, evidence, "youtube_download", {"video": SOURCES.media_video, "mode": "audio"})
    assert Path(audio["path"]).is_file() and audio["bytes"] > 0
    assert any(x.get("codec_type") == "audio" for x in probe(audio["path"])["streams"])
    video = await call(
        client,
        evidence,
        "youtube_download",
        {"video": SOURCES.media_video, "mode": "video", "quality": "480p"},
    )
    streams = probe(video["path"])["streams"]
    assert any(x.get("codec_type") == "video" for x in streams)
    frames = await call(
        client,
        evidence,
        "youtube_extract_frames",
        {"video": SOURCES.media_video, "timestamps": [5.0], "width": 320},
    )
    assert frames["count"] == 1 and probe(frames["frames"][0]["path"])
    clip = await call(
        client,
        evidence,
        "youtube_extract_clip",
        {"video": SOURCES.media_video, "start_seconds": 5, "duration_seconds": 4},
    )
    assert Path(clip["path"]).is_file() and any(
        x.get("codec_type") == "video" for x in probe(clip["path"])["streams"]
    )
