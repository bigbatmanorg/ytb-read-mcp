import json
from pathlib import Path

from youtube_read_mcp.config import Settings
from youtube_read_mcp.transcript import (
    build_chunks,
    load_record,
    manifest,
    parse_json3,
    parse_vtt,
    save_record,
    search_record,
    transcript_range,
)


def sample_segments():
    return [
        {"start": 0.0, "end": 2.0, "text": "Docker Agent starts here"},
        {"start": 2.0, "end": 4.0, "text": "Subagents isolate transcript work"},
        {"start": 4.0, "end": 6.0, "text": "Playlist writes are separate"},
    ]


def test_parse_json3_timestamped():
    raw = json.dumps(
        {
            "events": [
                {"tStartMs": 1000, "dDurationMs": 2500, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
                {"tStartMs": 4000, "dDurationMs": 1000, "segs": [{"utf8": "Again"}]},
            ]
        }
    )
    result = parse_json3(raw)
    assert result[0] == {"start": 1.0, "end": 3.5, "text": "Hello world"}
    assert result[1]["start"] == 4.0


def test_parse_vtt_timestamped_and_markup_removed():
    raw = """WEBVTT

00:00:01.000 --> 00:00:03.500
<c>Hello</c> world

00:00:04.000 --> 00:00:05.000
Again
"""
    result = parse_vtt(raw)
    assert result[0] == {"start": 1.0, "end": 3.5, "text": "Hello world"}
    assert result[1]["text"] == "Again"


def test_chunks_range_and_search():
    record = {
        "video_id": "dQw4w9WgXcQ",
        "title": "Example",
        "segments": sample_segments(),
    }
    chunks = build_chunks(record["segments"], max_seconds=3, max_chars=1000)
    assert len(chunks) >= 2
    ranged = transcript_range(record, 1.5, 4.1)
    assert "Subagents" in ranged["text"]
    found = search_record(record, "playlist separate", 3)
    assert found
    assert "Playlist" in found[0]["text"]


def test_atomic_cache_roundtrip(tmp_path: Path):
    cfg = Settings(data_dir=tmp_path)
    segments = sample_segments()
    record = {
        "schema_version": 1,
        "video_id": "dQw4w9WgXcQ",
        "title": "Example",
        "duration_seconds": 6,
        "language": "en",
        "source": "manual",
        "prepared_at": "2026-09-25T00:00:00+00:00",
        "provenance": {"backend": "test"},
        "segments": segments,
        "chunks": build_chunks(segments),
    }
    path = save_record(record, cfg)
    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()
    loaded = load_record("dQw4w9WgXcQ", cfg)
    assert loaded["source"] == "manual"
    assert manifest(loaded)["segment_count"] == 3


def test_caption_candidate_order_prefers_manual_then_auto_then_alternate():
    from youtube_read_mcp.transcript import track_candidates

    manual = {
        "fr": [{"ext": "vtt", "url": "manual-fr"}],
        "en": [{"ext": "vtt", "url": "manual-en-vtt"}, {"ext": "json3", "url": "manual-en-json3"}],
    }
    automatic = {
        "en-US": [{"ext": "json3", "url": "auto-en"}],
        "de": [{"ext": "vtt", "url": "auto-de"}],
    }
    values = track_candidates(manual, automatic, ["en"])
    assert [(source, lang, item["url"]) for source, lang, item in values] == [
        ("manual", "en", "manual-en-json3"),
        ("automatic", "en-US", "auto-en"),
        ("manual", "fr", "manual-fr"),
        ("automatic", "de", "auto-de"),
    ]


def test_live_probe_skips_music_notation_before_searching():
    from youtube_read_mcp.live_check import searchable_probe_term

    assert searchable_probe_term([{"text": "[♪♪♪]"}, {"text": "We're no strangers"}]) == "We're"
