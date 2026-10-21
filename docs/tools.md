# Tool catalog and agent workflows

The MCP server advertises detailed docstrings as tool descriptions, tool parameter JSON schemas, shared instructions, resources and prompts.

## Tools by workflow

**Discovery:** `youtube_search`, `youtube_video_info`, `youtube_channel_info`, `youtube_channel_videos`, `youtube_channel_playlists`, `youtube_playlist_info`, `youtube_video_chapters`, `youtube_comments`.

**Transcripts:** `youtube_list_subtitles`, `youtube_prepare_transcript`, `youtube_transcript_manifest`, `youtube_transcript_search`, `youtube_transcripts_search`, `youtube_transcript_read`, `youtube_transcript_range`, `youtube_transcript_chunk` (legacy), `youtube_transcript_export`.

**Media:** `youtube_media_formats`, `youtube_download`, `youtube_extract_frames`, `youtube_extract_clip`.

**Batch:** `youtube_batch_prepare`, `youtube_sync_source`, `youtube_job_status`, `youtube_job_cancel`.

**Diagnostics:** `youtube_health`.

### Find and analyze one video

1. Search with `youtube_search(query,limit)`; resolve the selected `video_id`.
2. Get metadata using `youtube_video_info(video)`, optionally with `full=true` for chapters and tags.
3. Prepare with `youtube_prepare_transcript(video)`. It uses cached captions and only uses configured STT if captions are unavailable.
4. Inspect `youtube_transcript_manifest` to check language, source, `timing_quality`, and number of chunks.
5. For specific questions, call `youtube_transcript_search(video,query)` then `youtube_transcript_range(video,start_seconds,end_seconds)`. For all content, paginate `youtube_transcript_read(video,cursor,max_chars)` until `complete=true`.
6. Treat timestamp citations as approximate when `timing_quality=stt_chunk_approximate`.

### Work with videos, Shorts, and streams

Call `youtube_channel_videos(channel_url,tab="videos")`, then repeat for `shorts` or `streams`. Paginate with `next_offset`; pages may be shorter than expected, and the total is not authoritative. `youtube_channel_playlists` lists playlists, then `youtube_playlist_info` pages through their video IDs.

### Frame-based visual analysis

Call `youtube_video_chapters` or search a transcript to find relevant times. Then call `youtube_extract_frames(video,timestamps=[120,365,750],width=640)`. The tool returns local JPG paths; have your calling vision-capable agent open/analyze those images. Never imply that frame extraction itself interprets images.

### Batch channel-processing loop

1. Page `youtube_sync_source` to find new IDs.
2. Submit wanted videos with `youtube_batch_prepare(videos)`; start `ytb-read-mcp worker` as a separate process first.
3. Poll `youtube_job_status(job_id)` until completed/partial/failed/cancelled. Failures are item-scoped.
4. Read the cached results with transcript tools. Repeated `youtube_prepare_transcript` calls reuse cache when matching preferred languages.

### MCP prompts/resources

Prompts: `research_video`, `analyze_channel`, `analyze_video_visuals`.

Resources: `youtube://transcript/{video_id}` (cached manifest), `youtube://video/{video_id}` (cached metadata). A resource read never performs a live network request. Not all MCP clients expose prompts/resources in their UI; tools always remain available.

### Return format and completeness

- Long transcript tool output is bounded; `youtube_transcript_read` returns `cursor`, `next_cursor`, `complete`, and segment totals.
- `youtube_transcripts_search` uses SQLite FTS5 lexical search, not semantic embeddings. It indexes prepared transcripts.
- Channel/playlist `has_more` means another page **may** exist; it is a continuation hint rather than a verified total.
- Search results from yt-dlp are live and not guaranteed exhaustive.
- Media tools write only under the configured data directory and return a host-local path, not a publicly reachable URL.
