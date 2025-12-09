"""Helper functions for MCP server configuration."""

from __future__ import annotations

from claude_agent_framework.config.settings import MCPServerConfig, MCPServerType


def create_stdio_server_config(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> MCPServerConfig:
    """
    Create a stdio MCP server configuration.

    Args:
        name: Server name/identifier
        command: Command to run (e.g., 'npx', 'python')
        args: Command arguments
        env: Environment variables

    Returns:
        MCPServerConfig for a stdio server
    """
    return MCPServerConfig(
        name=name,
        type=MCPServerType.STDIO,
        command=command,
        args=args or [],
        env=env or {},
    )


def create_http_server_config(
    name: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> MCPServerConfig:
    """
    Create an HTTP MCP server configuration.

    Args:
        name: Server name/identifier
        url: Server URL
        headers: HTTP headers (e.g., authentication)

    Returns:
        MCPServerConfig for an HTTP server
    """
    return MCPServerConfig(
        name=name,
        type=MCPServerType.HTTP,
        url=url,
        headers=headers or {},
    )


def create_sse_server_config(
    name: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> MCPServerConfig:
    """
    Create an SSE (Server-Sent Events) MCP server configuration.

    Args:
        name: Server name/identifier
        url: Server URL
        headers: HTTP headers (e.g., authentication)

    Returns:
        MCPServerConfig for an SSE server
    """
    return MCPServerConfig(
        name=name,
        type=MCPServerType.SSE,
        url=url,
        headers=headers or {},
    )


# Pre-configured common MCP servers
FILESYSTEM_SERVER = create_stdio_server_config(
    name="filesystem",
    command="npx",
    args=["@modelcontextprotocol/server-filesystem"],
)


MEMORY_SERVER = create_stdio_server_config(
    name="memory",
    command="npx",
    args=["@modelcontextprotocol/server-memory"],
)


def get_common_server(name: str) -> MCPServerConfig | None:
    """Get a pre-configured common MCP server."""
    servers = {
        "filesystem": FILESYSTEM_SERVER,
        "memory": MEMORY_SERVER,
    }
    return servers.get(name)
