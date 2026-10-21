"""Installable stdio-first CLI, diagnostics, deterministic self-test, and worker."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path


def self_test() -> dict[str, object]:
    """Offline and fully deterministic smoke test using temp storage, no YouTube calls."""
    from tempfile import TemporaryDirectory

    from fastmcp import Client

    from . import api, core, storage, transcript
    from .config import Settings
    from .server import mcp

    assert core.normalize_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    try:
        core.normalize_video_id("https://evilyoutube.com/watch?v=dQw4w9WgXcQ")
        raise AssertionError("host validation failed")
    except ValueError:
        pass
    assert (
        transcript.parse_vtt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhi world\n")[0]["text"] == "hi world"
    )

    async def verify_mcp() -> int:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {x.name for x in tools}
            assert {
                "youtube_search",
                "youtube_prepare_transcript",
                "youtube_transcript_read",
                "youtube_health",
                "youtube_download",
            } <= names
            result = await client.call_tool("youtube_health", {})
            assert not result.is_error
            return len(names)

    with TemporaryDirectory() as tmp:
        cfg = Settings(data_dir=Path(tmp))
        record = {
            "schema_version": 2,
            "video_id": "dQw4w9WgXcQ",
            "title": "fixture",
            "duration_seconds": 6,
            "language": "en",
            "source": "manual",
            "timing_quality": "caption_timed",
            "provenance": {},
            "prepared_at": "fixture",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "agent context memory"},
                {"start": 2.0, "end": 4.0, "text": "video agent test"},
                {"start": 4.0, "end": 6.0, "text": "memory context evidence"},
            ],
        }
        record["chunks"] = transcript.build_chunks(record["segments"])
        record["content_hash"] = "fixture-hash"
        transcript.save_record(record, cfg)
        storage.index_transcript(record, cfg)
        assert storage.search_transcripts("memory", cfg=cfg)["count"] == 2
        assert api.read_transcript(record["video_id"], max_chars=500, cfg=cfg)["complete"]
        assert Path(api.export_transcript(record["video_id"], "srt", cfg=cfg)["path"]).exists()
        job = storage.create_job("prepare_transcript", [record["video_id"]], cfg=cfg)
        assert storage.run_job_once(cfg, prepare=lambda _: {"available": True})
        assert storage.job_status(job["id"], cfg)["state"] == "completed"
    return {
        "status": "passed",
        "kind": "offline-deterministic",
        "mcp_tools": asyncio.run(verify_mcp()),
        "tests": [
            "url-validation",
            "caption-parser",
            "cache",
            "fts5",
            "pagination",
            "subtitle-export",
            "persistent-job",
            "mcp-tools-list",
            "mcp-tool-call",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ytb-read-mcp", description="Zero-config YouTube research MCP (stdio by default)"
    )
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Start MCP server (default: stdio)")
    serve.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    sub.add_parser("doctor", help="Print local dependency checks; no network")
    sub.add_parser("test", help="Run built-in offline deterministic smoke tests")
    sub.add_parser("live-test", help="Opt-in live YouTube smoke tests; network required")
    worker = sub.add_parser("worker", help="Process persisted batch jobs; run separately from stdio clients")
    worker.add_argument("--once", action="store_true", help="Process at most one queued item and exit")
    opts = parser.parse_args()
    command = opts.command or "serve"
    if command == "doctor":
        from .api import health

        print(json.dumps(health(), indent=2))
    elif command == "test":
        print(json.dumps(self_test(), indent=2))
    elif command == "live-test":
        from .live_check import main as live

        live()
    elif command == "worker":
        from filelock import FileLock, Timeout

        from .config import settings
        from .storage import run_job_once

        try:
            with FileLock(str(settings.db_path) + ".worker.lock", timeout=0):
                while True:
                    performed = run_job_once()
                    if opts.once:
                        break
                    if not performed:
                        time.sleep(max(1, settings.worker_poll_seconds))
        except Timeout:
            raise SystemExit("Another worker owns this database; start only one worker") from None
    elif command == "serve":
        from .config import settings
        from .server import mcp

        transport = getattr(opts, "transport", "stdio")
        if transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(
                transport="http",
                host=getattr(opts, "host", None) or settings.host,
                port=getattr(opts, "port", None) or settings.port,
                stateless_http=True,
            )
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
