# Live coverage matrix

Only a `PASS` recorded in a live report counts as exercised. The last full run
was `./scripts/test-live.sh --with-stt --with-media --with-jobs --with-http` on
2026-11-03 against v1.3.0 (Linux x86-64, Python 3.14) with a LiteLLM `whisper-1` STT backend: 10 passed.

| Capability group | Status | Test |
| --- | --- | --- |
| stdio protocol, prompts, tool catalog, health | PASS | `test_01_stdio_core.py` |
| metadata, search, captions, transcript lifecycle and export | PASS | `test_01_stdio_core.py` |
| error recovery without killing the stdio session | PASS | `test_01_stdio_core.py` |
| channels, playlists, comments, chapters, resources, prompts | PASS | `test_03_discovery_resources.py` |
| media download, frames, clips | PASS | `test_04_media.py` |
| worker jobs, FTS indexing of batch transcripts, source sync, cancellation, restart recovery, concurrent clients | PASS | `test_05_jobs_http.py` |
| Streamable HTTP transport | PASS | `test_05_jobs_http.py` |
| transcript stats, chapter outline, heatmap peaks, SponsorBlock segments and exclusion, timestamp links | PASS | `test_06_insights.py` |
| configured STT fallback, cache reuse, multi-chunk (60 s) timestamp offsets | PASS | `test_02_optional_stt.py` |
| Docker image, macOS, Windows | NOT_RUN | — |
