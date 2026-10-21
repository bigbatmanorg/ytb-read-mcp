from pathlib import Path

import pytest

from youtube_read_mcp import storage
from youtube_read_mcp.config import Settings

VIDS=["dQw4w9WgXcQ","9bZkp7q19f0","J---aiyznGQ"]


def test_fts_index_and_refresh(tmp_path: Path):
    cfg=Settings(data_dir=tmp_path)
    record={"video_id":VIDS[0],"language":"en","source":"manual","content_hash":"v1","segments":[{"start":1,"end":3,"text":"agent memory evidence"},{"start":4,"end":6,"text":"coding agents"}]}
    storage.index_transcript(record,cfg)
    result=storage.search_transcripts("memory",cfg=cfg)
    assert result["count"]==1
    assert result["results"][0]["video_id"]==VIDS[0]
    assert storage.search_transcripts('" OR gibberish',cfg=cfg)["count"] == 0
    record.update(content_hash="v2",segments=[{"start":8,"end":9,"text":"different subject"}])
    storage.index_transcript(record,cfg)
    assert storage.search_transcripts("memory",cfg=cfg)["count"] == 0
    assert storage.search_transcripts("different",cfg=cfg)["count"]==1


def test_jobs_partial_and_cancel(tmp_path):
    cfg=Settings(data_dir=tmp_path)
    job=storage.create_job("prepare_transcript",VIDS[:2],cfg=cfg)
    assert job["state"]=="queued"
    def fake(vid):
        return {"available":vid==VIDS[0]}
    assert storage.run_job_once(cfg,prepare=fake)
    assert storage.job_status(job["id"],cfg)["completed"]==1
    assert storage.run_job_once(cfg,prepare=fake)
    final=storage.job_status(job["id"],cfg)
    assert final["state"]=="partial" and final["failed"]==1
    assert not storage.run_job_once(cfg,prepare=fake)
    next_job=storage.create_job("prepare_transcript",VIDS,cfg)
    result=storage.cancel_job(next_job["id"],cfg)
    assert result["state"]=="cancelled"
    assert all(item["state"]=="cancelled" for item in result["items"])


def test_idempotent_sync(tmp_path):
    cfg=Settings(data_dir=tmp_path)
    assert storage.sync_source("channel1",VIDS[:2],cfg)["new_video_ids"]==VIDS[:2]
    assert storage.sync_source("channel1",VIDS,cfg)["new_video_ids"]==VIDS[2:]
    assert storage.sync_source("channel1",VIDS[:2],cfg)["new_video_ids"]==[]


def test_invalid_job_video_rejected(tmp_path):
    cfg=Settings(data_dir=tmp_path)
    with pytest.raises(ValueError):
        storage.create_job("prepare_transcript",["definitely not a YouTube video ID"],cfg)
