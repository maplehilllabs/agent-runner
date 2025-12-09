"""
Cost tracking and budget management.

Provides detailed cost tracking for agent executions including:
- Per-session tracking
- Cumulative tracking
- Budget alerts
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_framework.core.result import AgentResult, TokenUsage

# Pricing per million tokens (as of late 2024)
# These should be updated as pricing changes
PRICING = {
    "sonnet": {
        "input": 3.0,  # $3 per 1M input tokens
        "output": 15.0,  # $15 per 1M output tokens
        "cache_write": 3.75,  # $3.75 per 1M cache write tokens
        "cache_read": 0.30,  # $0.30 per 1M cache read tokens
    },
    "opus": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "haiku": {
        "input": 0.25,
        "output": 1.25,
        "cache_write": 0.30,
        "cache_read": 0.03,
    },
}


@dataclass
class CostEntry:
    """A single cost entry."""
    timestamp: datetime
    session_id: str | None
    model: str
    usage: TokenUsage
    cost_usd: float
    task_description: str = ""


@dataclass
class CostSummary:
    """Summary of costs over a period."""
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    num_sessions: int = 0
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def add_entry(self, entry: CostEntry) -> None:
        """Add a cost entry to the summary."""
        self.total_cost_usd += entry.cost_usd
        self.total_input_tokens += entry.usage.input_tokens
        self.total_output_tokens += entry.usage.output_tokens
        self.total_cache_creation_tokens += entry.usage.cache_creation_tokens
        self.total_cache_read_tokens += entry.usage.cache_read_tokens
        self.num_sessions += 1
        self.entries.append(entry)


class CostTracker:
    """
    Tracks costs across agent executions.

    Features:
    - Per-session cost tracking
    - Cumulative cost tracking
    - Budget enforcement
    - Cost reporting
    """

    def __init__(
        self,
        storage_path: Path | str | None = None,
        budget_limit_usd: float | None = None,
        alert_threshold_pct: float = 80.0,
    ):
        """
        Initialize the cost tracker.

        Args:
            storage_path: Path to store cost data (optional)
            budget_limit_usd: Maximum budget in USD (optional)
            alert_threshold_pct: Percentage of budget to trigger alert
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.budget_limit_usd = budget_limit_usd
        self.alert_threshold_pct = alert_threshold_pct

        self.summary = CostSummary()
        self._load_history()

    def _load_history(self) -> None:
        """Load cost history from storage."""
        if self.storage_path and self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)

                for entry_data in data.get("entries", []):
                    entry = CostEntry(
                        timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                        session_id=entry_data.get("session_id"),
                        model=entry_data["model"],
                        usage=TokenUsage(
                            input_tokens=entry_data["usage"]["input_tokens"],
                            output_tokens=entry_data["usage"]["output_tokens"],
                            cache_creation_tokens=entry_data["usage"].get("cache_creation_tokens", 0),
                            cache_read_tokens=entry_data["usage"].get("cache_read_tokens", 0),
                        ),
                        cost_usd=entry_data["cost_usd"],
                        task_description=entry_data.get("task_description", ""),
                    )
                    self.summary.add_entry(entry)
            except (json.JSONDecodeError, KeyError):
                pass  # Start fresh if file is corrupted

    def _save_history(self) -> None:
        """Save cost history to storage."""
        if not self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "total_cost_usd": self.summary.total_cost_usd,
            "entries": [
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "session_id": entry.session_id,
                    "model": entry.model,
                    "usage": {
                        "input_tokens": entry.usage.input_tokens,
                        "output_tokens": entry.usage.output_tokens,
                        "cache_creation_tokens": entry.usage.cache_creation_tokens,
                        "cache_read_tokens": entry.usage.cache_read_tokens,
                    },
                    "cost_usd": entry.cost_usd,
                    "task_description": entry.task_description,
                }
                for entry in self.summary.entries
            ],
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def calculate_cost(usage: TokenUsage, model: str = "sonnet") -> float:
        """
        Calculate cost from token usage.

        Args:
            usage: Token usage data
            model: Model name for pricing

        Returns:
            Cost in USD
        """
        pricing = PRICING.get(model.lower(), PRICING["sonnet"])

        cost = (
            (usage.input_tokens / 1_000_000) * pricing["input"]
            + (usage.output_tokens / 1_000_000) * pricing["output"]
            + (usage.cache_creation_tokens / 1_000_000) * pricing["cache_write"]
            + (usage.cache_read_tokens / 1_000_000) * pricing["cache_read"]
        )

        return cost

    def track_result(
        self,
        result: AgentResult,
        model: str = "sonnet",
        task_description: str = "",
    ) -> CostEntry:
        """
        Track the cost of an agent result.

        Args:
            result: The agent execution result
            model: Model name for pricing
            task_description: Description of the task

        Returns:
            The cost entry created
        """
        # Use the SDK's reported cost if available, otherwise calculate
        cost = result.total_cost_usd
        if cost == 0.0:
            cost = self.calculate_cost(result.total_usage, model)

        entry = CostEntry(
            timestamp=datetime.now(),
            session_id=result.session_id,
            model=model,
            usage=result.total_usage,
            cost_usd=cost,
            task_description=task_description,
        )

        self.summary.add_entry(entry)
        self._save_history()

        return entry

    def check_budget(self) -> tuple[bool, str]:
        """
        Check if budget limits are exceeded.

        Returns:
            Tuple of (is_within_budget, message)
        """
        if self.budget_limit_usd is None:
            return True, "No budget limit set"

        current = self.summary.total_cost_usd
        limit = self.budget_limit_usd
        pct_used = (current / limit) * 100 if limit > 0 else 0

        if current >= limit:
            return False, f"Budget exceeded: ${current:.4f} / ${limit:.2f} ({pct_used:.1f}%)"

        if pct_used >= self.alert_threshold_pct:
            return True, f"Budget alert: ${current:.4f} / ${limit:.2f} ({pct_used:.1f}%)"

        return True, f"Budget OK: ${current:.4f} / ${limit:.2f} ({pct_used:.1f}%)"

    def get_remaining_budget(self) -> float | None:
        """Get remaining budget in USD."""
        if self.budget_limit_usd is None:
            return None
        return max(0.0, self.budget_limit_usd - self.summary.total_cost_usd)

    def get_report(self) -> dict[str, Any]:
        """Generate a cost report."""
        return {
            "total_cost_usd": self.summary.total_cost_usd,
            "total_sessions": self.summary.num_sessions,
            "total_tokens": self.summary.total_tokens,
            "total_input_tokens": self.summary.total_input_tokens,
            "total_output_tokens": self.summary.total_output_tokens,
            "total_cache_creation_tokens": self.summary.total_cache_creation_tokens,
            "total_cache_read_tokens": self.summary.total_cache_read_tokens,
            "budget_limit_usd": self.budget_limit_usd,
            "remaining_budget_usd": self.get_remaining_budget(),
            "average_cost_per_session": (
                self.summary.total_cost_usd / self.summary.num_sessions
                if self.summary.num_sessions > 0
                else 0.0
            ),
            "recent_entries": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "session_id": e.session_id,
                    "cost_usd": e.cost_usd,
                    "tokens": e.usage.total_tokens,
                }
                for e in self.summary.entries[-10:]  # Last 10 entries
            ],
        }

    def reset(self) -> None:
        """Reset all cost tracking."""
        self.summary = CostSummary()
        if self.storage_path and self.storage_path.exists():
            self.storage_path.unlink()
