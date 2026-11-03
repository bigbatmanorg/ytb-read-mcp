from pathlib import Path

import pytest

from youtube_read_mcp import storage
from youtube_read_mcp.config import Settings

VIDS = ["dQw4w9WgXcQ", "9bZkp7q19f0", "J---aiyznGQ"]


def test_fts_index_and_refresh(tmp_path: Path):
    cfg = Settings(data_dir=tmp_path)
    record = {
        "video_id": VIDS[0],
        "language": "en",
        "source": "manual",
        "content_hash": "v1",
        "segments": [
            {"start": 1, "end": 3, "text": "agent memory evidence"},
            {"start": 4, "end": 6, "text": "coding agents"},
        ],
    }
    storage.index_transcript(record, cfg)
    result = storage.search_transcripts("memory", cfg=cfg)
    assert result["count"] == 1
    assert result["results"][0]["video_id"] == VIDS[0]
    assert storage.search_transcripts('" OR gibberish', cfg=cfg)["count"] == 0
    record.update(content_hash="v2", segments=[{"start": 8, "end": 9, "text": "different subject"}])
    storage.index_transcript(record, cfg)
    assert storage.search_transcripts("memory", cfg=cfg)["count"] == 0
    assert storage.search_transcripts("different", cfg=cfg)["count"] == 1


def test_jobs_partial_and_cancel(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    job = storage.create_job("prepare_transcript", VIDS[:2], cfg=cfg)
    assert job["state"] == "queued"

    def fake(vid):
        return {"available": vid == VIDS[0]}

    assert storage.run_job_once(cfg, prepare=fake)
    assert storage.job_status(job["id"], cfg)["completed"] == 1
    assert storage.run_job_once(cfg, prepare=fake)
    final = storage.job_status(job["id"], cfg)
    assert final["state"] == "partial" and final["failed"] == 1
    assert not storage.run_job_once(cfg, prepare=fake)
    next_job = storage.create_job("prepare_transcript", VIDS, cfg)
    result = storage.cancel_job(next_job["id"], cfg)
    assert result["state"] == "cancelled"
    assert all(item["state"] == "cancelled" for item in result["items"])


def test_idempotent_sync(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    assert storage.sync_source("channel1", VIDS[:2], cfg)["new_video_ids"] == VIDS[:2]
    assert storage.sync_source("channel1", VIDS, cfg)["new_video_ids"] == VIDS[2:]
    assert storage.sync_source("channel1", VIDS[:2], cfg)["new_video_ids"] == []


def test_invalid_job_video_rejected(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    with pytest.raises(ValueError):
        storage.create_job("prepare_transcript", ["definitely not a YouTube video ID"], cfg)


def _item(cfg, job_id, video):
    with storage.connection(cfg) as db:
        return db.execute(
            "SELECT state,attempts FROM job_items WHERE job_id=? AND item_key=?", (job_id, video)
        ).fetchone()


def test_default_worker_prepare_indexes_transcripts(monkeypatch, tmp_path):
    from youtube_read_mcp import transcript

    cfg = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        transcript,
        "extract",
        lambda url: {
            "title": "t",
            "subtitles": {"en": [{"ext": "json3", "url": "https://www.youtube.com/en"}]},
        },
    )
    monkeypatch.setattr(
        transcript,
        "fetch_track",
        lambda variant: ([{"start": 0.0, "end": 2.0, "text": "batch indexed"}], "json3"),
    )
    job = storage.create_job("prepare_transcript", [VIDS[0]], cfg)
    assert storage.run_job_once(cfg)
    assert storage.job_status(job["id"], cfg)["state"] == "completed"
    assert storage.search_transcripts("indexed", cfg=cfg)["count"] == 1


def test_cancel_after_progress_reaches_terminal_state(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    job = storage.create_job("prepare_transcript", VIDS, cfg)
    assert storage.run_job_once(cfg, prepare=lambda vid: {"available": True})
    assert storage.cancel_job(job["id"], cfg)["state"] == "cancelled"


def test_abandoned_running_item_of_cancelled_job_is_released(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    job = storage.create_job("prepare_transcript", VIDS[:2], cfg)
    with storage.connection(cfg) as db:  # simulate a worker that died mid-item
        db.execute("UPDATE job_items SET state='running',attempts=1 WHERE item_key=?", (VIDS[0],))
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))
    assert storage.cancel_job(job["id"], cfg)["state"] == "running"
    assert not storage.run_job_once(cfg, prepare=lambda vid: {"available": True})
    status = storage.job_status(job["id"], cfg)
    assert status["state"] == "cancelled"
    assert {item["state"] for item in status["items"]} == {"cancelled"}


def test_item_that_repeatedly_kills_worker_is_failed(tmp_path):
    cfg = Settings(data_dir=tmp_path)
    job = storage.create_job("prepare_transcript", VIDS[:2], cfg)
    with storage.connection(cfg) as db:
        db.execute(
            "UPDATE job_items SET state='running',attempts=? WHERE item_key=?",
            (storage.MAX_ITEM_ATTEMPTS, VIDS[0]),
        )
    calls = []
    assert storage.run_job_once(cfg, prepare=lambda vid: calls.append(vid) or {"available": True})
    assert storage.run_job_once(cfg, prepare=lambda vid: calls.append(vid) or {"available": True})
    assert calls == [VIDS[1]]
    assert _item(cfg, job["id"], VIDS[0])["state"] == "failed"
    assert storage.job_status(job["id"], cfg)["state"] == "partial"


def test_attempts_are_counted_and_old_schema_migrates(tmp_path):
    import sqlite3

    cfg = Settings(data_dir=tmp_path)
    old = sqlite3.connect(cfg.db_path)
    old.execute(
        "CREATE TABLE job_items (job_id TEXT NOT NULL, item_key TEXT NOT NULL, state TEXT NOT NULL, result TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(job_id,item_key))"
    )
    old.close()
    job = storage.create_job("prepare_transcript", [VIDS[0]], cfg)
    assert storage.run_job_once(cfg, prepare=lambda vid: {"available": True})
    assert _item(cfg, job["id"], VIDS[0])["attempts"] == 1
