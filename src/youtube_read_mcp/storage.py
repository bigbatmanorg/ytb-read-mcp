"""SQLite FTS5 transcript search + durable simple worker jobs; no external services."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from .config import Settings, settings
from .core import normalize_video_id


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def connection(cfg: Settings = settings) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(cfg.db_path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS videos (video_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS transcripts (video_id TEXT PRIMARY KEY, language TEXT NOT NULL, source TEXT NOT NULL, content_hash TEXT NOT NULL, indexed_at TEXT NOT NULL);
    CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(video_id UNINDEXED, start UNINDEXED, end UNINDEXED, content, tokenize='unicode61');
    CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS job_items (job_id TEXT NOT NULL, item_key TEXT NOT NULL, state TEXT NOT NULL, result TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(job_id,item_key));
    CREATE TABLE IF NOT EXISTS source_sync (source TEXT PRIMARY KEY, ids TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    try:
        with db:
            yield db
    finally:
        db.close()


def index_transcript(record: dict[str, Any], cfg: Settings = settings) -> None:
    video = normalize_video_id(record["video_id"])
    with connection(cfg) as db:
        prior = db.execute("SELECT content_hash FROM transcripts WHERE video_id=?", (video,)).fetchone()
        if prior and prior[0] == record.get("content_hash"):
            return
        db.execute("DELETE FROM transcript_fts WHERE video_id=?", (video,))
        db.executemany(
            "INSERT INTO transcript_fts(video_id,start,end,content) VALUES (?,?,?,?)",
            [
                (video, float(seg["start"]), float(seg["end"]), seg["text"])
                for seg in record.get("segments", [])
            ],
        )
        db.execute(
            "INSERT OR REPLACE INTO transcripts(video_id,language,source,content_hash,indexed_at) VALUES(?,?,?,?,?)",
            (
                video,
                record.get("language", "unknown"),
                record.get("source", "unknown"),
                record.get("content_hash", ""),
                now(),
            ),
        )


def search_transcripts(
    query: str, limit: int = 10, video: str = "", cfg: Settings = settings
) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    # Quoting each lexical token avoids raw FTS syntax injection and MATCH errors.
    import re

    terms = re.findall(r"\w+", query, flags=re.UNICODE)[:12]
    if not terms:
        return {"results": [], "count": 0}
    match = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
    where = "AND video_id=?" if video else ""
    args: tuple[Any, ...] = (match, normalize_video_id(video), limit) if video else (match, limit)
    with connection(cfg) as db:
        rows = db.execute(
            f"SELECT video_id, start, end, snippet(transcript_fts, 3, '[', ']', '…', 18) AS excerpt, bm25(transcript_fts) AS rank FROM transcript_fts WHERE transcript_fts MATCH ? {where} ORDER BY rank LIMIT ?",
            args,
        ).fetchall()
    return {"results": [dict(x) for x in rows], "count": len(rows), "search_mode": "lexical_fts5"}


def save_video(info: dict[str, Any], cfg: Settings = settings) -> None:
    with connection(cfg) as db:
        db.execute(
            "INSERT OR REPLACE INTO videos(video_id,metadata,updated_at) VALUES(?,?,?)",
            (normalize_video_id(info["id"]), json.dumps(info, ensure_ascii=False), now()),
        )


def create_job(kind: str, items: list[str], cfg: Settings = settings) -> dict[str, Any]:
    if kind != "prepare_transcript":
        raise ValueError("Unknown job kind")
    if not 1 <= len(items) <= 250:
        raise ValueError("batch contains 1–250 items")
    unique = list(dict.fromkeys(normalize_video_id(x) for x in items))
    job_id = uuid.uuid4().hex
    with connection(cfg) as db:
        db.execute(
            "INSERT INTO jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (job_id, kind, "queued", json.dumps({"items": unique}), now(), now()),
        )
        db.executemany(
            "INSERT INTO job_items(job_id,item_key,state,updated_at) VALUES(?,?,?,?)",
            [(job_id, x, "queued", now()) for x in unique],
        )
    return job_status(job_id, cfg)


def job_status(job_id: str, cfg: Settings = settings) -> dict[str, Any]:
    with connection(cfg) as db:
        job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise ValueError("Job not found")
        rows = db.execute(
            "SELECT item_key,state,result FROM job_items WHERE job_id=? ORDER BY rowid", (job_id,)
        ).fetchall()
    return {
        "id": job["id"],
        "kind": job["kind"],
        "state": job["state"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "cancel_requested": bool(job["cancel_requested"]),
        "total": len(rows),
        "completed": sum(x["state"] == "completed" for x in rows),
        "failed": sum(x["state"] == "failed" for x in rows),
        "items": [
            {
                "video_id": x["item_key"],
                "state": x["state"],
                "result": json.loads(x["result"]) if x["result"] else None,
            }
            for x in rows
        ],
    }


def cancel_job(job_id: str, cfg: Settings = settings) -> dict[str, Any]:
    with connection(cfg) as db:
        db.execute("UPDATE jobs SET cancel_requested=1,updated_at=? WHERE id=?", (now(), job_id))
        db.execute("UPDATE job_items SET state='cancelled' WHERE job_id=? AND state='queued'", (job_id,))
        db.execute("UPDATE jobs SET state='cancelled' WHERE id=? AND state='queued'", (job_id,))
    return job_status(job_id, cfg)


def run_job_once(cfg: Settings = settings, prepare=None) -> bool:
    """Exactly one item. Safe to restart worker: running items can be reclaimed."""
    from .transcript import prepare_transcript

    prepare = prepare or (lambda vid: prepare_transcript(vid, cfg=cfg))
    with connection(cfg) as db:
        db.execute("BEGIN IMMEDIATE")
        item = db.execute(
            "SELECT j.id AS job_id,i.item_key FROM job_items i JOIN jobs j ON j.id=i.job_id WHERE i.state IN ('queued','running') AND j.cancel_requested=0 ORDER BY CASE i.state WHEN 'running' THEN 1 ELSE 0 END, j.created_at, i.rowid LIMIT 1"
        ).fetchone()
        if not item:
            return False
        job_id, video = item["job_id"], item["item_key"]
        db.execute(
            "UPDATE job_items SET state='running',updated_at=? WHERE job_id=? AND item_key=?",
            (now(), job_id, video),
        )
        db.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (now(), job_id))
    try:
        result = prepare(video)
        state = "completed" if result.get("available", False) else "failed"
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"[:500]}
        state = "failed"
    with connection(cfg) as db:
        db.execute(
            "UPDATE job_items SET state=?,result=?,updated_at=? WHERE job_id=? AND item_key=?",
            (state, json.dumps(result, ensure_ascii=False), now(), job_id, video),
        )
        pending = db.execute("SELECT state FROM job_items WHERE job_id=?", (job_id,)).fetchall()
        states = {x[0] for x in pending}
        if not states.intersection({"queued", "running"}):
            final = (
                "partial"
                if "failed" in states and "completed" in states
                else (
                    "failed"
                    if "failed" in states
                    else ("cancelled" if "cancelled" in states else "completed")
                )
            )
            db.execute("UPDATE jobs SET state=?,updated_at=? WHERE id=?", (final, now(), job_id))
    return True


def sync_source(source: str, ids: list[str], cfg: Settings = settings) -> dict[str, Any]:
    """Persist identity-based scan state; caller controls metadata paging and scan overlap."""
    valid = list(dict.fromkeys(normalize_video_id(x) for x in ids))
    with connection(cfg) as db:
        old = db.execute("SELECT ids FROM source_sync WHERE source=?", (source,)).fetchone()
        before = set(json.loads(old[0])) if old else set()
        new = [x for x in valid if x not in before]
        merged = list(dict.fromkeys(valid + list(before)))
        db.execute(
            "INSERT OR REPLACE INTO source_sync(source,ids,updated_at) VALUES(?,?,?)",
            (source, json.dumps(merged), now()),
        )
    return {"source": source, "scanned": len(valid), "new_video_ids": new, "known_total": len(merged)}
