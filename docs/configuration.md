# Configuration reference

**No configuration is needed for ordinary stdio usage.** The server starts without STT, credentials, HTTP, or pre-created directories. Environment overrides are read when the MCP process starts, not on every call.

| Variable | Default | Effect |
|---|---|---|
| `YTB_DATA_DIR` | XDG data dir (`~/.local/share/ytb-read-mcp` on Linux) | SQLite, cached transcripts and downloaded files |
| `DATA_DIR` | unset | Legacy alternative to `YTB_DATA_DIR` |
| `YTB_HOST` | `127.0.0.1` | HTTP listen host |
| `YTB_PORT` / `PORT` | `8001` | HTTP port |
| `PREFERRED_LANGUAGES` | `en,en-US,en-GB` | Preferred caption order |
| `STT_BASE_URL` | unset | OpenAI-compatible API base ending in `/v1`; enables STT fallback |
| `STT_API_KEY` | unset | Optional token; never included in MCP results |
| `STT_MODEL` | `whisper-1` | Model name passed to transcription API |
| `STT_TIMEOUT_SECONDS` | `180` | Per STT request timeout |
| `STT_CHUNK_SECONDS` | `900` | Audio split length (seconds) |
| `TRANSCRIPT_CHUNK_SECONDS` | `600` | Duration-based transcript chunking |
| `TRANSCRIPT_MAX_CHARS` | `14000` | Char target for prepared chunks |
| `TRANSCRIPT_CACHE_MAX_AGE_HOURS` | `0` | 0 = indefinite; otherwise refresh when old |
| `YTB_COOKIE_FILE` | unset | Local Netscape cookies.txt path |
| `YTB_PROXY` | unset | yt-dlp proxy URL |
| `YTB_JS_RUNTIME` | `auto` | `auto`, `deno`, `node`, `quickjs`; auto picks installed runtime |
| `YTB_MAX_DOWNLOAD_MB` | `1024` | Media download upper bound |
| `YTB_MAX_DISK_MB` | `4096` | Guard against excessive cached media |
| `YTB_WORKER_POLL_SECONDS` | `2` | Idle job-worker polling interval |

## Example local STT

```bash
STT_BASE_URL=http://localhost:8080/v1 \
STT_MODEL=whisper-1 \
ytb-read-mcp
```

For locally installed STT backends that do not require a key, omit `STT_API_KEY`. For restricted backends, add it as an environment variable in your MCP client's environment rather than committing it to source code.

## Data and credentials

- Secrets remain in process environment or a local cookie file; tool handlers never expose a 'set cookies' tool.
- SQLite runs with WAL mode. One durable worker per data directory; stdio clients can share that directory for reads.
- Only the configured artifact root is writable by media tools. Do not set that root to a sensitive folder.
- Stdio tool and artifact paths refer to the MCP **host machine/container**. A remote agent cannot automatically open a local file in a different container unless volumes are shared.
- Use `YTB_DATA_DIR` to share storage between MCP and a worker. On multi-host use a shared path or run worker on the same machine as data; SQLite on unreliable network filesystems is not recommended.
