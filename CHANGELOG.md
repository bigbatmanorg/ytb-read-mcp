# Changelog

## 1.3.0 — 2026-11-03

### Added
- **Clickable timestamp links:** `url` fields such as `https://youtu.be/ID?t=323` on transcript search hits, FTS results, ranges, chapters, outline sections, heatmap peaks and frames.
- **`youtube_transcript_outline`:** the transcript grouped by chapter, falling back to description timestamps, then to fixed time windows. Each section has word count, reading time, preview or full text, and a link; the outline also returns overall stats and top terms.
- **`youtube_video_heatmap`:** the most replayed moments from YouTube's viewer heatmap, with the transcript text at each peak.
- **`youtube_sponsor_segments`:** SponsorBlock segments (sponsor, self-promotion, intro, outro, filler, …), looked up by hash prefix and cached for 24 hours.
- **`exclude_categories`** on `youtube_transcript_read`, `youtube_transcript_range` and the outline, to skip those segments.
- **Transcript stats** in manifests: word count, words per minute, reading minutes and caption coverage.
- **`YTB_SPONSORBLOCK_API`** setting.

### Changed
- Prepared transcript records now also store chapters and heatmap data.
- `youtube_transcript_read` and `youtube_transcript_range` are annotated as open-world, because they can consult SponsorBlock.
- SponsorBlock lookups retry once. If SponsorBlock stays unavailable, they fall back to the last cached result (`stale: true`), or else return a retryable `SPONSORBLOCK_UNAVAILABLE` error. Transcript reads with `exclude_categories` keep working and add a warning instead of failing.
- The CI `deterministic` job no longer runs the live e2e tests, which need network access to YouTube and SponsorBlock.

## 1.2.0 — 2026-11-03

### Fixed
- Transcripts prepared by the batch worker are now indexed for `youtube_transcripts_search`. Previously, only transcripts prepared through `youtube_prepare_transcript` were searchable.
- A job cancelled after some items finished now ends as `cancelled` instead of staying `running`.
- If a worker dies while processing an item of a cancelled job, that item is now released when a worker next runs.
- An item that stops the worker three times is now marked `failed` instead of blocking the queue forever. Existing databases gain an `attempts` column automatically.
- STT segment timestamps now use each audio chunk's real length. Previously they drifted when `STT_CHUNK_SECONDS` was below the 60 s minimum.
- `youtube_sync_source` now accepts bare playlist IDs.
- Channel URLs with non-Latin or percent-encoded `@handles` are now accepted.

### Changed
- The STT audio download now honours `YTB_MAX_DOWNLOAD_MB`.
- Transcript provenance no longer records the STT backend URL. That URL may name internal hosts or embed credentials.
- Every MCP tool now declares `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint` annotations.
- Documentation now matches the code:
  - `STT_CHUNK_SECONDS` defaults to 570.
  - The FTS table is named `transcript_fts`.
  - HTTP has no built-in authentication.
  - Install commands are pinned to release tags.

## 1.1.0 — 2026-10-22

First public version: 26 MCP tools for search, metadata, transcripts (captions with optional STT fallback), FTS5 search, media, frames, clips and durable batch jobs, over stdio or HTTP.
