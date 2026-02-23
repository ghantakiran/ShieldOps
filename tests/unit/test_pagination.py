"""Tests for cursor-based pagination utilities.

Covers encode_cursor, parse_cursor, paginate, PaginatedResponse model,
and DEFAULT_LIMIT / MAX_LIMIT constants.
"""

import base64
import json

from shieldops.api.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    PaginatedResponse,
    encode_cursor,
    paginate,
    parse_cursor,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_default_limit_is_50(self):
        assert DEFAULT_LIMIT == 50

    def test_max_limit_is_200(self):
        assert MAX_LIMIT == 200

    def test_default_limit_less_than_max(self):
        assert DEFAULT_LIMIT < MAX_LIMIT


# ---------------------------------------------------------------------------
# encode_cursor / parse_cursor
# ---------------------------------------------------------------------------


class TestEncodeCursor:
    def test_encode_returns_string(self):
        result = encode_cursor(0)
        assert isinstance(result, str)

    def test_encode_cursor_is_base64(self):
        cursor = encode_cursor(10)
        # Should decode without error after re-padding
        padding = 4 - len(cursor) % 4
        if padding != 4:
            cursor += "=" * padding
        decoded = base64.urlsafe_b64decode(cursor)
        data = json.loads(decoded)
        assert data["offset"] == 10

    def test_encode_cursor_zero_offset(self):
        cursor = encode_cursor(0)
        assert parse_cursor(cursor) == 0

    def test_encode_cursor_large_offset(self):
        cursor = encode_cursor(99999)
        assert parse_cursor(cursor) == 99999

    def test_encode_cursor_strips_padding(self):
        cursor = encode_cursor(5)
        assert "=" not in cursor


class TestParseCursor:
    def test_roundtrip_offset_0(self):
        assert parse_cursor(encode_cursor(0)) == 0

    def test_roundtrip_offset_50(self):
        assert parse_cursor(encode_cursor(50)) == 50

    def test_roundtrip_offset_200(self):
        assert parse_cursor(encode_cursor(200)) == 200

    def test_roundtrip_offset_1(self):
        assert parse_cursor(encode_cursor(1)) == 1

    def test_invalid_cursor_returns_0(self):
        assert parse_cursor("not-valid-base64!!!") == 0

    def test_empty_string_returns_0(self):
        assert parse_cursor("") == 0

    def test_non_json_base64_returns_0(self):
        # Valid base64 but not JSON
        raw = base64.urlsafe_b64encode(b"just text").decode().rstrip("=")
        assert parse_cursor(raw) == 0

    def test_json_without_offset_returns_0(self):
        raw = base64.urlsafe_b64encode(json.dumps({"foo": "bar"}).encode()).decode().rstrip("=")
        assert parse_cursor(raw) == 0

    def test_json_with_non_int_offset_returns_0(self):
        raw = base64.urlsafe_b64encode(json.dumps({"offset": "abc"}).encode()).decode().rstrip("=")
        # int("abc") will raise, so returns 0
        assert parse_cursor(raw) == 0


# ---------------------------------------------------------------------------
# PaginatedResponse model
# ---------------------------------------------------------------------------


class TestPaginatedResponseModel:
    def test_default_items_empty(self):
        resp = PaginatedResponse()
        assert resp.items == []

    def test_default_next_cursor_none(self):
        resp = PaginatedResponse()
        assert resp.next_cursor is None

    def test_default_has_more_false(self):
        resp = PaginatedResponse()
        assert resp.has_more is False

    def test_default_total_count_zero(self):
        resp = PaginatedResponse()
        assert resp.total_count == 0

    def test_default_limit_matches_constant(self):
        resp = PaginatedResponse()
        assert resp.limit == DEFAULT_LIMIT

    def test_custom_values(self):
        resp = PaginatedResponse(
            items=[1, 2, 3],
            next_cursor="abc",
            has_more=True,
            total_count=100,
            limit=25,
        )
        assert resp.items == [1, 2, 3]
        assert resp.next_cursor == "abc"
        assert resp.has_more is True
        assert resp.total_count == 100
        assert resp.limit == 25

    def test_serialization_roundtrip(self):
        resp = PaginatedResponse(items=["a", "b"], total_count=2)
        data = resp.model_dump()
        assert data["items"] == ["a", "b"]
        assert data["total_count"] == 2


# ---------------------------------------------------------------------------
# paginate function
# ---------------------------------------------------------------------------


