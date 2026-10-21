# Live coverage matrix

This matrix is intentionally conservative: only a `PASS` recorded in a live
report counts as exercised. The current core suite passes health, search,
video metadata, subtitle listing, transcript preparation/manifest/read/range,
single/cross-transcript search, export, prompts, and stdio error recovery.

| Capability group | Current status |
| --- | --- |
| stdio protocol, prompts, tool catalog, health | PASS in `test_01_stdio_core.py` |
| metadata/search/captions/transcript persistence | PASS in `test_01_stdio_core.py` |
| configured STT fallback | NOT_RUN/FAIL until `YTB_TEST_STT_VIDEO` is verified captionless |
| channels, playlists, comments, chapters | NOT_RUN |
| media download, frames, clips | NOT_RUN |
| worker/jobs/source synchronization | NOT_RUN |
| HTTP, Docker, resources, concurrent clients | NOT_RUN |

The untested rows prevent an `ADVANCED VERIFIED` or `FULLY VERIFIED` claim.
