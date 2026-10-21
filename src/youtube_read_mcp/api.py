"""Transport-independent application API; designed for deterministic unit and MCP tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import core, media, storage, transcript
from .config import Settings, settings


def read_transcript(video: str, cursor: int = 0, max_chars: int = 12000, format: str = "segments", *, cfg: Settings = settings) -> dict[str, Any]:
    if format not in {"segments", "text"}:
        raise ValueError("format must be segments or text")
    max_chars = max(500, min(int(max_chars),30000))
    record = transcript.load_record(video,cfg)
    segs = record.get("segments", [])
    if not 0 <= cursor <= len(segs):
        raise ValueError("Invalid transcript cursor")
    selected: list[dict[str, Any]] = []
    chars = 0
    end = cursor
    while end < len(segs):
        next_seg = segs[end]
        length = len(str(next_seg.get("text") or "")) + 1
        if selected and chars + length > max_chars:
            break
        if length > max_chars:
            raise ValueError("One transcript segment exceeds max_chars; raise max_chars or use youtube_transcript_export. No text has been silently truncated.")
        selected.append(next_seg)
        chars += length
        end += 1
        if chars >= max_chars:
            break
    result: dict[str, Any] = {"video_id":record["video_id"],"language":record.get("language"),"timing_quality":record.get("timing_quality","unknown"), "cursor":cursor,"next_cursor":end if end<len(segs) else None,"complete":end>=len(segs),"returned_segments":len(selected),"total_segments":len(segs)}
    result["segments" if format == "segments" else "text"] = selected if format == "segments" else " ".join(x["text"] for x in selected)
    return result


def export_transcript(video: str, format: str = "srt", *, cfg: Settings = settings) -> dict[str, Any]:
    if format not in {"srt","vtt","txt","json"}:
        raise ValueError("format must be srt, vtt, txt, or json")
    record = transcript.load_record(video,cfg)
    if record.get("timing_quality") == "stt_chunk_approximate" and format in {"srt","vtt"}:
        raise ValueError("STT only produced chunk-approximate timestamps; timestamped subtitle export is misleading")
    path = cfg.transcript_dir / record["video_id"] / f"export.{format}"
    def clock(t: float, sep: str) -> str:
        ms = round(max(0,t)*1000)
        h,rem=divmod(ms,3600000); m,rem=divmod(rem,60000); s,ms=divmod(rem,1000)
        return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"
    if format == "json":
        body = json.dumps(record,ensure_ascii=False,indent=2)
    elif format == "txt":
        body = "\n".join(x["text"] for x in record["segments"])
    else:
        rows = ["WEBVTT\n"] if format == "vtt" else []
        for i,x in enumerate(record["segments"],1):
            prefix = f"{i}\n" if format == "srt" else ""
            sep = "," if format == "srt" else "."
            rows.append(f"{prefix}{clock(float(x['start']),sep)} --> {clock(float(x['end']),sep)}\n{x['text']}\n")
        body = "\n".join(rows)
    temp = path.with_suffix(".tmp")
    temp.write_text(body,encoding="utf-8")
    temp.replace(path)
    return {"video_id":record["video_id"],"format":format,"path":str(path),"bytes":path.stat().st_size}


def prepare(video: str, preferred_languages: str = "", force_refresh: bool = False, *, cfg: Settings = settings) -> dict[str, Any]:
    languages = [s.strip() for s in preferred_languages.split(",") if s.strip()] or None
    result = transcript.prepare_transcript(video,preferred_languages=languages,force_refresh=force_refresh,cfg=cfg)
    if result.get("available"):
        storage.index_transcript(transcript.load_record(video,cfg),cfg)
    return result


def sync_source(source: str, limit: int = 100, offset: int = 0, *, cfg: Settings = settings) -> dict[str, Any]:
    if source.startswith("https://") and "/playlist?" in source:
        data = core.playlist_info(source,limit,offset)
    else:
        data = core.channel_videos(source,limit,offset,paged=True)
    ids = [x["id"] for x in data["entries"] if x.get("id") and core.VIDEO_ID_RE.fullmatch(str(x["id"]))]
    result = storage.sync_source(source,ids,cfg)
    return {**result,"next_offset":data.get("next_offset"),"has_more":data["has_more"],"scan_complete":not data["has_more"],"page_offset":offset}


def health(cfg: Settings = settings) -> dict[str, Any]:
    import shutil
    from yt_dlp.version import __version__ as ytdlp_version
    from . import __version__
    from importlib.util import find_spec
    runtime = next((x for x in ("deno","node","qjs") if shutil.which(x)),None)
    if runtime is None:
        try:
            import deno
            if Path(deno.find_deno_bin()).is_file():
                runtime = "deno (bundled Python wheel)"
        except (ImportError, FileNotFoundError, RuntimeError):
            pass
    status = {"version":__version__, "yt_dlp_version":ytdlp_version,"stdio_ready":True,"ffmpeg":bool(shutil.which("ffmpeg")),"js_runtime":runtime,"yt_dlp_ejs":find_spec("yt_dlp_ejs") is not None,"stt_configured":bool(cfg.stt_base_url),"cookies_configured":bool(cfg.cookie_file),"data_dir":str(cfg.data_dir),"data_dir_writable":False,"sqlite_fts5":False}
    try:
        cfg.data_dir.mkdir(parents=True,exist_ok=True)
        probe = cfg.data_dir / ".write-probe"
        probe.write_text("ok");probe.unlink()
        status["data_dir_writable"] = True
        with storage.connection(cfg) as db:
            db.execute("SELECT count(*) FROM transcript_fts").fetchone()
        status["sqlite_fts5"] = True
    except Exception as exc:
        status["storage_error"] = str(exc)
    status["recommendations"] = ([] if runtime else ["Install Deno >=2.3 for reliable YouTube JS challenges (see docs/installation.md)"])
    return status
