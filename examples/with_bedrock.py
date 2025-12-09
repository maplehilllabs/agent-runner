#!/usr/bin/env python3
"""
Example using AWS Bedrock.

This example demonstrates:
- Configuring AWS Bedrock
- Using Bedrock model IDs
- AWS credential setup
"""

import asyncio
from pathlib import Path

from claude_agent_framework import AgentRunner, Settings
from claude_agent_framework.config.settings import (
    AgentConfig,
    ModelType,
    LoggingConfig,
    BedrockConfig,
)


async def main():
    """Run an agent using AWS Bedrock."""

    # Configure settings with Bedrock
    settings = Settings(
        agent=AgentConfig(
            name="bedrock-agent",
            model=ModelType.SONNET,
            max_turns=20,
        ),
        bedrock=BedrockConfig(
            enabled=True,
            region="us-east-1",
            # Use AWS profile for credentials
            # profile="default",
            # Or use environment variables:
            # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

            # Specify Bedrock model ID
            model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            # For faster operations:
            # small_model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        ),
        logging=LoggingConfig(
            enabled=True,
            log_dir=Path("./logs"),
        ),
    )

    # Create runner
    runner = AgentRunner(settings)

    # Run a task via Bedrock
    result = await runner.run_once(
        prompt="What are the key benefits of using AWS Bedrock for Claude?",
        task_description="Bedrock info query",
    )

    print(f"Status: {result.status.value}")
    print(f"Using Bedrock: {settings.bedrock.enabled}")
    print(f"Region: {settings.bedrock.region}")
    print(f"Cost: ${result.total_cost_usd:.4f}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
