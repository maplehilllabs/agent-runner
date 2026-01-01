"""
Webhook event handlers and routing logic.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_framework.webhook.models import (
    LinearWebhookPayload,
    WebhookRouteRule,
)

if TYPE_CHECKING:
    from claude_agent_framework.config.settings import Settings
    from claude_agent_framework.core.runner import AgentRunner

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Handles webhook events and routes them to agent prompts.
    """

    def __init__(
        self,
        settings: Settings,
        route_rules: list[WebhookRouteRule] | None = None,
    ):
        """
        Initialize webhook handler.

        Args:
            settings: Framework settings
            route_rules: List of routing rules (loaded from config or provided)
        """
        self.settings = settings
        self.route_rules = route_rules or []
        self._load_routes_from_file()

    def _load_routes_from_file(self) -> None:
        """Load routing rules from YAML file if configured."""
        if not self.settings.webhook.routes_file:
            return

        routes_file = self.settings.webhook.routes_file
        if not routes_file.exists():
            logger.warning(f"Webhook routes file not found: {routes_file}")
            return

        try:
            import yaml
            with open(routes_file) as f:
                routes_data = yaml.safe_load(f)

            if isinstance(routes_data, list):
                self.route_rules = [WebhookRouteRule(**rule) for rule in routes_data]
                logger.info(f"Loaded {len(self.route_rules)} webhook routing rules")
            else:
                logger.warning(f"Invalid routes file format: {routes_file}")
        except Exception as e:
            logger.error(f"Failed to load webhook routes: {e}")

    def find_matching_rule(
        self,
        event_key: str,
        payload: LinearWebhookPayload | None = None
    ) -> WebhookRouteRule | None:
        """
        Find the first matching route rule for the given event key and payload.

        Args:
            event_key: Event key in format "Type.action" (e.g., "Issue.create")
            payload: Webhook payload for condition checking

        Returns:
            Matching route rule or None
        """
        for rule in self.route_rules:
            if rule.enabled and rule.matches(event_key, payload):
                return rule
        return None

    async def handle_linear_webhook(
        self,
        payload: LinearWebhookPayload,
        headers: dict[str, str | None],
    ) -> dict[str, str]:
        """
        Handle a Linear webhook event.

        Args:
            payload: Linear webhook payload
            headers: Linear-specific headers

        Returns:
            Response dictionary with status and message
        """
        event_key = payload.get_event_key()
        logger.info(
            f"Processing Linear webhook: {event_key} "
            f"(delivery_id={headers.get('delivery_id')})"
        )

        # Find matching route rule (with condition checking)
        rule = self.find_matching_rule(event_key, payload)

        if not rule:
            logger.info(f"No matching route rule for event: {event_key}")
            return {
                "status": "ignored",
                "message": f"No route configured for {event_key}"
            }

        # Render the prompt from the template
        prompt = rule.render_prompt(payload)

        logger.info(f"Triggering agent with prompt: {prompt[:100]}...")

        # Trigger the agent in the background (don't wait for completion)
        asyncio.create_task(self._run_agent(prompt, event_key, headers))

        return {
            "status": "accepted",
            "message": f"Agent triggered for {event_key}",
            "event_key": event_key,
        }

    async def _run_agent(
        self,
        prompt: str,
        event_key: str,
        headers: dict[str, str | None],
    ) -> None:
        """
        Run the agent with the given prompt (background task).

        Args:
            prompt: The prompt to send to the agent
            event_key: The webhook event key
            headers: Linear-specific headers
        """
        try:
            # Import here to avoid circular dependencies
            from claude_agent_framework.core.runner import AgentRunner

            # Create a new runner instance
            runner = AgentRunner(self.settings)

            # Run the agent
            result = await runner.run_once(prompt)

            # Log the result
            if result.status.value == "success":
                logger.info(
                    f"Agent completed successfully for {event_key}: "
                    f"{result.token_usage.total_tokens} tokens, "
                    f"${result.cost_usd:.4f}"
                )
            else:
                logger.error(
                    f"Agent failed for {event_key}: {result.error_message}"
                )

        except Exception as e:
            logger.error(f"Error running agent for {event_key}: {e}", exc_info=True)

    def save_routes_to_file(self, file_path: Path) -> None:
        """
        Save current routing rules to a YAML file.

        Args:
            file_path: Path to save the routes file
        """
        import yaml

        routes_data = [rule.model_dump() for rule in self.route_rules]

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            yaml.dump(routes_data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved {len(self.route_rules)} webhook routes to {file_path}")


def create_default_linear_routes() -> list[WebhookRouteRule]:
    """
    Create default routing rules for Linear webhooks.

    Returns:
        List of default route rules
    """
    return [
        WebhookRouteRule(
            event_pattern="Issue.create",
            prompt_template=(
                "A new issue was created in Linear:\n\n"
                "Title: {title}\n"
                "Description: {description}\n"
                "URL: {url}\n\n"
                "Please analyze this issue and provide insights."
            ),
            description="Handle new issue creation",
        ),
        WebhookRouteRule(
            event_pattern="Issue.update",
            prompt_template=(
                "An issue was updated in Linear:\n\n"
                "Title: {title}\n"
                "State: {state}\n"
                "Priority: {priority}\n"
                "URL: {url}\n\n"
                "Please check if any action is needed."
            ),
            description="Handle issue updates",
        ),
        WebhookRouteRule(
            event_pattern="Comment.create",
            prompt_template=(
                "A new comment was added:\n\n"
                "{data}\n\n"
                "URL: {url}\n\n"
                "Please review this comment."
            ),
            description="Handle new comments",
        ),
    ]
