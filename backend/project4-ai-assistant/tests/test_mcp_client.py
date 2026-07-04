"""MCP client tests — tool discovery and translation (docs/project4-prd.md §9)."""

from types import SimpleNamespace

import mcp_client
from mcp_client import MCPToolClient, to_anthropic_tool

# The 4a allowlist (docs/project4-prd.md §4) — what discovery must yield
ALLOWLIST = {
    "get_rooms",
    "get_room",
    "get_room_events",
    "get_events",
    "get_lakehouse_summary",
    "get_lakehouse_anomalies",
    "get_lakehouse_rooms",
}


def mcp_tool(name):
    return SimpleNamespace(
        name=name,
        description=f"Tool {name}",
        inputSchema={"type": "object", "properties": {}},
    )


class FakeCM:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, tools, call_result=None):
        self._tools = tools
        self._call_result = call_result
        self.initialized = False

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        return SimpleNamespace(tools=self._tools)

    async def call_tool(self, name, arguments):
        return self._call_result


def test_to_anthropic_tool_translates_schema():
    tool = mcp_tool("get_rooms")
    assert to_anthropic_tool(tool) == {
        "name": "get_rooms",
        "description": "Tool get_rooms",
        "input_schema": {"type": "object", "properties": {}},
    }


async def test_connect_discovers_the_allowlist(monkeypatch):
    session = FakeSession([mcp_tool(n) for n in sorted(ALLOWLIST)])
    monkeypatch.setattr(
        mcp_client, "streamablehttp_client", lambda url: FakeCM((None, None, None))
    )
    monkeypatch.setattr(mcp_client, "ClientSession", lambda r, w: FakeCM(session))

    client = MCPToolClient("http://backend:8000/mcp")
    await client.connect()

    assert client.connected
    assert session.initialized
    assert {t["name"] for t in client.tools} == ALLOWLIST


async def test_call_tool_extracts_text_and_error_flag(monkeypatch):
    from mcp.types import TextContent

    result = SimpleNamespace(
        content=[
            TextContent(type="text", text='{"rooms": []}'),
            SimpleNamespace(type="other"),
        ],
        isError=False,
    )
    session = FakeSession([], call_result=result)
    client = MCPToolClient("http://backend:8000/mcp")
    client.session = session

    text, is_error = await client.call_tool("get_rooms", {})
    assert text == '{"rooms": []}'
    assert is_error is False
