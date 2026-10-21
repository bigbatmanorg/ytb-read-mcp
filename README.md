# ytb-read-mcp

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/) [![MCP](https://img.shields.io/badge/MCP-stdio%20%2B%20HTTP-green)](https://modelcontextprotocol.io/) [![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Zero-config, local-first YouTube research MCP**, based on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FastMCP](https://gofastmcp.com/). YouTube search, video metadata, channel/playlist discovery, subtitles, transcript preparation/search/export, comments, downloads, frames, clips, optional speech recognition, and resumable batch transcript jobs.

No YouTube API key, login, hosted database, or separate service is required for the **basic stdio MCP**. Anonymous access is subject to YouTube availability and extractor challenges: the package includes the official Deno runtime and yt-dlp EJS support on supported platforms. Run `ytb-read-mcp doctor` if extraction fails. STT is **optional**, not bundled, and configured through environment variables.

> This is an independent third-party project. It is not affiliated with Google/YouTube. Only retrieve content you are permitted to access and use.

## 30-second start

**Run directly from GitHub (after you publish the repository):**

```bash
uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp ytb-read-mcp
```

**Install once:**

```bash
uv tool install git+https://github.com/bigbatmanorg/ytb-read-mcp
# if the uv tool binaries directory is not on PATH:
uv tool update-shell

```

```bash
ytb-read-mcp              # MCP server, stdio, no console chatter
```

**Local checkout (recommended before GitHub publication):**

```bash
unzip ytb-read-mcp.zip
cd ytb-read-mcp
uv sync
uv run ytb-read-mcp
```

The executable also has the compatibility alias `youtube-read-mcp`.

### MCP client configuration

Use this JSON in any MCP client that can spawn stdio commands (e.g. Copilot, Claude Desktop, Docker Agent) with the client's appropriate configuration wrapper:

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/bigbatmanorg/ytb-read-mcp", "ytb-read-mcp"]
    }
  }
}
```

If you installed it with `uv tool install`, simplify to `"command": "ytb-read-mcp"` and `"args": []`. Different clients may use `servers` instead of `mcpServers`; see their documentation.

**Before GitHub publication** this URL will not work unless the repository exists and contains this code. From a local checkout use `"command": "uv", "args": ["run", "--directory", "/absolute/path/ytb-read-mcp", "ytb-read-mcp"]` (or the installed absolute executable path).

## Optional features by environment variable

No config file required. Pass variables in the client's `env` object or export them before starting the MCP process.

```json
{
  "mcpServers": {
    "youtube": {
      "command": "ytb-read-mcp",
      "env": {
        "STT_BASE_URL": "http://stt:8080/v1",
        "STT_MODEL": "whisper-1",
        "STT_API_KEY": "optional-secret",
        "PREFERRED_LANGUAGES": "en,en-US,en-GB"
      }
    }
  }
}
```

When captions are missing and `STT_BASE_URL` is configured, the MCP downloads audio and calls the OpenAI-compatible `/audio/transcriptions` API. The API key is optional for local endpoints. STT is not silently required for normal usage. More variables are documented in [Configuration](docs/configuration.md).

## Testing and diagnostics

```bash
uv run ytb-read-mcp test                         # built-in deterministic offline smoke test
uv sync --extra dev
uv run pytest -q                                 # deterministic test suite, no YouTube network calls
uv run ytb-read-mcp doctor                       # local dependencies and storage diagnostics
uv run ytb-read-mcp live-test                    # optional LIVE network test: may fail due to YouTube
```

For one-shot local verification run `./scripts/check.sh`. CI runs the offline suite on Python 3.12 and 3.13. **Offline unit/contract tests verify code deterministically, not whether YouTube is currently reachable**; the live test is explicitly separate.

## Tools

26 MCP tools organized by purpose:

| Task | Tools |
|---|---|
| Discovery | `youtube_search`, `youtube_video_info`, `youtube_channel_info`, `youtube_channel_videos`, `youtube_channel_playlists`, `youtube_playlist_info`, `youtube_comments`, `youtube_video_chapters` |
| Transcripts | `youtube_list_subtitles`, `youtube_prepare_transcript`, `youtube_transcript_manifest`, `youtube_transcript_read`, `youtube_transcript_search`, `youtube_transcripts_search`, `youtube_transcript_range`, `youtube_transcript_chunk`, `youtube_transcript_export` |
| Media | `youtube_media_formats`, `youtube_download`, `youtube_extract_frames`, `youtube_extract_clip` |
| Jobs | `youtube_batch_prepare`, `youtube_sync_source`, `youtube_job_status`, `youtube_job_cancel` |
| Diagnostics | `youtube_health` |

Tool descriptions contain usage instructions and are exposed through MCP. Three MCP prompts (`research_video`, `analyze_channel`, `analyze_video_visuals`) and cached resources are also provided. [Full usage guide](docs/tools.md).

## Batch jobs (optional)

For large channel/playlist processing, **start an independent worker**, then submit batches from MCP:

```bash
ytb-read-mcp worker
```

The worker processes one item at a time and saves job/item states in SQLite. stdio alone does not keep work running after the client exits. Start one worker for each data directory; a lock prevents concurrent workers. See [Architecture](docs/architecture.md).

## HTTP mode and Docker (optional)

```bash
ytb-read-mcp serve --transport http --host 127.0.0.1 --port 8001
# Docker Compose includes both HTTP server and an independent worker.
docker compose up --build -d
```

HTTP binds localhost by default. If exposing HTTP beyond localhost, **put it behind authentication and network access controls**. Docker publishes to `127.0.0.1:8001` by default. No API authentication is implemented in this project.

## Project docs

- [Installation & troubleshooting](docs/installation.md)
- [Configuration reference](docs/configuration.md)
- [Tool catalog and workflows](docs/tools.md)
- [Design, caching and jobs](docs/architecture.md)
- [Testing and limitations](docs/testing.md)

## Attribution

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FastMCP](https://github.com/jlowin/fastmcp), [HTTPX](https://www.python-httpx.org/), FFmpeg and Python SQLite. Distributed under the [MIT License](LICENSE); dependencies retain their respective licenses.
