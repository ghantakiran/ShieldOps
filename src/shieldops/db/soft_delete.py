"""Soft-delete mixin and utilities for data models.

Provides non-destructive deletion by setting ``deleted_at`` timestamps
instead of removing rows. Supports restore and permanent purge.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SoftDeleteMixin(BaseModel):
    """Mixin that adds soft-delete fields to any Pydantic model."""

    deleted_at: datetime | None = None
    deleted_by: str | None = None


class SoftDeletableRecord(SoftDeleteMixin):
    """A generic record with soft-delete support."""

    id: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def soft_delete(item: SoftDeleteMixin, deleted_by: str = "system") -> None:
    """Mark an item as soft-deleted."""
    item.deleted_at = datetime.now(UTC)
    item.deleted_by = deleted_by


def restore(item: SoftDeleteMixin) -> None:
    """Restore a soft-deleted item."""
    item.deleted_at = None
    item.deleted_by = None


def purge(items: list[Any], item_id: str) -> Any | None:
    """Permanently remove an item from a list (for GDPR erasure).

    Returns the removed item, or None if not found.
    """
    for i, item in enumerate(items):
        _id = getattr(item, "id", None)
        if _id == item_id:
            return items.pop(i)
    return None


def filter_deleted(
    items: list[Any],
    include_deleted: bool = False,
) -> list[Any]:
    """Filter items, optionally excluding soft-deleted ones."""
    if include_deleted:
        return list(items)
    return [item for item in items if getattr(item, "deleted_at", None) is None]


class SoftDeleteStore:
    """In-memory store with soft-delete support.

    Useful for testing and as a reference implementation for DB-backed stores.
    """

    def __init__(self) -> None:
        self._records: dict[str, SoftDeletableRecord] = {}

    def create(self, record: SoftDeletableRecord) -> SoftDeletableRecord:
        self._records[record.id] = record
        return record

    def get(self, record_id: str, include_deleted: bool = False) -> SoftDeletableRecord | None:
        record = self._records.get(record_id)
        if record is None:
            return None
        if not include_deleted and record.is_deleted:
            return None
        return record

    def list_all(self, include_deleted: bool = False) -> list[SoftDeletableRecord]:
        records = list(self._records.values())
        return filter_deleted(records, include_deleted=include_deleted)

    def soft_delete(self, record_id: str, deleted_by: str = "system") -> bool:
        record = self._records.get(record_id)
        if record is None:
            return False
        soft_delete(record, deleted_by=deleted_by)
        return True

    def restore(self, record_id: str) -> bool:
        record = self._records.get(record_id)
        if record is None:
            return False
        restore(record)
        return True

    def purge(self, record_id: str) -> bool:
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

    @property
    def total_count(self) -> int:
        return len(self._records)

    @property
    def active_count(self) -> int:
        return sum(1 for r in self._records.values() if not r.is_deleted)

    @property
    def deleted_count(self) -> int:
        return sum(1 for r in self._records.values() if r.is_deleted)
