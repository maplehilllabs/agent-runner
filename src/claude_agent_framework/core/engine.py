"""
Core Agent Engine - The main execution engine for Claude agents.

This module provides the AgentEngine class which handles all interactions
with the Claude Agent SDK, including configuration, execution, and result processing.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any, Literal

from claude_agent_sdk import (
    AssistantMessage as SDKAssistantMessage,
)
from claude_agent_sdk import (
    ResultMessage as SDKResultMessage,
)
from claude_agent_sdk import (
    SystemMessage as SDKSystemMessage,
)
from claude_agent_sdk import (
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from claude_agent_sdk import (
    UserMessage as SDKUserMessage,
)
from claude_agent_sdk.types import (
    AgentDefinition,
    ClaudeAgentOptions,
    McpHttpServerConfig,
    McpSSEServerConfig,
    McpStdioServerConfig,
    SandboxSettings,
    SystemPromptPreset,
)

from claude_agent_framework.config.settings import (
    MCPServerType,
    PermissionMode,
    Settings,
)
from claude_agent_framework.core.result import (
    AgentMessage,
    AgentResult,
    AgentStatus,
    TodoItem,
    TokenUsage,
    ToolCall,
)
from claude_agent_framework.tracking.logger import AgentLogger


class AgentEngine:
    """
    Core agent execution engine.

    Handles all interactions with the Claude Agent SDK including:
    - Configuration and initialization
    - Sub-agent setup
    - MCP server integration
    - Message processing and result tracking
    - Cost and usage tracking
    """

    def __init__(
        self,
        settings: Settings,
        logger: AgentLogger | None = None,
        on_message: Callable[[dict[str, Any]], None] | None = None,
        on_tool_call: Callable[[ToolCall], None] | None = None,
        on_todo_update: Callable[[list[TodoItem]], None] | None = None,
    ):
        """
        Initialize the agent engine.

        Args:
            settings: Configuration settings
            logger: Optional logger instance
            on_message: Callback for each message
            on_tool_call: Callback for tool calls
            on_todo_update: Callback for todo updates
        """
        self.settings = settings
        self.logger = logger
        self.on_message = on_message
        self.on_tool_call = on_tool_call
        self.on_todo_update = on_todo_update

        # Setup environment for Bedrock if enabled
        self._setup_environment()

        # Track processed message IDs for deduplication
        self._processed_message_ids: set[str] = set()

    def _setup_environment(self) -> None:
        """Setup environment variables for the agent."""
        # API key
        if self.settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.settings.anthropic_api_key

        # Bedrock configuration
        if self.settings.bedrock.enabled:
            os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
            os.environ["AWS_REGION"] = self.settings.bedrock.region

            if self.settings.bedrock.profile:
                os.environ["AWS_PROFILE"] = self.settings.bedrock.profile

            if self.settings.bedrock.bedrock_model_id:
                os.environ["ANTHROPIC_MODEL"] = self.settings.bedrock.bedrock_model_id

            if self.settings.bedrock.bedrock_small_model_id:
                os.environ["ANTHROPIC_SMALL_FAST_MODEL"] = self.settings.bedrock.bedrock_small_model_id

    def get_auth_info(self) -> dict[str, Any]:
        """Get information about the current authentication configuration.

        The Claude Agent SDK supports multiple authentication methods:
        1. ANTHROPIC_API_KEY - Direct API key from Anthropic Console (sk-ant-...)
        2. CLAUDE_CODE_OAUTH_TOKEN - OAuth token from Claude Code CLI (requires Anthropic approval)
        3. AWS Bedrock - AWS credentials with CLAUDE_CODE_USE_BEDROCK=1
        4. Google Vertex AI - GCP credentials with CLAUDE_CODE_USE_VERTEX=1

        Note: The SDK is intended to be used with API keys (pay-as-you-go billing).
        OAuth tokens from Claude Pro/Max subscriptions are NOT officially supported
        for SDK usage unless you have prior approval from Anthropic.
        """
        api_key = self.settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        bedrock_enabled = self.settings.bedrock.enabled or os.environ.get("CLAUDE_CODE_USE_BEDROCK") == "1"
        vertex_enabled = os.environ.get("CLAUDE_CODE_USE_VERTEX") == "1"

        if bedrock_enabled:
            return {
                "method": "AWS Bedrock",
                "region": self.settings.bedrock.region or os.environ.get("AWS_REGION", "us-east-1"),
                "profile": self.settings.bedrock.profile or os.environ.get("AWS_PROFILE", "default"),
                "model_id": self.settings.bedrock.bedrock_model_id or os.environ.get("ANTHROPIC_MODEL", "auto"),
            }
        elif vertex_enabled:
            return {
                "method": "Google Vertex AI",
                "project": os.environ.get("CLOUD_ML_PROJECT_ID", "not set"),
                "region": os.environ.get("CLOUD_ML_REGION", "not set"),
                "model": self.settings.agent.model.value,
            }
        elif api_key:
            # Mask the API key for display
            masked_key = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "<set>"
            return {
                "method": "Anthropic API",
                "api_key": masked_key,
                "model": self.settings.agent.model.value,
            }
        elif oauth_token:
            # OAuth token from Claude Code CLI login
            masked_token = f"{oauth_token[:10]}...{oauth_token[-4:]}" if len(oauth_token) > 14 else "<set>"
            return {
                "method": "Claude Code OAuth",
                "oauth_token": masked_token,
                "model": self.settings.agent.model.value,
                "note": "OAuth tokens may not be officially supported for SDK use",
            }
        else:
            # Check if Claude Code has credentials in macOS Keychain
            keychain_auth = self._check_keychain_credentials()
            if keychain_auth:
                return keychain_auth

            return {
                "method": "Unknown",
                "error": "No authentication configured",
                "hint": "Set ANTHROPIC_API_KEY, configure Bedrock, or run 'claude login' for OAuth",
            }

    def _check_keychain_credentials(self) -> dict[str, Any] | None:
        """Check if Claude Code has credentials stored in macOS Keychain.

        SECURITY NOTE: This method has been disabled to prevent keychain dumping.
        The Claude Agent SDK will automatically retrieve credentials from the
        keychain when needed using secure APIs.

        TODO: If keychain detection is needed, implement using official macOS
        Security framework APIs instead of dumping the entire keychain.
        """
        # Disabled for security reasons - dumping keychain is a security risk
        # The SDK will handle keychain access securely if credentials exist
        return None

    def _build_system_prompt(self) -> str | SystemPromptPreset | None:
        """Build the system prompt configuration."""
        prompt_type = self.settings.agent.system_prompt_type

        if prompt_type == "preset":
            preset_name = self.settings.agent.system_prompt_preset
            append_text = self.settings.agent.system_prompt_content
            prompt: SystemPromptPreset = {
                "type": "preset",
                "preset": preset_name,
            }
            if append_text:
                prompt["append"] = append_text
            return prompt

        elif prompt_type == "custom":
            return self.settings.agent.system_prompt_content

        elif prompt_type == "append":
            return {
                "type": "preset",
                "preset": "claude_code",
                "append": self.settings.agent.system_prompt_content or "",
            }

        return None

    def _build_agents_config(self) -> dict[str, AgentDefinition] | None:
        """Build sub-agents configuration."""
        if not self.settings.sub_agents:
            return None

        agents: dict[str, AgentDefinition] = {}
        for agent in self.settings.sub_agents:
            agents[agent.name] = AgentDefinition(
                description=agent.description,
                prompt=agent.prompt,
                tools=agent.tools,
                model=agent.model.value if agent.model else None,
            )

        return agents

    def _build_mcp_servers_config(self) -> dict[str, McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig] | None:
        """Build MCP servers configuration."""
        if not self.settings.mcp_servers:
            return None

        servers: dict[str, McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig] = {}
        for server in self.settings.mcp_servers:
            if server.type == MCPServerType.STDIO:
                servers[server.name] = McpStdioServerConfig(
                    command=server.command or "",
                    args=server.args,
                    env=server.env,
                )
            elif server.type == MCPServerType.SSE:
                servers[server.name] = McpSSEServerConfig(
                    url=server.url or "",
                    headers=server.headers,
                )
            elif server.type == MCPServerType.HTTP:
                servers[server.name] = McpHttpServerConfig(
                    url=server.url or "",
                    headers=server.headers,
                )
            # SDK type servers are handled separately

        return servers if servers else None

    def _build_sandbox_config(self) -> SandboxSettings | None:
        """Build sandbox configuration."""
        if not self.settings.sandbox.enabled:
            return None

        return SandboxSettings(
            enabled=True,
        )

    def _build_options(self) -> ClaudeAgentOptions:
        """Build the complete options object for the SDK."""
        # Permission mode mapping
        permission_map: dict[PermissionMode, Literal['default', 'acceptEdits', 'bypassPermissions', 'plan']] = {
            PermissionMode.DEFAULT: "default",
            PermissionMode.ACCEPT_EDITS: "acceptEdits",
            PermissionMode.BYPASS_PERMISSIONS: "bypassPermissions",
            PermissionMode.PLAN: "plan",
        }

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Build sub-agents
        agents = self._build_agents_config()

        # Build MCP servers
        mcp_servers = self._build_mcp_servers_config()

        # Build sandbox
        sandbox = self._build_sandbox_config()

        # Setting sources type
        setting_sources: list[Literal['user', 'project', 'local']] | None = None
        if self.settings.agent.setting_sources:
            setting_sources = [s for s in self.settings.agent.setting_sources if s in ('user', 'project', 'local')]  # type: ignore

        # Create options object
        options = ClaudeAgentOptions(
            model=self.settings.agent.model.value,
            system_prompt=system_prompt,
            max_turns=self.settings.agent.max_turns,
            max_thinking_tokens=self.settings.agent.max_thinking_tokens,
            max_budget_usd=self.settings.agent.max_budget_usd,
            permission_mode=permission_map[self.settings.agent.permission_mode],
            allowed_tools=self.settings.agent.allowed_tools or [],
            disallowed_tools=self.settings.agent.disallowed_tools or [],
            cwd=str(self.settings.agent.cwd) if self.settings.agent.cwd else None,
            setting_sources=setting_sources,
            agents=agents,
            mcp_servers=mcp_servers or {},
            sandbox=sandbox,
            resume=self.settings.session_id,
            continue_conversation=self.settings.continue_conversation,
        )

        return options

    def _process_message(
        self,
        message: Any,
        result: AgentResult,
    ) -> None:
        """Process a single message from the SDK."""
        # Log the message
        if self.logger:
            self.logger.log_message(message)

        # Track raw message (convert to dict for storage if possible)
        try:
            if hasattr(message, '__dict__'):
                result.raw_messages.append(vars(message))
            else:
                result.raw_messages.append(str(message))
        except Exception:
            result.raw_messages.append(str(message))

        # Callback
        if self.on_message:
            self.on_message(message)

        # Process by type
        if isinstance(message, SDKSystemMessage):
            self._process_system_message(message, result)
        elif isinstance(message, SDKAssistantMessage):
            self._process_assistant_message(message, result)
        elif isinstance(message, SDKUserMessage):
            self._process_user_message(message, result)
        elif isinstance(message, SDKResultMessage):
            self._process_result_message(message, result)

    def _process_system_message(
        self,
        message: SDKSystemMessage,
        result: AgentResult,
    ) -> None:
        """Process a system message."""
        subtype = message.subtype

        if subtype == "init":
            # Get session_id from data if available
            data = message.data if hasattr(message, 'data') else {}
            result.session_id = data.get("session_id") if isinstance(data, dict) else None
            if self.logger:
                self.logger.log_info(f"Session initialized: {result.session_id}")

    def _process_assistant_message(
        self,
        message: SDKAssistantMessage,
        result: AgentResult,
    ) -> None:
        """Process an assistant message."""
        content = message.content

        # Get message ID for deduplication (parallel tool uses share the same ID/usage)
        message_id = getattr(message, 'id', None)

        # Track message
        agent_msg = AgentMessage(
            role="assistant",
            content=[self._block_to_dict(b) for b in content],
            message_id=message_id,
        )

        result.messages.append(agent_msg)

        # Track token usage (only once per unique message ID)
        if message_id and message_id not in self._processed_message_ids:
            self._processed_message_ids.add(message_id)

            usage = getattr(message, 'usage', None)
            if usage:
                # Extract token counts from usage dict or object
                if isinstance(usage, dict):
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    cache_creation = usage.get('cache_creation_input_tokens', 0)
                    cache_read = usage.get('cache_read_input_tokens', 0)
                else:
                    input_tokens = getattr(usage, 'input_tokens', 0)
                    output_tokens = getattr(usage, 'output_tokens', 0)
                    cache_creation = getattr(usage, 'cache_creation_input_tokens', 0)
                    cache_read = getattr(usage, 'cache_read_input_tokens', 0)

                step_usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                )
                result.total_usage.add(step_usage)

                if self.logger:
                    self.logger.log_token_usage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_creation=cache_creation,
                        cache_read=cache_read,
                    )

        # Process content blocks
        for block in content:
            if isinstance(block, ToolUseBlock):
                tool_call = ToolCall(
                    tool_name=block.name,
                    tool_input=block.input,
                )
                result.tool_calls.append(tool_call)

                if self.on_tool_call:
                    self.on_tool_call(tool_call)

                if self.logger:
                    self.logger.log_tool_call(tool_call)

                # Check for TodoWrite
                if block.name == "TodoWrite":
                    todos = block.input.get("todos", [])
                    result.todos = [
                        TodoItem(
                            content=t.get("content", ""),
                            status=t.get("status", "pending"),
                            active_form=t.get("activeForm", ""),
                        )
                        for t in todos
                    ]
                    if self.on_todo_update:
                        self.on_todo_update(result.todos)

    def _block_to_dict(self, block: Any) -> dict[str, Any]:
        """Convert a content block to a dictionary."""
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        elif isinstance(block, ToolUseBlock):
            return {"type": "tool_use", "name": block.name, "input": block.input, "id": block.id}
        elif isinstance(block, ToolResultBlock):
            return {"type": "tool_result", "tool_use_id": block.tool_use_id, "content": block.content}
        elif hasattr(block, '__dict__'):
            return vars(block)
        else:
            return {"type": "unknown", "value": str(block)}

    def _process_user_message(
        self,
        message: SDKUserMessage,
        result: AgentResult,
    ) -> None:
        """Process a user message (usually tool results)."""
        content = message.content

        # Convert content to list if it's a string
        if isinstance(content, str):
            content_list = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            content_list = [self._block_to_dict(b) if not isinstance(b, dict) else b for b in content]
        else:
            content_list = [{"type": "text", "text": str(content)}]

        agent_msg = AgentMessage(
            role="user",
            content=content_list,
        )
        result.messages.append(agent_msg)

    def _process_result_message(
        self,
        message: SDKResultMessage,
        result: AgentResult,
    ) -> None:
        """Process the final result message."""
        subtype = message.subtype
        result.result_text = message.result
        result.total_cost_usd = message.total_cost_usd or 0.0
        result.num_turns = message.num_turns
        result.duration_ms = float(message.duration_ms) if message.duration_ms is not None else 0.0
        result.session_id = message.session_id

        # Map subtype to status
        status_map = {
            "success": AgentStatus.SUCCESS,
            "error_max_turns": AgentStatus.MAX_TURNS_REACHED,
            "error_during_execution": AgentStatus.ERROR,
            "error_max_structured_output_retries": AgentStatus.ERROR,
        }
        result.status = status_map.get(subtype, AgentStatus.ERROR)

        if result.status == AgentStatus.ERROR:
            result.error = f"Execution ended with: {subtype}"
            result.error_type = subtype

    async def run(self, prompt: str) -> AgentResult:
        """
        Run the agent with the given prompt.

        Args:
            prompt: The task/prompt for the agent

        Returns:
            AgentResult containing the execution results
        """
        # Import here to avoid circular imports and allow lazy loading
        from claude_agent_sdk import query

        result = AgentResult(
            status=AgentStatus.RUNNING,
            start_time=datetime.now(),
        )

        self._processed_message_ids.clear()

        try:
            options = self._build_options()

            if self.logger:
                self.logger.log_info(f"Starting agent with prompt: {prompt[:100]}...")
                self.logger.log_debug(f"Options: {options}")

            # Iterate through all messages without breaking early
            # to avoid asyncio cleanup issues with the SDK
            async for message in query(prompt=prompt, options=options):
                self._process_message(message, result)

        except Exception as e:
            result.status = AgentStatus.ERROR
            result.error = str(e)
            result.error_type = type(e).__name__

            if self.logger:
                self.logger.log_error(f"Agent execution failed: {e}")

        result.end_time = datetime.now()
        if result.status == AgentStatus.RUNNING:
            result.status = AgentStatus.SUCCESS

        if self.logger:
            self.logger.log_result(result)

        return result

    async def run_streaming(
        self,
        prompt: str,
    ) -> AsyncIterator[tuple[dict[str, Any], AgentResult]]:
        """
        Run the agent with streaming output.

        Yields tuples of (message, current_result) for real-time processing.

        Args:
            prompt: The task/prompt for the agent

        Yields:
            Tuples of (raw_message, current_result)
        """
        from claude_agent_sdk import query

        result = AgentResult(
            status=AgentStatus.RUNNING,
            start_time=datetime.now(),
        )

        self._processed_message_ids.clear()

        try:
            options = self._build_options()

            async for message in query(prompt=prompt, options=options):
                self._process_message(message, result)
                yield message, result

        except Exception as e:
            result.status = AgentStatus.ERROR
            result.error = str(e)
            result.error_type = type(e).__name__
            raise

        finally:
            result.end_time = datetime.now()
            if result.status == AgentStatus.RUNNING:
                result.status = AgentStatus.SUCCESS
