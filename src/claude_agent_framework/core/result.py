"""Result types for agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    """Status of agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    MAX_TURNS_REACHED = "max_turns_reached"
    CANCELLED = "cancelled"


@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: TokenUsage) -> None:
        """Add another usage to this one."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cache_read_tokens += other.cache_read_tokens


@dataclass
class ToolCall:
    """Record of a tool call."""
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float | None = None
    success: bool = True
    error: str | None = None


@dataclass
class TodoItem:
    """Todo item from agent execution."""
    content: str
    status: str  # pending, in_progress, completed
    active_form: str


@dataclass
class AgentMessage:
    """A single message in the agent conversation."""
    role: str  # user, assistant, system
    content: str | list[Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str | None = None
    usage: TokenUsage | None = None


@dataclass
class AgentResult:
    """Complete result of an agent execution."""
    # Core result
    status: AgentStatus
    result_text: str | None = None
    structured_output: Any | None = None

    # Execution metadata
    session_id: str | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_ms: float = 0.0

    # Token and cost tracking
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    total_cost_usd: float = 0.0
    num_turns: int = 0

    # Conversation history
    messages: list[AgentMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)

    # Error information
    error: str | None = None
    error_type: str | None = None

    # Raw data for debugging
    raw_messages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == AgentStatus.SUCCESS

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0

    def get_final_message(self) -> str:
        """Get the final assistant message."""
        if self.result_text:
            return self.result_text
        # Find last assistant message
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                if isinstance(msg.content, str):
                    return msg.content
                # Handle content blocks
                text_parts = []
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    return "\n".join(text_parts)
        return ""

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the execution."""
        return {
            "status": self.status.value,
            "session_id": self.session_id,
            "duration_seconds": self.duration_seconds,
            "num_turns": self.num_turns,
            "total_tokens": self.total_usage.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "num_tool_calls": len(self.tool_calls),
            "num_todos": len(self.todos),
            "completed_todos": len([t for t in self.todos if t.status == "completed"]),
            "error": self.error,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "result_text": self.result_text,
            "structured_output": self.structured_output,
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "total_usage": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "cache_creation_tokens": self.total_usage.cache_creation_tokens,
                "cache_read_tokens": self.total_usage.cache_read_tokens,
                "total_tokens": self.total_usage.total_tokens,
            },
            "total_cost_usd": self.total_cost_usd,
            "num_turns": self.num_turns,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "message_id": m.message_id,
                }
                for m in self.messages
            ],
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "tool_input": tc.tool_input,
                    "tool_output": tc.tool_output,
                    "timestamp": tc.timestamp.isoformat(),
                    "duration_ms": tc.duration_ms,
                    "success": tc.success,
                    "error": tc.error,
                }
                for tc in self.tool_calls
            ],
            "todos": [
                {
                    "content": t.content,
                    "status": t.status,
                    "active_form": t.active_form,
                }
                for t in self.todos
            ],
            "error": self.error,
            "error_type": self.error_type,
        }
