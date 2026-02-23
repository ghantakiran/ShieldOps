"""Tests for soft-delete mixin, utilities, and in-memory store.

Covers SoftDeleteMixin, SoftDeletableRecord, soft_delete, restore, purge,
filter_deleted, and SoftDeleteStore.
"""

from datetime import UTC, datetime

from shieldops.db.soft_delete import (
    SoftDeletableRecord,
    SoftDeleteMixin,
    SoftDeleteStore,
    filter_deleted,
    purge,
    restore,
    soft_delete,
)

# ---------------------------------------------------------------------------
# SoftDeleteMixin
# ---------------------------------------------------------------------------


class TestSoftDeleteMixin:
    def test_deleted_at_default_none(self):
        mixin = SoftDeleteMixin()
        assert mixin.deleted_at is None

    def test_deleted_by_default_none(self):
        mixin = SoftDeleteMixin()
        assert mixin.deleted_by is None

    def test_set_deleted_at(self):
        mixin = SoftDeleteMixin()
        now = datetime.now(UTC)
        mixin.deleted_at = now
        assert mixin.deleted_at == now

    def test_set_deleted_by(self):
        mixin = SoftDeleteMixin()
        mixin.deleted_by = "admin"
        assert mixin.deleted_by == "admin"


# ---------------------------------------------------------------------------
# SoftDeletableRecord
# ---------------------------------------------------------------------------


class TestSoftDeletableRecord:
    def test_creation_with_id(self):
        record = SoftDeletableRecord(id="r1")
        assert record.id == "r1"

    def test_default_data_empty_dict(self):
        record = SoftDeletableRecord(id="r1")
        assert record.data == {}

    def test_custom_data(self):
        record = SoftDeletableRecord(id="r1", data={"foo": "bar"})
        assert record.data["foo"] == "bar"

    def test_created_at_auto_set(self):
        record = SoftDeletableRecord(id="r1")
        assert record.created_at is not None
        assert record.created_at.tzinfo is not None

    def test_updated_at_auto_set(self):
        record = SoftDeletableRecord(id="r1")
        assert record.updated_at is not None

    def test_is_deleted_false_by_default(self):
        record = SoftDeletableRecord(id="r1")
        assert record.is_deleted is False

    def test_is_deleted_true_when_deleted_at_set(self):
        record = SoftDeletableRecord(id="r1")
        record.deleted_at = datetime.now(UTC)
        assert record.is_deleted is True

    def test_inherits_mixin_fields(self):
        record = SoftDeletableRecord(id="r1")
        assert hasattr(record, "deleted_at")
        assert hasattr(record, "deleted_by")


# ---------------------------------------------------------------------------
# soft_delete utility function
# ---------------------------------------------------------------------------


