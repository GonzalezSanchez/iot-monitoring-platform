import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("MODEL", "claude-haiku-4-5")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://backend:8000/mcp")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
RATE_LIMIT_PER_DAY = int(os.getenv("RATE_LIMIT_PER_DAY", "20"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "6"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "2000"))

# Timeout (seconds) for every Claude call — a hanging request must never pin an
# SSE connection open (docs/project4-llm-mcp.md §Security).
CLAUDE_TIMEOUT_SECONDS = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", "60"))

BRAIN_PROMPT_PATH = Path(__file__).parent / "brain.md"


def load_brain_prompt() -> str:
    """The system prompt lives in brain.md and is loaded at runtime (PRD §8)."""
    return BRAIN_PROMPT_PATH.read_text(encoding="utf-8")
