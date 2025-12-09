# Claude Agent Framework

A modular, production-ready framework for running Claude agents in automated workflows. Perfect for cron jobs, services, data processing, log analysis, and any task that benefits from AI automation.

## Features

- **Flexible Execution Modes**: Run once (cron), continuously (service), or on a schedule
- **Full Agent SDK Support**: All Claude Agent SDK features including tools, sub-agents, MCP servers
- **AWS Bedrock Integration**: Use Claude via AWS Bedrock with full authentication support
- **Comprehensive Configuration**: Configure via `.env`, YAML, or programmatically
- **Rich TUI**: Interactive terminal interface for configuration management
- **Cost Tracking**: Monitor token usage and costs with budget enforcement
- **Full Logging**: Complete agent traces with structured logging
- **Slack Notifications**: Send results to Slack via webhook
- **Sub-Agent Support**: Define specialized sub-agents for complex workflows
- **MCP Server Integration**: Connect external tools via Model Context Protocol

## Installation

```bash
# Install from source
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- Claude Agent SDK (`claude-agent-sdk>=0.1.12`)
- Anthropic API key or AWS Bedrock access

## Quick Start

### 1. Generate Configuration

```bash
# Generate .env template
caf config --generate-env

# Or use the interactive TUI
caf config --tui
```

### 2. Set Your API Key

```bash
# In .env file
ANTHROPIC_API_KEY=sk-ant-...

# Or for AWS Bedrock
CAF_BEDROCK__ENABLED=true
CAF_BEDROCK__REGION=us-east-1
```

### 3. Run Your First Task

```bash
# Simple one-off task
caf run "Analyze the Python files in this directory for code quality issues"

# From a prompt file
caf run -f prompts/daily_check.md

# With budget limit
caf run "Check database logs for errors" --max-budget 1.0
```

## Execution Modes

### One-Off Execution (Cron Mode)

Perfect for scheduled tasks via cron:

```bash
# Run once and exit
caf run "Generate daily report from logs in /var/log/app"

# Example crontab entry (runs at 2 AM daily)
0 2 * * * cd /path/to/project && caf run -f prompts/daily_report.md
```

### Service Mode

Continuous execution with configurable intervals:

```bash
# Run every hour
caf service "Monitor application health" --interval 3600

# Run every 30 minutes
caf service -f prompts/monitor.md -i 1800
```

### Cron Schedule Mode

Built-in cron expression support:

```bash
# Run at 2 AM every day
caf cron "Daily backup verification" --schedule "0 2 * * *"

# Run every hour
caf cron -f prompts/hourly_check.md -s "0 * * * *"
```

## Configuration

### Environment Variables

All settings can be configured via environment variables with the `CAF_` prefix:

```bash
# Core Settings
ANTHROPIC_API_KEY=sk-ant-...
CAF_AGENT__NAME=my-agent
CAF_AGENT__MODEL=sonnet
CAF_AGENT__MAX_TURNS=50
CAF_AGENT__MAX_BUDGET_USD=10.0

# AWS Bedrock
CAF_BEDROCK__ENABLED=true
CAF_BEDROCK__REGION=us-east-1
CAF_BEDROCK__PROFILE=default

# Slack Notifications
CAF_SLACK__ENABLED=true
CAF_SLACK__WEBHOOK_URL=https://hooks.slack.com/...
CAF_SLACK__NOTIFY_ON_SUCCESS=true
CAF_SLACK__NOTIFY_ON_ERROR=true

# Logging
CAF_LOGGING__LOG_DIR=./logs
CAF_LOGGING__LOG_LEVEL=INFO
CAF_LOGGING__LOG_AGENT_TRACE=true
```

### YAML Configuration

For complex configurations, use a YAML file:

```yaml
# config.yaml
agent:
  name: data-processor
  model: sonnet
  max_turns: 100
  system_prompt_type: append
  system_prompt_content: |
    You are a data processing specialist.
    Focus on accuracy and efficiency.

sub_agents:
  - name: data-validator
    description: Validates data quality and integrity
    prompt: |
      You are a data validation specialist.
      Check for missing values, outliers, and inconsistencies.
    tools:
      - Read
      - Grep
      - Bash

slack:
  enabled: true
  webhook_url: ${SLACK_WEBHOOK_URL}
  notify_on_success: true
  include_cost: true

logging:
  log_dir: ./logs
  log_agent_trace: true
  separate_trace_file: true
```

### Interactive TUI

Launch the interactive configuration interface:

```bash
caf config --tui
# Or directly
caf-tui
```

The TUI provides:
- Visual configuration editing
- Sub-agent management
- MCP server setup
- Slack notification configuration
- Configuration testing

## Sub-Agents

Define specialized sub-agents for complex workflows:

```yaml
sub_agents:
  - name: code-reviewer
    description: Expert code reviewer for security and quality
    prompt: |
      You are an expert code reviewer.
      Focus on security vulnerabilities and best practices.
    tools:
      - Read
      - Grep
      - Glob
    model: sonnet

  - name: log-analyzer
    description: Analyzes application logs for errors
    prompt: |
      You are a log analysis expert.
      Identify error patterns and root causes.
    tools:
      - Read
      - Grep
      - Bash
