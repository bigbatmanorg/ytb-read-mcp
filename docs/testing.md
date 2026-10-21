# Verification and release readiness

## Always run offline deterministic tests

```bash
./scripts/check.sh
```

This runs `uv sync --extra dev`, Python compilation, pytest, the built-in `ytb-read-mcp test`, and local health check. Tests should never download from YouTube. The built-in test is also runnable from an installed uv tool without installing developer extras.

### What offline tests can prove

- URL/ID validation and dangerous hostname rejection.
- Deterministic JSON3/VTT parsing and preferred caption-track order.
- Transcript caching, read pagination, timestamp ranges and exports.
- SQLite FTS5 lexical search, job creation/processing/cancellation/state.
- Stable MCP tool registration, expected tool names and typed input schemas.
- In-process MCP tool calls without YouTube network requests.

### What requires live verification

- YouTube accessibility, cookies/PO tokens/proxies, changing extractor format handling.
- Transcript availability for any particular video.
- FFmpeg codec/format compatibility and real media download/frame/clip generation.
- The specific remote STT service's API and audio-response behavior.

Explicit live test:

```bash
LIVE_TEST_VIDEO=dQw4w9WgXcQ LIVE_TEST_QUERY="science" ytb-read-mcp live-test
```

The live test currently checks metadata, search, transcript preparation and searchable text. It may fail without a supported JS runtime, in blocked regions, or if the source has no usable captions and STT is not configured. Its failure is not the same as deterministic code failure.

## MCP Inspector

For stdio-level protocol inspection (separate optional Node utility):

```bash
npx @modelcontextprotocol/inspector --cli ytb-read-mcp --method tools/list
```

Do not inject JSON debug output into server stdout. To exercise an MCP call, use Inspector's `tools/call` method with the desired tool name and arguments.

## Release steps

1. Run `./scripts/check.sh` with Python 3.12 and/or 3.13.
2. Inspect the CLI help, `doctor`, and stdio MCP `tools/list`.
3. Optionally run `live-test` on the target host and test STT/media separately if configured.
4. Confirm there are no `.env` files, keys, cookie files or downloaded media in the git repository.
5. Push to `bigbatmanorg/ytb-read-mcp`, then test the documented `uvx --from git+...` command.
6. Tag a release and pin a tag/commit in production client configs if you require reproducible deployments.
