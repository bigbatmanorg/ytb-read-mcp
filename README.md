# ytb-read-mcp

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/) [![MCP](https://img.shields.io/badge/MCP-stdio%20%2B%20HTTP-green)](https://modelcontextprotocol.io/) [![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Zero-config, local-first YouTube research MCP**, based on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FastMCP](https://gofastmcp.com/). YouTube search, video metadata, channel/playlist discovery, subtitles, transcript preparation/search/export, comments, downloads, frames, clips, optional speech recognition, and resumable batch transcript jobs.

No YouTube API key, login, hosted database, or separate service is required for the **basic stdio MCP**. Anonymous access is subject to YouTube availability and extractor challenges: the package includes the official Deno runtime and yt-dlp EJS support on supported platforms. Run `ytb-read-mcp doctor` if extraction fails. STT is **optional**, not bundled, and configured through environment variables.

> This is an independent third-party project. It is not affiliated with Google/YouTube. Only retrieve content you are permitted to access and use.

## 30-second start

**Run directly from GitHub, pinned to a release:**

```bash
uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0 ytb-read-mcp
```

**Install once:**

```bash
uv tool install git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0
# if the uv tool binaries directory is not on PATH:
uv tool update-shell
```

```bash
ytb-read-mcp              # MCP server, stdio, no console chatter
```

**Local checkout:**

```bash
git clone https://github.com/bigbatmanorg/ytb-read-mcp
cd ytb-read-mcp
uv sync
uv run ytb-read-mcp
```

The executable also has the compatibility alias `youtube-read-mcp`. Releases are listed on the [releases page](https://github.com/bigbatmanorg/ytb-read-mcp/releases); changes are in [CHANGELOG.md](CHANGELOG.md).

<!-- install:start -->
## Install in your agent

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_youtube-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=youtube&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/bigbatmanorg/ytb-read-mcp%40v1.3.0%22%2C%22ytb-read-mcp%22%5D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install_youtube-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=youtube&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/bigbatmanorg/ytb-read-mcp%40v1.3.0%22%2C%22ytb-read-mcp%22%5D%7D&quality=insiders)
[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=youtube&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJnaXQraHR0cHM6Ly9naXRodWIuY29tL2JpZ2JhdG1hbm9yZy95dGItcmVhZC1tY3BAdjEuMy4wIiwieXRiLXJlYWQtbWNwIl19)

It works with any MCP client that can start a stdio command. It needs [uv](https://docs.astral.sh/uv/). `uvx` fetches the pinned release, so no clone or virtualenv is needed. Pick your agent below.

No API key or configuration is needed. Optional speech-to-text and other settings are described in [Optional features by environment variable](#optional-features-by-environment-variable).


<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add youtube -s user -- uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0 ytb-read-mcp
```

</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>VS Code / GitHub Copilot</b></summary>

Use the button above, or add this to `.vscode/mcp.json` (workspace) or to the user `mcp.json` (command
*MCP: Open User Configuration*):

```json
{
  "servers": {
    "youtube": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Cursor</b></summary>

Use the button above, or add this to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Windsurf</b></summary>

Add this to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>OpenAI Codex CLI</b></summary>

```bash
codex mcp add youtube -- uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0 ytb-read-mcp
```

Or add this to `~/.codex/config.toml`:

```toml
[mcp_servers.youtube]
command = "uvx"
args = ["--from", "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0", "ytb-read-mcp"]
```

</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add this to `~/.gemini/settings.json` (or to `.gemini/settings.json` in a project):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>DeepAgents</b></summary>

**Deep Agents CLI:** add this to `~/.deepagents/.mcp.json` (all projects) or to `.mcp.json` in a project.

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

**Python library** (`pip install deepagents langchain-mcp-adapters`):

```python
import asyncio
import os

from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "youtube": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["--from", "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0", "ytb-read-mcp"],
    }
})


async def main():
    tools = await client.get_tools()
    agent = create_deep_agent(model="anthropic:claude-sonnet-5-5", tools=tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "What can you do?"}]})
    print(result["messages"][-1].content)


asyncio.run(main())
```

</details>

<details>
<summary><b>Docker Agent</b></summary>

Save this as `agent.yaml`, then run `docker agent run agent.yaml`:

```yaml
agents:
  root:
    model: anthropic/claude-sonnet-5-5
    description: Assistant with the youtube MCP tools
    instruction: Use the youtube tools to answer the user's requests.
    toolsets:
      - type: mcp
        command: uvx
        args:
          - "--from"
          - "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0"
          - "ytb-read-mcp"
```

</details>

<details>
<summary><b>Hermes Agent</b></summary>

Add this to `~/.hermes/config.yaml`, then run `/reload-mcp` in a chat:

```yaml
mcp_servers:
  youtube:
    command: uvx
    args: ["--from", "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0", "ytb-read-mcp"]
```

</details>

<details>
<summary><b>Cline / Roo Code / Kilo Code</b></summary>

MCP Servers → Configure (`cline_mcp_settings.json` / `mcp_settings.json`):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Zed</b></summary>

Add this to `settings.json`:

```json
{
  "context_servers": {
    "youtube": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>opencode</b></summary>

Add this to `opencode.json` (project) or `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "youtube": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0",
        "ytb-read-mcp"
      ],
      "enabled": true
    }
  }
}
```

</details>

<details>
<summary><b>Goose</b></summary>

Run `goose configure` → Add Extension → Command-line Extension, with the command `uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0 ytb-read-mcp`. Or add this to
`~/.config/goose/config.yaml`:

```yaml
extensions:
  youtube:
    type: stdio
    enabled: true
    cmd: uvx
    args: ["--from", "git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0", "ytb-read-mcp"]
```

</details>

<details>
<summary><b>Other clients, a permanent install, a local checkout</b></summary>

Most clients take the standard `mcpServers` JSON shown for Claude Desktop. Some use `servers` instead.

To install once instead of fetching on each start:

```bash
uv tool install git+https://github.com/bigbatmanorg/ytb-read-mcp@v1.3.0
```

then use `"command": "ytb-read-mcp"`, `"args": []`.

From a checkout: `"command": "uv"`, `"args": ["run", "--directory", "/abs/path/ytb-read-mcp", "ytb-read-mcp"]`.

</details>

<!-- install:end -->

Every tool declares MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) so clients can decide which calls need confirmation.

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

For deliberate re-transcription (for example, validating an STT provider when
YouTube has automatic captions), pass `force_stt: true` to
`youtube_prepare_transcript`. It bypasses caption tracks, requires configured
STT, and maintains a separate cache provenance from caption-derived text.

## Testing and diagnostics

```bash
uv run ytb-read-mcp test                         # built-in deterministic offline smoke test
uv sync --extra dev
uv run pytest -q                                 # deterministic test suite, no YouTube network calls
uv run ytb-read-mcp doctor                       # local dependencies and storage diagnostics
uv run ytb-read-mcp live-test                    # optional LIVE network test: may fail due to YouTube
./scripts/test-live.sh                           # real stdio MCP + YouTube core evidence
./scripts/test-live.sh --with-stt                # use ignored .env STT configuration
./scripts/test-installed.sh                      # build wheel and run through isolated uvx
```

For one-shot local verification run `./scripts/check.sh`. Live reports go in `test-results/` and redact secrets. **Offline unit/contract tests verify code deterministically, not whether YouTube is currently reachable**; a core live pass does not claim media, worker, Docker, HTTP, or STT coverage.

## Tools

29 MCP tools organized by purpose:

| Task | Tools |
|---|---|
| Discovery | `youtube_search`, `youtube_video_info`, `youtube_channel_info`, `youtube_channel_videos`, `youtube_channel_playlists`, `youtube_playlist_info`, `youtube_comments`, `youtube_video_chapters` |
| Timeline | `youtube_transcript_outline`, `youtube_video_heatmap`, `youtube_sponsor_segments` |
| Transcripts | `youtube_list_subtitles`, `youtube_prepare_transcript`, `youtube_transcript_manifest`, `youtube_transcript_read`, `youtube_transcript_search`, `youtube_transcripts_search`, `youtube_transcript_range`, `youtube_transcript_chunk`, `youtube_transcript_export` |
| Media | `youtube_media_formats`, `youtube_download`, `youtube_extract_frames`, `youtube_extract_clip` |
| Jobs | `youtube_batch_prepare`, `youtube_sync_source`, `youtube_job_status`, `youtube_job_cancel` |
| Diagnostics | `youtube_health` |

Tool descriptions contain usage instructions and are exposed through MCP. Three MCP prompts (`research_video`, `analyze_channel`, `analyze_video_visuals`) and cached resources are also provided. [Full usage guide](docs/tools.md).

## Timelines, highlights and clean transcripts

- **Clickable moments:** search hits, ranges, chapters, outline sections, heatmap peaks and frames include a `url` such as `https://youtu.be/ID?t=323`, so agents can cite moments that open at the right second.
- **Outline:** `youtube_transcript_outline` groups the transcript by chapter (YouTube chapters or description timestamps, else fixed time windows) with word counts, reading time, previews and top terms.
- **Stats:** `youtube_prepare_transcript` and `youtube_transcript_manifest` report word count, words per minute, reading minutes and caption coverage.
- **Most replayed:** `youtube_video_heatmap` returns the most rewatched moments from YouTube's viewer heatmap, with what was said there.
- **SponsorBlock:** `youtube_sponsor_segments` lists community-labelled sponsor reads, intros, outros and filler. The same categories can be passed as `exclude_categories` to `youtube_transcript_read`, `youtube_transcript_range` and the outline. Lookups send only a 4-character hash prefix of the video ID to [SponsorBlock](https://sponsor.ajay.app/) and are cached for 24 hours. Set `YTB_SPONSORBLOCK_API=""` to disable.

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
