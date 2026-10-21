"""Executed with the real FastMCP package when normal uv dev sync is available."""

import pytest

fastmcp = pytest.importorskip("fastmcp", reason="FastMCP wheel unavailable in source-only environment")


@pytest.mark.asyncio
async def test_mcp_descriptions_and_health():
    from youtube_read_mcp.server import mcp

    async with fastmcp.Client(mcp) as client:
        tools = await client.list_tools()
        assert len(tools) >= 26
        for tool in tools:
            assert len(tool.description or "") >= 65, tool.name
            assert tool.input_schema.get("type") == "object", tool.name
        result = await client.call_tool("youtube_health", {})
        assert result.data["stdio_ready"] is True


@pytest.mark.asyncio
async def test_agent_prompts_registered():
    from youtube_read_mcp.server import mcp

    async with fastmcp.Client(mcp) as client:
        prompts = await client.list_prompts()
        assert {"research_video", "analyze_channel", "analyze_video_visuals"} <= {x.name for x in prompts}
