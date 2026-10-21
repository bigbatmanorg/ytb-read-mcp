import json
from pathlib import Path

import pytest

from youtube_read_mcp import api, core, transcript
from youtube_read_mcp.config import Settings

VIDEO = "dQw4w9WgXcQ"


def seeded(tmp_path: Path):
    cfg = Settings(data_dir=tmp_path)
    segs = [
        {"start": float(i * 2), "end": float(i * 2 + 1), "text": f"test number {i} context evidence"}
        for i in range(12)
    ]
    record = {
        "video_id": VIDEO,
        "schema_version": 2,
        "title": "Example",
        "language": "en",
        "source": "manual",
        "timing_quality": "caption_timed",
        "content_hash": "hash",
        "segments": segs,
        "chunks": transcript.build_chunks(segs),
    }
    transcript.save_record(record, cfg)
    return cfg, record


def test_transcript_read_has_continuation_and_no_loss(tmp_path):
    cfg, rec = seeded(tmp_path)
    cursor = 0
    seen = []
    for _ in range(10):
        page = api.read_transcript(VIDEO, cursor, max_chars=500, cfg=cfg)
        seen.extend(page["segments"])
        if page["complete"]:
            assert page["next_cursor"] is None
            break
        assert page["next_cursor"] > cursor
        cursor = page["next_cursor"]
    assert seen == rec["segments"]


def test_oversized_segment_does_not_silently_truncate(tmp_path):
    cfg, rec = seeded(tmp_path)
    rec["segments"] = [{"start": 0.0, "end": 3.0, "text": "X" * 30100}]
    transcript.save_record(rec, cfg)
    with pytest.raises(ValueError, match="exceeds max_chars"):
        api.read_transcript(VIDEO, max_chars=30000, cfg=cfg)


def test_srt_vtt_txt_export(tmp_path):
    cfg, rec = seeded(tmp_path)
    for fmt in ("srt", "vtt", "txt", "json"):
        result = api.export_transcript(VIDEO, fmt, cfg=cfg)
        path = Path(result["path"])
        assert path.is_file()
        assert path.parent == cfg.transcript_dir / VIDEO
        assert result["bytes"] > 0
    assert "WEBVTT" in (cfg.transcript_dir / VIDEO / "export.vtt").read_text()
    rec["timing_quality"] = "stt_chunk_approximate"
    transcript.save_record(rec, cfg)
    with pytest.raises(ValueError, match="approximate"):
        api.export_transcript(VIDEO, "vtt", cfg=cfg)


def test_url_validation_and_channel_tabs():
    video = "dQw4w9WgXcQ"
    for url in (
        f"https://notyoutube.com/watch?v={video}",
        f"http://youtube.com/watch?v={video}",
        f"https://youtube.com:444/watch?v={video}",
        f"https://youtube.com.evil.test/watch?v={video}",
    ):
        with pytest.raises(ValueError):
            core.normalize_video_id(url)
    assert (
        core.channel_url("https://youtube.com/@example/videos", tab="shorts")
        == "https://www.youtube.com/@example/shorts"
    )
    with pytest.raises(ValueError):
        core.channel_url("https://youtube.com/watch?v=" + video)
    with pytest.raises(ValueError):
        core.playlist_url("https://notyoutube.com/playlist?list=PLabc123456789")


def test_chapters_subtitles_formats(monkeypatch):
    monkeypatch.setattr(
        core,
        "extract",
        lambda *args, **kwargs: {
            "chapters": [{"title": "A", "start_time": 0, "end_time": 4}],
            "subtitles": {"en": [{"ext": "vtt", "url": "secret-link"}]},
            "automatic_captions": {},
            "formats": [{"format_id": "18", "height": 360, "url": "private-media-url"}],
        },
    )
    assert core.chapters(VIDEO)["chapters"][0]["title"] == "A"
    assert core.subtitles(VIDEO)["manual"]["en"] == ["vtt"]
    assert "private-media-url" not in json.dumps(core.media_formats(VIDEO))


def test_caption_precedence_preferred_auto_before_unpreferred_manual():
    manual = {"de": [{"ext": "json3", "url": "de"}]}
    auto = {"en": [{"ext": "json3", "url": "en"}]}
    assert transcript.pick_track(manual, auto, ["en"])[1] == "en"


def test_timing_quality_is_preserved():
    segs = transcript._dedupe_segments(
        [{"start": 0, "end": 10, "text": "test", "timing": "chunk_approximate"}]
    )
    assert segs[0]["timing"] == "chunk_approximate"
