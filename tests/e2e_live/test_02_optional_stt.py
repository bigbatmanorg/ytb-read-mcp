"""Real STT fallback.  Select explicitly with --with-stt so normal core runs stay bounded."""

from __future__ import annotations

import os

import pytest

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
