# Live coverage matrix

Only a `PASS` recorded in a live report counts as exercised. The last full run
was `./scripts/test-live.sh --with-media --with-jobs --with-http` on
2026-11-03 against v1.2.0 (Linux x86-64, Python 3.14), with 7 passed and 1 not run.

| Capability group | Status | Test |
| --- | --- | --- |
| stdio protocol, prompts, tool catalog, health | PASS | `test_01_stdio_core.py` |
| metadata, search, captions, transcript lifecycle and export | PASS | `test_01_stdio_core.py` |
| error recovery without killing the stdio session | PASS | `test_01_stdio_core.py` |
| channels, playlists, comments, chapters, resources, prompts | PASS | `test_03_discovery_resources.py` |
| media download, frames, clips | PASS | `test_04_media.py` |
| worker jobs, FTS indexing of batch transcripts, source sync, cancellation, restart recovery, concurrent clients | PASS | `test_05_jobs_http.py` |
| Streamable HTTP transport | PASS | `test_05_jobs_http.py` |
| configured STT fallback | NOT_RUN: needs an STT backend (`--with-stt`) | `test_02_optional_stt.py` |
| Docker image, macOS, Windows | NOT_RUN | — |
