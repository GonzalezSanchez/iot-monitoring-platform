"""The agentic chat loop (PRD §9).

A hand-written bounded loop instead of the SDK's tool_runner: the tool runner
only returns complete messages, and /ai/chat streams token by token. Each yield
is one SSE event dict (schema: PRD §10).
"""

from typing import Any, AsyncGenerator, Dict, List, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolResultBlockParam

import config
from mcp_client import MCPToolClient


async def chat(
    client: AsyncAnthropic,
    mcp: MCPToolClient,
    messages: List[MessageParam],
) -> AsyncGenerator[Dict[str, Any], None]:
    system_prompt = config.load_brain_prompt()
    conversation: List[MessageParam] = list(messages[-config.MAX_HISTORY_MESSAGES :])

    for _ in range(config.MAX_STEPS):
        async with client.messages.stream(
            model=config.MODEL,
            system=system_prompt,
            max_tokens=config.MAX_TOKENS,
            tools=mcp.tools,
            messages=conversation,
        ) as stream:
            async for text in stream.text_stream:
                yield {"type": "token", "content": text}
            response = await stream.get_final_message()

        conversation.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            yield {"type": "done"}
            return

        tool_results: List[ToolResultBlockParam] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool_use", "name": block.name}
            text, is_error = await mcp.call_tool(block.name, cast(Dict[str, Any], block.input))
            result: ToolResultBlockParam = {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": text,
            }
            if is_error:
                result["is_error"] = True
            tool_results.append(result)
        conversation.append({"role": "user", "content": tool_results})

    yield {
        "type": "error",
        "code": "step_limit_reached",
        "message": "Reached the maximum number of steps for this answer.",
    }
