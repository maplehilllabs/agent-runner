"""Utility helper functions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_cost(cost_usd: float) -> str:
    """Format cost in USD."""
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    elif cost_usd < 1.0:
        return f"${cost_usd:.3f}"
    else:
        return f"${cost_usd:.2f}"


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """JSON dumps with handling for special types."""

    def default_serializer(o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, default=default_serializer, **kwargs)


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_prompt_file(path: Path) -> str:
    """Load a prompt from a file."""
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()
