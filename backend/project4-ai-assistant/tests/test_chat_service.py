"""Chat loop tests — contract: docs/project4-prd.md §12 (chat service)."""

import config
from chat_service import chat
from conftest import (
    FakeAnthropic,
    FakeMCP,
    FakeStream,
    collect,
    final_message,
    text_block,
    tool_use_block,
)

USER = {"role": "user", "content": "Which rooms are there?"}


async def test_text_only_turn_streams_tokens_then_done(fake_mcp):
    client = FakeAnthropic(
        [FakeStream(["Hel", "lo"], final_message("end_turn", [text_block("Hello")]))]
    )
    events = await collect(chat(client, fake_mcp, [USER]))
    assert events == [
        {"type": "token", "content": "Hel"},
        {"type": "token", "content": "lo"},
        {"type": "done"},
    ]


async def test_tool_use_turn_calls_mcp_and_continues():
    mcp = FakeMCP(result=('[{"room_id": "conf-a1"}]', False))
    turn1 = FakeStream(
        [],
        final_message(
            "tool_use",
            [tool_use_block("get_rooms", block_id="tu_42", tool_input={"limit": 5})],
        ),
    )
    turn2 = FakeStream(
        ["There is one room."],
        final_message("end_turn", [text_block("There is one room.")]),
    )
    client = FakeAnthropic([turn1, turn2])

    events = await collect(chat(client, mcp, [USER]))

    assert {"type": "tool_use", "name": "get_rooms"} in events
    assert events[-1] == {"type": "done"}
    # The exact tool name and arguments Claude produced reach the MCP session
    assert mcp.calls == [("get_rooms", {"limit": 5})]
    # The second API call got the tool result fed back, matched by tool_use_id
    second_call_messages = client.messages.calls[1]["messages"]
    tool_results = second_call_messages[-1]["content"]
    assert tool_results[0]["tool_use_id"] == "tu_42"
    assert tool_results[0]["content"] == '[{"room_id": "conf-a1"}]'


async def test_history_is_capped_before_first_call(fake_mcp):
    client = FakeAnthropic(
        [FakeStream(["ok"], final_message("end_turn", [text_block("ok")]))]
    )
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(10)
    ]
    await collect(chat(client, fake_mcp, history))
    sent = client.messages.calls[0]["messages"]
    assert len(sent) == config.MAX_HISTORY_MESSAGES
    assert sent[0]["content"] == f"msg {10 - config.MAX_HISTORY_MESSAGES}"


async def test_step_limit_stops_endless_tool_use(fake_mcp):
    endless_tool_turn = FakeStream(
        [], final_message("tool_use", [tool_use_block("get_rooms")])
    )
    client = FakeAnthropic([endless_tool_turn], repeat_last=True)

    events = await collect(chat(client, fake_mcp, [USER]))

    assert len(client.messages.calls) == config.MAX_STEPS
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "step_limit_reached"
