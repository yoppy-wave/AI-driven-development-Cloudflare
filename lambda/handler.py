"""Minimal API Lambda used to verify the CDK asset and API integration path."""

import json
import os
from typing import Any


def handler(event: dict[str, Any], _context: object) -> dict[str, object]:
    if event.get("requestContext") is None:
        return response(400, {"message": "requestContext is required"})
    return response(200, {"status": "ok", "environment": os.environ.get("APP_ENVIRONMENT", "unknown")})


def response(status_code: int, body: dict[str, str]) -> dict[str, object]:
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}