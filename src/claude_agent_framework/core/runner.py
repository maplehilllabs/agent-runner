"""
Agent Runner - Orchestrates agent execution with full lifecycle management.

Handles:
- Single execution (cron mode)
- Service mode (continuous execution)
- Logging and notifications
- Cost tracking
"""

from __future__ import annotations

import asyncio
import platform
import signal
from collections.abc import Callable
from datetime import datetime

from rich.console import Console

from claude_agent_framework.config.settings import Settings
from claude_agent_framework.core.engine import AgentEngine
from claude_agent_framework.core.result import AgentResult, AgentStatus, TodoItem
from claude_agent_framework.notifications.slack import SlackNotifier
from claude_agent_framework.tracking.cost_tracker import CostTracker
from claude_agent_framework.tracking.logger import AgentLogger


class AgentRunner:
    """
    High-level agent runner with full lifecycle management.

    Features:
    - Single execution mode (for cron jobs)
    - Service mode (continuous execution with intervals)
    - Comprehensive logging and tracing
    - Slack notifications
    - Cost tracking and budget enforcement
    """

    def __init__(
        self,
        settings: Settings,
        console: Console | None = None,
        on_result: Callable[[AgentResult], None] | None = None,
    ):
        """
        Initialize the agent runner.

        Args:
            settings: Configuration settings
            console: Rich console for output
            on_result: Callback when agent completes
        """
        self.settings = settings
        self.console = console or Console()
        self.on_result = on_result

        # Initialize logger
        self.logger = AgentLogger(
            name=settings.agent.name,
            log_dir=settings.logging.log_dir,
            log_level=settings.logging.log_level,
            log_format=settings.logging.log_format,
            rotate_logs=settings.logging.rotate_logs,
            max_log_size_mb=settings.logging.max_log_size_mb,
            backup_count=settings.logging.backup_count,
            log_agent_trace=settings.logging.log_agent_trace,
            log_tool_calls=settings.logging.log_tool_calls,
            log_token_usage=settings.logging.log_token_usage,
            separate_trace_file=settings.logging.separate_trace_file,
            console_output=True,
            rich_console=self.console,
        ) if settings.logging.enabled else None

        # Initialize Slack notifier
        self.slack = SlackNotifier(settings.slack)

        # Initialize cost tracker
        cost_storage = settings.logging.log_dir / "costs.json" if settings.logging.enabled else None
        self.cost_tracker = CostTracker(
            storage_path=cost_storage,
            budget_limit_usd=settings.agent.max_budget_usd,
        )

        # Initialize engine
        self.engine = AgentEngine(
            settings=settings,
            logger=self.logger,
            on_todo_update=self._on_todo_update,
        )

        # Service mode state
        self._running = False
        self._shutdown_event = asyncio.Event()

    def _on_todo_update(self, todos: list[TodoItem]) -> None:
        """Handle todo updates."""
        if self.console:
            self.console.print("[cyan]Todo Update:[/cyan]")
            for todo in todos:
                status_icon = {
                    "completed": "[green]✓[/green]",
                    "in_progress": "[yellow]⟳[/yellow]",
                    "pending": "[dim]○[/dim]",
                }.get(todo.status, "○")
                self.console.print(f"  {status_icon} {todo.content}")

    async def run_once(
        self,
        prompt: str | None = None,
        task_description: str = "",
    ) -> AgentResult:
        """
        Run the agent once (cron mode).

        Args:
            prompt: Task prompt (uses settings.task_prompt if not provided)
            task_description: Description for notifications

        Returns:
            AgentResult with execution results
        """
        # Get prompt
        task_prompt = prompt or self.settings.get_task_prompt()
        if not task_prompt:
            raise ValueError("No task prompt provided")

        # Check budget before running
        within_budget, budget_msg = self.cost_tracker.check_budget()
        if not within_budget:
            if self.logger:
                self.logger.log_error(f"Budget exceeded: {budget_msg}")
            result = AgentResult(
                status=AgentStatus.BUDGET_EXCEEDED,
                error=budget_msg,
            )
            await self._handle_result(result, task_description or task_prompt[:100])
            return result

        # Start logging session
        if self.logger:
            self.logger.start_session()
            self.logger.log_info(f"Starting task: {task_prompt[:100]}...")

        try:
            # Run the agent
            result = await self.engine.run(task_prompt)

            # Track cost
            self.cost_tracker.track_result(
                result,
                model=self.settings.agent.model.value,
                task_description=task_description or task_prompt[:100],
            )

            # Handle result
            await self._handle_result(result, task_description or task_prompt[:100])

            return result

        finally:
            if self.logger:
                self.logger.end_session()

    async def _handle_result(
        self,
        result: AgentResult,
        task_description: str,
    ) -> None:
        """Handle agent result - logging, notifications, callbacks."""
        # Log result
        if self.logger:
            self.logger.log_result(result)
            self.logger.display_result_summary(result)
            self.logger.display_final_message(result)

            # Save full trace
            self.logger.save_full_trace(result)

        # Send Slack notification
        if self.slack.enabled:
            await self.slack.notify_result(result, task_description)

        # Call result callback
        if self.on_result:
            self.on_result(result)

    async def run_service(
        self,
        prompt: str | None = None,
        task_description: str = "",
    ) -> None:
        """
        Run the agent as a service (continuous mode).

        Executes the task at regular intervals until stopped.

        Args:
            prompt: Task prompt
            task_description: Description for notifications
        """
        self._running = True
        self._shutdown_event.clear()

        # Setup signal handlers (not available on Windows)
        if platform.system() != "Windows":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_shutdown)

        if self.logger:
            self.logger.log_info(f"Starting service mode (interval: {self.settings.service_interval_seconds}s)")

        run_count = 0
        while self._running:
            run_count += 1

            if self.logger:
                self.logger.log_info(f"Service run #{run_count}")

            try:
                result = await self.run_once(prompt, task_description)

                if not result.is_success:
                    if self.logger:
                        self.logger.log_warning(f"Run #{run_count} failed: {result.error}")

            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Run #{run_count} error: {e}")

            # Wait for next interval or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.settings.service_interval_seconds,
                )
                # Shutdown was requested
                break
            except asyncio.TimeoutError:
                # Normal timeout, continue to next run
                pass

        if self.logger:
            self.logger.log_info("Service stopped")

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        if self.logger:
            self.logger.log_info("Shutdown requested...")
        self._running = False
        self._shutdown_event.set()

    async def run_with_cron(
        self,
        prompt: str | None = None,
        task_description: str = "",
    ) -> None:
        """
        Run the agent on a cron schedule.

        Args:
            prompt: Task prompt
            task_description: Description for notifications
        """
        if not self.settings.cron_schedule:
            raise ValueError("No cron schedule configured")

        try:
            from croniter import croniter
        except ImportError:
            raise ImportError("croniter is required for cron scheduling. Install with: pip install croniter")

        self._running = True
        self._shutdown_event.clear()

        # Setup signal handlers (not available on Windows)
        if platform.system() != "Windows":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_shutdown)

        cron = croniter(self.settings.cron_schedule)

        if self.logger:
            self.logger.log_info(f"Starting cron mode (schedule: {self.settings.cron_schedule})")

        run_count = 0
        while self._running:
            # Calculate next run time
            next_run = cron.get_next(datetime)
            wait_seconds = (next_run - datetime.now()).total_seconds()

            if wait_seconds > 0:
                if self.logger:
                    self.logger.log_info(f"Next run at {next_run} (in {wait_seconds:.0f}s)")

                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=wait_seconds,
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Time for next run

            run_count += 1
            if self.logger:
                self.logger.log_info(f"Cron run #{run_count}")

            try:
                result = await self.run_once(prompt, task_description)

                if not result.is_success:
                    if self.logger:
                        self.logger.log_warning(f"Run #{run_count} failed: {result.error}")

            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Run #{run_count} error: {e}")

        if self.logger:
            self.logger.log_info("Cron service stopped")

    def stop(self) -> None:
        """Stop the service."""
        self._handle_shutdown()

    def get_cost_report(self) -> dict:
        """Get current cost report."""
        return self.cost_tracker.get_report()
