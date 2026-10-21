"""Curated public sources for LIVE tests.

Every test validates the feature it uses at runtime.  Overrides make a changed
YouTube fixture an explicit, reproducible configuration choice rather than a
hidden fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Sources:
    # This long-standing public music video is small, public, and has English
    # manual captions.  It is intentionally not used to assert a fixed title.
    video: str = os.getenv("YTB_TEST_VIDEO", "dQw4w9WgXcQ")
    caption_video: str = os.getenv("YTB_TEST_CAPTION_VIDEO", "dQw4w9WgXcQ")
    media_video: str = os.getenv("YTB_TEST_MEDIA_VIDEO", "dQw4w9WgXcQ")
    # Me at the zoo is a short public candidate normally without subtitle tracks.
    stt_video: str = os.getenv("YTB_TEST_STT_VIDEO", "jNQXAC9IVRw")
    channel: str = os.getenv("YTB_TEST_CHANNEL", "https://www.youtube.com/@RickAstleyYT")
    playlist_channel: str = os.getenv("YTB_TEST_PLAYLIST_CHANNEL", "https://www.youtube.com/@freecodecamp")
    playlist: str = os.getenv("YTB_TEST_PLAYLIST", "")


SOURCES = Sources()
