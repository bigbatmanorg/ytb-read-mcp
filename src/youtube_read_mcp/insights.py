"""Timeline insights layered on prepared transcripts: heatmap peaks, SponsorBlock, chapter outline."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from . import core, transcript
from .config import Settings, settings

SPONSORBLOCK_CATEGORIES = (
    "sponsor",
    "selfpromo",
    "interaction",
    "intro",
    "outro",
    "preview",
    "music_offtopic",
    "filler",
)
SPONSORBLOCK_CACHE_HOURS = 24
_STOPWORDS = set(
    """
    about above after again against also because been before being below between both could does doing
    down during each from further have having here into itself just more most other over same should some
    such than that their them then there these they this those through under until very were what when
    where which while will with would your yours yourself going really thing things know like yeah okay
    right well gonna wanna dont that's it's i'm you're we're they're there's what's don't didn't
    doesn't can't won't isn't aren't wasn't i've you've we've i'll you'll we'll even pretty actually
    basically literally still much many lot lots kind sort mean maybe something anything everything
    make makes made want need think thought look looks good great little come back only first
    """.split()
)
# Caption notation such as [music] or [applause] is not spoken content.
_CAPTION_NOTATION = re.compile(r"\[[^\]]*\]")


def _load_record(video: str, cfg: Settings) -> dict[str, Any] | None:
    try:
        return transcript.load_record(video, cfg)
    except FileNotFoundError:
        return None


def _text_between(record: dict[str, Any] | None, start: float, end: float) -> str | None:
    if not record:
        return None
    return " ".join(
        str(seg["text"])
        for seg in record.get("segments", [])
        if float(seg["end"]) >= start and float(seg["start"]) <= end
    )


def heatmap_peaks(video: str, top: int = 5, *, cfg: Settings = settings) -> dict[str, Any]:
    """Most-replayed moments from YouTube's heatmap, with transcript text when prepared."""
    top = max(1, min(int(top), 20))
    video_id = core.normalize_video_id(video)
    record = _load_record(video_id, cfg)
    points = (record or {}).get("heatmap")
    duration = (record or {}).get("duration_seconds")
    if not points:
        info = core.extract(core.video_url(video_id))
        points = [p for p in (info.get("heatmap") or []) if isinstance(p, dict)]
        duration = info.get("duration")
    if not points:
        return {
            "video_id": video_id,
            "available": False,
            "reason": "YouTube publishes a heatmap only for videos with enough views.",
            "peaks": [],
        }
    values = [float(p.get("value") or 0) for p in points]
    # Local maxima, strongest first, at least ~3% of the video apart so peaks are distinct moments.
    candidates = [
        i
        for i, value in enumerate(values)
        if value >= (values[i - 1] if i else 0) and value >= (values[i + 1] if i + 1 < len(values) else 0)
    ]
    candidates.sort(key=lambda i: -values[i])
    separation = max(10.0, float(duration or 0) * 0.03)
    chosen: list[int] = []
    for i in candidates:
        start = float(points[i]["start_time"])
        if all(abs(start - float(points[j]["start_time"])) >= separation for j in chosen):
            chosen.append(i)
        if len(chosen) >= top:
            break
    peaks = []
    for i in chosen:
        start, end = float(points[i]["start_time"]), float(points[i]["end_time"])
        peaks.append(
            {
                "start_seconds": round(start, 1),
                "end_seconds": round(end, 1),
                "intensity": round(values[i], 3),
                "url": core.timestamp_url(video_id, start),
                "transcript": _text_between(record, start - 5, end + 5),
            }
        )
    return {
        "video_id": video_id,
        "available": True,
        "peaks": peaks,
        "transcript_prepared": record is not None,
        "note": "intensity is YouTube's relative replay value (1.0 = most replayed point).",
    }


def _fetch_sponsorblock(video_id: str, cfg: Settings) -> list[dict[str, Any]]:
    # The hash-prefix endpoint avoids sending the exact video ID to the SponsorBlock server.
    prefix = hashlib.sha256(video_id.encode()).hexdigest()[:4]
    with httpx.Client(timeout=20, headers={"User-Agent": "ytb-read-mcp"}) as client:
        response = client.get(
            f"{cfg.sponsorblock_api}/api/skipSegments/{prefix}",
            params={"categories": json.dumps(list(SPONSORBLOCK_CATEGORIES)), "actionTypes": '["skip"]'},
        )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    entry = next((x for x in response.json() if x.get("videoID") == video_id), None)
    return [
        {"category": seg["category"], "start": float(seg["segment"][0]), "end": float(seg["segment"][1])}
        for seg in (entry or {}).get("segments", [])
        if seg.get("category") in SPONSORBLOCK_CATEGORIES
    ]


