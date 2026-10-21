"""Deterministic integration coverage; deliberately contains no network calls."""

from pathlib import Path

from youtube_read_mcp import api, storage, transcript
from youtube_read_mcp.config import Settings

VIDEO = "dQw4w9WgXcQ"


def test_cached_transcript_round_trip_and_fts(tmp_path: Path) -> None:
    cfg = Settings(data_dir=tmp_path)
    segments = [
        {"start": 0.0, "end": 2.0, "text": "local deterministic evidence"},
        {"start": 2.0, "end": 4.0, "text": "second transcript segment"},
    ]
    record = {
        "schema_version": 2,
        "video_id": VIDEO,
        "title": "fixture",
        "language": "en",
        "source": "manual",
        "timing_quality": "caption_timed",
        "content_hash": "fixture-v1",
        "segments": segments,
        "chunks": transcript.build_chunks(segments),
    }
    transcript.save_record(record, cfg)
    storage.index_transcript(record, cfg)
    assert storage.search_transcripts("deterministic", cfg=cfg)["count"] == 1
    assert api.read_transcript(VIDEO, max_chars=500, cfg=cfg)["complete"]
