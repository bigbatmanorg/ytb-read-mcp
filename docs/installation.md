# Installation and troubleshooting

## Requirements

- Python 3.12 or newer, [uv](https://docs.astral.sh/uv/)
- Network access to YouTube for live retrieval (not needed for deterministic tests)
- The package installs the **official Deno runtime** via its Python wheel on supported platforms, and `yt-dlp[default]` installs the matching EJS scripts. No separate runtime installation is normally needed. See [yt-dlp's EJS guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
- Optional: FFmpeg for downloads requiring merging, STT audio preparation, frames and clips
- Optional: a running OpenAI-compatible speech-to-text backend

### Immediate stdio use

```bash
# From local clone
uv sync
uv run ytb-read-mcp

# Once GitHub repo bigbatmanorg/ytb-read-mcp is published:
uvx --from git+https://github.com/bigbatmanorg/ytb-read-mcp ytb-read-mcp

# Install locally as a permanent uv tool:
uv tool install .
ytb-read-mcp
```

Use direct installed binary in your MCP client's `command`. For running from GitHub include the `uvx` args; no STT or configuration file is needed. Stdio communicates via stdout; never write logs/debug messages to stdout in a stdio MCP process.

### Copilot/Docker Agent and other MCP clients

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

This is the generic MCP schema. Copilot environments may require a different enclosing JSON key or agent-scoped YAML; follow the client's format, reusing the command and args unchanged.

To use an optional STT backend add `env` with `STT_BASE_URL`, `STT_MODEL`, and optionally `STT_API_KEY`. Avoid hardcoding credentials into a public repository.

### Verify

```bash
ytb-read-mcp test         # Deterministic local tests, no network
ytb-read-mcp doctor       # Dependencies, writable data, JS runtime
# From repo checkout:
./scripts/check.sh        # Full pytest and smoke-test suite
```

To validate the actual MCP protocol from a separately installed client:

```bash
npx @modelcontextprotocol/inspector --cli ytb-read-mcp --method tools/list
```

This requires Node/npm for Inspector only. No Node app or daemon is required by the MCP server itself.

### YouTube challenge failures

1. Upgrade the uv tool from its source (`uv tool upgrade ytb-read-mcp` for tools installed from a package index; reinstall/upgrade git source as appropriate).
2. Run `ytb-read-mcp doctor` and confirm `yt_dlp_ejs` and a JS runtime such as Deno are available.
3. Ensure network egress to YouTube; proxies/cookies can be passed as env vars.
4. If a video requires authenticated access, use a locally stored cookies.txt file via `YTB_COOKIE_FILE`. Be aware account cookies are security-sensitive and may create account/rate-limit risks.
5. Test with `ytb-read-mcp live-test`. Live tests can fail due to upstream changes or region-specific access, independently of deterministic package health.

### Docker

`docker compose up --build -d` starts an HTTP MCP server on **127.0.0.1:8001** and a worker. The image includes FFmpeg; the official Deno binary is installed with the Python dependencies. A Docker build requires network access to Docker, PyPI and Deno. Set host/proxy authentication outside the application before exposing HTTP publicly.

### Known limitations

- Some YouTube videos require authentication, region access, PO tokens or an updated yt-dlp version; no anonymous tool can guarantee universal access.
- STT response timestamps may be approximate when the backend only returns raw text.
- Channel/playlist pagination is best-effort because availability and yt-dlp extractor behavior vary.
- Media extraction can require substantial time/bandwidth. Offline deterministic tests do not prove successful media retrieval from YouTube.
- Batch jobs require a separate worker. Do not assume MCP stdio jobs survive client shutdown.
