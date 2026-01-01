# Webhook Integration Guide

The Claude Agent Framework now supports webhook integration, allowing you to trigger agents automatically from external events like Linear issue updates, GitHub events, and more.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Linear Integration](#linear-integration)
- [Configuration](#configuration)
- [Routing Rules](#routing-rules)
- [Security](#security)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Overview

The webhook server receives HTTP POST requests from external services and triggers Claude agents based on configurable routing rules. This enables automated workflows like:

- 🎯 Auto-triaging new issues
- 🔍 Analyzing code review comments
- 📊 Generating reports on project updates
- 🤖 Responding to team notifications
- ✅ Automating repetitive tasks

### Architecture

```
External Service (Linear) → Webhook Server → Route Rules → Agent Runner → Claude
```

## Quick Start

### 1. Install Dependencies

The webhook feature requires FastAPI and Uvicorn (automatically installed):

```bash
pip install -e .
```

### 2. Generate Example Routes

```bash
caf webhook --generate-routes
```

This creates `webhook_routes.yaml` with example Linear webhook handlers.

### 3. Configure Environment

Add to your `.env` file:

```bash
# Webhook Configuration
CAF_WEBHOOK__ENABLED=true
CAF_WEBHOOK__HOST=0.0.0.0
CAF_WEBHOOK__PORT=8000
CAF_WEBHOOK__LINEAR_WEBHOOK_SECRET=your_linear_webhook_secret_here
CAF_WEBHOOK__ROUTES_FILE=./webhook_routes.yaml

# Required: Anthropic API Key
ANTHROPIC_API_KEY=your_api_key_here
```

### 4. Start the Server

```bash
caf webhook
```

The server will start at `http://0.0.0.0:8000` with endpoints:
- `POST /webhooks/linear` - Linear webhook endpoint
- `GET /health` - Health check endpoint

## Linear Integration

### Setting Up Linear Webhooks

1. **Go to Linear Settings**
   - Navigate to your workspace settings
   - Click on "API" → "Webhooks"

2. **Create a New Webhook**
   - Click "New Webhook"
   - Set the URL to your webhook server: `https://your-domain.com/webhooks/linear`
   - Copy the signing secret (you'll need this for validation)

3. **Select Events**
   Choose which events to send:
   - Issue created
   - Issue updated
   - Comment created
   - Project updated
   - etc.

4. **Configure Secret**
   Add the signing secret to your `.env`:
   ```bash
   CAF_WEBHOOK__LINEAR_WEBHOOK_SECRET=whsec_xxx
   ```

### Linear Event Types

The following Linear events are supported:

| Event Type | Pattern | Description |
|------------|---------|-------------|
| Issue Created | `Issue.create` | New issue created |
| Issue Updated | `Issue.update` | Issue properties changed |
| Issue Removed | `Issue.remove` | Issue deleted |
| Comment Created | `Comment.create` | New comment added |
| Comment Updated | `Comment.update` | Comment edited |
| Project Updated | `Project.update` | Project details changed |
| Label Created | `Label.create` | New label created |

### Example Linear Webhook Payload

```json
{
  "action": "create",
  "type": "Issue",
  "createdAt": "2025-01-01T12:00:00.000Z",
  "data": {
    "id": "ISS-123",
    "title": "Fix authentication bug",
    "description": "Users cannot log in with SSO",
    "priority": 1,
    "state": {
      "name": "Todo"
    }
  },
  "url": "https://linear.app/company/issue/ISS-123",
  "webhookTimestamp": 1704110400000,
  "organizationId": "org-xxx"
}
```

## Configuration

### Webhook Settings

Configure webhooks in `.env` or `config.yaml`:

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Enabled | `CAF_WEBHOOK__ENABLED` | `false` | Enable webhook server |
| Host | `CAF_WEBHOOK__HOST` | `0.0.0.0` | Host to bind to |
| Port | `CAF_WEBHOOK__PORT` | `8000` | Port to listen on |
| Linear Secret | `CAF_WEBHOOK__LINEAR_WEBHOOK_SECRET` | `null` | Linear webhook signing secret |
| Max Timestamp Age | `CAF_WEBHOOK__MAX_TIMESTAMP_AGE_SECONDS` | `60` | Max webhook age (replay protection) |
| Routes File | `CAF_WEBHOOK__ROUTES_FILE` | `null` | Path to routing rules YAML |

### Example config.yaml

```yaml
webhook:
  enabled: true
  host: 0.0.0.0
  port: 8000
  linear_webhook_secret: whsec_xxx
  max_timestamp_age_seconds: 60
  routes_file: ./webhook_routes.yaml

agent:
  model: sonnet
  max_turns: 30
  permission_mode: acceptEdits

logging:
  enabled: true
  log_dir: ./logs
  log_agent_trace: true
```

## Routing Rules

Routing rules map webhook events to agent prompts. Rules are defined in a YAML file.

### Rule Structure

```yaml
- event_pattern: "Issue.create"      # Event to match
  description: "Handle new issues"   # Human-readable description
  enabled: true                      # Enable/disable this rule
  prompt_template: |                 # Template with placeholders
    A new issue was created:
    Title: {title}
    Description: {description}
```

### Pattern Matching

- **Exact match**: `"Issue.create"` - matches only Issue creation
- **Wildcard**: `"Issue.*"` - matches all Issue events
- **Global**: `"*"` - matches all events

### Template Variables

Available in all Linear webhook templates:

| Variable | Description | Example |
|----------|-------------|---------|
| `{title}` | Issue title | "Fix login bug" |
| `{description}` | Issue description | "Users cannot log in..." |
| `{state}` | Issue state | "In Progress" |
| `{priority}` | Issue priority (0-4) | 1 |
| `{url}` | Entity URL | "https://linear.app/..." |
| `{action}` | Action type | "create" |
| `{type}` | Entity type | "Issue" |
| `{actor_name}` | User who triggered event | "John Doe" |
| `{data}` | Full payload data | {...} |

### Example Routes

**Auto-triage new issues:**
```yaml
- event_pattern: Issue.create
  enabled: true
  prompt_template: |
    New issue from {actor_name}:

    Title: {title}
    Priority: {priority}

    Please:
    1. Categorize this issue
    2. Identify affected components
    3. Suggest initial investigation steps
```

**Monitor high-priority updates:**
```yaml
- event_pattern: Issue.update
  enabled: true
  prompt_template: |
    Issue updated: {title}
    State: {state}
    Priority: {priority}

    Alert team if this is urgent (priority 1-2) or blocked.
```

**Process comments:**
```yaml
- event_pattern: Comment.create
  enabled: true
  prompt_template: |
    New comment on {url}

    Check if this comment:
    - Asks questions needing answers
    - Reports blockers
    - Requests code review
```

## Security

### Signature Validation

All Linear webhooks are validated using HMAC-SHA256 signatures:

1. **Signature Header**: `Linear-Signature`
2. **Algorithm**: HMAC-SHA256
3. **Secret**: Configured via `CAF_WEBHOOK__LINEAR_WEBHOOK_SECRET`
4. **Comparison**: Constant-time to prevent timing attacks

### Timestamp Validation

Webhooks older than 60 seconds (configurable) are rejected to prevent replay attacks.

### HTTPS Requirement

**Always use HTTPS in production!** Linear requires HTTPS endpoints.

### Best Practices

1. ✅ **Always set webhook secret** - Never skip signature validation
2. ✅ **Use environment variables** - Don't commit secrets to git
3. ✅ **Enable HTTPS** - Use reverse proxy (nginx/Caddy) with TLS
4. ✅ **Restrict IP access** - Firewall webhook endpoint if possible
5. ✅ **Monitor logs** - Track webhook deliveries and failures
6. ✅ **Set budget limits** - Use `CAF_AGENT__MAX_BUDGET_USD` to control costs

### Linear IP Whitelist

Linear sends webhooks from these IPs (as of 2025):
```
35.231.147.226
35.243.134.228
34.140.253.14
34.38.87.206
34.134.222.122
35.222.25.142
```

## Deployment

### Local Development

```bash
# Start webhook server locally
caf webhook --port 8000

# Test with ngrok
ngrok http 8000
# Use the ngrok URL in Linear webhook settings
```

### Production Deployment

#### Option 1: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .

CMD ["caf", "webhook"]
```

```bash
docker build -t caf-webhook .
docker run -p 8000:8000 --env-file .env caf-webhook
```

#### Option 2: systemd Service

```ini
[Unit]
Description=Claude Agent Framework Webhook Server
After=network.target

[Service]
Type=simple
User=caf
WorkingDirectory=/opt/caf
EnvironmentFile=/opt/caf/.env
ExecStart=/opt/caf/venv/bin/caf webhook
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Option 3: Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name webhooks.example.com;

    ssl_certificate /etc/letsencrypt/live/webhooks.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/webhooks.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Common Issues

**1. Signature validation fails**
```
Error: Invalid webhook signature
```

Solution:
- Verify `CAF_WEBHOOK__LINEAR_WEBHOOK_SECRET` matches Linear webhook secret
- Check that secret starts with `whsec_`
- Ensure no extra whitespace in secret

**2. Timestamp too old**
```
Error: Webhook timestamp too old: 120s (max: 60s)
```

Solution:
- Check server time is synchronized (use NTP)
- Increase `CAF_WEBHOOK__MAX_TIMESTAMP_AGE_SECONDS` if needed

**3. No route matches event**
```
Status: ignored
Message: No route configured for Issue.update
```

Solution:
- Add a route rule for this event pattern
- Check `enabled: true` in route rule
- Verify pattern syntax (exact match vs wildcard)

**4. Agent fails to run**
```
Error running agent: API key not found
```

Solution:
- Set `ANTHROPIC_API_KEY` in `.env`
- Verify agent configuration is valid
- Check logs for detailed error messages

### Debug Mode

Enable detailed logging:

```bash
CAF_LOGGING__LOG_LEVEL=DEBUG caf webhook
```

### Testing Webhooks Locally

Use curl to test:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test Linear webhook (without signature - will fail if secret is set)
curl -X POST http://localhost:8000/webhooks/linear \
  -H "Content-Type: application/json" \
  -H "Linear-Event: Issue" \
  -H "Linear-Delivery: test-123" \
  -d '{
    "action": "create",
    "type": "Issue",
    "createdAt": "2025-01-01T12:00:00.000Z",
    "data": {
      "title": "Test issue",
      "description": "Testing webhook"
    },
    "url": "https://linear.app/test",
    "webhookTimestamp": 1704110400000,
    "organizationId": "test"
  }'
```

### Logs Location

Webhook activity is logged to:
- **Console**: Real-time output
- **Log file**: `./logs/agent.log`
- **Trace files**: `./logs/trace_*.json` (if enabled)

## Advanced Usage

### Custom Route Logic

For complex routing logic, extend `WebhookHandler`:

```python
from claude_agent_framework.webhook.handlers import WebhookHandler

class CustomHandler(WebhookHandler):
    async def handle_linear_webhook(self, payload, headers):
        # Custom logic here
        if payload.get_issue_priority() == 1:
            # Override prompt for urgent issues
            prompt = f"URGENT: {payload.get_issue_title()}"
            await self._run_agent(prompt, payload.get_event_key(), headers)
            return {"status": "urgent_handled"}

        return await super().handle_linear_webhook(payload, headers)
```

### Multiple Webhook Sources

Add additional webhook endpoints in `server.py`:

```python
@app.post("/webhooks/github")
async def github_webhook(request: Request):
    # Handle GitHub webhooks
    pass
```

### Webhook Analytics

Track webhook metrics:

```python
# In handler
self.metrics = {
    "total_webhooks": 0,
    "successful": 0,
    "failed": 0
}
```

## Need Help?

- 📖 [Main README](README.md)
- 🐛 [Report Issues](https://github.com/your-repo/issues)
- 💬 [Discussions](https://github.com/your-repo/discussions)

## Sources

- [Linear Webhooks Documentation](https://linear.app/developers/webhooks)
- [Linear Webhook Guide](https://inventivehq.com/blog/linear-webhooks-guide)
- [Linear API Documentation](https://developers.linear.app/docs/graphql/webhooks)
