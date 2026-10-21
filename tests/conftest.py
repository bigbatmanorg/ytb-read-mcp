"""Test support for source-only environments without downloaded runtime wheels.

When yt-dlp is installed, the REAL installed module is used. Otherwise a no-network
import shim permits deterministic pure-function tests only. This shim is not shipped
in the installable package, and cannot be used to validate live yt-dlp behavior.
"""

import importlib.util
import sys
import types

if importlib.util.find_spec("yt_dlp") is None:
    package = types.ModuleType("yt_dlp")
    package.__path__ = []
    version = types.ModuleType("yt_dlp.version")
    version.__version__ = "test-only-no-yt-dlp"

    class UnavailableYoutubeDL:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("This source-only test environment has no yt-dlp installed")

    package.YoutubeDL = UnavailableYoutubeDL
    package.version = version
    sys.modules["yt_dlp"] = package
    sys.modules["yt_dlp.version"] = version
