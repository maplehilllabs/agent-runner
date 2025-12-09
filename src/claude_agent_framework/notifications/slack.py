"""
Slack notification system.

Sends agent execution results to Slack via webhook.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from claude_agent_framework.config.settings import SlackConfig
    from claude_agent_framework.core.result import AgentResult


class SlackNotifier:
    """
    Send notifications to Slack via webhook.

    Supports:
    - Success/error notifications
    - Rich message formatting with blocks
    - Cost and duration reporting
    - Todo status summaries
    """

    def __init__(self, config: SlackConfig):
        """
        Initialize the Slack notifier.

        Args:
            config: Slack configuration
        """
        self.config = config
        self.enabled = config.enabled and config.webhook_url is not None

    async def send_message(
        self,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Send a message to Slack.

        Args:
            text: Fallback text for notifications
            blocks: Optional rich message blocks

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.config.webhook_url:
            return False

        payload: dict[str, Any] = {
            "text": text,
            "username": self.config.username,
            "icon_emoji": self.config.icon_emoji,
        }

        if self.config.channel:
            payload["channel"] = self.config.channel

        if blocks:
            payload["blocks"] = blocks

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.webhook_url,
                    json=payload,
                    timeout=30.0,
                )
                if response.status_code != 200:
                    print(f"[Slack] Error: HTTP {response.status_code} - {response.text}")
                return response.status_code == 200
        except Exception as e:
            print(f"[Slack] Exception: {e}")
            return False

    def _build_result_blocks(
        self,
        result: AgentResult,
        task_description: str = "",
    ) -> list[dict[str, Any]]:
        """Build Slack blocks for an agent result."""
        is_success = result.is_success
        status_emoji = ":white_check_mark:" if is_success else ":x:"
        status_text = "Success" if is_success else f"Error: {result.error_type or 'Unknown'}"

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Agent Execution {status_text}",
                    "emoji": True,
                },
            },
        ]

        # Task description
        if task_description:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Task:* {task_description[:200]}{'...' if len(task_description) > 200 else ''}",
                },
            })

        # Metrics section
        metrics_text = []

        if self.config.include_duration:
            metrics_text.append(f"*Duration:* {result.duration_seconds:.2f}s")

        if self.config.include_cost:
            metrics_text.append(f"*Cost:* ${result.total_cost_usd:.4f}")

        metrics_text.append(f"*Turns:* {result.num_turns}")
        metrics_text.append(f"*Tokens:* {result.total_usage.total_tokens:,}")
        metrics_text.append(f"*Tool Calls:* {len(result.tool_calls)}")

        if result.session_id:
            metrics_text.append(f"*Session:* `{result.session_id[:12]}...`")

        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": text}
                for text in metrics_text
            ],
        })

        # Todos summary
        if result.todos:
            completed = len([t for t in result.todos if t.status == "completed"])
            pending = len([t for t in result.todos if t.status == "pending"])
            in_progress = len([t for t in result.todos if t.status == "in_progress"])

            todo_text = f"*Todos:* {completed} completed, {in_progress} in progress, {pending} pending"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": todo_text},
            })

        # Error details
        if result.error:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Error:*\n```{result.error[:500]}```",
                },
            })

        # Final message preview
        final_msg = result.get_final_message()
        if final_msg:
            # Truncate for Slack
            preview = final_msg[:500] + ("..." if len(final_msg) > 500 else "")
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Agent Response:*\n```{preview}```",
                },
            })

        # Timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Completed at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                }
            ],
        })

        return blocks

    async def notify_result(
        self,
        result: AgentResult,
        task_description: str = "",
    ) -> bool:
        """
        Send a notification for an agent result.

        Args:
            result: The agent execution result
            task_description: Description of the task

        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            return False

        # Check if we should notify based on result status
        if result.is_success and not self.config.notify_on_success:
            return False
        if not result.is_success and not self.config.notify_on_error:
            return False

        blocks = self._build_result_blocks(result, task_description)
        fallback_text = f"Agent {'completed successfully' if result.is_success else 'failed'}"

        if task_description:
            fallback_text += f": {task_description[:100]}"

        return await self.send_message(fallback_text, blocks)

    async def send_simple_message(self, message: str) -> bool:
        """
        Send a simple text message to Slack.

        Args:
            message: The message to send

        Returns:
            True if successful
        """
        return await self.send_message(message)

    async def send_alert(
        self,
        title: str,
        message: str,
        level: str = "warning",
    ) -> bool:
        """
        Send an alert message.

        Args:
            title: Alert title
            message: Alert message
            level: Alert level (info, warning, error)

        Returns:
            True if successful
        """
        emoji_map = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":rotating_light:",
        }
        emoji = emoji_map.get(level, ":bell:")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Alert at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    }
                ],
            },
        ]

        return await self.send_message(f"{title}: {message}", blocks)
