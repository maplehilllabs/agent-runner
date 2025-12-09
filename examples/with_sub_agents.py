#!/usr/bin/env python3
"""
Example using sub-agents for complex workflows.

This example demonstrates:
- Defining multiple sub-agents
- Using specialized agents for different tasks
- Sub-agent tool restrictions
"""

import asyncio
from pathlib import Path

from claude_agent_framework import AgentRunner, Settings
from claude_agent_framework.config.settings import (
    AgentConfig,
    SubAgentConfig,
    ModelType,
    LoggingConfig,
    SlackConfig,
)


async def main():
    """Run an agent with sub-agents."""

    # Define sub-agents
    sub_agents = [
        SubAgentConfig(
            name="code-reviewer",
            description="Use for reviewing code quality, security, and best practices.",
            prompt="""You are an expert code reviewer. Focus on:
- Security vulnerabilities
- Code quality and maintainability
- Performance issues
- Best practices

Be specific and provide actionable feedback.""",
            tools=["Read", "Grep", "Glob"],
            model=ModelType.SONNET,
        ),
        SubAgentConfig(
            name="test-analyzer",
            description="Use for analyzing test coverage and test quality.",
            prompt="""You are a test analysis specialist. Focus on:
- Test coverage gaps
- Test quality and reliability
- Missing edge cases
- Test organization

Provide specific recommendations.""",
            tools=["Read", "Grep", "Glob", "Bash"],
            model=ModelType.HAIKU,  # Use faster model for test analysis
        ),
    ]

    # Configure settings
    settings = Settings(
        agent=AgentConfig(
            name="code-analysis-agent",
            model=ModelType.SONNET,
            max_turns=30,
            cwd=Path.cwd(),
        ),
        sub_agents=sub_agents,
        logging=LoggingConfig(
            enabled=True,
            log_dir=Path("./logs"),
        ),
    )

    # Create runner
    runner = AgentRunner(settings)

    # Run analysis task
    result = await runner.run_once(
        prompt="""Analyze the Python code in this project:

1. First, use the code-reviewer to check for quality issues
2. Then, use the test-analyzer to evaluate test coverage
3. Summarize findings and provide top recommendations

Focus on the most impactful improvements.""",
        task_description="Code quality analysis",
    )

    print(f"\nAnalysis Complete!")
    print(f"Status: {result.status.value}")
    print(f"Cost: ${result.total_cost_usd:.4f}")
    print(f"Tool Calls: {len(result.tool_calls)}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
