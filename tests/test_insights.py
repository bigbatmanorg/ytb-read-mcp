import hashlib
import json

import httpx
import pytest

from youtube_read_mcp import api, core, insights, storage, transcript
from youtube_read_mcp.config import Settings

VIDEO = "dQw4w9WgXcQ"


def seeded(tmp_path, **extra):
    cfg = Settings(data_dir=tmp_path)
    segments = [
        {"start": float(i * 10), "end": float(i * 10 + 9), "text": text}
        for i, text in enumerate(
            [
                "welcome to the channel",
                "this video is sponsored by a mattress company",
                "kubernetes operators reconcile desired state",
                "operators watch custom resources continuously",
                "thanks for watching please subscribe",
            ]
        )
    ]
    record = {
        "schema_version": 2,
        "video_id": VIDEO,
        "title": "Operators",
        "duration_seconds": 50,
        "language": "en",
        "source": "manual",
        "timing_quality": "caption_timed",
        "content_hash": "h",
        "segments": segments,
        "chunks": transcript.build_chunks(segments, max_seconds=60),
        **extra,
    }
    transcript.save_record(record, cfg)
    return cfg, record


def test_timestamp_links_on_search_range_and_fts(tmp_path):
    cfg, record = seeded(tmp_path)
    assert core.timestamp_url(f"https://youtu.be/{VIDEO}", 61.9) == f"https://youtu.be/{VIDEO}?t=61"
    hit = transcript.search_record(record, "operators", 1)[0]
    assert hit["url"] == f"https://youtu.be/{VIDEO}?t={int(hit['start_seconds'])}"
    assert transcript.transcript_range(record, 20, 30)["url"].endswith("?t=20")
    storage.index_transcript(record, cfg)
    assert storage.search_transcripts("reconcile", cfg=cfg)["results"][0]["url"].endswith("?t=20")


def test_manifest_reports_reading_stats(tmp_path):
    _, record = seeded(tmp_path)
    stats = transcript.manifest(record)["stats"]
    assert stats["word_count"] == 27
    assert stats["spoken_seconds"] == 49.0
    assert stats["words_per_minute"] == pytest.approx(33.1, abs=0.1)
    assert stats["reading_minutes"] == 0.1
    assert stats["caption_coverage"] == 0.9


def test_prepare_persists_chapters_and_heatmap(monkeypatch, tmp_path):
    cfg = Settings(data_dir=tmp_path)
    info = {
        "title": "t",
        "duration": 20,
        "subtitles": {"en": [{"ext": "json3", "url": "https://www.youtube.com/en"}]},
        "chapters": [{"title": "Intro", "start_time": 0.0, "end_time": 20.0}],
        "heatmap": [{"start_time": 0.0, "end_time": 10.0, "value": 1.0}],
    }
    monkeypatch.setattr(transcript, "extract", lambda url: info)
    monkeypatch.setattr(
        transcript, "fetch_track", lambda v: ([{"start": 0.0, "end": 2.0, "text": "hi"}], "json3")
    )
    assert api.prepare(VIDEO, cfg=cfg)["has_chapters"] is True
    record = transcript.load_record(VIDEO, cfg)
    assert record["chapters"][0]["url"].endswith("?t=0")
    assert record["heatmap"] == info["heatmap"]


def test_heatmap_peaks_are_distinct_strongest_moments_with_text(tmp_path):
    values = [0.1, 0.2, 1.0, 0.9, 0.3, 0.2, 0.7, 0.2, 0.1, 0.4]
    heatmap = [{"start_time": i * 5.0, "end_time": i * 5.0 + 5, "value": v} for i, v in enumerate(values)]
    cfg, _ = seeded(tmp_path, heatmap=heatmap)
    result = insights.heatmap_peaks(VIDEO, top=3, cfg=cfg)
    assert [p["start_seconds"] for p in result["peaks"]] == [10.0, 30.0, 45.0]
    assert result["peaks"][0]["url"].endswith("?t=10")
    assert "sponsored" in result["peaks"][0]["transcript"]


def test_heatmap_unavailable_for_low_view_videos(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "extract", lambda url: {"duration": 30})
    result = insights.heatmap_peaks(VIDEO, cfg=Settings(data_dir=tmp_path))
    assert result["available"] is False and result["peaks"] == []


