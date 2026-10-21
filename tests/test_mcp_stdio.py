"""Actual stdio JSON-RPC path; executed in CI with real FastMCP dependency."""
import sys

import pytest

fastmcp = pytest.importorskip("fastmcp", reason="FastMCP wheel unavailable in source-only environment")


@pytest.mark.asyncio
async def test_spawn_stdio_server_and_call_health(tmp_path):
    client=fastmcp.Client({
        "mcpServers": {
            "youtube": {
                "command": sys.executable,
                "args": ["-m", "youtube_read_mcp.cli"],
                "env": {"YTB_DATA_DIR": str(tmp_path)},
            }
        }
    })
    async with client:
        tools=await client.list_tools()
        tool=next((x for x in tools if x.name.endswith("youtube_health")),None)
        assert tool is not None
        result=await client.call_tool(tool.name,{})
        assert result.data["stdio_ready"] is True
        assert result.data["data_dir"] == str(tmp_path)
