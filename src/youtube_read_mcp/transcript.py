from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import yt_dlp
from filelock import FileLock
from yt_dlp.version import __version__ as YTDLP_VERSION

from .config import Settings, settings
from .core import _ydl_opts, extract, normalize_video_id, video_url

CACHE_SCHEMA_VERSION = 2
TIMESTAMP_RE = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{3})")
TAG_RE = re.compile(r"<[^>]+>")


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _seconds(value: str) -> float:
    match = TIMESTAMP_RE.search(value)
    if not match:
        raise ValueError(f"Invalid VTT timestamp: {value}")
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(match.group("ms")) / 1000.0
    )


def _clean_text(value: str) -> str:
    value = TAG_RE.sub("", value)
    value = html.unescape(value)
    value = value.replace("\u200b", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_json3(raw: bytes | str) -> list[dict[str, Any]]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    data = json.loads(raw)
    result: list[dict[str, Any]] = []
    for event in data.get("events", []):
        if not isinstance(event, dict):
            continue
        text = _clean_text(
            "".join(str(seg.get("utf8", "")) for seg in event.get("segs", []) if isinstance(seg, dict))
        )
        if not text:
            continue
        start = float(event.get("tStartMs") or 0) / 1000.0
        duration = float(event.get("dDurationMs") or 0) / 1000.0
        result.append({"start": start, "end": max(start, start + duration), "text": text})
    return _dedupe_segments(result)


def parse_vtt(raw: bytes | str) -> list[dict[str, Any]]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        left, right = [x.strip() for x in line.split("-->", 1)]
        right = right.split(" ", 1)[0]
        try:
            start, end = _seconds(left), _seconds(right)
        except ValueError:
            i += 1
            continue
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        text = _clean_text(" ".join(text_lines))
        if text:
            result.append({"start": start, "end": max(start, end), "text": text})
        i += 1
    return _dedupe_segments(result)


def _dedupe_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    previous = None
    for seg in sorted(segments, key=lambda x: (float(x["start"]), float(x["end"]))):
        text = _clean_text(str(seg.get("text") or ""))
        if not text or text == previous:
            continue
        previous = text
        result.append(
            {
                **({"timing": seg["timing"]} if "timing" in seg else {}),
                "start": round(float(seg["start"]), 3),
                "end": round(float(seg["end"]), 3),
                "text": text,
            }
        )
    return result


def _lang_match(key: str, requested: str) -> bool:
    return (
        key.lower() == requested.lower() or key.split("-", 1)[0].lower() == requested.split("-", 1)[0].lower()
    )


def track_candidates(
    manual: dict[str, Any], automatic: dict[str, Any], preferred_languages: list[str]
) -> list[tuple[str, str, dict[str, Any]]]:
    """Return caption candidates in deterministic quality/language order.

    Order: preferred manual -> preferred automatic -> remaining manual -> remaining automatic.
    Each language contributes its best available format (json3, then vtt, then first URL).
    """
    ordered: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    def add(source: str, tracks: dict[str, Any], language: str) -> None:
        key = (source, language)
        if key in seen:
            return
        variant = _pick_variant(tracks.get(language))
        if variant:
            seen.add(key)
            ordered.append((source, language, variant))

    for source, tracks in (("manual", manual), ("automatic", automatic)):
        for requested in preferred_languages:
            for language in tracks:
                if _lang_match(language, requested):
                    add(source, tracks, language)

    for source, tracks in (("manual", manual), ("automatic", automatic)):
        for language in tracks:
            add(source, tracks, language)
    return ordered


def pick_track(
    manual: dict[str, Any], automatic: dict[str, Any], preferred_languages: list[str]
) -> tuple[str, str, dict[str, Any]] | None:
    candidates = track_candidates(manual, automatic, preferred_languages)
    return candidates[0] if candidates else None


def _pick_variant(variants: Any) -> dict[str, Any] | None:
    if not isinstance(variants, list):
        return None
    usable = [x for x in variants if isinstance(x, dict) and x.get("url")]
    for ext in ("json3", "vtt"):
        found = next((x for x in usable if x.get("ext") == ext), None)
        if found:
            return found
    return usable[0] if usable else None


def fetch_track(variant: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    url = variant["url"]
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        response = client.get(url)
        response.raise_for_status()
    ext = str(variant.get("ext") or "")
    if ext == "json3" or response.content.lstrip().startswith(b"{"):
        return parse_json3(response.content), "json3"
    return parse_vtt(response.content), "vtt"


def build_chunks(
    segments: list[dict[str, Any]], *, max_seconds: int = 600, max_chars: int = 14000
) -> list[dict[str, Any]]:
    if not segments:
        return []
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    chars = 0
    start = float(segments[0]["start"])

    def flush() -> None:
        nonlocal current, chars, start
        if not current:
            return
        text = " ".join(str(x["text"]) for x in current).strip()
        chunks.append(
            {
                "index": len(chunks),
                "start": float(current[0]["start"]),
                "end": float(current[-1]["end"]),
                "chars": len(text),
                "text": text,
            }
        )
        current = []
        chars = 0

    for seg in segments:
        seg_text = str(seg["text"])
        span = float(seg["end"]) - start
        if current and (span > max_seconds or chars + len(seg_text) + 1 > max_chars):
            flush()
            start = float(seg["start"])
        current.append(seg)
        chars += len(seg_text) + 1
    flush()
    return chunks


def transcript_range(record: dict[str, Any], start_seconds: float, end_seconds: float) -> dict[str, Any]:
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds")
    if end_seconds - start_seconds > 7200:
        raise ValueError("range exceeds 2 hours; use transcript_read pagination")
    segments = [
        seg
        for seg in record.get("segments", [])
        if float(seg["end"]) >= start_seconds and float(seg["start"]) <= end_seconds
    ]
    text = " ".join(str(x["text"]) for x in segments)
    if len(text) > 30000:
        raise ValueError("This timestamp range is too large; use youtube_transcript_read cursor pagination")
    return {
        "video_id": record["video_id"],
        "title": record.get("title"),
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "segments": segments,
        "text": text,
    }


def search_record(record: dict[str, Any], query: str, limit: int = 8) -> list[dict[str, Any]]:
    words = [x.lower() for x in re.findall(r"[\w'-]+", query) if len(x) > 1]
    if not words:
        return []
    scored: list[tuple[int, int]] = []
    segments = record.get("segments", [])
    for idx, seg in enumerate(segments):
        text = str(seg.get("text") or "").lower()
        score = sum(text.count(word) for word in words)
        if score:
            scored.append((score, idx))
    scored.sort(key=lambda x: (-x[0], x[1]))
    result: list[dict[str, Any]] = []
    used: set[int] = set()
    for score, idx in scored:
        if len(result) >= max(1, min(limit, 20)):
            break
        if idx in used:
            continue
        lo, hi = max(0, idx - 1), min(len(segments), idx + 2)
        window = segments[lo:hi]
        used.update(range(lo, hi))
        result.append(
            {
                "score": score,
                "start_seconds": float(window[0]["start"]),
                "end_seconds": float(window[-1]["end"]),
                "text": " ".join(str(x["text"]) for x in window),
            }
        )
    return result


def _cache_dir(video_id: str, cfg: Settings) -> Path:
    path = cfg.transcript_dir / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(video_id: str, cfg: Settings) -> Path:
    return _cache_dir(video_id, cfg) / "transcript.json"


def _is_fresh(path: Path, cfg: Settings) -> bool:
    if not path.exists():
        return False
    if cfg.cache_max_age_hours <= 0:
        return True
    cutoff = datetime.now(UTC) - timedelta(hours=cfg.cache_max_age_hours)
    return datetime.fromtimestamp(path.stat().st_mtime, UTC) >= cutoff


def save_record(record: dict[str, Any], cfg: Settings = settings) -> Path:
    path = _cache_path(record["video_id"], cfg)
    tmp = path.with_suffix(".json.tmp")
    payload = json.dumps(record, ensure_ascii=False, indent=2)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_record(video: str, cfg: Settings = settings) -> dict[str, Any]:
    video_id = normalize_video_id(video)
    path = _cache_path(video_id, cfg)
    if not path.exists():
        raise FileNotFoundError(f"No prepared transcript cache for {video_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def manifest(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": True,
        "schema_version": record.get("schema_version"),
        "video_id": record.get("video_id"),
        "title": record.get("title"),
        "duration_seconds": record.get("duration_seconds"),
        "language": record.get("language"),
        "source": record.get("source"),
        "timing_quality": record.get("timing_quality", "unknown"),
        "prepared_at": record.get("prepared_at"),
        "provenance": record.get("provenance"),
        "content_hash": record.get("content_hash"),
        "segment_count": len(record.get("segments", [])),
        "chunks": [
            {k: chunk[k] for k in ("index", "start", "end", "chars")} for chunk in record.get("chunks", [])
        ],
    }


def _download_audio(video_id: str, workdir: Path, cfg: Settings = settings) -> Path:
    template = str(workdir / "source.%(ext)s")
    opts = _ydl_opts(cfg, skip_download=False, format="bestaudio/best", outtmpl=template, noplaylist=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(video_url(video_id), download=True)
    files = [p for p in workdir.glob("source.*") if p.is_file()]
    if not files:
        raise RuntimeError("yt-dlp did not produce an audio file")
    return max(files, key=lambda p: p.stat().st_mtime)


def _split_audio(source: Path, workdir: Path, seconds: int) -> list[Path]:
    output = workdir / "chunk_%03d.wav"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-f",
        "segment",
        "-segment_time",
        str(max(60, seconds)),
        "-reset_timestamps",
        "1",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    subprocess.run(command, check=True, timeout=3600)
    chunks = sorted(workdir.glob("chunk_*.wav"))
    if not chunks:
        raise RuntimeError("ffmpeg produced no STT chunks")
    return chunks


def _stt_one(path: Path, offset_seconds: float, cfg: Settings) -> list[dict[str, Any]]:
    if not cfg.stt_base_url:
        raise RuntimeError("STT_BASE_URL is not configured")
    headers = {"Authorization": f"Bearer {cfg.stt_api_key}"} if cfg.stt_api_key else {}
    url = f"{cfg.stt_base_url}/audio/transcriptions"

    def request(response_format: str) -> dict[str, Any]:
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "audio/wav")}
            data = {"model": cfg.stt_model, "response_format": response_format}
            with httpx.Client(timeout=cfg.stt_timeout_seconds) as client:
                response = client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                value = response.json()
                if not isinstance(value, dict):
                    raise RuntimeError("STT endpoint returned a non-object JSON response")
                return value

    try:
        payload = request("verbose_json")
    except httpx.HTTPStatusError as exc:
        # Some OpenAI-compatible Whisper gateways only implement plain JSON.
        if exc.response.status_code not in {400, 404, 415, 422}:
            raise
        try:
            payload = request("json")
        except httpx.HTTPStatusError as fallback_exc:
            # Response bodies are capped and used only as a backend diagnostic;
            # request headers and credentials are never included.
            detail = fallback_exc.response.text.strip().replace("\n", " ")[:500]
            raise RuntimeError(
                f"STT backend rejected both verbose_json and json responses "
                f"({fallback_exc.response.status_code}): {detail}"
            ) from fallback_exc

    result: list[dict[str, Any]] = []
    for seg in payload.get("segments") or []:
        if not isinstance(seg, dict) or not str(seg.get("text") or "").strip():
            continue
        start = offset_seconds + float(seg.get("start") or 0)
        end = offset_seconds + float(seg.get("end") or seg.get("start") or 0)
        result.append({"start": start, "end": max(start, end), "text": _clean_text(str(seg["text"]))})
    if not result:
        text = _clean_text(str(payload.get("text") or ""))
        if text:
            # A plain text-only STT response does not provide word/sentence timing.
            # Use chunk boundaries as APPROXIMATE intervals; never invent exact points.
            import wave

            with wave.open(str(path), "rb") as wav:
                chunk_duration = wav.getnframes() / float(wav.getframerate())
            result.append(
                {
                    "start": offset_seconds,
                    "end": offset_seconds + chunk_duration,
                    "text": text,
                    "timing": "chunk_approximate",
                }
            )
    return result


def transcribe_with_stt(video_id: str, cfg: Settings = settings) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"yt-stt-{video_id}-") as tmp_name:
        workdir = Path(tmp_name)
        source = _download_audio(video_id, workdir, cfg)
        chunks = _split_audio(source, workdir, cfg.stt_chunk_seconds)
        segments: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            segments.extend(_stt_one(chunk, index * cfg.stt_chunk_seconds, cfg))
    return _dedupe_segments(segments)


