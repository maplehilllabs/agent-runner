"""
CLI entry point for Claude Agent Framework.

Provides commands for:
- Running agents (once, service, cron)
- Configuration management
- Status and cost reporting
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claude_agent_framework.config.settings import Settings, load_settings
from claude_agent_framework.core.runner import AgentRunner

app = typer.Typer(
    name="caf",
    help="Claude Agent Framework - Run Claude agents for automation tasks",
    add_completion=False,
)

console = Console()


def load_config(
    env_file: Path | None = None,
    config_file: Path | None = None,
) -> Settings:
    """Load configuration from files."""
    return load_settings(env_file=env_file, config_file=config_file)


@app.command()
def run(
    prompt: str | None = typer.Argument(
        None,
        help="Task prompt for the agent",
    ),
    prompt_file: Path | None = typer.Option(
        None,
        "--prompt-file",
        "-f",
        help="File containing the task prompt",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Path to .env file",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml file",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Override model (sonnet, opus, haiku)",
    ),
    max_turns: int | None = typer.Option(
        None,
        "--max-turns",
        "-t",
        help="Maximum conversation turns",
    ),
    max_budget: float | None = typer.Option(
        None,
        "--max-budget",
        "-b",
        help="Maximum budget in USD",
    ),
    cwd: Path | None = typer.Option(
        None,
        "--cwd",
        "-d",
        help="Working directory for the agent",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output result as JSON",
    ),
) -> None:
    """
    Run the agent once with a task prompt.

    This is ideal for cron jobs or one-off tasks.

    Examples:
        caf run "Analyze the database logs for errors"
        caf run -f prompts/daily_check.md
        caf run "Check server health" --max-budget 1.0
    """
    # Load configuration
    settings = load_config(env_file, config_file)

    # Apply CLI overrides
    if model:
        from claude_agent_framework.config.settings import ModelType
        settings.agent.model = ModelType(model)

    if max_turns:
        settings.agent.max_turns = max_turns

    if max_budget:
        settings.agent.max_budget_usd = max_budget

    if cwd:
        settings.agent.cwd = cwd

    # Get prompt
    task_prompt = prompt
    if prompt_file and prompt_file.exists():
        task_prompt = prompt_file.read_text()
    elif not task_prompt:
        task_prompt = settings.get_task_prompt()

    if not task_prompt:
        console.print("[red]Error: No prompt provided. Use argument or --prompt-file[/red]")
        raise typer.Exit(1)

    # Run agent
    runner = AgentRunner(settings, console=console if not quiet else None)

    async def execute():
        return await runner.run_once(task_prompt, task_description=task_prompt[:100])

    result = asyncio.run(execute())

    # Output result
    if json_output:
        import json
        console.print(json.dumps(result.to_dict(), indent=2, default=str))
    elif not quiet:
        if not result.is_success:
            console.print(f"[red]Agent failed: {result.error}[/red]")
            raise typer.Exit(1)

    raise typer.Exit(0 if result.is_success else 1)


@app.command()
def service(
    prompt: str | None = typer.Argument(
        None,
        help="Task prompt for the agent",
    ),
    prompt_file: Path | None = typer.Option(
        None,
        "--prompt-file",
        "-f",
        help="File containing the task prompt",
    ),
    interval: int = typer.Option(
        3600,
        "--interval",
        "-i",
        help="Interval between runs in seconds",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Path to .env file",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml file",
    ),
) -> None:
    """
    Run the agent as a continuous service.

    The agent will execute at regular intervals until stopped (Ctrl+C).

    Examples:
        caf service "Monitor system logs" --interval 1800
        caf service -f prompts/monitor.md -i 3600
    """
    settings = load_config(env_file, config_file)
    settings.service_mode = True
    settings.service_interval_seconds = interval

    # Get prompt
    task_prompt = prompt
    if prompt_file and prompt_file.exists():
        task_prompt = prompt_file.read_text()
    elif not task_prompt:
        task_prompt = settings.get_task_prompt()

    if not task_prompt:
        console.print("[red]Error: No prompt provided.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[cyan]Starting service mode[/cyan]\n"
        f"Interval: {interval}s\n"
        f"Task: {task_prompt[:100]}...\n"
        f"Press Ctrl+C to stop",
        title="Claude Agent Service",
    ))

    runner = AgentRunner(settings, console=console)

    asyncio.run(runner.run_service(task_prompt, task_description=task_prompt[:100]))


@app.command()
def cron(
    prompt: str | None = typer.Argument(
        None,
        help="Task prompt for the agent",
    ),
    schedule: str = typer.Option(
        ...,
        "--schedule",
        "-s",
        help="Cron schedule expression (e.g., '0 * * * *' for hourly)",
    ),
    prompt_file: Path | None = typer.Option(
        None,
        "--prompt-file",
        "-f",
        help="File containing the task prompt",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Path to .env file",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml file",
    ),
) -> None:
    """
    Run the agent on a cron schedule.

    Uses cron expression syntax for scheduling.

    Examples:
        caf cron "Daily backup check" --schedule "0 2 * * *"
        caf cron -f prompts/hourly.md -s "0 * * * *"
    """
    settings = load_config(env_file, config_file)
    settings.cron_schedule = schedule

    # Get prompt
    task_prompt = prompt
    if prompt_file and prompt_file.exists():
        task_prompt = prompt_file.read_text()
    elif not task_prompt:
        task_prompt = settings.get_task_prompt()

    if not task_prompt:
        console.print("[red]Error: No prompt provided.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[cyan]Starting cron mode[/cyan]\n"
        f"Schedule: {schedule}\n"
        f"Task: {task_prompt[:100]}...\n"
        f"Press Ctrl+C to stop",
        title="Claude Agent Cron",
    ))

    runner = AgentRunner(settings, console=console)

    asyncio.run(runner.run_with_cron(task_prompt, task_description=task_prompt[:100]))


@app.command()
def config(
    generate_env: bool = typer.Option(
        False,
        "--generate-env",
        "-g",
        help="Generate .env template file",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        "-s",
        help="Show current configuration",
    ),
    tui: bool = typer.Option(
        False,
        "--tui",
        "-t",
        help="Launch interactive TUI",
    ),
    output_dir: Path = typer.Option(
        Path.cwd(),
        "--output",
        "-o",
        help="Output directory for generated files",
    ),
) -> None:
    """
    Manage configuration.

    Generate templates, view config, or launch the interactive TUI.

    Examples:
        caf config --generate-env
        caf config --show
        caf config --tui
    """
    if tui:
        from claude_agent_framework.tui import main as tui_main
        tui_main(config_dir=output_dir)
        return

    settings = Settings()

    if generate_env:
        template = settings.generate_env_template()
        output_file = output_dir / ".env.template"
        output_file.write_text(template)
        console.print(f"[green]Generated {output_file}[/green]")
        return

    if show:
        import yaml
        config_dict = settings.model_dump(exclude_none=True)
        # Mask sensitive values
        if config_dict.get("anthropic_api_key"):
            key = config_dict["anthropic_api_key"]
            config_dict["anthropic_api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        if config_dict.get("slack", {}).get("webhook_url"):
            config_dict["slack"]["webhook_url"] = "***"

        yaml_str = yaml.dump(config_dict, default_flow_style=False)
        from rich.syntax import Syntax
        console.print(Syntax(yaml_str, "yaml", theme="monokai"))
        return

    # Default: show help
    console.print("Use --generate-env, --show, or --tui. Run 'caf config --help' for details.")


@app.command()
def costs(
    env_file: Path | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Path to .env file",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml file",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        "-r",
        help="Reset cost tracking",
    ),
) -> None:
    """
    View cost tracking information.

    Shows cumulative costs and recent usage.

    Examples:
        caf costs
        caf costs --reset
    """
    settings = load_config(env_file, config_file)

    from claude_agent_framework.tracking.cost_tracker import CostTracker

    cost_storage = settings.logging.log_dir / "costs.json"
    tracker = CostTracker(
        storage_path=cost_storage,
        budget_limit_usd=settings.agent.max_budget_usd,
    )

    if reset:
        if typer.confirm("Reset all cost tracking data?"):
            tracker.reset()
            console.print("[green]Cost tracking reset.[/green]")
        return

    report = tracker.get_report()

    table = Table(title="Cost Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Cost", f"${report['total_cost_usd']:.4f}")
    table.add_row("Total Sessions", str(report['total_sessions']))
    table.add_row("Total Tokens", f"{report['total_tokens']:,}")
    table.add_row("Input Tokens", f"{report['total_input_tokens']:,}")
    table.add_row("Output Tokens", f"{report['total_output_tokens']:,}")
    table.add_row("Avg Cost/Session", f"${report['average_cost_per_session']:.4f}")

    if report['budget_limit_usd']:
        table.add_row("Budget Limit", f"${report['budget_limit_usd']:.2f}")
        table.add_row("Remaining", f"${report['remaining_budget_usd']:.2f}")

    console.print(table)

    if report['recent_entries']:
        console.print()
        recent_table = Table(title="Recent Sessions")
        recent_table.add_column("Time", style="dim")
        recent_table.add_column("Session", style="cyan")
        recent_table.add_column("Tokens", style="green")
        recent_table.add_column("Cost", style="yellow")

        for entry in report['recent_entries']:
            recent_table.add_row(
                entry['timestamp'][:19],
                entry['session_id'][:12] + "..." if entry['session_id'] else "N/A",
                f"{entry['tokens']:,}",
                f"${entry['cost_usd']:.4f}",
            )

        console.print(recent_table)


@app.command()
def auth(
    env_file: Path | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Path to .env file",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml file",
    ),
) -> None:
    """
    Show authentication configuration.

    Displays which auth method will be used (Anthropic API or AWS Bedrock).

    Examples:
        caf auth
        caf auth --config config.yaml
    """
    settings = load_config(env_file, config_file)

    from claude_agent_framework.core.engine import AgentEngine
    engine = AgentEngine(settings)
    auth_info = engine.get_auth_info()

    table = Table(title="Authentication Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    for key, value in auth_info.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)

    if auth_info.get("method") == "Unknown":
        console.print("[red]Warning: No valid authentication configured![/red]")
        console.print("Set ANTHROPIC_API_KEY or enable Bedrock in config.")


@app.command()
def version() -> None:
    """Show version information."""
    from claude_agent_framework import __version__

    console.print(Panel(
        f"[cyan]Claude Agent Framework[/cyan]\n"
        f"Version: {__version__}",
        title="Version Info",
    ))


if __name__ == "__main__":
    app()
