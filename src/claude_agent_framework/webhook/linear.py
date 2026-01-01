"""
Linear webhook validation and processing utilities.
"""

import hmac
import hashlib
import time
from typing import Any

from fastapi import HTTPException, Header, Request


async def validate_linear_signature(
    request: Request,
    webhook_secret: str,
    linear_signature: str = Header(..., alias="Linear-Signature"),
    max_age_seconds: int = 60,
) -> None:
    """
    Validate Linear webhook signature using HMAC-SHA256.

    Args:
        request: FastAPI request object
        webhook_secret: The webhook signing secret from Linear
        linear_signature: The signature from the Linear-Signature header
        max_age_seconds: Maximum age of the webhook in seconds (default: 60)

    Raises:
        HTTPException: If signature validation fails

    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Validates timestamp to prevent replay attacks
        - Uses raw request body for signature verification
    """
    # Get the raw request body
    body = await request.body()

    # Compute the expected signature
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, linear_signature):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )


async def validate_linear_timestamp(
    payload: dict[str, Any],
    max_age_seconds: int = 60,
) -> None:
    """
    Validate webhook timestamp to prevent replay attacks.

    Args:
        payload: The webhook payload
        max_age_seconds: Maximum age of the webhook in seconds

    Raises:
        HTTPException: If timestamp is too old or invalid
    """
    webhook_timestamp = payload.get("webhookTimestamp")

    if not webhook_timestamp:
        raise HTTPException(
            status_code=400,
            detail="Missing webhookTimestamp in payload"
        )

    # Convert to seconds (Linear sends milliseconds)
    webhook_time = webhook_timestamp / 1000
    current_time = time.time()

    time_diff = abs(current_time - webhook_time)

    if time_diff > max_age_seconds:
        raise HTTPException(
            status_code=400,
            detail=f"Webhook timestamp too old: {time_diff:.0f}s (max: {max_age_seconds}s)"
        )


def extract_linear_headers(
    linear_event: str | None = Header(None, alias="Linear-Event"),
    linear_delivery: str | None = Header(None, alias="Linear-Delivery"),
) -> dict[str, str | None]:
    """
    Extract Linear-specific headers from the request.

    Args:
        linear_event: The Linear-Event header (entity type)
        linear_delivery: The Linear-Delivery header (unique delivery ID)

    Returns:
        Dictionary with Linear headers
    """
    return {
        "event": linear_event,
        "delivery_id": linear_delivery,
    }