def prepare_transcript(
    video: str,
    *,
    preferred_languages: list[str] | None = None,
    force_refresh: bool = False,
    force_stt: bool = False,
    cfg: Settings = settings,
) -> dict[str, Any]:
    video_id = normalize_video_id(video)
    preferred = list(preferred_languages or cfg.preferred_languages)
    cache_path = _cache_path(video_id, cfg)
    lock = FileLock(str(cache_path) + ".lock", timeout=300)
    with lock:
        if not force_refresh and _is_fresh(cache_path, cfg):
            cached = load_record(video_id, cfg)
            cached_languages = list((cached.get("provenance") or {}).get("preferred_languages") or [])
            if (
                cached_languages == preferred
                and bool((cached.get("provenance") or {}).get("force_stt")) == force_stt
            ):
                return manifest(cached)

        info = extract(video_url(video_id))
        caption_candidates = (
            []
            if force_stt
            else track_candidates(
                info.get("subtitles") or {}, info.get("automatic_captions") or {}, preferred
            )
        )
        segments: list[dict[str, Any]] = []
        language = "unknown"
        source = "unavailable"
        provenance: dict[str, Any] = {"backend": "yt-dlp", "preferred_languages": preferred}
        errors: list[str] = []

        for candidate_source, candidate_language, variant in caption_candidates:
            try:
                candidate_segments, fmt = fetch_track(variant)
                if not candidate_segments:
                    errors.append(
                        f"caption track produced no usable segments: {candidate_source}/{candidate_language}/{fmt}"
                    )
                    continue
                segments = candidate_segments
                source = candidate_source
                language = candidate_language
                provenance.update({"caption_format": fmt, "caption_source": source})
                break
            except Exception as exc:  # try the next caption track before STT
                errors.append(
                    f"caption fetch failed ({candidate_source}/{candidate_language}): "
                    f"{type(exc).__name__}: {exc}"
                )

        if not segments and cfg.stt_base_url:
            try:
                segments = transcribe_with_stt(video_id, cfg)
                source = "stt"
                language = "unknown"  # STT backend did not provide verified language
                provenance.update(
                    {"stt_model": cfg.stt_model, "stt_base_url": cfg.stt_base_url, "force_stt": force_stt}
                )
            except Exception as exc:
                errors.append(f"STT fallback failed: {type(exc).__name__}: {exc}")

        if not segments:
            return {
                "available": False,
                "video_id": video_id,
                "title": info.get("title"),
                "reason": "No usable captions and STT fallback was unavailable or failed.",
                "errors": errors,
            }

        timing_quality = (
            "stt_chunk_approximate"
            if any(x.get("timing") == "chunk_approximate" for x in segments)
            else ("stt_timed" if source == "stt" else "caption_timed")
        )
        chunks = build_chunks(
            segments,
            max_seconds=max(60, cfg.transcript_chunk_seconds),
            max_chars=max(1000, cfg.transcript_max_chars),
        )
        transcript_text = "\n".join(str(segment.get("text") or "") for segment in segments)
        record = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "video_id": video_id,
            "title": info.get("title") or video_id,
            "duration_seconds": info.get("duration"),
            "language": language,
            "source": source,
            "timing_quality": timing_quality,
            "prepared_at": utcnow(),
            "content_hash": hashlib.sha256(transcript_text.encode("utf-8")).hexdigest(),
            "provenance": {
                **provenance,
                "yt_dlp_version": YTDLP_VERSION,
                "errors_before_success": errors,
            },
            "segments": segments,
            "chunks": chunks,
        }
        save_record(record, cfg)
        return manifest(record)
