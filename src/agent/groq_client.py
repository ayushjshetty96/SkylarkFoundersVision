"""Groq API client helpers, connectivity checks, and error classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from groq import Groq

from config.settings import Settings

try:
    from groq import APIStatusError, AuthenticationError, PermissionDeniedError, RateLimitError
except ImportError:  # pragma: no cover
    APIStatusError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    PermissionDeniedError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore


class GroqErrorCategory(str, Enum):
    MISSING_API_KEY = "missing_api_key"
    AUTHENTICATION = "authentication"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT = "rate_limit"
    REQUEST_TOO_LARGE = "request_too_large"
    MODEL_UNAVAILABLE = "model_unavailable"
    SERVER_UNAVAILABLE = "server_unavailable"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"
    SUCCESS = "success"


@dataclass
class GroqConfigStatus:
    api_key_present: bool
    model: str
    sdk: str = "groq"


@dataclass
class GroqConnectivityResult:
    category: GroqErrorCategory
    ok: bool
    message: str
    http_status: int | None = None
    model: str | None = None
    response_preview: str | None = None


def inspect_groq_config(settings: Settings) -> GroqConfigStatus:
    return GroqConfigStatus(
        api_key_present=bool(settings.groq_api_key and settings.groq_api_key.strip()),
        model=settings.groq_model,
    )


def _extract_http_status(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    match = re.search(r"\b(4\d{2}|5\d{2})\b", str(exc))
    if match:
        return int(match.group(1))
    return None


def classify_groq_error(exc: BaseException) -> GroqConnectivityResult:
    """Map a Groq SDK exception to a safe, actionable category."""
    message = str(exc)
    upper = message.upper()
    status = _extract_http_status(exc)

    if isinstance(exc, AuthenticationError) or status == 401:
        return GroqConnectivityResult(
            category=GroqErrorCategory.AUTHENTICATION,
            ok=False,
            message="Groq authentication failed. Check GROQ_API_KEY.",
            http_status=status or 401,
        )
    if isinstance(exc, PermissionDeniedError) or status == 403:
        return GroqConnectivityResult(
            category=GroqErrorCategory.PERMISSION_DENIED,
            ok=False,
            message="Groq permission denied (HTTP 403). Verify API key permissions.",
            http_status=status or 403,
        )
    if isinstance(exc, RateLimitError) or status == 429 or "RATE LIMIT" in upper:
        return GroqConnectivityResult(
            category=GroqErrorCategory.RATE_LIMIT,
            ok=False,
            message="Groq rate limit exceeded. Please retry shortly.",
            http_status=status or 429,
        )
    if status == 413 or "REQUEST TOO LARGE" in upper or "413" in message:
        return GroqConnectivityResult(
            category=GroqErrorCategory.REQUEST_TOO_LARGE,
            ok=False,
            message=(
                "Request too large for Groq model. Context was compacted; "
                "try a more specific question."
            ),
            http_status=status or 413,
        )
    if status == 404 or "NOT FOUND" in upper:
        return GroqConnectivityResult(
            category=GroqErrorCategory.MODEL_UNAVAILABLE,
            ok=False,
            message="Groq model unavailable (HTTP 404). Verify GROQ_MODEL.",
            http_status=status or 404,
        )
    if status in (500, 502, 503) or "UNAVAILABLE" in upper:
        return GroqConnectivityResult(
            category=GroqErrorCategory.SERVER_UNAVAILABLE,
            ok=False,
            message="Groq service temporarily unavailable. Please retry.",
            http_status=status,
        )
    if isinstance(exc, APIStatusError):
        return GroqConnectivityResult(
            category=GroqErrorCategory.UNKNOWN,
            ok=False,
            message=f"Groq API error (HTTP {status}): {message[:200]}",
            http_status=status,
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return GroqConnectivityResult(
            category=GroqErrorCategory.NETWORK_ERROR,
            ok=False,
            message=f"Network error reaching Groq API: {type(exc).__name__}",
        )

    return GroqConnectivityResult(
        category=GroqErrorCategory.UNKNOWN,
        ok=False,
        message=f"{type(exc).__name__}: {message[:300]}",
        http_status=status,
    )


def create_groq_client(settings: Settings) -> Groq:
    if not settings.groq_api_key or not settings.groq_api_key.strip():
        raise ValueError("GROQ_API_KEY is missing")
    return Groq(api_key=settings.groq_api_key.strip())


def is_request_too_large(exc: BaseException) -> bool:
    result = classify_groq_error(exc)
    return result.category == GroqErrorCategory.REQUEST_TOO_LARGE


def chat_completion(
    client: Groq,
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int | None = None,
) -> Any:
    """Create a Groq chat completion with optional tools."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


def check_groq_connectivity(settings: Settings) -> GroqConnectivityResult:
    """Run a minimal Groq chat completion (no tools). Never logs the API key."""
    config_status = inspect_groq_config(settings)
    if not config_status.api_key_present:
        return GroqConnectivityResult(
            category=GroqErrorCategory.MISSING_API_KEY,
            ok=False,
            message="GROQ_API_KEY is not set. Add it to .env or Streamlit secrets.",
            model=settings.groq_model,
        )

    try:
        client = create_groq_client(settings)
        response = chat_completion(
            client,
            model=settings.groq_model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        preview = (response.choices[0].message.content or "").strip()[:80]
        return GroqConnectivityResult(
            category=GroqErrorCategory.SUCCESS,
            ok=True,
            message="Groq API connectivity OK",
            model=settings.groq_model,
            response_preview=preview or None,
        )
    except Exception as exc:
        result = classify_groq_error(exc)
        result.model = settings.groq_model
        if settings.groq_api_key:
            detail = str(exc).replace(settings.groq_api_key, "***REDACTED***")
            if detail not in result.message:
                result.message = f"{result.message} Detail: {detail[:250]}"
        return result


def format_groq_error_for_user(exc: BaseException) -> str:
    return classify_groq_error(exc).message
