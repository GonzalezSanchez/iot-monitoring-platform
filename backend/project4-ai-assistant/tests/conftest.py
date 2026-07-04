import os
from types import SimpleNamespace

import pytest

# Set before any src import: the app fails fast without a key (PRD §13), and
# the MCP URL must refuse connections instantly instead of timing out.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ["MCP_SERVER_URL"] = "http://127.0.0.1:1/mcp"


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name, block_id="tu_1", tool_input=None):
    return SimpleNamespace(type="tool_use", name=name, id=block_id, input=tool_input or {})


def final_message(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class FakeStream:
    """Mimics the SDK's messages.stream() context manager."""

    def __init__(self, texts, final):
        self._texts = texts
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def text_stream(self):
        async def gen():
            for t in self._texts:
                yield t

        return gen()

    async def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, turns, repeat_last=False):
        self.turns = list(turns)
        self.repeat_last = repeat_last
        self.calls = []

    def stream(self, **kwargs):
        # Snapshot: chat() mutates the messages list after this call
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if len(self.turns) > 1 or not self.repeat_last:
            return self.turns.pop(0)
        return self.turns[0]


class FakeAnthropic:
    def __init__(self, turns, repeat_last=False):
        self.messages = FakeMessages(turns, repeat_last=repeat_last)


class FakeMCP:
    def __init__(self, tools=None, result=("{}", False)):
        self.tools = tools or [
            {"name": "get_rooms", "description": "", "input_schema": {"type": "object"}}
        ]
        self.calls = []
        self._result = result
        self.session = object()

    @property
    def connected(self):
        return True

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._result

    async def close(self):
        pass


async def collect(agen):
    return [event async for event in agen]


@pytest.fixture
def fake_mcp():
    return FakeMCP()
