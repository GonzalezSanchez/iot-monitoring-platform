"""MCP client for the project 1b tool surface (PRD §9).

Connects once (FastAPI lifespan) over streamable HTTP, discovers the tools, and
translates them to Anthropic tool dicts for the manual chat loop. No hand-written
httpx wrappers: the 7-tool allowlist lives in 1b, this side only mirrors it.
"""

import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Tuple

from anthropic.types import ToolParam
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent

logger = logging.getLogger(__name__)


def to_anthropic_tool(tool: Any) -> ToolParam:
    """Translate an MCP Tool (name/description/inputSchema) to the Anthropic shape."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


class MCPToolClient:
    """One long-lived MCP session per service instance."""

    def __init__(self, url: str):
        self.url = url
        self.session: ClientSession | None = None
        self.tools: List[ToolParam] = []
        self._stack: AsyncExitStack | None = None

    @property
    def connected(self) -> bool:
        return self.session is not None

    async def connect(self) -> None:
        self._stack = AsyncExitStack()
        try:
            read, write, _ = await self._stack.enter_async_context(
                streamablehttp_client(self.url)
            )
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.list_tools()
        except BaseException:
            await self._close_stack()
            raise
        self.session = session
        self.tools = [to_anthropic_tool(t) for t in result.tools]
        logger.info("MCP connected: %d tools: %s", len(self.tools), [t["name"] for t in self.tools])

    async def _close_stack(self) -> None:
        if self._stack is None:
            return
        try:
            await self._stack.aclose()
        except Exception as e:
            # The streamable HTTP transport can complain when torn down after a
            # failed connect; the session is unusable either way.
            logger.debug("MCP stack close after failure: %s", e)
        self._stack = None

    async def close(self) -> None:
        await self._close_stack()
        self.session = None
        self.tools = []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """Call an MCP tool; returns (text content, is_error)."""
        assert self.session is not None, "MCP session not connected"
        result = await self.session.call_tool(name, arguments)
        parts = [
            block.text for block in result.content if isinstance(block, TextContent)
        ]
        text = "\n".join(parts) if parts else str(result.content)
        return text, bool(result.isError)
