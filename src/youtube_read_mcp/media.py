"""Bounded media extraction; all artifacts live within the configured data directory."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from .config import Settings, settings
from .core import _ydl_opts, extract, normalize_video_id, video_url


def _require_ffmpeg() -> str:
    command = shutil.which("ffmpeg")
    if not command:
        raise RuntimeError("DEPENDENCY_MISSING: ffmpeg is needed for this operation")
    return command


def _artifact(video: str, subdir: str, cfg: Settings) -> Path:
    video_id = normalize_video_id(video)
    target = cfg.media_dir / video_id / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _disk_used_mb(root: Path) -> float:
    return sum(x.stat().st_size for x in root.rglob("*") if x.is_file()) / (1024 * 1024)


def download_media(video: str, mode: str = "audio", quality: str = "best", *, cfg: Settings = settings) -> dict[str, Any]:
    if mode not in {"audio", "video"}:
        raise ValueError("mode must be audio or video")
    if quality not in {"best", "1080p", "720p", "480p"}:
        raise ValueError("quality must be best, 1080p, 720p, or 480p")
    if _disk_used_mb(cfg.media_dir) > cfg.max_disk_mb:
        raise RuntimeError("RESOURCE_LIMIT_EXCEEDED: media disk budget exceeded")
    target = _artifact(video, "downloads", cfg)
    vid = normalize_video_id(video)
    pattern = ("bestaudio/best" if mode == "audio" else ("bv*+ba/b" if quality == "best" else f"bv*[height<={int(quality[:-1])}]+ba/b[height<={int(quality[:-1])}]"))
    template = str(target / f"{mode}-{quality}.%(ext)s")
    options = _ydl_opts(cfg, skip_download=False, noplaylist=True, format=pattern, outtmpl=template, max_filesize=max(1,cfg.max_download_mb) * 1024 * 1024, continuedl=True, retries=2, fragment_retries=2, restrictfilenames=True)
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url(vid), download=True)
        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp returned no media info")
    files = [p for p in target.glob(f"{mode}-{quality}.*") if p.is_file() and p.suffix not in {".part", ".ytdl", ".temp"}]
    if not files:
        raise RuntimeError("DOWNLOAD_FAILED: no resulting media file")
    output = max(files, key=lambda x:x.stat().st_mtime)
    if output.stat().st_size > cfg.max_download_mb*1024*1024:
        output.unlink(missing_ok=True)
        raise RuntimeError("RESOURCE_LIMIT_EXCEEDED: download exceeded configured limit")
    return {"video_id":vid,"mode":mode,"quality":quality,"path":str(output),"bytes":output.stat().st_size,"title":info.get("title")}


def _best_stream_url(info: dict[str, Any]) -> str | None:
    items = [x for x in (info.get("formats") or []) if x.get("url") and x.get("vcodec") not in ("none", None) and x.get("protocol") in ("https", "http")]
    items.sort(key=lambda x: (int(x.get("height") or 0) > 720, abs(int(x.get("height") or 720)-480), -(int(x.get("tbr") or 0))))
    return str(items[0]["url"]) if items else None


def _run_ffmpeg(args: list[str], timeout: int = 120) -> None:
    try:
        subprocess.run([_require_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args], check=True, timeout=timeout, capture_output=True)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg timed out while processing media") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg failed: {exc.stderr.decode('utf-8','replace')[-700:]}") from exc


def extract_frames(video: str, timestamps: list[float], width: int = 640, *, cfg: Settings = settings) -> dict[str, Any]:
    if not 1 <= len(timestamps) <= 12 or any(not (0 <= t <= 172800) for t in timestamps):
        raise ValueError("Supply 1–12 timestamps between 0 and 172800 seconds")
    if not 160 <= width <= 1920:
        raise ValueError("width must be 160–1920 pixels")
    info = extract(video_url(video))
    source_url = _best_stream_url(info)
    target = _artifact(video,"frames",cfg)
    output = []
    for t in timestamps:
        path = target / f"frame-{int(t*1000):012d}-{width}.jpg"
        if path.is_file():
            output.append({"timestamp":t,"path":str(path),"cached":True})
            continue
        with tempfile.TemporaryDirectory(dir=cfg.temp_dir) as temporary:
            staging = Path(temporary) / "frame.jpg"
            failure = None
            if source_url:
                try:
                    _run_ffmpeg(["-ss",str(t),"-i",source_url,"-frames:v","1","-vf",f"scale={width}:-2", "-q:v","3",str(staging)],timeout=70)
                except RuntimeError as exc:
                    failure = str(exc)
            if not staging.is_file() or not staging.stat().st_size:
                # fallback to local media: more reliable for websites requiring specific headers
                media = download_media(video,"video","480p",cfg=cfg)
                _run_ffmpeg(["-ss",str(t),"-i",media["path"],"-frames:v","1","-vf",f"scale={width}:-2", "-q:v","3",str(staging)],timeout=180)
            if not staging.exists() or not staging.stat().st_size:
                raise RuntimeError(f"Frame extraction produced no output; remote error: {failure}")
            os.replace(staging,path)
        output.append({"timestamp":t,"path":str(path),"cached":False})
    return {"video_id":normalize_video_id(video),"frames":output,"count":len(output)}


def extract_clip(video: str, start_seconds: float, duration_seconds: float = 20, *, cfg: Settings = settings) -> dict[str, Any]:
    if not 0 <= start_seconds <= 172800 or not 0.2 <= duration_seconds <= 120:
        raise ValueError("clip start must be 0–172800 seconds and duration 0.2–120 seconds")
    media = download_media(video,"video","480p",cfg=cfg)
    target = _artifact(video,"clips",cfg)
    path = target / f"clip-{int(start_seconds*1000)}-{int(duration_seconds*1000)}.mp4"
    if not path.exists():
        with tempfile.TemporaryDirectory(dir=cfg.temp_dir) as temporary:
            temp = Path(temporary) / "clip.mp4"
            _run_ffmpeg(["-ss",str(start_seconds),"-i",media["path"],"-t",str(duration_seconds),"-map","0:v:0", "-map", "0:a?", "-c:v","libx264","-preset","ultrafast","-crf","26","-c:a","aac","-movflags","+faststart",str(temp)],timeout=300)
            os.replace(temp,path)
    return {"video_id":normalize_video_id(video),"start_seconds":start_seconds,"duration_seconds":duration_seconds,"path":str(path),"bytes":path.stat().st_size}
