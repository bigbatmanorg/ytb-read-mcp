"""Single source of config. Basic MCP needs no env vars, API keys or config files."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _data_dir() -> Path:
    explicit = os.getenv("YTB_DATA_DIR") or os.getenv("DATA_DIR")
    if explicit:
        return Path(explicit).expanduser()
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "ytb-read-mcp"
    return Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "ytb-read-mcp"


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: _int("YTB_PORT", _int("PORT", 8001)))
    host: str = field(default_factory=lambda: os.getenv("YTB_HOST", "127.0.0.1"))
    data_dir: Path = field(default_factory=_data_dir)
    stt_base_url: str = field(default_factory=lambda: os.getenv("STT_BASE_URL", "").rstrip("/"))
    stt_api_key: str = field(default_factory=lambda: os.getenv("STT_API_KEY", ""))
    stt_model: str = field(default_factory=lambda: os.getenv("STT_MODEL", "whisper-1"))
    stt_timeout_seconds: int = field(default_factory=lambda: _int("STT_TIMEOUT_SECONDS", 180))
    stt_chunk_seconds: int = field(default_factory=lambda: _int("STT_CHUNK_SECONDS", 900))
    transcript_chunk_seconds: int = field(default_factory=lambda: _int("TRANSCRIPT_CHUNK_SECONDS", 600))
    transcript_max_chars: int = field(default_factory=lambda: _int("TRANSCRIPT_MAX_CHARS", 14000))
    cache_max_age_hours: int = field(default_factory=lambda: _int("TRANSCRIPT_CACHE_MAX_AGE_HOURS", 0))
    preferred_languages_raw: str = field(default_factory=lambda: os.getenv("PREFERRED_LANGUAGES", "en,en-US,en-GB"))
    cookie_file: str = field(default_factory=lambda: os.getenv("YTB_COOKIE_FILE", ""))
    proxy: str = field(default_factory=lambda: os.getenv("YTB_PROXY", ""))
    js_runtime: str = field(default_factory=lambda: os.getenv("YTB_JS_RUNTIME", "auto"))
    max_download_mb: int = field(default_factory=lambda: _int("YTB_MAX_DOWNLOAD_MB", 1024))
    max_disk_mb: int = field(default_factory=lambda: _int("YTB_MAX_DISK_MB", 4096))
    worker_poll_seconds: int = field(default_factory=lambda: _int("YTB_WORKER_POLL_SECONDS", 2))

    @property
    def transcript_dir(self) -> Path:
        path = self.data_dir / "transcripts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def media_dir(self) -> Path:
        path = self.data_dir / "media"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def temp_dir(self) -> Path:
        path = self.data_dir / "tmp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "ytb-read.sqlite3"

    @property
    def preferred_languages(self) -> list[str]:
        return [x.strip() for x in self.preferred_languages_raw.split(",") if x.strip()]


settings = Settings()
