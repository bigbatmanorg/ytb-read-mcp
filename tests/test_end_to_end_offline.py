"""Recorded-data workflows with every external boundary replaced by deterministic fakes."""
from pathlib import Path

import pytest

from youtube_read_mcp import api, core, media, storage, transcript
from youtube_read_mcp.config import Settings

VIDEO = "dQw4w9WgXcQ"


def test_prepare_index_search_read_workflow(monkeypatch, tmp_path):
    cfg = Settings(data_dir=tmp_path)
    calls = []
    info = {
        "title": "Test tutorial", "duration": 20.0,
        "subtitles": {"de": [{"ext": "vtt", "url": "https://www.youtube.com/de"}]},
        "automatic_captions": {"en": [{"ext": "json3", "url": "https://www.youtube.com/en"}]},
    }
    monkeypatch.setattr(transcript, "extract", lambda url: info)
    def fetch(variant):
        calls.append(variant["url"])
        if variant["url"].endswith("/de"):
            raise AssertionError("unpreferred manual track should not be tried before preferred auto")
        return ([{"start": 0.0, "end": 3.0, "text": "agent memory context"},
                 {"start": 4.0, "end": 6.0, "text": "tool contract verified"}], "json3")
    monkeypatch.setattr(transcript, "fetch_track", fetch)
    first = api.prepare(VIDEO,preferred_languages="en",cfg=cfg)
    assert first["available"] and first["source"]=="automatic" and first["language"]=="en"
    assert first["timing_quality"]=="caption_timed"
    assert calls==["https://www.youtube.com/en"]
    assert storage.search_transcripts("contract",cfg=cfg)["count"]==1
    assert api.read_transcript(VIDEO,cfg=cfg)["complete"]
    second = api.prepare(VIDEO,preferred_languages="en",cfg=cfg)
    assert first["content_hash"]==second["content_hash"]
    assert len(calls)==1, "Second preparation must use cache"


def test_stt_disabled_does_not_download_audio(monkeypatch,tmp_path):
    cfg=Settings(data_dir=tmp_path, stt_base_url="")
    monkeypatch.setattr(transcript,"extract",lambda url: {"title":"no captions","subtitles":{},"automatic_captions":{}})
    def no_audio(*a,**k):
        raise AssertionError("Audio should not be downloaded when STT is not configured")
    monkeypatch.setattr(transcript,"transcribe_with_stt",no_audio)
    result=api.prepare(VIDEO,cfg=cfg)
    assert result["available"] is False


def test_stt_fallback_unknown_language_and_approximate_timing(monkeypatch,tmp_path):
    cfg=Settings(data_dir=tmp_path, stt_base_url="http://stt.local/v1")
    monkeypatch.setattr(transcript,"extract",lambda url: {"title":"no captions","subtitles":{},"automatic_captions":{}})
    monkeypatch.setattr(transcript,"transcribe_with_stt",lambda v,cfg: [{"start":0.0,"end":12.0,"text":"spoken text","timing":"chunk_approximate"}])
    result=api.prepare(VIDEO,cfg=cfg)
    assert result["language"]=="unknown"
    assert result["timing_quality"]=="stt_chunk_approximate"
    with pytest.raises(ValueError,match="approximate"):
        api.export_transcript(VIDEO,"srt",cfg=cfg)


def test_channel_and_playlist_paging_without_network(monkeypatch):
    inputs=[]
    def fake(target,**kwargs):
        inputs.append((target,kwargs))
        return {"title":"Example","entries":[{"id":VIDEO,"title":"one"},{"id":"9bZkp7q19f0","title":"two"}]}
    monkeypatch.setattr(core,"extract",fake)
    ch=core.channel_videos("https://youtube.com/@example",limit=2,offset=10,tab="shorts",paged=True)
    assert ch["entries"][0]["id"]==VIDEO
    assert ch["next_offset"]==12
    assert inputs[0][1]["playliststart"]==11
    assert inputs[0][1]["playlistend"]==12
    pl=core.playlist_info("PLabcdefghijklmnop",limit=2,offset=20)
    assert pl["has_more"]
    assert inputs[1][1]["playliststart"]==21


def test_media_frame_remote_success(monkeypatch,tmp_path):
    cfg=Settings(data_dir=tmp_path)
    monkeypatch.setattr(media,"extract",lambda _: {"formats":[{"url":"https://rr.googlevideo.com/a","vcodec":"avc1","height":360,"protocol":"https"}]})
    def fake_ffmpeg(args,**kwargs):
        Path(args[-1]).write_bytes(b"fake-jpeg-data")
    monkeypatch.setattr(media,"_run_ffmpeg",fake_ffmpeg)
    def no_download(*args,**kwargs):
        raise AssertionError("Remote extraction succeeded; fallback download not allowed")
    monkeypatch.setattr(media,"download_media",no_download)
    result=media.extract_frames(VIDEO,[3.0,8.5],cfg=cfg)
    assert len(result["frames"])==2
    for frame in result["frames"]:
        assert Path(frame["path"]).is_file()
        assert Path(frame["path"]).is_relative_to(cfg.media_dir)
    cached=media.extract_frames(VIDEO,[3.0],cfg=cfg)
    assert cached["frames"][0]["cached"] is True
