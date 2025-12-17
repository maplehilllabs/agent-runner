"""
Rich TUI Application for Claude Agent Framework configuration.

Provides an interactive terminal interface for:
- Creating and editing configuration
- Managing sub-agents
- Setting up MCP servers
- Configuring Slack notifications
- Testing the agent
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from claude_agent_framework.config.settings import (
    MCPServerConfig,
    MCPServerType,
    ModelType,
    PermissionMode,
    Settings,
    SubAgentConfig,
)


class ConfigTUI:
    """
    Interactive TUI for configuring the Claude Agent Framework.

    Provides a menu-driven interface for all configuration options.
    """

    def __init__(self, config_dir: Path | None = None):
        """Initialize the TUI."""
        self.console = Console()
        self.config_dir = config_dir or Path.cwd()
        self.settings: Settings | None = None

        # Try to load existing settings
        self._load_existing_settings()

    def _load_existing_settings(self) -> None:
        """Load existing settings if available."""
        env_file = self.config_dir / ".env"
        yaml_file = self.config_dir / "config.yaml"

        if env_file.exists() or yaml_file.exists():
            try:
                self.settings = Settings(
                    _env_file=str(env_file) if env_file.exists() else None
                )
            except Exception:
                self.settings = Settings()
        else:
            self.settings = Settings()

    def _print_header(self, title: str) -> None:
        """Print a section header."""
        self.console.print()
        self.console.print(Panel(
            Text(title, style="bold cyan", justify="center"),
            box=box.DOUBLE,
            border_style="cyan",
        ))
        self.console.print()

    def _print_menu(self, title: str, options: list[tuple[str, str]]) -> str:
        """Print a menu and get user selection."""
        self._print_header(title)

        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Key", style="cyan", width=4)
        table.add_column("Option", style="white")

        for key, desc in options:
            # Escape brackets to prevent Rich from interpreting as markup
            table.add_row(f"\\[{key}]", desc)

        self.console.print(table)
        self.console.print()

        valid_keys = [opt[0].lower() for opt in options]
        while True:
            choice = Prompt.ask("Select option", default=valid_keys[0]).lower()
            if choice in valid_keys:
                return choice
            self.console.print("[red]Invalid option. Please try again.[/red]")

    def _confirm_save(self) -> bool:
        """Confirm before saving."""
        return Confirm.ask("Save configuration?", default=True)

    # =========================================================================
    # Main Menu
    # =========================================================================

    def run(self) -> None:
        """Run the main TUI loop."""
        self.console.clear()
        self._print_header("Claude Agent Framework Configuration")

        while True:
            choice = self._print_menu("Main Menu", [
                ("1", "Agent Configuration"),
                ("2", "Authentication & API"),
                ("3", "Sub-Agents"),
                ("4", "MCP Servers"),
                ("5", "Slack Notifications"),
                ("6", "Logging"),
                ("7", "AWS Bedrock"),
                ("8", "Sandbox Settings"),
                ("9", "View Current Config"),
                ("g", "Generate .env Template"),
                ("s", "Save Configuration"),
                ("t", "Test Agent"),
                ("q", "Quit"),
            ])

            if choice == "1":
                self._configure_agent()
            elif choice == "2":
                self._configure_auth()
            elif choice == "3":
                self._configure_sub_agents()
            elif choice == "4":
                self._configure_mcp_servers()
            elif choice == "5":
                self._configure_slack()
            elif choice == "6":
                self._configure_logging()
            elif choice == "7":
                self._configure_bedrock()
            elif choice == "8":
                self._configure_sandbox()
            elif choice == "9":
                self._view_config()
            elif choice == "g":
                self._generate_env_template()
            elif choice == "s":
                self._save_config()
            elif choice == "t":
                self._test_agent()
            elif choice == "q":
                if Confirm.ask("Exit without saving?", default=False):
                    break
                continue

    # =========================================================================
    # Agent Configuration
    # =========================================================================

    def _configure_agent(self) -> None:
        """Configure core agent settings."""
        self._print_header("Agent Configuration")

        if self.settings is None:
            self.settings = Settings()

        # Agent name
        self.settings.agent.name = Prompt.ask(
            "Agent name",
            default=self.settings.agent.name
        )

        # Model selection
        models = [m.value for m in ModelType]
        self.console.print(f"Available models: {', '.join(models)}")
        model_str = Prompt.ask(
            "Model",
            default=self.settings.agent.model.value,
            choices=models
        )
        self.settings.agent.model = ModelType(model_str)

        # System prompt type
        prompt_types = ["preset", "custom", "append"]
        self.console.print(f"System prompt types: {', '.join(prompt_types)}")
        self.settings.agent.system_prompt_type = Prompt.ask(
            "System prompt type",
            default=self.settings.agent.system_prompt_type,
            choices=prompt_types
        )

        if self.settings.agent.system_prompt_type in ["custom", "append"]:
            self.console.print("[dim]Enter your system prompt (end with empty line):[/dim]")
            lines = []
            while True:
                line = Prompt.ask("", default="")
                if not line:
                    break
                lines.append(line)
            self.settings.agent.system_prompt_content = "\n".join(lines)
        elif self.settings.agent.system_prompt_type == "preset":
            self.settings.agent.system_prompt_preset = Prompt.ask(
                "Preset name",
                default="claude_code"
            )

        # Max turns
        self.settings.agent.max_turns = IntPrompt.ask(
            "Max turns",
            default=self.settings.agent.max_turns
        )

        # Max budget
        if Confirm.ask("Set budget limit?", default=False):
            budget = Prompt.ask("Max budget (USD)", default="10.0")
            self.settings.agent.max_budget_usd = float(budget)

        # Permission mode
        perm_modes = [p.value for p in PermissionMode]
        self.console.print(f"Permission modes: {', '.join(perm_modes)}")
        perm_str = Prompt.ask(
            "Permission mode",
            default=self.settings.agent.permission_mode.value,
            choices=perm_modes
        )
        self.settings.agent.permission_mode = PermissionMode(perm_str)

        # Working directory
        cwd = Prompt.ask(
            "Working directory",
            default=str(self.settings.agent.cwd or Path.cwd())
        )
        self.settings.agent.cwd = Path(cwd).expanduser().resolve()

        self.console.print("[green]Agent configuration updated![/green]")

    # =========================================================================
    # Authentication Configuration
    # =========================================================================

    def _configure_auth(self) -> None:
        """Configure authentication settings."""
        self._print_header("Authentication Configuration")

        if self.settings is None:
            self.settings = Settings()

        # Check for existing API key
        existing_key = self.settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        masked_key = f"{existing_key[:8]}...{existing_key[-4:]}" if len(existing_key) > 12 else "(not set)"

        self.console.print(f"Current API key: {masked_key}")

        if Confirm.ask("Update API key?", default=False):
            self.console.print("[yellow]⚠ Security Warning:[/yellow] API keys will be stored in plaintext in .env files.")
            self.console.print("[dim]Paste your API key (input will be hidden):[/dim]")
            new_key = getpass.getpass("Anthropic API key: ")
            if new_key:
                self.settings.anthropic_api_key = new_key
                self.console.print("[green]API key updated![/green]")
            else:
                self.console.print("[yellow]No API key entered.[/yellow]")

        # Option to use Bedrock instead
        if Confirm.ask("Configure AWS Bedrock instead of API key?", default=False):
            self._configure_bedrock()

    # =========================================================================
    # Sub-Agents Configuration
    # =========================================================================

    def _configure_sub_agents(self) -> None:
        """Configure sub-agents."""
        self._print_header("Sub-Agents Configuration")

        if self.settings is None:
            self.settings = Settings()

        while True:
            # Show existing sub-agents
            if self.settings.sub_agents:
                table = Table(title="Configured Sub-Agents")
                table.add_column("Name", style="cyan")
                table.add_column("Description")
                table.add_column("Tools")
                table.add_column("Model")

                for agent in self.settings.sub_agents:
                    tools_str = ", ".join(agent.tools) if agent.tools else "all"
                    model_str = agent.model.value if agent.model else "inherit"
                    table.add_row(agent.name, agent.description[:40], tools_str[:30], model_str)

                self.console.print(table)
                self.console.print()

            choice = self._print_menu("Sub-Agent Options", [
                ("a", "Add new sub-agent"),
                ("e", "Edit sub-agent"),
                ("d", "Delete sub-agent"),
                ("b", "Back to main menu"),
            ])

            if choice == "a":
                self._add_sub_agent()
            elif choice == "e":
                self._edit_sub_agent()
            elif choice == "d":
                self._delete_sub_agent()
            elif choice == "b":
                break

    def _add_sub_agent(self) -> None:
        """Add a new sub-agent."""
        self.console.print("[cyan]Adding new sub-agent...[/cyan]")

        name = Prompt.ask("Sub-agent name")
        description = Prompt.ask("Description (when to use this agent)")

        self.console.print("[dim]Enter the system prompt (end with empty line):[/dim]")
        lines = []
        while True:
            line = Prompt.ask("", default="")
            if not line:
                break
            lines.append(line)
        prompt = "\n".join(lines)

        # Tools
        self.console.print("[dim]Enter allowed tools (comma-separated, or 'all' for all tools):[/dim]")
        tools_input = Prompt.ask("Tools", default="all")
        tools = None if tools_input.lower() == "all" else [t.strip() for t in tools_input.split(",")]

        # Model
        models = ["inherit"] + [m.value for m in ModelType]
        model_str = Prompt.ask("Model", default="inherit", choices=models)
        model = None if model_str == "inherit" else ModelType(model_str)

        agent = SubAgentConfig(
            name=name,
            description=description,
            prompt=prompt,
            tools=tools,
            model=model,
        )

        if self.settings:
            self.settings.sub_agents.append(agent)
            self.console.print(f"[green]Sub-agent '{name}' added![/green]")

    def _edit_sub_agent(self) -> None:
        """Edit an existing sub-agent."""
        if not self.settings or not self.settings.sub_agents:
            self.console.print("[yellow]No sub-agents to edit.[/yellow]")
            return

        names = [a.name for a in self.settings.sub_agents]
        name = Prompt.ask("Sub-agent name to edit", choices=names)

        agent = next(a for a in self.settings.sub_agents if a.name == name)

        agent.description = Prompt.ask("Description", default=agent.description)

        if Confirm.ask("Update prompt?", default=False):
            self.console.print("[dim]Enter the new prompt (end with empty line):[/dim]")
            lines = []
            while True:
                line = Prompt.ask("", default="")
                if not line:
                    break
                lines.append(line)
            agent.prompt = "\n".join(lines)

        self.console.print(f"[green]Sub-agent '{name}' updated![/green]")

    def _delete_sub_agent(self) -> None:
        """Delete a sub-agent."""
        if not self.settings or not self.settings.sub_agents:
            self.console.print("[yellow]No sub-agents to delete.[/yellow]")
            return

        names = [a.name for a in self.settings.sub_agents]
        name = Prompt.ask("Sub-agent name to delete", choices=names)

        if Confirm.ask(f"Delete sub-agent '{name}'?", default=False):
            self.settings.sub_agents = [a for a in self.settings.sub_agents if a.name != name]
            self.console.print(f"[green]Sub-agent '{name}' deleted![/green]")

    # =========================================================================
    # MCP Servers Configuration
    # =========================================================================

    def _configure_mcp_servers(self) -> None:
        """Configure MCP servers."""
        self._print_header("MCP Servers Configuration")

        if self.settings is None:
            self.settings = Settings()

        while True:
            if self.settings.mcp_servers:
                table = Table(title="Configured MCP Servers")
                table.add_column("Name", style="cyan")
                table.add_column("Type")
                table.add_column("Command/URL")

                for server in self.settings.mcp_servers:
                    cmd_or_url = server.command or server.url or "N/A"
                    table.add_row(server.name, server.type.value, cmd_or_url[:40])

                self.console.print(table)
                self.console.print()

            choice = self._print_menu("MCP Server Options", [
                ("a", "Add new MCP server"),
                ("d", "Delete MCP server"),
                ("b", "Back to main menu"),
            ])

            if choice == "a":
                self._add_mcp_server()
            elif choice == "d":
                self._delete_mcp_server()
            elif choice == "b":
                break

    def _add_mcp_server(self) -> None:
        """Add a new MCP server."""
        self.console.print("[cyan]Adding new MCP server...[/cyan]")

        name = Prompt.ask("Server name")

        types = [t.value for t in MCPServerType if t != MCPServerType.SDK]
        server_type_str = Prompt.ask("Server type", choices=types, default="stdio")
        server_type = MCPServerType(server_type_str)

        server = MCPServerConfig(name=name, type=server_type)

        if server_type == MCPServerType.STDIO:
            server.command = Prompt.ask("Command (e.g., npx, python)")
            args_input = Prompt.ask("Arguments (comma-separated)", default="")
            server.args = [a.strip() for a in args_input.split(",") if a.strip()]

            if Confirm.ask("Add environment variables?", default=False):
                while True:
                    key = Prompt.ask("Env var name (empty to finish)", default="")
                    if not key:
                        break
                    value = Prompt.ask(f"Value for {key}")
                    server.env[key] = value
        else:
            server.url = Prompt.ask("Server URL")

            if Confirm.ask("Add headers?", default=False):
                while True:
                    key = Prompt.ask("Header name (empty to finish)", default="")
                    if not key:
                        break
                    value = Prompt.ask(f"Value for {key}")
                    server.headers[key] = value

        if self.settings:
            self.settings.mcp_servers.append(server)
            self.console.print(f"[green]MCP server '{name}' added![/green]")

    def _delete_mcp_server(self) -> None:
        """Delete an MCP server."""
        if not self.settings or not self.settings.mcp_servers:
            self.console.print("[yellow]No MCP servers to delete.[/yellow]")
            return

        names = [s.name for s in self.settings.mcp_servers]
        name = Prompt.ask("Server name to delete", choices=names)

        if Confirm.ask(f"Delete MCP server '{name}'?", default=False):
            self.settings.mcp_servers = [s for s in self.settings.mcp_servers if s.name != name]
            self.console.print(f"[green]MCP server '{name}' deleted![/green]")

    # =========================================================================
    # Slack Configuration
    # =========================================================================

    def _configure_slack(self) -> None:
        """Configure Slack notifications."""
        self._print_header("Slack Notifications Configuration")

        if self.settings is None:
            self.settings = Settings()

        self.settings.slack.enabled = Confirm.ask(
            "Enable Slack notifications?",
            default=self.settings.slack.enabled
        )

        if not self.settings.slack.enabled:
            return

        # Show masked existing webhook if set
        existing_webhook = self.settings.slack.webhook_url
        if existing_webhook:
            masked = f"{existing_webhook[:30]}...{existing_webhook[-10:]}" if len(existing_webhook) > 45 else existing_webhook
            self.console.print(f"Current webhook: [dim]{masked}[/dim]")

        if not existing_webhook or Confirm.ask("Update webhook URL?", default=not existing_webhook):
            self.console.print("[yellow]⚠ Security Warning:[/yellow] Webhook URLs are sensitive credentials.")
            self.console.print("[dim]Paste your webhook URL (input will be hidden):[/dim]")
            new_webhook = getpass.getpass("Slack Webhook URL: ")
            if new_webhook:
                self.settings.slack.webhook_url = new_webhook
                self.console.print("[green]Webhook URL updated![/green]")
            else:
                self.console.print("[yellow]No webhook URL entered.[/yellow]")

        self.settings.slack.username = Prompt.ask(
            "Bot username",
            default=self.settings.slack.username
        )

        self.settings.slack.icon_emoji = Prompt.ask(
            "Bot emoji",
            default=self.settings.slack.icon_emoji
        )

        self.settings.slack.notify_on_success = Confirm.ask(
            "Notify on success?",
            default=self.settings.slack.notify_on_success
        )

        self.settings.slack.notify_on_error = Confirm.ask(
            "Notify on error?",
            default=self.settings.slack.notify_on_error
        )

        self.settings.slack.include_cost = Confirm.ask(
            "Include cost info?",
            default=self.settings.slack.include_cost
        )

        self.settings.slack.include_duration = Confirm.ask(
            "Include duration?",
            default=self.settings.slack.include_duration
        )

        self.console.print("[green]Slack configuration updated![/green]")

    # =========================================================================
    # Logging Configuration
    # =========================================================================

    def _configure_logging(self) -> None:
        """Configure logging settings."""
        self._print_header("Logging Configuration")

        if self.settings is None:
            self.settings = Settings()

        self.settings.logging.enabled = Confirm.ask(
            "Enable logging?",
            default=self.settings.logging.enabled
        )

        if not self.settings.logging.enabled:
            return

        log_dir = Prompt.ask(
            "Log directory",
            default=str(self.settings.logging.log_dir)
        )
        self.settings.logging.log_dir = Path(log_dir)

        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        self.settings.logging.log_level = Prompt.ask(
            "Log level",
            default=self.settings.logging.log_level,
            choices=levels
        )

        self.settings.logging.log_agent_trace = Confirm.ask(
            "Log full agent trace?",
            default=self.settings.logging.log_agent_trace
        )

        self.settings.logging.separate_trace_file = Confirm.ask(
            "Use separate trace file?",
            default=self.settings.logging.separate_trace_file
        )

        self.settings.logging.rotate_logs = Confirm.ask(
            "Enable log rotation?",
            default=self.settings.logging.rotate_logs
        )

        if self.settings.logging.rotate_logs:
            self.settings.logging.max_log_size_mb = IntPrompt.ask(
                "Max log size (MB)",
                default=self.settings.logging.max_log_size_mb
            )
            self.settings.logging.backup_count = IntPrompt.ask(
                "Backup count",
                default=self.settings.logging.backup_count
            )

        self.console.print("[green]Logging configuration updated![/green]")

    # =========================================================================
    # Bedrock Configuration
    # =========================================================================

    def _configure_bedrock(self) -> None:
        """Configure AWS Bedrock settings."""
        self._print_header("AWS Bedrock Configuration")

        if self.settings is None:
            self.settings = Settings()

        self.settings.bedrock.enabled = Confirm.ask(
            "Enable AWS Bedrock?",
            default=self.settings.bedrock.enabled
        )

        if not self.settings.bedrock.enabled:
            return

        self.settings.bedrock.region = Prompt.ask(
            "AWS Region",
            default=self.settings.bedrock.region
        )

        profile = Prompt.ask(
            "AWS Profile (leave empty for default)",
            default=self.settings.bedrock.profile or ""
        )
        self.settings.bedrock.profile = profile if profile else None

        model_id = Prompt.ask(
            "Bedrock Model ID",
            default=self.settings.bedrock.bedrock_model_id or "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
        self.settings.bedrock.bedrock_model_id = model_id

        self.console.print("[green]Bedrock configuration updated![/green]")

    # =========================================================================
    # Sandbox Configuration
    # =========================================================================

    def _configure_sandbox(self) -> None:
        """Configure sandbox settings."""
        self._print_header("Sandbox Configuration")

        if self.settings is None:
            self.settings = Settings()

        self.settings.sandbox.enabled = Confirm.ask(
            "Enable sandbox mode?",
            default=self.settings.sandbox.enabled
        )

        if not self.settings.sandbox.enabled:
            return

        self.settings.sandbox.auto_allow_bash = Confirm.ask(
            "Auto-allow bash commands in sandbox?",
            default=self.settings.sandbox.auto_allow_bash
        )

        if Confirm.ask("Configure excluded commands?", default=False):
            excluded = Prompt.ask(
                "Excluded commands (comma-separated)",
                default=",".join(self.settings.sandbox.excluded_commands)
            )
            self.settings.sandbox.excluded_commands = [c.strip() for c in excluded.split(",") if c.strip()]

        self.console.print("[green]Sandbox configuration updated![/green]")

    # =========================================================================
    # View and Save Configuration
    # =========================================================================

    def _view_config(self) -> None:
        """View current configuration."""
        self._print_header("Current Configuration")

        if self.settings is None:
            self.console.print("[yellow]No configuration loaded.[/yellow]")
            return

        # Show as YAML-ish format
        import yaml
        config_dict = self.settings.model_dump(exclude_none=True, exclude_defaults=True)

        # Convert paths to strings
        def convert_paths(obj: Any) -> Any:
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            return obj

        config_dict = convert_paths(config_dict)

        yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
        syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def _save_config(self) -> None:
        """Save configuration to files."""
        self._print_header("Save Configuration")

        if self.settings is None:
            self.console.print("[yellow]No configuration to save.[/yellow]")
            return

        choice = self._print_menu("Save Format", [
            ("e", "Save as .env file"),
            ("y", "Save as YAML file"),
            ("b", "Save both"),
            ("c", "Cancel"),
        ])

        if choice == "c":
            return

        if choice in ["e", "b"]:
            env_path = self.config_dir / ".env"
            env_content = self.settings.generate_env_template()

            # Fill in actual values
            if self.settings.anthropic_api_key:
                env_content = env_content.replace(
                    "ANTHROPIC_API_KEY=",
                    f"ANTHROPIC_API_KEY={self.settings.anthropic_api_key}"
                )

            with open(env_path, "w") as f:
                f.write(env_content)
            self.console.print(f"[green]Saved to {env_path}[/green]")

        if choice in ["y", "b"]:
            yaml_path = self.config_dir / "config.yaml"
            self.settings.save_to_yaml(yaml_path)
            self.console.print(f"[green]Saved to {yaml_path}[/green]")

    def _generate_env_template(self) -> None:
        """Generate a .env template file."""
        self._print_header("Generate .env Template")

        if self.settings is None:
            self.settings = Settings()

        env_content = self.settings.generate_env_template()

        output_path = self.config_dir / ".env.template"
        with open(output_path, "w") as f:
            f.write(env_content)

        self.console.print(f"[green]Template saved to {output_path}[/green]")
        self.console.print()
        self.console.print("[dim]Preview:[/dim]")
        syntax = Syntax(env_content[:2000], "bash", theme="monokai")
        self.console.print(syntax)

    # =========================================================================
    # Test Agent
    # =========================================================================

    def _test_agent(self) -> None:
        """Test the agent with current configuration."""
        self._print_header("Test Agent")

        if self.settings is None:
            self.console.print("[yellow]No configuration loaded.[/yellow]")
            return

        prompt = Prompt.ask(
            "Test prompt",
            default="Hello! Please confirm you're working correctly."
        )

        self.console.print("[cyan]Running agent...[/cyan]")
        self.console.print()

        # Import and run
        import anyio

        from claude_agent_framework.core.engine import AgentEngine
        from claude_agent_framework.tracking.logger import AgentLogger

        logger = AgentLogger(
            name=self.settings.agent.name,
            log_dir=self.settings.logging.log_dir,
            console_output=True,
            rich_console=self.console,
        )

        engine = AgentEngine(settings=self.settings, logger=logger)

        async def run_test():
            result = await engine.run(prompt)
            return result

        try:
            result = anyio.run(run_test)
            logger.display_result_summary(result)
            logger.display_final_message(result)
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")


def main(config_dir: Path | None = None) -> None:
    """
    Main entry point for the TUI.

    Args:
        config_dir: Configuration directory. If None and called from command line,
                    parses from sys.argv. If None and called programmatically,
                    uses current working directory.
    """
    if config_dir is None:
        # Check if we're being called directly (caf-tui) or from the CLI (caf config --tui)
        import sys
        if len(sys.argv) > 0 and sys.argv[0].endswith('caf-tui'):
            # Called as standalone caf-tui command, parse args
            import argparse
            parser = argparse.ArgumentParser(description="Claude Agent Framework Configuration TUI")
            parser.add_argument(
                "--dir",
                type=Path,
                default=Path.cwd(),
                help="Configuration directory",
            )
            args = parser.parse_args()
            config_dir = args.dir
        else:
            # Called from caf config --tui or programmatically
            config_dir = Path.cwd()

    tui = ConfigTUI(config_dir=config_dir)
    tui.run()


if __name__ == "__main__":
    main()
