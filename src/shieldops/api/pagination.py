"""Cursor-based pagination utilities.

Provides base64-encoded cursor pagination for all list endpoints.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Generic paginated response."""

    items: list[Any] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int = 0
    limit: int = DEFAULT_LIMIT


def encode_cursor(offset: int) -> str:
    """Encode an offset as a base64 cursor string."""
    payload = json.dumps({"offset": offset}).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def parse_cursor(cursor: str) -> int:
    """Decode a base64 cursor string to an offset."""
    try:
        padding = 4 - len(cursor) % 4
        if padding != 4:
            cursor += "=" * padding
        payload = base64.urlsafe_b64decode(cursor)
        data = json.loads(payload)
        return int(data.get("offset", 0))
    except Exception:
        return 0


def paginate(
    items: list[Any],
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> PaginatedResponse[Any]:
    """Apply cursor-based pagination to a list.

    Args:
        items: Full list of items.
        cursor: Optional cursor from previous page.
        limit: Page size (clamped to MAX_LIMIT).

    Returns:
        PaginatedResponse with items, next cursor, and metadata.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    offset = parse_cursor(cursor) if cursor else 0
    total = len(items)

    page = items[offset : offset + limit]
    has_more = (offset + limit) < total
    next_cursor = encode_cursor(offset + limit) if has_more else None

    return PaginatedResponse(
        items=page,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total,
        limit=limit,
    )
