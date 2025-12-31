"""
Pydantic models for webhook payloads and configuration.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LinearAction(str, Enum):
    """Linear webhook action types."""
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"


class LinearEventType(str, Enum):
    """Linear webhook event types."""
    ISSUE = "Issue"
    COMMENT = "Comment"
    PROJECT = "Project"
    PROJECT_UPDATE = "ProjectUpdate"
    LABEL = "Label"
    CYCLE = "Cycle"
    REACTION = "Reaction"
    ISSUE_ATTACHMENT = "IssueAttachment"
    DOCUMENT = "Document"
    INITIATIVE = "Initiative"
    CUSTOMER = "Customer"
    CUSTOMER_REQUEST = "CustomerRequest"
    USER = "User"
    ISSUE_SLA = "IssueSla"
    OAUTH_APP_REVOKED = "OAuthAppRevoked"


class LinearActor(BaseModel):
    """Actor who triggered the webhook event."""
    id: str
    name: str | None = None
    type: str | None = None


class LinearWebhookPayload(BaseModel):
    """Linear webhook payload structure."""
    action: LinearAction = Field(..., description="Type of action (create, update, remove)")
    type: LinearEventType = Field(..., description="Entity type (Issue, Comment, etc.)")
    actor: LinearActor | None = Field(default=None, description="User who triggered the event")
    createdAt: str = Field(..., description="ISO 8601 timestamp of the action")
    data: dict[str, Any] = Field(..., description="The entity data")
    url: str = Field(..., description="URL to the entity")
    webhookTimestamp: int = Field(..., description="Unix timestamp in milliseconds")
    webhookId: str = Field(..., description="Webhook configuration ID")
    organizationId: str = Field(..., description="Organization ID")
    updatedFrom: dict[str, Any] | None = Field(
        default=None,
        description="Previous values for update actions"
    )

    def get_event_key(self) -> str:
        """Get a unique key for this event type and action."""
        return f"{self.type.value}.{self.action.value}"

    def get_issue_id(self) -> str | None:
        """Get the issue ID if this is an issue-related event."""
        if self.type == LinearEventType.ISSUE:
            return self.data.get("id")
        return None

    def get_issue_title(self) -> str | None:
        """Get the issue title if this is an issue-related event."""
        if self.type == LinearEventType.ISSUE:
            return self.data.get("title")
        return None

    def get_issue_description(self) -> str | None:
        """Get the issue description if this is an issue-related event."""
        if self.type == LinearEventType.ISSUE:
            return self.data.get("description")
        return None

    def get_issue_state(self) -> str | None:
        """Get the issue state if this is an issue-related event."""
        if self.type == LinearEventType.ISSUE:
            state = self.data.get("state", {})
            if isinstance(state, dict):
                return state.get("name")
        return None

    def get_issue_priority(self) -> int | None:
        """Get the issue priority if this is an issue-related event."""
        if self.type == LinearEventType.ISSUE:
            return self.data.get("priority")
        return None


class WebhookRouteRule(BaseModel):
    """
    Routing rule to map webhook events to agent prompts.

    Example:
        {
            "event_pattern": "Issue.create",
            "prompt_template": "Analyze this new issue: {title}\\n\\n{description}",
            "enabled": true
        }
    """
    event_pattern: str = Field(
        ...,
        description="Event pattern to match (e.g., 'Issue.create', 'Issue.*', '*')"
    )
    prompt_template: str = Field(
        ...,
        description="Prompt template with placeholders for webhook data"
    )
    enabled: bool = Field(default=True, description="Whether this rule is active")
    description: str | None = Field(default=None, description="Human-readable description")

    def matches(self, event_key: str) -> bool:
        """Check if this rule matches the given event key."""
        if self.event_pattern == "*":
            return True

        if "*" in self.event_pattern:
            # Simple wildcard matching
            pattern_parts = self.event_pattern.split(".")
            event_parts = event_key.split(".")

            if len(pattern_parts) != len(event_parts):
                return False

            for pattern_part, event_part in zip(pattern_parts, event_parts):
                if pattern_part != "*" and pattern_part != event_part:
                    return False
            return True

        return self.event_pattern == event_key

    def render_prompt(self, payload: LinearWebhookPayload) -> str:
        """Render the prompt template with webhook payload data."""
        # Build context for template rendering
        context = {
            "action": payload.action.value,
            "type": payload.type.value,
            "url": payload.url,
            "title": payload.get_issue_title() or "",
            "description": payload.get_issue_description() or "",
            "state": payload.get_issue_state() or "",
            "priority": payload.get_issue_priority() or 0,
            "actor_name": payload.actor.name if payload.actor else "Unknown",
            "data": payload.data,
        }

        # Simple template rendering using str.format()
        try:
            return self.prompt_template.format(**context)
        except KeyError as e:
            # If a key is missing, return the template as-is with a warning
            return f"[Template Error: Missing key {e}]\n\n{self.prompt_template}"