def sponsor_segments(
    video: str, categories: list[str] | None = None, *, cfg: Settings = settings
) -> dict[str, Any]:
    """Community-labelled non-content segments (sponsor reads, intros, …) from SponsorBlock."""
    video_id = core.normalize_video_id(video)
    wanted = list(categories or SPONSORBLOCK_CATEGORIES)
    unknown = sorted(set(wanted) - set(SPONSORBLOCK_CATEGORIES))
    if unknown:
        raise ValueError(f"Unknown SponsorBlock categories: {', '.join(unknown)}")
    if not cfg.sponsorblock_api:
        raise ValueError("SponsorBlock is disabled (YTB_SPONSORBLOCK_API is empty)")
    cache = transcript._cache_dir(video_id, cfg) / "sponsorblock.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else None
    fresh = cached and datetime.fromisoformat(cached["fetched_at"]) > datetime.now(UTC) - timedelta(
        hours=SPONSORBLOCK_CACHE_HOURS
    )
    if not fresh:
        cached = {"fetched_at": datetime.now(UTC).isoformat(), "segments": _fetch_sponsorblock(video_id, cfg)}
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(cached), encoding="utf-8")
        tmp.replace(cache)
    segments = [
        {**seg, "url": core.timestamp_url(video_id, seg["start"])}
        for seg in cached["segments"]
        if seg["category"] in wanted
    ]
    return {
        "video_id": video_id,
        "segments": segments,
        "excluded_seconds": round(sum(s["end"] - s["start"] for s in segments), 1),
        "source": "sponsorblock",
        "fetched_at": cached["fetched_at"],
    }


def excluded_indexes(
    record: dict[str, Any], categories: list[str] | None, *, cfg: Settings = settings
) -> set[int]:
    """Transcript segment indexes whose midpoint lies inside an excluded SponsorBlock segment."""
    if not categories:
        return set()
    spans = sponsor_segments(record["video_id"], categories, cfg=cfg)["segments"]
    return {
        index
        for index, seg in enumerate(record.get("segments", []))
        if any(s["start"] <= (float(seg["start"]) + float(seg["end"])) / 2 < s["end"] for s in spans)
    }


def top_terms(texts: list[str], limit: int = 15) -> list[dict[str, Any]]:
    words = Counter(
        word
        for text in texts
        for word in re.findall(r"\w[\w'-]*", _CAPTION_NOTATION.sub(" ", text.lower().replace("’", "'")))
        if len(word) >= 4 and not word.isdigit() and word not in _STOPWORDS
    )
    return [{"term": term, "count": count} for term, count in words.most_common(limit)]


def outline(
    video: str,
    include_text: bool = False,
    exclude_categories: list[str] | None = None,
    *,
    cfg: Settings = settings,
) -> dict[str, Any]:
    """Transcript grouped by chapter (or fixed time windows) with per-section counts and links."""
    record = transcript.load_record(video, cfg)
    video_id = record["video_id"]
    chapters = record.get("chapters")
    if chapters is None:
        # Records prepared before v1.3.0 did not store chapters; fetch once and persist.
        chapters = core.chapters(video_id)["chapters"]
        record["chapters"] = chapters
        transcript.save_record(record, cfg)
    if chapters:
        source = "chapters"
        sections = [(c["title"], float(c["start_time"] or 0), c.get("end_time")) for c in chapters]
    else:
        source = "time_windows"
        sections = [(f"Part {c['index'] + 1}", float(c["start"]), c["end"]) for c in record.get("chunks", [])]
    skipped = excluded_indexes(record, exclude_categories, cfg=cfg)
    segments = [seg for i, seg in enumerate(record.get("segments", [])) if i not in skipped]
    result_sections = []
    for title, start, end in sections:
        end = float(end) if end is not None else float("inf")
        texts = [str(s["text"]) for s in segments if start <= float(s["start"]) < end]
        text = " ".join(texts)
        section = {
            "title": title,
            "start_seconds": start,
            "end_seconds": None if end == float("inf") else end,
            "url": core.timestamp_url(video_id, start),
            "word_count": transcript.word_count(text),
            "reading_minutes": round(transcript.word_count(text) / transcript.READING_WPM, 1),
        }
        section["text" if include_text else "preview"] = text if include_text else text[:240]
        result_sections.append(section)
    return {
        "video_id": video_id,
        "title": record.get("title"),
        "source": source,
        "sections": result_sections,
        "excluded_segments": len(skipped),
        "stats": transcript.transcript_stats(record),
        "top_terms": top_terms([str(s["text"]) for s in segments]),
    }
