"""Monday.com GraphQL HTTP client."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from src.monday.models import (
    FetchBoardItemsResult,
    MondayBoard,
    MondayColumn,
    MondayColumnValue,
    MondayItem,
)
from src.monday.queries import BOARD_ITEMS_PAGE_QUERY, BOARD_SCHEMA_QUERY

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_PAGE_LIMIT = 100
MAX_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class MondayAPIError(Exception):
    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class MondayClient:
    def __init__(
        self,
        api_token: str,
        api_url: str = "https://api.monday.com/v2",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        if not api_token:
            raise ValueError("MONDAY_API_TOKEN is required")
        self._api_url = api_url.rstrip("/")
        self._headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def _execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        self._api_url,
                        headers=self._headers,
                        json=payload,
                    )

                if response.status_code in RETRY_STATUS_CODES:
                    wait = 2**attempt
                    logger.warning(
                        "Monday API returned %s; retry %s/%s in %ss",
                        response.status_code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    continue

                if response.status_code == 401:
                    raise MondayAPIError("Authentication failed", retryable=False, status_code=401)
                if response.status_code == 403:
                    raise MondayAPIError("Access forbidden", retryable=False, status_code=403)
                if response.status_code >= 400:
                    raise MondayAPIError(
                        f"HTTP {response.status_code}: {response.text[:200]}",
                        retryable=response.status_code in RETRY_STATUS_CODES,
                        status_code=response.status_code,
                    )

                data = response.json()
                if "errors" in data and data["errors"]:
                    messages = "; ".join(
                        e.get("message", str(e)) for e in data["errors"]
                    )
                    retryable = any(
                        "rate limit" in m.lower() or "complexity" in m.lower()
                        for m in messages.split(";")
                    )
                    raise MondayAPIError(
                        f"GraphQL error: {messages}",
                        retryable=retryable,
                    )
                return data.get("data", {})

            except httpx.TimeoutException as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning("Monday API timeout; retry %s/%s", attempt + 1, MAX_RETRIES)
                time.sleep(wait)
            except MondayAPIError as exc:
                if exc.retryable and attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                    last_error = exc
                    continue
                raise

        raise MondayAPIError(
            f"Monday API request failed after {MAX_RETRIES} retries: {last_error}",
            retryable=False,
        )

    def get_board_schema(self, board_id: str) -> MondayBoard:
        data = self._execute(BOARD_SCHEMA_QUERY, {"board_id": [board_id]})
        boards = data.get("boards") or []
        if not boards:
            raise MondayAPIError(f"Board {board_id} not found", retryable=False)

        board = boards[0]
        columns = [
            MondayColumn(
                id=c["id"],
                title=c["title"],
                type=c["type"],
                settings_str=c.get("settings_str"),
            )
            for c in board.get("columns", [])
        ]
        return MondayBoard(
            id=str(board["id"]),
            name=board["name"],
            columns=columns,
            items_count=board.get("items_count"),
        )

    def fetch_board_items(
        self,
        board_id: str,
        *,
        page_limit: int = DEFAULT_PAGE_LIMIT,
    ) -> FetchBoardItemsResult:
        start = time.perf_counter()
        all_items: list[MondayItem] = []
        cursor: str | None = None
        pages = 0

        while True:
            variables: dict[str, Any] = {
                "board_id": board_id,
                "limit": page_limit,
            }
            if cursor:
                variables["cursor"] = cursor

            data = self._execute(BOARD_ITEMS_PAGE_QUERY, variables)
            boards = data.get("boards") or []
            if not boards:
                break

            items_page = boards[0].get("items_page") or {}
            raw_items = items_page.get("items") or []
            pages += 1

            for item in raw_items:
                column_values = [
                    MondayColumnValue(
                        id=cv["id"],
                        text=cv.get("text"),
                        value=cv.get("value"),
                        type=cv.get("type"),
                    )
                    for cv in item.get("column_values", [])
                ]
                all_items.append(
                    MondayItem(
                        id=str(item["id"]),
                        name=item.get("name", ""),
                        column_values=column_values,
                    )
                )

            cursor = items_page.get("cursor")
            if not cursor:
                break

        duration_ms = int((time.perf_counter() - start) * 1000)
        return FetchBoardItemsResult(
            records=all_items,
            pages=pages,
            total_items=len(all_items),
            duration_ms=duration_ms,
            board_id=board_id,
        )
