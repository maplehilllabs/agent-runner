#!/usr/bin/env python3
"""
Basic usage example for Claude Agent Framework.

This example demonstrates:
- Simple one-off task execution
- Result handling
- Cost tracking
"""

import asyncio
from pathlib import Path

from claude_agent_framework import AgentRunner, Settings
from claude_agent_framework.config.settings import AgentConfig, ModelType, LoggingConfig


async def main():
    """Run a simple agent task."""

    # Configure the agent
    settings = Settings(
        # API key from environment (ANTHROPIC_API_KEY) or set directly
        # anthropic_api_key="sk-ant-...",

        agent=AgentConfig(
            name="example-agent",
            model=ModelType.SONNET,
            max_turns=10,
            system_prompt_type="append",
            system_prompt_content="Be concise and focused.",
        ),

        logging=LoggingConfig(
            enabled=True,
            log_dir=Path("./logs"),
            log_level="INFO",
        ),
    )

    # Create runner
    runner = AgentRunner(settings)

    # Run a simple task
    result = await runner.run_once(
        prompt="What are the top 3 best practices for Python error handling? Be brief.",
        task_description="Python best practices query",
    )

    # Check results
    print(f"\n{'='*50}")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Total Cost: ${result.total_cost_usd:.4f}")
    print(f"Tokens Used: {result.total_usage.total_tokens:,}")
    print(f"{'='*50}")

    print("\nAgent Response:")
    print(result.get_final_message())

    return result


if __name__ == "__main__":
    asyncio.run(main())
