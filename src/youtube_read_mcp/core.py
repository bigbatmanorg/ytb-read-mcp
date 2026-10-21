"""Hardened, centrally configured yt-dlp adapter and compact YouTube discovery API."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .config import Settings, settings

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,120}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}
_CHANNEL_PATHS = {"channel", "user", "c", "@"}


def _url(value: str) -> Any:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in _HOSTS or parsed.username or parsed.password:
        raise ValueError("Only HTTPS URLs on the supported YouTube hosts are allowed")
    if parsed.port not in (None, 443):
        raise ValueError("Unexpected port in YouTube URL")
    return parsed


def normalize_video_id(value: str) -> str:
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value
    parsed = _url(value)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
        if VIDEO_ID_RE.fullmatch(candidate):
            return candidate
    if parsed.path == "/watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
        if VIDEO_ID_RE.fullmatch(candidate):
            return candidate
    parts = [x for x in parsed.path.split("/") if x]
    if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"} and VIDEO_ID_RE.fullmatch(parts[1]):
        return parts[1]
    raise ValueError("Could not extract a YouTube video ID")


def video_url(value: str) -> str:
    return f"https://www.youtube.com/watch?v={normalize_video_id(value)}"


def playlist_url(value: str) -> str:
    value = value.strip()
    if value.startswith("https://"):
        parsed = _url(value)
        if parsed.path != "/playlist":
            raise ValueError("Expected a YouTube playlist URL")
        value = (parse_qs(parsed.query).get("list") or [""])[0]
    if not PLAYLIST_ID_RE.fullmatch(value):
        raise ValueError("Invalid YouTube playlist ID")
    return f"https://www.youtube.com/playlist?list={value}"


def channel_url(value: str, tab: str = "videos") -> str:
    if tab not in {"videos", "shorts", "streams", "playlists"}:
        raise ValueError("tab must be videos, shorts, streams, or playlists")
    parsed = _url(value.strip())
    parts = [x for x in parsed.path.split("/") if x]
    if not parts or len(parts) > 3 or not (parts[0].startswith("@") or parts[0] in {"channel", "user", "c"}):
        raise ValueError("Expected YouTube channel, handle, or custom-channel URL")
    if parts[0] in {"channel", "user", "c"} and len(parts) < 2:
        raise ValueError("Channel path lacks an identifier")
    base = parts[:1] if parts[0].startswith("@") else parts[:2]
    if parts[0] == "channel" and not CHANNEL_ID_RE.fullmatch(parts[1]):
        raise ValueError("Invalid channel ID")
    if not all(re.fullmatch(r"[@A-Za-z0-9_.-]+", p) for p in base):
        raise ValueError("Invalid channel path")
    return "https://www.youtube.com/" + "/".join(base) + "/" + tab


def _ydl_opts(cfg: Settings = settings, **extra: Any) -> dict[str, Any]:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "socket_timeout": 30, "retries": 2, "fragment_retries": 2}
    if cfg.cookie_file:
        path = Path(cfg.cookie_file).expanduser()
        if not path.is_file():
            raise ValueError("YTB_COOKIE_FILE points to a missing file")
        opts["cookiefile"] = str(path)
    if cfg.proxy:
        opts["proxy"] = cfg.proxy
    if cfg.js_runtime not in {"auto", "deno", "node", "quickjs"}:
        raise ValueError("YTB_JS_RUNTIME must be auto, deno, node, or quickjs")
    if cfg.js_runtime in {"auto", "deno"}:
        # uv tool scripts execute under a private venv: its Deno binary is not
        # necessarily in the parent PATH. Use the official deno Python wheel.
        try:
            import deno
            deno_path = str(deno.find_deno_bin())
        except (ImportError, FileNotFoundError, RuntimeError):
            deno_path = shutil.which("deno")
        if deno_path:
            opts["js_runtimes"] = {"deno": {"path": deno_path}}
        elif cfg.js_runtime == "deno":
            raise ValueError("Deno runtime was requested but not installed")
    if "js_runtimes" not in opts:
        for runtime, executable in (("node", "node"), ("quickjs", "qjs")):
            if cfg.js_runtime not in {"auto", runtime}:
                continue
            binary = shutil.which(executable)
            if binary:
                opts["js_runtimes"] = {runtime: {"path": binary}}
                break
    opts.update(extra)
    return opts


def extract(target: str, *, cfg: Settings = settings, **opts: Any) -> dict[str, Any]:
    with yt_dlp.YoutubeDL(_ydl_opts(cfg, **opts)) as ydl:
        value = ydl.extract_info(target, download=False)
        if not isinstance(value, dict):
            raise RuntimeError("yt-dlp returned an unexpected response")
        return value


def compact_entry(entry: dict[str, Any], *, include_description: bool = True, full: bool = False) -> dict[str, Any]:
    keys = ["id", "title", "webpage_url", "channel", "channel_id", "channel_url", "uploader", "uploader_id", "duration", "view_count", "like_count", "comment_count", "upload_date", "timestamp", "release_timestamp", "live_status", "availability", "original_url"]
    if include_description:
        keys.append("description")
    if full:
        keys += ["tags", "categories", "chapters", "thumbnails", "language", "subtitles", "automatic_captions", "age_limit", "license", "thumbnail", "format_id", "resolution"]
    result = {key: entry[key] for key in keys if entry.get(key) is not None}
    if result.get("id") and not result.get("webpage_url") and VIDEO_ID_RE.fullmatch(str(result["id"])):
        result["webpage_url"] = video_url(result["id"])
    description = result.get("description")
    if isinstance(description, str) and len(description) > (25000 if full else 8000):
        result["description"] = description[: (25000 if full else 8000)] + "…"
    if full:
        for track_type in ("subtitles", "automatic_captions"):
            if track_type in result:
                result[track_type] = {lang: [dict(ext=v.get("ext"), name=v.get("name")) for v in variants if isinstance(v, dict)] for lang, variants in result[track_type].items()}
    return result


def _page(info: dict[str, Any], offset: int, limit: int) -> dict[str, Any]:
    entries = [compact_entry(e, include_description=False) for e in (info.get("entries") or []) if isinstance(e, dict)]
    # yt-dlp usually returns exactly the requested playlist slice; some extractors ignore paging.
    return {"entries": entries[:limit], "offset": offset, "limit": limit, "next_offset": offset + len(entries) if len(entries) >= limit else None, "has_more": len(entries) >= limit, "pagination_hint": "has_more indicates a possible next page; repeat with next_offset until entries are exhausted"}


def search(query: str, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
    if not query.strip() or len(query) > 300:
        raise ValueError("query must be 1–300 characters")
    limit = max(1, min(int(limit), 50))
    offset = max(0, min(int(offset), 200))
    count = offset + limit
    info = extract(f"ytsearch{count}:{query}", extract_flat=True, playlistend=count, noplaylist=False)
    return [compact_entry(e, include_description=False) for e in (info.get("entries") or [])[offset:count] if isinstance(e, dict)]


def video_info(video: str, full: bool = False) -> dict[str, Any]:
    return compact_entry(extract(video_url(video)), full=full)


def channel_info(channel: str) -> dict[str, Any]:
    info = extract(channel_url(channel), extract_flat=True, playlistend=1, noplaylist=False)
    return {k: info.get(k) for k in ("id", "title", "description", "channel", "channel_id", "channel_url", "uploader", "uploader_id", "webpage_url") if info.get(k) is not None}


def channel_videos(channel: str, limit: int = 30, offset: int = 0, tab: str = "videos", *, paged: bool = False) -> Any:
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    target = channel_url(channel, tab)
    info = extract(target, extract_flat=True, playliststart=offset+1, playlistend=offset+limit, noplaylist=False)
    page = _page(info, offset, limit)
    page.update({"channel": info.get("channel") or info.get("title"), "channel_id": info.get("channel_id"), "tab": tab})
    return page if paged else page["entries"]


def channel_playlists(channel: str, limit: int = 30, offset: int = 0) -> dict[str, Any]:
    return channel_videos(channel, limit, offset, tab="playlists", paged=True)


def playlist_info(playlist: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    limit, offset = max(1, min(int(limit), 250)), max(0, int(offset))
    info = extract(playlist_url(playlist), extract_flat=True, playliststart=offset+1, playlistend=offset+limit, noplaylist=False)
    return {"id": info.get("id"), "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"), **_page(info, offset, limit)}


def comments(video: str, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    info = extract(video_url(video), getcomments=True, extractor_args={"youtube": {"max_comments": [str(limit), "all", "all", "0"]}})
    result = []
    for item in (info.get("comments") or [])[:limit]:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and len(text) > 4000:
            text = text[:4000] + "…"
        result.append({"id": item.get("id"), "author": item.get("author"), "text": text, "like_count": item.get("like_count"), "timestamp": item.get("timestamp"), "parent": item.get("parent")})
    return result


def subtitles(video: str) -> dict[str, Any]:
    info = extract(video_url(video))
    def tracks(name: str) -> dict[str, Any]:
        return {lang: sorted(set(str(v.get("ext")) for v in variants if isinstance(v, dict) and v.get("ext"))) for lang, variants in (info.get(name) or {}).items()}
    return {"video_id": normalize_video_id(video), "manual": tracks("subtitles"), "automatic": tracks("automatic_captions")}


def chapters(video: str) -> dict[str, Any]:
    info = extract(video_url(video))
    return {"video_id": normalize_video_id(video), "chapters": [{k: x.get(k) for k in ("title", "start_time", "end_time") } for x in (info.get("chapters") or [])], "available": bool(info.get("chapters"))}


def media_formats(video: str) -> dict[str, Any]:
    info = extract(video_url(video))
    formats = [{k: x.get(k) for k in ("format_id", "ext", "width", "height", "fps", "vcodec", "acodec", "filesize", "filesize_approx", "tbr") if x.get(k) is not None} for x in (info.get("formats") or [])]
    return {"video_id": normalize_video_id(video), "formats": formats[:250], "truncated": len(formats) > 250}