def _sponsorblock(monkeypatch, segments, calls):
    def handler(request):
        calls.append(request)
        if not segments:
            return httpx.Response(404)
        body = [
            {"videoID": "other00000x", "segments": [{"category": "sponsor", "segment": [0, 50]}]},
            {"videoID": VIDEO, "segments": segments},
        ]
        return httpx.Response(200, json=body)

    real = httpx.Client
    monkeypatch.setattr(
        insights.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )


def test_sponsorblock_uses_hash_prefix_filters_and_caches(monkeypatch, tmp_path):
    cfg = Settings(data_dir=tmp_path)
    calls = []
    _sponsorblock(
        monkeypatch,
        [{"category": "sponsor", "segment": [10, 19]}, {"category": "outro", "segment": [40, 50]}],
        calls,
    )
    result = insights.sponsor_segments(VIDEO, ["sponsor"], cfg=cfg)
    assert [s["category"] for s in result["segments"]] == ["sponsor"]
    assert result["segments"][0]["url"].endswith("?t=10")
    path = calls[0].url.path
    assert path.endswith(hashlib.sha256(VIDEO.encode()).hexdigest()[:4]) and VIDEO not in str(calls[0].url)
    assert len(insights.sponsor_segments(VIDEO, cfg=cfg)["segments"]) == 2
    assert len(calls) == 1
    with pytest.raises(ValueError, match="Unknown SponsorBlock"):
        insights.sponsor_segments(VIDEO, ["ads"], cfg=cfg)


def test_sponsorblock_404_means_no_segments(monkeypatch, tmp_path):
    _sponsorblock(monkeypatch, [], [])
    assert insights.sponsor_segments(VIDEO, cfg=Settings(data_dir=tmp_path))["segments"] == []


def test_read_range_and_outline_exclude_sponsor_segments(monkeypatch, tmp_path):
    cfg, _ = seeded(tmp_path)
    _sponsorblock(monkeypatch, [{"category": "sponsor", "segment": [10, 19]}], [])
    page = api.read_transcript(VIDEO, exclude_categories=["sponsor"], cfg=cfg)
    assert page["excluded_segments"] == 1 and page["complete"]
    assert all("mattress" not in seg["text"] for seg in page["segments"])
    ranged = api.transcript_range(VIDEO, 0, 30, exclude_categories=["sponsor"], cfg=cfg)
    assert "mattress" not in ranged["text"] and "kubernetes" in ranged["text"]
    outline = insights.outline(VIDEO, include_text=True, exclude_categories=["sponsor"], cfg=cfg)
    assert outline["excluded_segments"] == 1 and "mattress" not in json.dumps(outline["sections"])


def test_outline_by_chapter_with_counts_terms_and_links(tmp_path):
    chapters = [
        {"title": "Intro", "start_time": 0.0, "end_time": 20.0, "url": ""},
        {"title": "Operators", "start_time": 20.0, "end_time": 50.0, "url": ""},
    ]
    cfg, _ = seeded(tmp_path, chapters=chapters)
    result = insights.outline(VIDEO, cfg=cfg)
    assert result["source"] == "chapters"
    intro, ops = result["sections"]
    assert (intro["word_count"], ops["word_count"]) == (12, 15)
    assert ops["url"].endswith("?t=20") and ops["preview"].startswith("kubernetes")
    assert {"term": "operators", "count": 2} in result["top_terms"]
    assert result["stats"]["word_count"] == 27


def test_outline_without_chapters_uses_time_windows(tmp_path):
    cfg, _ = seeded(tmp_path, chapters=[])
    result = insights.outline(VIDEO, cfg=cfg)
    assert result["source"] == "time_windows" and result["sections"][0]["title"] == "Part 1"


def test_outline_backfills_chapters_for_older_records(monkeypatch, tmp_path):
    cfg, _ = seeded(tmp_path)
    monkeypatch.setattr(
        core, "extract", lambda url: {"chapters": [{"title": "All", "start_time": 0, "end_time": 50}]}
    )
    assert insights.outline(VIDEO, cfg=cfg)["sections"][0]["title"] == "All"
    assert transcript.load_record(VIDEO, cfg)["chapters"][0]["title"] == "All"


def test_top_terms_ignore_caption_notation_and_filler():
    terms = insights.top_terms(["[Music] don’t even worry, the Valve steam deck [music] steam"])
    assert [t["term"] for t in terms] == ["steam", "worry", "valve", "deck"]
