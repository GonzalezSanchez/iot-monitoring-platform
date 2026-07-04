import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, List, Literal, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic
from anthropic.types import MessageParam
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import config
from chat_service import chat
from mcp_client import MCPToolClient

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    """Rate-limit key. All traffic arrives via the Cloudflare tunnel, so the
    socket address is always the same — key on CF-Connecting-IP instead
    (docs/project4-llm-mcp.md §Security)."""
    return request.headers.get("CF-Connecting-IP") or get_remote_address(request)


limiter = Limiter(key_func=client_ip)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error(
            "ANTHROPIC_API_KEY is not set — the AI assistant cannot start. "
            "Add it to .env.prod (production) or .env (local)."
        )
        raise RuntimeError("ANTHROPIC_API_KEY missing")

    app.state.anthropic = anthropic.AsyncAnthropic(
        timeout=config.CLAUDE_TIMEOUT_SECONDS
    )
    app.state.mcp = MCPToolClient(config.MCP_SERVER_URL)
    try:
        await app.state.mcp.connect()
    except Exception as e:
        # Service still starts; /ai/chat answers 503 until 1b is reachable.
        logger.warning("MCP connect to %s failed: %s", config.MCP_SERVER_URL, e)

    yield

    await app.state.mcp.close()
    await app.state.anthropic.close()


app = FastAPI(title="AI Assistant", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
# slowapi's handler signature is narrower than Starlette's protocol expects
app.add_exception_handler(RateLimitExceeded, cast(Callable, _rate_limit_exceeded_handler))


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=config.MAX_INPUT_CHARS)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(min_length=1)


@app.get("/ai/health")
async def health(request: Request):
    return {
        "status": "ok",
        "service": "ai-assistant",
        "mcp_connected": request.app.state.mcp.connected,
    }


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/ai/chat")
@limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute;{config.RATE_LIMIT_PER_DAY}/day")
async def ai_chat(request: Request, body: ChatRequest) -> StreamingResponse:
    mcp: MCPToolClient = request.app.state.mcp
    if not mcp.connected:
        try:
            await mcp.connect()
        except Exception:
            raise HTTPException(status_code=503, detail="AI assistant temporarily unavailable")

    messages = cast(List[MessageParam], [m.model_dump() for m in body.messages])
    logger.info("chat request from %s (%d messages)", client_ip(request), len(messages))

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in chat(request.app.state.anthropic, mcp, messages):
                if event["type"] == "tool_use":
                    logger.info("tool call %s by %s", event["name"], client_ip(request))
                yield sse(event)
        except anthropic.APIError as e:
            # Never leak SDK exception details (they can reference the API key
            # or account) — log server-side, send a generic event.
            logger.error("Anthropic API error: %s", e)
            yield sse({
                "type": "error",
                "code": "llm_unavailable",
                "message": "The AI assistant is temporarily unavailable.",
            })
        except Exception as e:
            logger.error("Unexpected error in chat stream: %s", e)
            yield sse({
                "type": "error",
                "code": "internal_error",
                "message": "Something went wrong while generating the answer.",
            })

    return StreamingResponse(event_stream(), media_type="text/event-stream")
