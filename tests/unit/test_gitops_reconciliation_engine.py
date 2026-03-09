"""Tests for shieldops.changes.gitops_reconciliation_engine — GitOpsReconciliationEngine."""

from __future__ import annotations

from shieldops.changes.gitops_reconciliation_engine import (
    DriftSeverity,
    GitOpsReconciliationEngine,
    ReconciliationRecord,
    ReconciliationStatus,
    SyncStrategy,
)


def _engine(**kw) -> GitOpsReconciliationEngine:
    return GitOpsReconciliationEngine(**kw)


class TestEnums:
    def test_status_synced(self):
        assert ReconciliationStatus.SYNCED == "synced"

    def test_status_drifted(self):
        assert ReconciliationStatus.DRIFTED == "drifted"

    def test_drift_severity(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_sync_strategy(self):
        assert SyncStrategy.AUTO_SYNC == "auto_sync"


class TestModels:
    def test_record_defaults(self):
        r = ReconciliationRecord()
        assert r.id
        assert r.branch == "main"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="app-deploy", cluster="prod-us-east")
        assert rec.name == "app-deploy"
        assert rec.cluster == "prod-us-east"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"deploy-{i}", cluster="prod")
        assert len(eng._records) == 3


class TestDetectDrift:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="app", cluster="prod", status=ReconciliationStatus.DRIFTED, drift_resources=3
        )
        result = eng.detect_drift()
        assert isinstance(result, list)


class TestSyncPerformance:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="app", cluster="prod", sync_duration_seconds=30.0)
        result = eng.analyze_sync_performance()
        assert isinstance(result, dict)


class TestConflictHotspots:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="app", cluster="prod", status=ReconciliationStatus.CONFLICT)
        result = eng.identify_conflict_hotspots()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="app", cluster="prod")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="app", cluster="prod")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="app", cluster="prod")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