class TestSoftDeleteFunction:
    def test_sets_deleted_at(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        assert record.deleted_at is not None

    def test_sets_deleted_by_default_system(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        assert record.deleted_by == "system"

    def test_sets_deleted_by_custom(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record, deleted_by="admin-user")
        assert record.deleted_by == "admin-user"

    def test_deleted_at_is_utc(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        assert record.deleted_at.tzinfo is not None

    def test_is_deleted_property_after_soft_delete(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        assert record.is_deleted is True


# ---------------------------------------------------------------------------
# restore utility function
# ---------------------------------------------------------------------------


class TestRestoreFunction:
    def test_clears_deleted_at(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        restore(record)
        assert record.deleted_at is None

    def test_clears_deleted_by(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record, deleted_by="admin")
        restore(record)
        assert record.deleted_by is None

    def test_is_deleted_false_after_restore(self):
        record = SoftDeletableRecord(id="r1")
        soft_delete(record)
        restore(record)
        assert record.is_deleted is False

    def test_restore_already_active_is_noop(self):
        record = SoftDeletableRecord(id="r1")
        restore(record)  # Should not raise
        assert record.deleted_at is None


# ---------------------------------------------------------------------------
# purge utility function
# ---------------------------------------------------------------------------


class TestPurgeFunction:
    def test_purge_removes_item(self):
        items = [SoftDeletableRecord(id="r1"), SoftDeletableRecord(id="r2")]
        removed = purge(items, "r1")
        assert removed is not None
        assert removed.id == "r1"
        assert len(items) == 1

    def test_purge_returns_none_for_missing(self):
        items = [SoftDeletableRecord(id="r1")]
        removed = purge(items, "nonexistent")
        assert removed is None
        assert len(items) == 1

    def test_purge_empty_list(self):
        items = []
        removed = purge(items, "r1")
        assert removed is None

    def test_purge_first_match_only(self):
        items = [
            SoftDeletableRecord(id="r1", data={"v": 1}),
            SoftDeletableRecord(id="r1", data={"v": 2}),
        ]
        removed = purge(items, "r1")
        assert removed.data["v"] == 1
        assert len(items) == 1


# ---------------------------------------------------------------------------
# filter_deleted utility function
# ---------------------------------------------------------------------------


class TestFilterDeleted:
    def test_excludes_deleted_by_default(self):
        r1 = SoftDeletableRecord(id="r1")
        r2 = SoftDeletableRecord(id="r2")
        soft_delete(r2)
        result = filter_deleted([r1, r2])
        assert len(result) == 1
        assert result[0].id == "r1"

    def test_includes_deleted_when_flag_true(self):
        r1 = SoftDeletableRecord(id="r1")
        r2 = SoftDeletableRecord(id="r2")
        soft_delete(r2)
        result = filter_deleted([r1, r2], include_deleted=True)
        assert len(result) == 2

    def test_empty_list(self):
        result = filter_deleted([])
        assert result == []

    def test_all_deleted(self):
        r1 = SoftDeletableRecord(id="r1")
        soft_delete(r1)
        result = filter_deleted([r1])
        assert result == []

    def test_none_deleted(self):
        r1 = SoftDeletableRecord(id="r1")
        r2 = SoftDeletableRecord(id="r2")
        result = filter_deleted([r1, r2])
        assert len(result) == 2

    def test_returns_new_list(self):
        items = [SoftDeletableRecord(id="r1")]
        result = filter_deleted(items)
        assert result is not items


# ---------------------------------------------------------------------------
# SoftDeleteStore
# ---------------------------------------------------------------------------


class TestSoftDeleteStoreCreate:
    def test_create_stores_record(self):
        store = SoftDeleteStore()
        record = SoftDeletableRecord(id="r1", data={"name": "test"})
        result = store.create(record)
        assert result.id == "r1"

    def test_create_returns_same_record(self):
        store = SoftDeleteStore()
        record = SoftDeletableRecord(id="r1")
        result = store.create(record)
        assert result is record

    def test_total_count_after_create(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        assert store.total_count == 2


class TestSoftDeleteStoreGet:
    def test_get_existing(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        assert store.get("r1") is not None

    def test_get_nonexistent_returns_none(self):
        store = SoftDeleteStore()
        assert store.get("nope") is None

    def test_get_deleted_returns_none_by_default(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1")
        assert store.get("r1") is None

    def test_get_deleted_with_include_deleted(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1")
        result = store.get("r1", include_deleted=True)
        assert result is not None
        assert result.is_deleted is True


class TestSoftDeleteStoreListAll:
    def test_list_all_excludes_deleted(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        store.soft_delete("r1")
        result = store.list_all()
        assert len(result) == 1
        assert result[0].id == "r2"

    def test_list_all_include_deleted(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        store.soft_delete("r1")
        result = store.list_all(include_deleted=True)
        assert len(result) == 2

    def test_list_all_empty_store(self):
        store = SoftDeleteStore()
        assert store.list_all() == []


class TestSoftDeleteStoreSoftDelete:
    def test_soft_delete_returns_true(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        assert store.soft_delete("r1") is True

    def test_soft_delete_nonexistent_returns_false(self):
        store = SoftDeleteStore()
        assert store.soft_delete("nope") is False

    def test_soft_delete_custom_deleted_by(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1", deleted_by="admin")
        record = store.get("r1", include_deleted=True)
        assert record.deleted_by == "admin"


class TestSoftDeleteStoreRestore:
    def test_restore_returns_true(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1")
        assert store.restore("r1") is True

    def test_restore_nonexistent_returns_false(self):
        store = SoftDeleteStore()
        assert store.restore("nope") is False

    def test_restore_makes_record_visible(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1")
        store.restore("r1")
        assert store.get("r1") is not None
        assert store.get("r1").is_deleted is False


class TestSoftDeleteStorePurge:
    def test_purge_returns_true(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        assert store.purge("r1") is True

    def test_purge_nonexistent_returns_false(self):
        store = SoftDeleteStore()
        assert store.purge("nope") is False

    def test_purge_permanently_removes(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.purge("r1")
        assert store.get("r1", include_deleted=True) is None
        assert store.total_count == 0


class TestSoftDeleteStoreCounts:
    def test_total_count_includes_deleted(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        store.soft_delete("r1")
        assert store.total_count == 2

    def test_active_count_excludes_deleted(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        store.soft_delete("r1")
        assert store.active_count == 1

    def test_deleted_count(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.create(SoftDeletableRecord(id="r2"))
        store.soft_delete("r1")
        assert store.deleted_count == 1

    def test_counts_empty_store(self):
        store = SoftDeleteStore()
        assert store.total_count == 0
        assert store.active_count == 0
        assert store.deleted_count == 0

    def test_counts_after_purge(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.purge("r1")
        assert store.total_count == 0
        assert store.active_count == 0
        assert store.deleted_count == 0

    def test_counts_after_restore(self):
        store = SoftDeleteStore()
        store.create(SoftDeletableRecord(id="r1"))
        store.soft_delete("r1")
        store.restore("r1")
        assert store.active_count == 1
        assert store.deleted_count == 0
