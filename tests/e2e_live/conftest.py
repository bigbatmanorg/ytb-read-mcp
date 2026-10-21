"""Fixtures for real stdio MCP verification.  No mocks or fake transports."""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from fastmcp import Client

from .sources import SOURCES


def _record_path() -> Path:
    root = Path(os.environ.get("YTB_E2E_RESULTS_DIR", "test-results"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "live-evidence.json"


@pytest.fixture(scope="session")
def evidence() -> dict:
    value = {
        "started_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "sources": SOURCES.__dict__,
        "calls": [],
    }
    yield value
    value["finished_at"] = datetime.now(UTC).isoformat()
    _record_path().write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


@pytest_asyncio.fixture
async def client(tmp_path_factory: pytest.TempPathFactory, evidence: dict):
    data_dir = tmp_path_factory.mktemp("ytb-live-data")
    env = dict(os.environ)
    env["YTB_DATA_DIR"] = str(data_dir)
    # The subprocess gets explicitly inherited STT values when the caller has
    # sourced .env; nothing reads or records their values here.
    config = {
        "mcpServers": {
            "youtube": {
                "command": sys.executable,
                "args": ["-m", "youtube_read_mcp.cli"],
                "env": env,
            }
        }
    }
    async with Client(config) as live_client:
        evidence["data_dir"] = str(data_dir)
        yield live_client


async def call(client: Client, evidence: dict, name: str, arguments: dict):
    """Call an actual server tool and retain redacted structured evidence."""
    result = await client.call_tool(name, arguments)
    evidence["calls"].append({"tool": name, "arguments": arguments, "is_error": result.is_error})
    assert not result.is_error, f"{name} failed: {result.content!r}"
    return result.data
