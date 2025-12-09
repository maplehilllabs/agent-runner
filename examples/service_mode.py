#!/usr/bin/env python3
"""
Example running as a service.

This example demonstrates:
- Service mode execution
- Interval-based running
- Graceful shutdown handling
"""

import asyncio
import signal
from pathlib import Path

from claude_agent_framework import AgentRunner, Settings
from claude_agent_framework.config.settings import (
    AgentConfig,
    ModelType,
    LoggingConfig,
    SlackConfig,
)


async def main():
    """Run an agent as a service with periodic execution."""

    # Configure settings
    settings = Settings(
        agent=AgentConfig(
            name="monitoring-agent",
            model=ModelType.SONNET,
            max_turns=20,
            max_budget_usd=5.0,  # Budget limit for service
        ),
        service_mode=True,
        service_interval_seconds=60,  # Run every minute for demo
        logging=LoggingConfig(
            enabled=True,
            log_dir=Path("./logs"),
        ),
        slack=SlackConfig(
            enabled=False,  # Set to True with webhook for notifications
        ),
    )

    # Create runner
    runner = AgentRunner(settings)

    print("Starting service mode...")
    print("Press Ctrl+C to stop")
    print(f"Interval: {settings.service_interval_seconds}s")
    print("-" * 50)

    # Run as service
    await runner.run_service(
        prompt="""Quick system check:
1. What time is it?
2. Confirm you're operational

Keep response under 50 words.""",
        task_description="Periodic health check",
    )

    print("\nService stopped.")


if __name__ == "__main__":
    asyncio.run(main())
