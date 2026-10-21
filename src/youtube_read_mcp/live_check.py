from __future__ import annotations

import json
import os
import re

from .core import search, video_info
from .transcript import load_record, prepare_transcript, search_record


def searchable_probe_term(segments: list[dict[str, object]]) -> str | None:
    """Return a token accepted by transcript search, skipping caption notation."""
    return next(
        (
            word
            for segment in segments
            for word in re.findall(r"[\w'-]+", str(segment.get("text") or ""))
            if len(word) > 1
        ),
        None,
    )


def main() -> None:
    video = os.getenv("LIVE_TEST_VIDEO", "dQw4w9WgXcQ")
    query = os.getenv("LIVE_TEST_QUERY", "Docker Agent")
    print(json.dumps({"video_info": video_info(video)}, indent=2, default=str))
    results = search(query, 3)
    if not results:
        raise SystemExit("live search returned no results")
    print(json.dumps({"search_count": len(results), "first": results[0]}, indent=2, default=str))
    prepared = prepare_transcript(video, force_refresh=True)
    if not prepared.get("available"):
        raise SystemExit(f"transcript preparation failed: {prepared}")
    record = load_record(video)
    # Some valid caption tracks begin with music notation (for example "[♪♪♪]").
    # Pick a searchable lexical token rather than assuming the first segment has one.
    probe_term = searchable_probe_term(record["segments"])
    if not probe_term:
        raise SystemExit("prepared transcript contains no searchable text")
    probe = search_record(record, probe_term, 1)
    if not probe:
        raise SystemExit("prepared transcript could not be searched")
    print(json.dumps({"transcript": prepared, "search_probe": probe[0]}, indent=2, default=str))


if __name__ == "__main__":
    main()
