import json

import pytest

from handler import handler


def test_handler_returns_health_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "pr-42")
    result = handler({"requestContext": {}}, object())
    assert result["statusCode"] == 200
    assert json.loads(str(result["body"])) == {"status": "ok", "environment": "pr-42"}


def test_handler_rejects_events_without_api_gateway_context() -> None:
    result = handler({}, object())
    assert result["statusCode"] == 400
    assert json.loads(str(result["body"])) == {"message": "requestContext is required"}