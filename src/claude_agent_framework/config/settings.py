"""
Settings and configuration management for Claude Agent Framework.

All settings can be configured via environment variables or .env file.
"""

from __future__ import annotations

import json
import os
import warnings
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelType(str, Enum):
    """Available Claude model types."""
    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
    CLAUDE_OPUS_4 = "claude-opus-4-20250514"


class PermissionMode(str, Enum):
    """Permission modes for tool execution."""
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    PLAN = "plan"


class MCPServerType(str, Enum):
    """Types of MCP servers."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    SDK = "sdk"


class SubAgentConfig(BaseModel):
    """Configuration for a sub-agent."""
    name: str = Field(..., description="Unique identifier for the sub-agent")
    description: str = Field(..., description="When to use this agent")
    prompt: str = Field(..., description="System prompt for the agent")
    tools: list[str] | None = Field(default=None, description="Allowed tools (None = inherit all)")
    model: ModelType | None = Field(default=None, description="Model override")

    model_config = {"extra": "forbid"}


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str = Field(..., description="Server name/identifier")
    type: MCPServerType = Field(default=MCPServerType.STDIO, description="Server type")
    command: str | None = Field(default=None, description="Command for stdio servers")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    url: str | None = Field(default=None, description="URL for HTTP/SSE servers")
    headers: dict[str, str] = Field(default_factory=dict, description="Headers for HTTP/SSE")

    model_config = {"extra": "forbid"}

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str | None) -> str | None:
        """Validate MCP server command for security.

        Security: Warns about potentially dangerous commands and shell features.
        """
        if v is None:
            return None

        # List of potentially dangerous patterns
        dangerous_patterns = [
            ("rm ", "file deletion"),
            ("sudo ", "privilege escalation"),
            ("curl | sh", "remote code execution"),
            ("wget | sh", "remote code execution"),
            ("|", "shell piping"),
            ("&&", "command chaining"),
            (";", "command separation"),
            ("`", "command substitution"),
            ("$(", "command substitution"),
        ]

        for pattern, risk in dangerous_patterns:
            if pattern in v:
                warnings.warn(
                    f"MCP server command contains potentially dangerous pattern '{pattern}' "
                    f"({risk}): {v}. Ensure this is from a trusted source.",
                    stacklevel=2
                )
                break

        return v


class SlackConfig(BaseModel):
    """Slack notification configuration."""
    enabled: bool = Field(default=False, description="Enable Slack notifications")
    webhook_url: str | None = Field(default=None, description="Slack webhook URL")
    channel: str | None = Field(default=None, description="Override channel (optional)")
    username: str = Field(default="Claude Agent", description="Bot username")
    icon_emoji: str = Field(default=":robot_face:", description="Bot emoji icon")
    notify_on_success: bool = Field(default=True, description="Notify on successful completion")
    notify_on_error: bool = Field(default=True, description="Notify on errors")
    include_cost: bool = Field(default=True, description="Include cost info in message")
    include_duration: bool = Field(default=True, description="Include duration in message")

    model_config = {"extra": "forbid"}


class WebhookConfig(BaseModel):
    """Webhook server configuration."""
    enabled: bool = Field(default=False, description="Enable webhook server")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to listen on")
    linear_webhook_secret: str | None = Field(
        default=None,
        description="Linear webhook signing secret for validation"
    )
    max_timestamp_age_seconds: int = Field(
        default=60,
        description="Maximum age of webhook timestamp in seconds"
    )
    routes_file: Path | None = Field(
        default=None,
        description="YAML file containing webhook route rules"
    )

    model_config = {"extra": "forbid"}


class LoggingConfig(BaseModel):
    """Logging configuration."""
    enabled: bool = Field(default=True, description="Enable logging")
    log_dir: Path = Field(default=Path("./logs"), description="Log directory")
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    rotate_logs: bool = Field(default=True, description="Enable log rotation")
    max_log_size_mb: int = Field(default=10, description="Max log file size in MB")
    backup_count: int = Field(default=5, description="Number of backup files to keep")
    log_agent_trace: bool = Field(default=True, description="Log full agent trace")
    log_tool_calls: bool = Field(default=True, description="Log tool calls")
    log_token_usage: bool = Field(default=True, description="Log token usage")
    separate_trace_file: bool = Field(default=True, description="Use separate file for traces")

    model_config = {"extra": "forbid"}


class BedrockConfig(BaseModel):
    """AWS Bedrock configuration."""
    enabled: bool = Field(default=False, description="Use AWS Bedrock")
    region: str = Field(default="us-east-1", description="AWS region")
    profile: str | None = Field(default=None, description="AWS profile name")
    bedrock_model_id: str | None = Field(
        default=None,
        alias="model_id",
        description="Bedrock model ID (e.g., global.anthropic.claude-sonnet-4-5-20250929-v1:0)"
    )
    bedrock_small_model_id: str | None = Field(
        default=None,
        alias="small_model_id",
        description="Bedrock model ID for small/fast operations"
    )

    model_config = {"extra": "forbid", "protected_namespaces": (), "populate_by_name": True}


class SandboxConfig(BaseModel):
    """Sandbox configuration for secure execution."""
    enabled: bool = Field(default=False, description="Enable sandbox mode")
    auto_allow_bash: bool = Field(default=False, description="Auto-allow bash in sandbox")
    excluded_commands: list[str] = Field(default_factory=list, description="Commands to exclude")
    allow_local_binding: bool = Field(default=False, description="Allow local port binding")
    allowed_unix_sockets: list[str] = Field(default_factory=list, description="Allowed Unix sockets")

    model_config = {"extra": "forbid"}


class AgentConfig(BaseModel):
    """Core agent configuration."""
    name: str = Field(default="claude-agent", description="Agent name")
    description: str = Field(default="", description="Agent description")

    # Model settings
    model: ModelType = Field(default=ModelType.SONNET, description="Claude model to use")

    # System prompt settings
    system_prompt_type: str = Field(
        default="preset",
        description="Type: 'preset', 'custom', or 'append'"
    )
    system_prompt_preset: str = Field(
        default="claude_code",
        description="Preset name when using preset type"
    )
    system_prompt_content: str | None = Field(
        default=None,
        description="Custom prompt content or append text"
    )

    # Execution settings
    max_turns: int = Field(default=50, description="Maximum conversation turns")
    max_thinking_tokens: int | None = Field(default=None, description="Max thinking tokens")
    max_budget_usd: float | None = Field(default=None, description="Maximum budget in USD")
    permission_mode: PermissionMode = Field(
        default=PermissionMode.ACCEPT_EDITS,
        description="Permission mode for tool execution"
    )

    # Tool settings
    allowed_tools: list[str] | None = Field(
        default=None,
        description="Allowed tools (None = all built-in tools)"
    )
    disallowed_tools: list[str] = Field(
        default_factory=list,
        description="Tools to explicitly disallow"
    )

    # Working directory
    cwd: Path | None = Field(default=None, description="Working directory")

    # Settings sources
    setting_sources: list[str] = Field(
        default_factory=lambda: ["user", "project"],
        description="Settings sources to load"
    )

    model_config = {"extra": "forbid"}

    @field_validator("cwd", mode="before")
    @classmethod
    def validate_cwd(cls, v: Any) -> Path | None:
        """Validate and resolve the working directory path.

        Security: Ensures path is resolved to absolute path and checks for
        suspicious patterns that might indicate path traversal attempts.
        """
        if v is None:
            return None
        if isinstance(v, str):
            path = Path(v).expanduser().resolve()

            # Security check: warn if path contains suspicious patterns
            path_str = str(path)
            if ".." in path_str or path_str.startswith("/etc") or path_str.startswith("/root"):
                warnings.warn(
                    f"Working directory path contains potentially unsafe location: {path_str}. "
                    "Ensure this is intentional.",
                    stacklevel=2
                )

            return path
        return v


class Settings(BaseSettings):
    """
    Main settings class - loads from environment variables and .env file.

    All settings can be overridden via environment variables with CAF_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="CAF_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # API Configuration
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key (can also use ANTHROPIC_API_KEY)"
    )

    # Agent Configuration
    agent: AgentConfig = Field(default_factory=AgentConfig)

    # Sub-agents (loaded from JSON env var or config file)
    sub_agents: list[SubAgentConfig] = Field(
        default_factory=list,
        description="Sub-agent configurations"
    )

    # MCP Servers (loaded from JSON env var or config file)
    mcp_servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description="MCP server configurations"
    )

    # Bedrock Configuration
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)

    # Sandbox Configuration
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)

    # Slack Configuration
    slack: SlackConfig = Field(default_factory=SlackConfig)

    # Webhook Configuration
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)

    # Logging Configuration
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Task/Prompt Configuration
    task_prompt: str | None = Field(
        default=None,
        description="Default task prompt for the agent"
    )
    task_prompt_file: Path | None = Field(
        default=None,
        description="File containing the task prompt"
    )

    # Service Mode Settings
    service_mode: bool = Field(default=False, description="Run as a service")
    service_interval_seconds: int = Field(default=3600, description="Interval between runs")
    cron_schedule: str | None = Field(default=None, description="Cron schedule expression")

    # Session Management
    session_id: str | None = Field(default=None, description="Session ID to resume")
    continue_conversation: bool = Field(default=False, description="Continue previous session")

    # Config file paths
    config_file: Path | None = Field(default=None, description="YAML config file path")
    sub_agents_file: Path | None = Field(default=None, description="Sub-agents config file")
    mcp_servers_file: Path | None = Field(default=None, description="MCP servers config file")

    @field_validator("sub_agents", mode="before")
    @classmethod
    def parse_sub_agents(cls, v: Any) -> list[SubAgentConfig]:
        if isinstance(v, str):
            try:
                data = json.loads(v)
                return [SubAgentConfig(**item) for item in data]
            except json.JSONDecodeError:
                return []
        return v or []

    @field_validator("mcp_servers", mode="before")
    @classmethod
    def parse_mcp_servers(cls, v: Any) -> list[MCPServerConfig]:
        if isinstance(v, str):
            try:
                data = json.loads(v)
                return [MCPServerConfig(**item) for item in data]
            except json.JSONDecodeError:
                return []
        return v or []

    def get_task_prompt(self) -> str | None:
        """Get the task prompt from direct value or file."""
        if self.task_prompt:
            return self.task_prompt
        if self.task_prompt_file and self.task_prompt_file.exists():
            return self.task_prompt_file.read_text()
        return None

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> Settings:
        """Load settings from a YAML configuration file."""
        import yaml

        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    def save_to_yaml(self, config_path: Path) -> None:
        """Save settings to a YAML configuration file."""
        import yaml

        # Convert to dict, excluding None values and defaults
        data = self.model_dump(exclude_none=True, exclude_defaults=True)

        # Convert Path objects and Enum values to strings
        def convert_values(obj: Any) -> Any:
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, dict):
                return {k: convert_values(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_values(item) for item in obj]
            return obj

        data = convert_values(data)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def generate_env_template(self) -> str:
        """Generate a .env template with all available settings."""
        lines = [
            "# Claude Agent Framework Configuration",
            "# =====================================",
            "",
            "# API Configuration",
            "# -----------------",
            "# Anthropic API key (required unless using Bedrock)",
            "ANTHROPIC_API_KEY=",
            "",
            "# Agent Configuration",
            "# -------------------",
            "CAF_AGENT__NAME=claude-agent",
            "CAF_AGENT__MODEL=sonnet",
            "CAF_AGENT__MAX_TURNS=50",
            "CAF_AGENT__PERMISSION_MODE=acceptEdits",
            "",
            "# System Prompt Configuration",
            "# ---------------------------",
            "# Options: preset, custom, append",
            "CAF_AGENT__SYSTEM_PROMPT_TYPE=preset",
            "CAF_AGENT__SYSTEM_PROMPT_PRESET=claude_code",
            "# CAF_AGENT__SYSTEM_PROMPT_CONTENT=Your custom prompt here",
            "",
            "# Budget and Limits",
            "# -----------------",
            "# CAF_AGENT__MAX_BUDGET_USD=10.0",
            "# CAF_AGENT__MAX_THINKING_TOKENS=5000",
            "",
            "# Working Directory",
            "# -----------------",
            "# CAF_AGENT__CWD=/path/to/project",
            "",
            "# AWS Bedrock Configuration",
            "# -------------------------",
            "CAF_BEDROCK__ENABLED=false",
            "CAF_BEDROCK__REGION=us-east-1",
            "# CAF_BEDROCK__PROFILE=default",
            "# CAF_BEDROCK__MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "",
            "# Sandbox Configuration",
            "# ---------------------",
            "CAF_SANDBOX__ENABLED=false",
            "CAF_SANDBOX__AUTO_ALLOW_BASH=false",
            "",
            "# Slack Notifications",
            "# -------------------",
            "CAF_SLACK__ENABLED=false",
            "CAF_SLACK__WEBHOOK_URL=",
            "CAF_SLACK__USERNAME=Claude Agent",
            "CAF_SLACK__NOTIFY_ON_SUCCESS=true",
            "CAF_SLACK__NOTIFY_ON_ERROR=true",
            "CAF_SLACK__INCLUDE_COST=true",
            "",
            "# Logging Configuration",
            "# ---------------------",
            "CAF_LOGGING__ENABLED=true",
            "CAF_LOGGING__LOG_DIR=./logs",
            "CAF_LOGGING__LOG_LEVEL=INFO",
            "CAF_LOGGING__LOG_AGENT_TRACE=true",
            "CAF_LOGGING__SEPARATE_TRACE_FILE=true",
            "",
            "# Task Configuration",
            "# ------------------",
            "# CAF_TASK_PROMPT=Your task prompt here",
            "# CAF_TASK_PROMPT_FILE=./prompts/task.md",
            "",
            "# Service Mode",
            "# ------------",
            "CAF_SERVICE_MODE=false",
            "CAF_SERVICE_INTERVAL_SECONDS=3600",
            "# CAF_CRON_SCHEDULE=0 * * * *",
            "",
            "# Session Management",
            "# ------------------",
            "# CAF_SESSION_ID=",
            "# CAF_CONTINUE_CONVERSATION=false",
            "",
            "# Configuration Files",
            "# -------------------",
            "# CAF_CONFIG_FILE=./config.yaml",
            "# CAF_SUB_AGENTS_FILE=./sub_agents.yaml",
            "# CAF_MCP_SERVERS_FILE=./mcp_servers.yaml",
            "",
            "# Sub-agents (JSON format)",
            "# ------------------------",
            '# CAF_SUB_AGENTS=[{"name":"code-reviewer","description":"Reviews code","prompt":"You are a code reviewer...","tools":["Read","Grep"]}]',
            "",
            "# MCP Servers (JSON format)",
            "# -------------------------",
            '# CAF_MCP_SERVERS=[{"name":"filesystem","type":"stdio","command":"npx","args":["@modelcontextprotocol/server-filesystem"]}]',
        ]
        return "\n".join(lines)


def load_settings(
    env_file: Path | None = None,
    config_file: Path | None = None,
) -> Settings:
    """
    Load settings from environment and optional config files.

    Priority (highest to lowest):
    1. Environment variables
    2. .env file
    3. YAML config file (if provided)
    """
    # Load .env file first to populate environment variables
    # This ensures API keys and secrets are available even when using YAML config
    _load_env_file(env_file or Path(".env"))

    # If a YAML config file is provided, load it directly
    # This gives the YAML config precedence for non-secret settings
    if config_file and config_file.exists():
        settings = Settings.load_from_yaml(config_file)
        # Merge API key from environment if not in YAML
        if not settings.anthropic_api_key:
            settings.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        return settings

    # Load settings from env
    settings = Settings(_env_file=env_file or ".env")

    return settings


def _load_env_file(env_file: Path) -> None:
    """Load environment variables from a .env file."""
    if not env_file.exists():
        return

    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value and value[0] == value[-1] and value[0] in ("'", '"'):
                        value = value[1:-1]
                    # Only set if not already in environment
                    if key and value and key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        warnings.warn(f"Failed to parse .env file {env_file}: {e}", stacklevel=2)