class TestPaginate:
    """Tests for the paginate() function."""

    def test_empty_list(self):
        result = paginate([], cursor=None, limit=10)
        assert result.items == []
        assert result.has_more is False
        assert result.next_cursor is None
        assert result.total_count == 0

    def test_single_item(self):
        result = paginate(["a"], cursor=None, limit=10)
        assert result.items == ["a"]
        assert result.has_more is False
        assert result.total_count == 1

    def test_no_cursor_returns_first_page(self):
        items = list(range(100))
        result = paginate(items, cursor=None, limit=10)
        assert result.items == list(range(10))
        assert result.has_more is True

    def test_cursor_returns_next_page(self):
        items = list(range(100))
        first_page = paginate(items, cursor=None, limit=10)
        second_page = paginate(items, cursor=first_page.next_cursor, limit=10)
        assert second_page.items == list(range(10, 20))

    def test_has_more_true_when_more_items(self):
        items = list(range(20))
        result = paginate(items, cursor=None, limit=10)
        assert result.has_more is True

    def test_has_more_false_at_end(self):
        items = list(range(10))
        result = paginate(items, cursor=None, limit=10)
        assert result.has_more is False

    def test_has_more_false_fewer_items_than_limit(self):
        items = list(range(5))
        result = paginate(items, cursor=None, limit=10)
        assert result.has_more is False

    def test_next_cursor_present_when_more(self):
        items = list(range(20))
        result = paginate(items, cursor=None, limit=10)
        assert result.next_cursor is not None

    def test_next_cursor_none_at_end(self):
        items = list(range(10))
        result = paginate(items, cursor=None, limit=10)
        assert result.next_cursor is None

    def test_total_count_reflects_full_list(self):
        items = list(range(75))
        result = paginate(items, cursor=None, limit=10)
        assert result.total_count == 75

    def test_limit_clamped_to_max_limit(self):
        items = list(range(500))
        result = paginate(items, cursor=None, limit=999)
        assert result.limit == MAX_LIMIT
        assert len(result.items) == MAX_LIMIT

    def test_limit_0_clamped_to_1(self):
        items = list(range(10))
        result = paginate(items, cursor=None, limit=0)
        assert result.limit == 1
        assert len(result.items) == 1

    def test_negative_limit_clamped_to_1(self):
        items = list(range(10))
        result = paginate(items, cursor=None, limit=-5)
        assert result.limit == 1

    def test_exact_page_boundary(self):
        items = list(range(20))
        result = paginate(items, cursor=None, limit=20)
        assert result.has_more is False
        assert result.next_cursor is None
        assert len(result.items) == 20

    def test_exact_page_boundary_second_page(self):
        items = list(range(40))
        first = paginate(items, cursor=None, limit=20)
        assert first.has_more is True
        second = paginate(items, cursor=first.next_cursor, limit=20)
        assert second.has_more is False
        assert second.items == list(range(20, 40))

    def test_traverse_all_pages(self):
        items = list(range(55))
        all_collected = []
        cursor = None
        for _ in range(100):  # safety bound
            page = paginate(items, cursor=cursor, limit=10)
            all_collected.extend(page.items)
            if not page.has_more:
                break
            cursor = page.next_cursor
        assert all_collected == items

    def test_default_limit_used_when_not_specified(self):
        items = list(range(100))
        result = paginate(items)
        assert result.limit == DEFAULT_LIMIT
        assert len(result.items) == DEFAULT_LIMIT

    def test_paginate_with_string_items(self):
        items = [f"item-{i}" for i in range(30)]
        result = paginate(items, cursor=None, limit=10)
        assert result.items == [f"item-{i}" for i in range(10)]

    def test_paginate_with_dict_items(self):
        items = [{"id": i} for i in range(15)]
        result = paginate(items, cursor=None, limit=5)
        assert len(result.items) == 5
        assert result.items[0] == {"id": 0}

    def test_limit_at_max_exactly(self):
        items = list(range(MAX_LIMIT + 10))
        result = paginate(items, cursor=None, limit=MAX_LIMIT)
        assert result.limit == MAX_LIMIT
        assert len(result.items) == MAX_LIMIT

    def test_limit_one_below_max(self):
        items = list(range(MAX_LIMIT + 10))
        result = paginate(items, cursor=None, limit=MAX_LIMIT - 1)
        assert result.limit == MAX_LIMIT - 1

    def test_cursor_beyond_list_returns_empty(self):
        items = list(range(10))
        far_cursor = encode_cursor(100)
        result = paginate(items, cursor=far_cursor, limit=10)
        assert result.items == []
        assert result.has_more is False