```

### Built-in Agent Templates

Use pre-built templates for common use cases:

```python
from claude_agent_framework.agents import (
    CODE_REVIEWER_AGENT,
    DATA_ANALYST_AGENT,
    LOG_ANALYZER_AGENT,
    SECURITY_AUDITOR_AGENT,
)

settings.sub_agents = [CODE_REVIEWER_AGENT, LOG_ANALYZER_AGENT]
```

## MCP Server Integration

Connect external tools via MCP:

```yaml
mcp_servers:
  - name: filesystem
    type: stdio
    command: npx
    args:
      - "@modelcontextprotocol/server-filesystem"
    env:
      ALLOWED_PATHS: /data

  - name: database
    type: http
    url: https://api.example.com/mcp
    headers:
      Authorization: Bearer ${DB_API_KEY}
```

## Logging and Tracing

Complete execution traces are saved automatically:

```
logs/
├── my-agent.log              # Main log file
├── my-agent_trace.jsonl      # Structured trace (JSONL)
├── session_20241201_trace.jsonl  # Per-session trace
├── trace_abc123.json         # Full execution result
└── costs.json                # Cost tracking data
```

### Log Configuration

```bash
CAF_LOGGING__ENABLED=true
CAF_LOGGING__LOG_DIR=./logs
CAF_LOGGING__LOG_LEVEL=INFO
CAF_LOGGING__LOG_AGENT_TRACE=true
CAF_LOGGING__SEPARATE_TRACE_FILE=true
CAF_LOGGING__ROTATE_LOGS=true
CAF_LOGGING__MAX_LOG_SIZE_MB=10
```

## Slack Notifications

Receive execution results via Slack:

```bash
CAF_SLACK__ENABLED=true
CAF_SLACK__WEBHOOK_URL=https://hooks.slack.com/services/...
CAF_SLACK__USERNAME=Claude Agent
CAF_SLACK__NOTIFY_ON_SUCCESS=true
CAF_SLACK__NOTIFY_ON_ERROR=true
CAF_SLACK__INCLUDE_COST=true
CAF_SLACK__INCLUDE_DURATION=true
```

Notifications include:
- Execution status (success/error)
- Duration and cost
- Token usage
- Todo completion status
- Agent response preview

## Cost Tracking

Monitor and control costs:

```bash
# View cost report
caf costs

# Reset tracking
caf costs --reset
```

Set budget limits:
```bash
CAF_AGENT__MAX_BUDGET_USD=50.0
```

The agent will stop if the budget is exceeded.

## AWS Bedrock Setup

Use Claude via AWS Bedrock:

```bash
# Enable Bedrock
CAF_BEDROCK__ENABLED=true
CAF_BEDROCK__REGION=us-east-1

# Use AWS profile
CAF_BEDROCK__PROFILE=my-profile

# Or use environment credentials
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Specify model
CAF_BEDROCK__MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

## Programmatic Usage

Use the framework in your Python code:

```python
import asyncio
from claude_agent_framework import AgentRunner, Settings

async def main():
    settings = Settings(
        anthropic_api_key="sk-ant-...",
        agent=AgentConfig(
            name="my-agent",
            model=ModelType.SONNET,
            max_turns=50,
        ),
        slack=SlackConfig(
            enabled=True,
            webhook_url="https://hooks.slack.com/...",
        ),
    )

    runner = AgentRunner(settings)
    result = await runner.run_once(
        prompt="Analyze the database for performance issues",
        task_description="Daily DB Check",
    )

    print(f"Status: {result.status}")
    print(f"Cost: ${result.total_cost_usd:.4f}")
    print(f"Result: {result.get_final_message()}")

asyncio.run(main())
```

## Example Use Cases

### Daily Database Health Check

```bash
# prompts/db_health.md
Analyze the database logs at /var/log/postgresql/ for the last 24 hours.

Look for:
1. Slow queries (>1s execution time)
2. Connection errors
3. Lock contention
4. Disk space warnings

Provide a summary with recommendations.
```

```bash
# Crontab: 6 AM daily
0 6 * * * cd /opt/agent && caf run -f prompts/db_health.md
```

### Application Log Monitoring

```bash
caf service "Monitor /var/log/app/error.log for new errors. \
Alert if you find critical errors or unusual patterns." \
--interval 1800
```

### Code Quality Check

```bash
caf run "Review all Python files in src/ for:
- Security vulnerabilities
- Code quality issues
- Missing error handling
- Performance concerns

Prioritize by severity."
```

## CLI Reference

```bash
# Run once
caf run <prompt> [options]
  -f, --prompt-file    Load prompt from file
  -m, --model          Override model (sonnet/opus/haiku)
  -t, --max-turns      Maximum conversation turns
  -b, --max-budget     Maximum budget in USD
  -d, --cwd            Working directory
  -q, --quiet          Minimal output
  -j, --json           Output as JSON

# Service mode
caf service <prompt> [options]
  -i, --interval       Interval between runs (seconds)

# Cron mode
caf cron <prompt> --schedule <expr> [options]
  -s, --schedule       Cron expression

# Configuration
caf config [options]
  -g, --generate-env   Generate .env template
  -s, --show           Show current config
  -t, --tui            Launch interactive TUI

# Cost tracking
caf costs [options]
  -r, --reset          Reset cost tracking

# Version
caf version
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.
