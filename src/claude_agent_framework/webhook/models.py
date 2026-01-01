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


class RouteCondition(BaseModel):
    """
    Condition to filter webhook events based on field values.

    Example:
        {
            "field": "assignee.name",
            "operator": "equals",
            "value": "Claude"
        }
    """
    field: str = Field(..., description="Dot-notation path to field (e.g., 'assignee.name')")
    operator: str = Field(
        default="equals",
        description="Comparison operator: equals, not_equals, contains, in, changed"
    )
    value: Any = Field(None, description="Value to compare against")

    def evaluate(self, payload: LinearWebhookPayload) -> bool:
        """
        Evaluate this condition against a webhook payload.

        Args:
            payload: The webhook payload to check

        Returns:
            True if condition matches, False otherwise
        """
        # Get the field value using dot notation
        field_value = self._get_field_value(payload, self.field)

        # Handle different operators
        if self.operator == "equals":
            return field_value == self.value
        elif self.operator == "not_equals":
            return field_value != self.value
        elif self.operator == "contains":
            if isinstance(field_value, str):
                return str(self.value) in field_value
            elif isinstance(field_value, (list, tuple)):
                return self.value in field_value
            return False
        elif self.operator == "in":
            if isinstance(self.value, (list, tuple)):
                return field_value in self.value
            return False
        elif self.operator == "changed":
            # Check if the field changed (using updatedFrom)
            if not payload.updatedFrom:
                return False
            old_value = self._get_field_value_from_dict(payload.updatedFrom, self.field)
            return old_value != field_value
        else:
            return False

    def _get_field_value(self, payload: LinearWebhookPayload, field_path: str) -> Any:
        """Get a field value from payload using dot notation."""
        return self._get_field_value_from_dict(payload.data, field_path)

    def _get_field_value_from_dict(self, data: dict[str, Any], field_path: str) -> Any:
        """Get a nested field value using dot notation."""
        parts = field_path.split(".")
        value = data

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value


class WebhookRouteRule(BaseModel):
    """
    Routing rule to map webhook events to agent prompts.

    Example:
        {
            "event_pattern": "Issue.update",
            "conditions": [
                {"field": "assignee.name", "operator": "equals", "value": "Claude"}
            ],
            "prompt_template": "Work on this issue: {title}",
            "enabled": true
        }
    """
    event_pattern: str = Field(
        ...,
        description="Event pattern to match (e.g., 'Issue.create', 'Issue.*', '*')"
    )
    conditions: list[RouteCondition] = Field(
        default_factory=list,
        description="Additional conditions to filter events (AND logic)"
    )
    prompt_template: str = Field(
        ...,
        description="Prompt template with placeholders for webhook data"
    )
    enabled: bool = Field(default=True, description="Whether this rule is active")
    description: str | None = Field(default=None, description="Human-readable description")

    def matches(self, event_key: str, payload: LinearWebhookPayload | None = None) -> bool:
        """
        Check if this rule matches the given event and conditions.

        Args:
            event_key: Event key like "Issue.create"
            payload: Optional payload for condition checking

        Returns:
            True if the rule matches
        """
        # First check event pattern
        if not self._matches_event_pattern(event_key):
            return False

        # Then check conditions if payload is provided
        if payload and self.conditions:
            return all(condition.evaluate(payload) for condition in self.conditions)

        return True

    def _matches_event_pattern(self, event_key: str) -> bool:
        """Check if this rule matches the given event key pattern."""
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
