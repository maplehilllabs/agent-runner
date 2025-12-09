"""Pre-built agent configurations and templates."""

from claude_agent_framework.agents.templates import (
    CODE_REVIEWER_AGENT,
    DATA_ANALYST_AGENT,
    LOG_ANALYZER_AGENT,
    SECURITY_AUDITOR_AGENT,
    get_agent_template,
)

__all__ = [
    "CODE_REVIEWER_AGENT",
    "DATA_ANALYST_AGENT",
    "LOG_ANALYZER_AGENT",
    "SECURITY_AUDITOR_AGENT",
    "get_agent_template",
]
