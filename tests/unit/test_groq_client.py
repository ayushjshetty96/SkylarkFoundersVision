"""Unit tests for Groq configuration and error classification."""

import pytest

from config.settings import Settings
from src.agent.groq_client import (
    GroqErrorCategory,
    check_groq_connectivity,
    classify_groq_error,
    inspect_groq_config,
)


class FakeAPIStatusError(Exception):
    status_code = None


def test_inspect_groq_config():
    settings = Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_test_key",
        GROQ_MODEL="openai/gpt-oss-120b",
    )
    status = inspect_groq_config(settings)
    assert status.api_key_present is True
    assert status.model == "openai/gpt-oss-120b"


def test_classify_authentication():
    exc = FakeAPIStatusError("401 Unauthorized")
    exc.status_code = 401
    result = classify_groq_error(exc)
    assert result.category == GroqErrorCategory.AUTHENTICATION
    assert result.http_status == 401


def test_classify_permission_denied():
    exc = FakeAPIStatusError("403 Forbidden")
    exc.status_code = 403
    result = classify_groq_error(exc)
    assert result.category == GroqErrorCategory.PERMISSION_DENIED


def test_classify_rate_limit():
    exc = FakeAPIStatusError("429 Too Many Requests")
    exc.status_code = 429
    result = classify_groq_error(exc)
    assert result.category == GroqErrorCategory.RATE_LIMIT


def test_classify_server_unavailable():
    exc = FakeAPIStatusError("503 Service Unavailable")
    exc.status_code = 503
    result = classify_groq_error(exc)
    assert result.category == GroqErrorCategory.SERVER_UNAVAILABLE


def test_missing_api_key_category():
    settings = Settings(
        MONDAY_API_TOKEN="token",
        MONDAY_WORK_ORDERS_BOARD_ID="1",
        MONDAY_DEALS_BOARD_ID="2",
        GROQ_API_KEY="gsk_placeholder",
        GROQ_MODEL="openai/gpt-oss-120b",
    )
    settings = settings.model_copy(update={"groq_api_key": ""})
    result = check_groq_connectivity(settings)
    assert result.category == GroqErrorCategory.MISSING_API_KEY
    assert result.ok is False
