"""
Agent logging system with full trace support.

Provides comprehensive logging of agent execution including:
- Message traces
- Tool calls
- Token usage
- Structured output
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from claude_agent_framework.core.result import AgentResult, ToolCall


class AgentLogger:
    """
    Comprehensive agent logger with trace support.

    Supports:
    - Console output with rich formatting
    - File logging with rotation
    - Separate trace file for full message dumps
    - Structured JSON logging
    """

    def __init__(
        self,
        name: str = "claude-agent",
        log_dir: Path | str = "./logs",
        log_level: str = "INFO",
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        rotate_logs: bool = True,
        max_log_size_mb: int = 10,
        backup_count: int = 5,
        log_agent_trace: bool = True,
        log_tool_calls: bool = True,
        log_token_usage: bool = True,
        separate_trace_file: bool = True,
        console_output: bool = True,
        rich_console: Console | None = None,
    ):
        """Initialize the agent logger."""
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_format = log_format
        self.rotate_logs = rotate_logs
        self.max_log_size_bytes = max_log_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self.log_agent_trace = log_agent_trace
        self.log_tool_calls = log_tool_calls
        self.log_token_usage = log_token_usage
        self.separate_trace_file = separate_trace_file
        self.console_output = console_output
        self.console = rich_console or Console()

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup loggers
        self._setup_loggers()

        # Session tracking
        self.session_id: str | None = None
        self.session_start: datetime | None = None

    def _setup_loggers(self) -> None:
        """Setup logging handlers."""
        # Main logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.log_level)
        self.logger.handlers.clear()

        # File handler
        log_file = self.log_dir / f"{self.name}.log"
        if self.rotate_logs:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.max_log_size_bytes,
                backupCount=self.backup_count,
            )
        else:
            file_handler = logging.FileHandler(log_file)

        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(logging.Formatter(self.log_format))
        self.logger.addHandler(file_handler)

        # Console handler with rich
        if self.console_output:
            console_handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=False,
                rich_tracebacks=True,
            )
            console_handler.setLevel(self.log_level)
            self.logger.addHandler(console_handler)

        # Trace logger (separate file)
        if self.separate_trace_file and self.log_agent_trace:
            self.trace_logger = logging.getLogger(f"{self.name}.trace")
            self.trace_logger.setLevel(logging.DEBUG)
            self.trace_logger.handlers.clear()

            trace_file = self.log_dir / f"{self.name}_trace.jsonl"
            trace_handler = logging.FileHandler(trace_file)
            trace_handler.setLevel(logging.DEBUG)
            trace_handler.setFormatter(logging.Formatter("%(message)s"))
            self.trace_logger.addHandler(trace_handler)
        else:
            self.trace_logger = self.logger

    def start_session(self, session_id: str | None = None) -> None:
        """Start a new logging session."""
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()

        self.log_info(f"Session started: {self.session_id}")

        # Create session-specific log file
        if self.separate_trace_file:
            session_trace_file = self.log_dir / f"session_{self.session_id}_trace.jsonl"
            self._session_trace_handler = logging.FileHandler(session_trace_file)
            self._session_trace_handler.setFormatter(logging.Formatter("%(message)s"))
            self.trace_logger.addHandler(self._session_trace_handler)

    def end_session(self) -> None:
        """End the current logging session."""
        if self.session_start:
            duration = datetime.now() - self.session_start
            self.log_info(f"Session ended: {self.session_id} (duration: {duration})")

        # Remove session-specific handler
        if hasattr(self, "_session_trace_handler"):
            self.trace_logger.removeHandler(self._session_trace_handler)
            self._session_trace_handler.close()

        self.session_id = None
        self.session_start = None

    def log_debug(self, message: str) -> None:
        """Log a debug message."""
        self.logger.debug(message)

    def log_info(self, message: str) -> None:
        """Log an info message."""
        self.logger.info(message)

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.logger.warning(message)

    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)

    def log_message(self, message: Any) -> None:
        """Log a raw SDK message."""
        if not self.log_agent_trace:
            return

        # Convert message to serializable format
        try:
            if hasattr(message, '__dict__'):
                # Dataclass or object with __dict__
                message_data = self._serialize_object(message)
            elif isinstance(message, dict):
                message_data = message
            else:
                message_data = str(message)
        except Exception:
            message_data = str(message)

        trace_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "type": "message",
            "data": message_data,
        }

        try:
            self.trace_logger.debug(json.dumps(trace_entry, default=str))
        except Exception as e:
            self.trace_logger.debug(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id,
                "type": "message",
                "data": str(message),
                "serialization_error": str(e),
            }))

    def _serialize_object(self, obj: Any) -> Any:
        """Recursively serialize an object to JSON-compatible format."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_object(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._serialize_object(v) for k, v in obj.items()}
        elif hasattr(obj, '__dict__'):
            result = {"__type__": type(obj).__name__}
            for key, value in vars(obj).items():
                if not key.startswith('_'):
                    result[key] = self._serialize_object(value)
            return result
        else:
            return str(obj)

    def log_tool_call(self, tool_call: ToolCall) -> None:
        """Log a tool call."""
        if not self.log_tool_calls:
            return

        self.log_info(f"Tool call: {tool_call.tool_name}")
        self.log_debug(f"Tool input: {json.dumps(tool_call.tool_input, indent=2)}")

        trace_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "type": "tool_call",
            "tool_name": tool_call.tool_name,
            "tool_input": tool_call.tool_input,
        }

        self.trace_logger.debug(json.dumps(trace_entry))

    def log_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_creation: int = 0,
        cache_read: int = 0,
    ) -> None:
        """Log token usage."""
        if not self.log_token_usage:
            return

        total = input_tokens + output_tokens
        self.log_debug(
            f"Tokens: input={input_tokens}, output={output_tokens}, "
            f"cache_create={cache_creation}, cache_read={cache_read}, total={total}"
        )

        trace_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "type": "token_usage",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "total_tokens": total,
        }

        self.trace_logger.debug(json.dumps(trace_entry))

    def log_result(self, result: AgentResult) -> None:
        """Log the final agent result."""
        summary = result.get_summary()

        self.log_info(f"Agent completed with status: {result.status.value}")
        self.log_info(f"Duration: {result.duration_seconds:.2f}s")
        self.log_info(f"Total cost: ${result.total_cost_usd:.4f}")
        self.log_info(f"Turns: {result.num_turns}")
        self.log_info(f"Tool calls: {len(result.tool_calls)}")

        if result.error:
            self.log_error(f"Error: {result.error}")

        trace_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "type": "result",
            "summary": summary,
            "full_result": result.to_dict(),
        }

        self.trace_logger.debug(json.dumps(trace_entry))

    def display_progress(
        self,
        message: str,
        current: int,
        total: int,
    ) -> None:
        """Display progress in console."""
        if not self.console_output:
            return

        percentage = (current / total * 100) if total > 0 else 0
        self.console.print(f"[cyan]{message}[/cyan] [{current}/{total}] {percentage:.1f}%")

    def display_tool_call(self, tool_call: ToolCall) -> None:
        """Display a tool call with rich formatting."""
        if not self.console_output:
            return

        self.console.print(
            Panel(
                f"[bold cyan]{tool_call.tool_name}[/bold cyan]\n"
                f"[dim]{json.dumps(tool_call.tool_input, indent=2)[:500]}[/dim]",
                title="Tool Call",
                border_style="cyan",
            )
        )

    def display_result_summary(self, result: AgentResult) -> None:
        """Display a result summary table."""
        if not self.console_output:
            return

        table = Table(title="Agent Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Status", result.status.value)
        table.add_row("Session ID", result.session_id or "N/A")
        table.add_row("Duration", f"{result.duration_seconds:.2f}s")
        table.add_row("Turns", str(result.num_turns))
        table.add_row("Total Tokens", str(result.total_usage.total_tokens))
        table.add_row("Cost", f"${result.total_cost_usd:.4f}")
        table.add_row("Tool Calls", str(len(result.tool_calls)))

        if result.todos:
            completed = len([t for t in result.todos if t.status == "completed"])
            table.add_row("Todos", f"{completed}/{len(result.todos)} completed")

        if result.error:
            table.add_row("Error", result.error[:100])

        self.console.print(table)

    def display_final_message(self, result: AgentResult, max_length: int = 10000) -> None:
        """Display the final agent message."""
        if not self.console_output:
            return

        final_msg = result.get_final_message()
        if final_msg:
            # Show full message or truncate at max_length
            display_msg = final_msg if len(final_msg) <= max_length else final_msg[:max_length] + f"\n\n... [truncated, {len(final_msg) - max_length} more characters]"
            self.console.print(
                Panel(
                    display_msg,
                    title="Agent Response",
                    border_style="green",
                )
            )

    def save_full_trace(self, result: AgentResult, output_path: Path | None = None) -> Path:
        """Save the full execution trace to a JSON file."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.log_dir / f"trace_{result.session_id or timestamp}.json"

        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

        self.log_info(f"Full trace saved to: {output_path}")
        return output_path
