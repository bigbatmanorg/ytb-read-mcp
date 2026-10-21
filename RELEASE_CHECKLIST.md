# Release checklist

## Evidence recorded on 2026-10-21 UTC

- [x] `./scripts/check.sh` passed: deterministic suite, built-in offline MCP
  self-test, local dependency checks, and SQLite FTS5 checks.
- [x] `./scripts/test-installed.sh` passed against the freshly built
  `ytb_read_mcp-1.1.0-py3-none-any.whl` in an isolated `uvx` environment.
- [x] Real stdio MCP core verification passed. Evidence:
  `test-results/2026-10-21T231018Z/report.json` (exit code 0).
- [x] Real configured STT verification passed using `sd5NHYqxDXo` with
  `force_stt=true`: actual YouTube audio download, bounded WAV chunking,
  configured OpenAI-compatible STT request, persisted transcript, and cache
  reuse all completed successfully. The report contains no credentials.
- [x] The STT chunk default is 570 seconds, safely below this provider's 25 MiB
  upload limit and strict 600-second decoded-audio limit.

## Required before claiming advanced or full verification

- [x] Run and record real positive tests for channel/playlist/comment/chapters
  using validated current public fixtures.
- [x] Run and record real FFmpeg media download, frames, and clip verification.
- [x] Run and record worker/job, source-sync, cancellation, and worker
  interruption/restart-recovery verification.
- [x] Run and record HTTP transport, MCP resource, prompt, and concurrent-client
  verification.
- [x] Build and run the Docker image through a real MCP client, including
  persistence across container recreation.
- [~] Cross-platform verification deferred by the user; it is not a blocker for
  this Linux release pass.
- [x] Confirm `.env` and `test-results/` are ignored; no cookies or downloaded
  artifacts are tracked.
- [x] Review the full working-tree diff and commit intended changes. Rerun the
  applicable checks on the exact release commit before publishing.

## Release decision

**ADVANCED VERIFIED on Linux x86-64 with configured STT.** Cross-platform
execution is explicitly deferred by the user. Do not label this release **FULLY
VERIFIED** until cross-platform evidence is added.

No release, tag, or push is authorized by this checklist.
