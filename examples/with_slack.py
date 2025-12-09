#!/usr/bin/env python3
"""
Example with Slack notifications.

This example demonstrates:
- Configuring Slack notifications
- Automatic result posting to Slack
- Custom notification settings
"""

import asyncio
import os
from pathlib import Path

from claude_agent_framework import AgentRunner, Settings
from claude_agent_framework.config.settings import (
    AgentConfig,
    ModelType,
    LoggingConfig,
    SlackConfig,
)


async def main():
    """Run an agent with Slack notifications."""

    # Get webhook URL from environment
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("Warning: SLACK_WEBHOOK_URL not set. Notifications disabled.")

    # Configure settings with Slack
    settings = Settings(
        agent=AgentConfig(
            name="slack-notified-agent",
            model=ModelType.SONNET,
            max_turns=20,
        ),
        slack=SlackConfig(
            enabled=bool(webhook_url),
            webhook_url=webhook_url,
            username="Claude Agent Bot",
            icon_emoji=":robot_face:",
            notify_on_success=True,
            notify_on_error=True,
            include_cost=True,
            include_duration=True,
        ),
        logging=LoggingConfig(
            enabled=True,
            log_dir=Path("./logs"),
        ),
    )

    # Create runner
    runner = AgentRunner(settings)

    # Run a task - result will be posted to Slack
    result = await runner.run_once(
        prompt="Generate a brief status report: What time is it and what's 2+2?",
        task_description="Test notification",
    )

    print(f"Status: {result.status.value}")
    print(f"Slack notification sent: {settings.slack.enabled}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
