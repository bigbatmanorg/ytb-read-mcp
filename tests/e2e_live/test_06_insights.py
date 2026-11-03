"""Real heatmap, SponsorBlock, outline and timestamp-link behaviour through stdio MCP."""

from __future__ import annotations

import pytest

from .conftest import call
from .sources import SOURCES


@pytest.mark.asyncio
async def test_real_timeline_insights(client, evidence):
    video = SOURCES.caption_video
    prepared = await call(client, evidence, "youtube_prepare_transcript", {"video": video})
    assert prepared["available"] and prepared["stats"]["word_count"] > 0
    assert prepared["stats"]["reading_minutes"] >= 0

    outline = await call(client, evidence, "youtube_transcript_outline", {"video": video})
    assert outline["source"] in {"chapters", "time_windows"} and outline["sections"]
    assert all(s["url"].startswith(f"https://youtu.be/{video}?t=") for s in outline["sections"])
    assert sum(s["word_count"] for s in outline["sections"]) <= outline["stats"]["word_count"]

    heatmap = await call(client, evidence, "youtube_video_heatmap", {"video": video, "top": 3})
    if heatmap["available"]:  # published only for videos with enough views
        assert heatmap["peaks"] and heatmap["peaks"][0]["intensity"] > 0
        assert heatmap["peaks"][0]["transcript"] is not None

    # SponsorBlock is a third-party service; an outage must surface as a retryable error only.
    result = await client.call_tool("youtube_sponsor_segments", {"video": video}, raise_on_error=False)
    evidence["calls"].append(
        {"tool": "youtube_sponsor_segments", "arguments": {"video": video}, "is_error": result.is_error}
    )
    if result.is_error:
        assert "SPONSORBLOCK_UNAVAILABLE" in str(result.content)
    else:
        assert result.data["source"] == "sponsorblock" and isinstance(result.data["segments"], list)
    page = await call(
        client,
        evidence,
        "youtube_transcript_read",
        {"video": video, "exclude_categories": ["sponsor", "intro"]},
    )
    assert "excluded_segments" in page

    hits = await call(client, evidence, "youtube_transcript_search", {"video": video, "query": "never"})
    assert all(hit["url"].startswith("https://youtu.be/") for hit in hits)
