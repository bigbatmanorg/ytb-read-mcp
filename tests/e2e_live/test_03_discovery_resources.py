"""Live discovery, resources, and prompt protocol coverage."""

from __future__ import annotations

import pytest

from .conftest import call
from .sources import SOURCES


@pytest.mark.asyncio
async def test_channel_comments_chapters_resources_and_prompts(client, evidence):
    channel = await call(client, evidence, "youtube_channel_info", {"channel_url": SOURCES.channel})
    assert channel.get("title") and (channel.get("id") or channel.get("channel_id"))
    videos = await call(
        client,
        evidence,
        "youtube_channel_videos",
        {"channel_url": SOURCES.channel, "limit": 2, "tab": "videos"},
    )
    assert videos["entries"] and all(len(x.get("id", "")) == 11 for x in videos["entries"])
    playlists = await call(
        client,
        evidence,
        "youtube_channel_playlists",
        {"channel_url": SOURCES.playlist_channel, "limit": 2},
    )
    assert playlists["entries"] and all(x.get("id") and x.get("title") for x in playlists["entries"])
    playlist = await call(
        client, evidence, "youtube_playlist_info", {"playlist": playlists["entries"][0]["id"], "limit": 2}
    )
    assert playlist["id"] == playlists["entries"][0]["id"] and playlist["entries"]
    comments = await call(client, evidence, "youtube_comments", {"video": SOURCES.video, "limit": 3})
    assert comments and all(x.get("id") and x.get("text") for x in comments)
    chapters = await call(client, evidence, "youtube_video_chapters", {"video": SOURCES.video})
    assert chapters["video_id"] == SOURCES.video

    await call(client, evidence, "youtube_video_info", {"video": SOURCES.video})
    await call(client, evidence, "youtube_prepare_transcript", {"video": SOURCES.caption_video})
    resources = await client.list_resource_templates()
    assert {"youtube://video/{video_id}", "youtube://transcript/{video_id}"} <= {
        x.uri_template for x in resources
    }
    metadata = await client.read_resource(f"youtube://video/{SOURCES.video}")
    manifest = await client.read_resource(f"youtube://transcript/{SOURCES.caption_video}")
    assert metadata and manifest
    prompt = await client.get_prompt("research_video", {"video": SOURCES.video, "question": "What is said?"})
    assert prompt.messages
