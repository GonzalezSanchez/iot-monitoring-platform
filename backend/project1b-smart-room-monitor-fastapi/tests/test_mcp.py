"""
MCP mount tests (project 4a) — contract: docs/project4-prd.md §6.

The tool-set test is the security regression test: if it fails, a writing
route (or an unreviewed new route) is exposed to the LLM.
"""

from fastapi.testclient import TestClient

import main

EXPECTED_TOOLS = {
    "get_rooms",
    "get_room",
    "get_room_events",
    "get_events",
    "get_lakehouse_summary",
    "get_lakehouse_anomalies",
    "get_lakehouse_rooms",
}

# Routes as they existed before the MCP mount (path, method) — /mcp must not
# show up here: it is not part of the public API surface.
EXPECTED_ROUTES = {
    ("/health", "get"),
    ("/events", "get"),
    ("/events", "post"),
    ("/rooms", "get"),
    ("/rooms/{room_id}", "get"),
    ("/rooms/{room_id}/events", "get"),
    ("/lakehouse/summary", "get"),
    ("/lakehouse/anomalies", "get"),
    ("/lakehouse/rooms", "get"),
}


def test_tool_set_is_exactly_the_allowlist():
    tool_names = {tool.name for tool in main.mcp.tools}
    assert tool_names == EXPECTED_TOOLS
    assert "create_event" not in tool_names


def test_mcp_endpoint_answers_initialize():
    with TestClient(main.app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert response.status_code == 200


def test_existing_routes_unchanged():
    schema = main.app.openapi()
    routes = {
        (path, method)
        for path, operations in schema["paths"].items()
        for method in operations
    }
    assert routes == EXPECTED_ROUTES
