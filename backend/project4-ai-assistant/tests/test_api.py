"""API tests — contract: docs/project4-prd.md §12 (API), error matrix §11."""

import pytest
from fastapi.testclient import TestClient

import config
import main
from conftest import FakeMCP


async def fake_chat(client, mcp, messages):
    yield {"type": "token", "content": "Hi"}
    yield {"type": "done"}


async def no_connect(self):
    raise RuntimeError("no MCP server in tests")


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(main, "chat", fake_chat)
    # A real connect attempt wrecks the TestClient event loop (anyio task
    # group teardown) — fail cleanly in the lifespan, then inject a fake.
    monkeypatch.setattr(main.MCPToolClient, "connect", no_connect)
    with TestClient(main.app) as client:
        client.app.state.mcp = FakeMCP()
        yield client


def chat_body(content="Which rooms are there?"):
    return {"messages": [{"role": "user", "content": content}]}


def test_health_returns_200(api):
    response = api.get("/ai/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_streams_sse(api):
    response = api.post(
        "/ai/chat", json=chat_body(), headers={"CF-Connecting-IP": "1.1.1.1"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token", "content": "Hi"}' in response.text
    assert 'data: {"type": "done"}' in response.text


def test_rate_limit_keys_on_cf_connecting_ip(api):
    # The 6th request within a minute from the same CF-Connecting-IP hits 429.
    for i in range(config.RATE_LIMIT_PER_MINUTE):
        response = api.post(
            "/ai/chat", json=chat_body(), headers={"CF-Connecting-IP": "2.2.2.2"}
        )
        assert response.status_code == 200, f"request {i + 1} should pass"

    response = api.post(
        "/ai/chat", json=chat_body(), headers={"CF-Connecting-IP": "2.2.2.2"}
    )
    assert response.status_code == 429

    # A different CF-Connecting-IP (same socket address) still gets through —
    # proof the limiter reads the header, not the connection (§Security).
    response = api.post(
        "/ai/chat", json=chat_body(), headers={"CF-Connecting-IP": "3.3.3.3"}
    )
    assert response.status_code == 200


def test_empty_messages_rejected(api):
    response = api.post(
        "/ai/chat",
        json={"messages": []},
        headers={"CF-Connecting-IP": "4.4.4.4"},
    )
    assert response.status_code == 422


def test_oversized_message_rejected(api):
    response = api.post(
        "/ai/chat",
        json=chat_body("x" * (config.MAX_INPUT_CHARS + 1)),
        headers={"CF-Connecting-IP": "5.5.5.5"},
    )
    assert response.status_code == 422
