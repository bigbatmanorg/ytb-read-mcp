# Architecture

## Design constraints

- Library-centric Python implementation; FastMCP is a thin adapter.
- stdio default; optional Streamable HTTP for local deployments (no built-in authentication).
- No config, API key, daemon, database service or STT needed for normal single-video searches/captions.
- sqlite3 metadata + FTS5; JSON transcript files; media artifacts in safe controlled root.
- Media and transcript extraction use yt-dlp + optional FFmpeg; environment-configured STT fallback.
- Tests independent of the public YouTube API are deterministic by design.

## Components

- `cli.py`: entry point, `serve`, `test`, `doctor`, `worker`, `live-test`.
- `server.py`: docstring-based MCP tools, instructions, resources and prompts.
- `core.py`: validated input IDs/URLs, yt-dlp configuration, discovery, metadata, captions, comments.
- `transcript.py`: caption normalization and splitting, caption quality priority, STT fallback, atomic file caching.
- `api.py`: transcript pagination and export, orchestration, health checks.
- `storage.py`: SQLite FTS5 transcript index, job/item state, per-source scan identity tracking.
- `media.py`: downloading, frames and clip extraction.
- `insights.py`: chapter outline, transcript statistics, heatmap peaks, SponsorBlock segments and exclusion.
- `config.py`: environment settings with XDG user-data defaults.

## Cache identities

Prepared transcript JSON is persisted per video ID (legacy-compatible path). Since v1.3.0 the record also keeps the video's chapters and heatmap so outline and heatmap tools work from the cache; older records fetch chapters once on first outline. Cache reuse considers the preferred language list and configured age limit. A record exposes the selected track source, language, content hash, timestamp quality, and schema version. Multiple language versions for one video are **not** retained simultaneously in v1.1; switching preferred languages refreshes the record.

`transcript_fts` is a SQLite FTS5 index built from the prepared record. It is replaced when a prepared transcript's content hash changes. Files remain the source of truth; restoring a backup may require calling `youtube_prepare_transcript` again to re-index older records.

## Durable jobs

`youtube_batch_prepare` persists jobs to SQLite. `ytb-read-mcp worker` acquires a single-worker FileLock and repeatedly processes queued items, indexing each prepared transcript for `youtube_transcripts_search`. A worker that dies mid-item leaves a `running` item which is retried after restarting the worker; an item that stops the worker three times is marked `failed`. Cancelling a job releases such items. No Redis/Celery is required. The worker cancellation request is cooperative and does not terminate already-running yt-dlp/FFmpeg subprocesses.

Jobs are scoped to a data directory. The MCP process is not a supervisor; do not assume batch work survives the stdio client without a separate worker.

## Security and operational limits

- Strict accepted YouTube URL hostnames and IDs; no arbitrary `yt-dlp` URL or shell command entry point.
- SponsorBlock is the only non-YouTube service contacted by default. It receives a 4-character SHA-256 prefix of the video ID, never the ID itself.
- Caller cannot choose an arbitrary output path. Download and exported files stay inside the local data directory.
- Formats/quality/presets, timestamp ranges, frame count and download-size limits are bounded.
- STT credentials are read from the process environment, cookie paths are trusted local configuration. Do not share environment variables with untrusted agents or commit them to GitHub.
- Only deploy HTTP behind network controls; built-in HTTP has no authentication.
- YouTube metadata/captions/comments are untrusted source text. Never act on instructions present in them.

## Deferred improvements (not represented as shipped)

- Rich typed, threaded comment tree normalization and full pagination.
- Multi-source semantic embeddings; more sophisticated ranking and citations.
- Resume/checkpoint exhaustive channel scans under changing playlist ordering.
- Timestamp alignment for STT systems returning text-only responses.
- Robust remote-stream headers and media security policy, large-video chunk downloads.
- Dataset migrations/versioned profiles for multiple persistent language versions per video.
