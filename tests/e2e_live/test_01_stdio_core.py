"""Core live verification through a real FastMCP stdio client."""

from __future__ import annotations

import hashlib
import re

import pytest

from .conftest import call
from .sources import SOURCES


@pytest.mark.asyncio
async def test_protocol_catalog_and_health(client, evidence):
    tools = await client.list_tools()
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names)) == 26
    assert all(tool.description and tool.input_schema.get("type") == "object" for tool in tools)
    prompts = await client.list_prompts()
    assert {"research_video", "analyze_channel", "analyze_video_visuals"} <= {p.name for p in prompts}
    health = await call(client, evidence, "youtube_health", {})
    assert health["stdio_ready"] and health["sqlite_fts5"] and health["data_dir_writable"]


@pytest.mark.asyncio
async def test_real_metadata_search_captions_and_transcript_lifecycle(client, evidence):
    info = await call(client, evidence, "youtube_video_info", {"video": SOURCES.video, "full": True})
    assert info["id"] == SOURCES.video and info["title"].strip() and info["duration"] > 0
    assert info["webpage_url"].startswith("https://")
    found = await call(
        client, evidence, "youtube_search", {"query": "Python programming tutorial", "limit": 3}
    )
    assert 1 <= len(found) <= 3 and all(len(x.get("id", "")) == 11 and x.get("title") for x in found)
    tracks = await call(client, evidence, "youtube_list_subtitles", {"video": SOURCES.caption_video})
    assert tracks["video_id"] == SOURCES.caption_video and (tracks["manual"] or tracks["automatic"])
    prepared = await call(client, evidence, "youtube_prepare_transcript", {"video": SOURCES.caption_video})
    assert prepared["available"] and prepared["segment_count"] > 0
    assert prepared["source"] in {"manual", "automatic"} and prepared["timing_quality"] == "caption_timed"
    manifest = await call(client, evidence, "youtube_transcript_manifest", {"video": SOURCES.caption_video})
    assert (
        manifest["content_hash"] == prepared["content_hash"]
        and manifest["segment_count"] == prepared["segment_count"]
    )

    cursor, reconstructed = 0, []
    while True:
        page = await call(
            client,
            evidence,
            "youtube_transcript_read",
            {"video": SOURCES.caption_video, "cursor": cursor, "max_chars": 500},
        )
        reconstructed.extend(page["segments"])
        if page["complete"]:
            break
        assert page["next_cursor"] > cursor
        cursor = page["next_cursor"]
    normalized = "\n".join(x["text"] for x in reconstructed)
    assert len(reconstructed) == manifest["segment_count"]
    assert hashlib.sha256(normalized.encode()).hexdigest() == manifest["content_hash"]
    # Caption tracks often start with music notation. Pick an ASCII lexical word
    # from the complete real transcript so the query is meaningful to both
    # per-record search and SQLite FTS tokenization.
    term = next(word for segment in reconstructed for word in re.findall(r"[A-Za-z]{3,}", segment["text"]))
    matches = await call(
        client, evidence, "youtube_transcript_search", {"video": SOURCES.caption_video, "query": term}
    )
    assert matches and term.lower() in matches[0]["text"].lower()
    fts = await call(
        client, evidence, "youtube_transcripts_search", {"query": term, "video": SOURCES.caption_video}
    )
    assert fts["count"] >= 1
    ranged = await call(
        client,
        evidence,
        "youtube_transcript_range",
        {"video": SOURCES.caption_video, "start_seconds": 0, "end_seconds": 30},
    )
    assert ranged["segments"] and all(x["end"] >= 0 and x["start"] <= 30 for x in ranged["segments"])
    exported = await call(
        client, evidence, "youtube_transcript_export", {"video": SOURCES.caption_video, "format": "json"}
    )
    assert exported["bytes"] > 0


@pytest.mark.asyncio
async def test_live_errors_do_not_kill_stdio_session(client, evidence):
    result = await client.call_tool("youtube_video_info", {"video": "not-a-video"}, raise_on_error=False)
    assert result.is_error
    health = await call(client, evidence, "youtube_health", {})
    assert health["stdio_ready"]
