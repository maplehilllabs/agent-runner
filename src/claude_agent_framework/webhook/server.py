"""
FastAPI webhook server for Claude Agent Framework.
"""

from __future__ import annotations

import logging
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, Request, HTTPException
from fastapi.responses import JSONResponse

from claude_agent_framework.config.settings import Settings
from claude_agent_framework.webhook.handlers import WebhookHandler
from claude_agent_framework.webhook.linear import (
    extract_linear_headers,
    validate_linear_signature,
    validate_linear_timestamp,
)
from claude_agent_framework.webhook.models import LinearWebhookPayload

logger = logging.getLogger(__name__)


class WebhookServer:
    """
    FastAPI webhook server for receiving and processing webhooks.
    """

    def __init__(self, settings: Settings):
        """
        Initialize webhook server.

        Args:
            settings: Framework settings
        """
        self.settings = settings
        self.handler = WebhookHandler(settings)
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title="Claude Agent Framework - Webhook Server",
            description="Webhook endpoints to trigger Claude agents from external events",
            version="0.1.0",
        )

        # Health check endpoint
        @app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy"}

        # Linear webhook endpoint
        @app.post("/webhooks/linear")
        async def linear_webhook(
            request: Request,
            linear_headers: dict[str, str | None] = Depends(extract_linear_headers),
        ) -> JSONResponse:
            """
            Receive and process Linear webhooks.

            This endpoint:
            1. Validates the webhook signature using HMAC-SHA256
            2. Validates the timestamp to prevent replay attacks
            3. Routes the event to the appropriate agent based on configured rules
            4. Returns immediately (agent runs in background)

            Returns:
                JSONResponse with status and message
            """
            # Validate signature if secret is configured
            if self.settings.webhook.linear_webhook_secret:
                try:
                    linear_signature = request.headers.get("Linear-Signature")
                    if not linear_signature:
                        raise HTTPException(
                            status_code=401,
                            detail="Missing Linear-Signature header"
                        )

                    await validate_linear_signature(
                        request=request,
                        webhook_secret=self.settings.webhook.linear_webhook_secret,
                        linear_signature=linear_signature,
                    )
                except HTTPException:
                    raise
            else:
                logger.warning(
                    "Linear webhook secret not configured - skipping signature validation"
                )

            # Parse the payload
            try:
                payload_dict = await request.json()
                payload = LinearWebhookPayload(**payload_dict)
            except Exception as e:
                logger.error(f"Failed to parse Linear webhook payload: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid payload: {str(e)}"
                )

            # Validate timestamp
            try:
                await validate_linear_timestamp(
                    payload_dict,
                    max_age_seconds=self.settings.webhook.max_timestamp_age_seconds,
                )
            except HTTPException:
                raise

            # Handle the webhook
            try:
                result = await self.handler.handle_linear_webhook(
                    payload=payload,
                    headers=linear_headers,
                )
                return JSONResponse(content=result, status_code=200)
            except Exception as e:
                logger.error(f"Error handling Linear webhook: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error"
                )

        # Generic webhook endpoint (for future expansion)
        @app.post("/webhooks/generic")
        async def generic_webhook(request: Request) -> JSONResponse:
            """
            Generic webhook endpoint for custom integrations.

            Returns:
                JSONResponse with status
            """
            payload = await request.json()
            logger.info(f"Received generic webhook: {payload}")

            return JSONResponse(
                content={
                    "status": "received",
                    "message": "Generic webhook processing not yet implemented"
                },
                status_code=200
            )

        return app

    def run(self, host: str | None = None, port: int | None = None) -> None:
        """
        Run the webhook server.

        Args:
            host: Host to bind to (defaults to settings)
            port: Port to listen on (defaults to settings)
        """
        host = host or self.settings.webhook.host
        port = port or self.settings.webhook.port

        logger.info(f"Starting webhook server on {host}:{port}")

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
        )

    async def start(self, host: str | None = None, port: int | None = None) -> None:
        """
        Start the webhook server (async).

        Args:
            host: Host to bind to (defaults to settings)
            port: Port to listen on (defaults to settings)
        """
        import asyncio

        host = host or self.settings.webhook.host
        port = port or self.settings.webhook.port

        logger.info(f"Starting webhook server on {host}:{port}")

        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
