"""Tests for shieldops.topology.asset_inventory_reconciler — AssetInventoryReconciler."""

from __future__ import annotations

from shieldops.topology.asset_inventory_reconciler import (
    AssetInventoryReconciler,
    AssetSource,
    DiscrepancyType,
    ReconciliationAnalysis,
    ReconciliationRecord,
    ReconciliationReport,
    ReconciliationStatus,
)


def _engine(**kw) -> AssetInventoryReconciler:
    return AssetInventoryReconciler(**kw)


class TestEnums:
    def test_reconciliationstatus_val1(self):
        assert ReconciliationStatus.MATCHED == "matched"

    def test_reconciliationstatus_val2(self):
        assert ReconciliationStatus.MISMATCHED == "mismatched"

    def test_reconciliationstatus_val3(self):
        assert ReconciliationStatus.MISSING == "missing"

    def test_reconciliationstatus_val4(self):
        assert ReconciliationStatus.STALE == "stale"

    def test_reconciliationstatus_val5(self):
        assert ReconciliationStatus.UNKNOWN == "unknown"

    def test_assetsource_val1(self):
        assert AssetSource.CMDB == "cmdb"

    def test_assetsource_val2(self):
        assert AssetSource.CLOUD_API == "cloud_api"

    def test_assetsource_val3(self):
        assert AssetSource.SCANNER == "scanner"

    def test_assetsource_val4(self):
        assert AssetSource.AGENT == "agent"

    def test_assetsource_val5(self):
        assert AssetSource.MANUAL == "manual"

    def test_discrepancytype_val1(self):
        assert DiscrepancyType.MISSING_ASSET == "missing_asset"

    def test_discrepancytype_val2(self):
        assert DiscrepancyType.EXTRA_ASSET == "extra_asset"

    def test_discrepancytype_val3(self):
        assert DiscrepancyType.ATTRIBUTE_MISMATCH == "attribute_mismatch"

    def test_discrepancytype_val4(self):
        assert DiscrepancyType.STALE_DATA == "stale_data"

    def test_discrepancytype_val5(self):
        assert DiscrepancyType.CLASSIFICATION_ERROR == "classification_error"


class TestModels:
    def test_record_defaults(self):
        r = ReconciliationRecord()
        assert r.id
        assert r.asset_name == ""

    def test_analysis_defaults(self):
        a = ReconciliationAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = ReconciliationReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_reconciliation(
            asset_name="test",
            reconciliation_status=ReconciliationStatus.MISMATCHED,
            reconciliation_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.asset_name == "test"
        assert r.reconciliation_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_reconciliation(asset_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_reconciliation(asset_name="test")
        assert eng.get_reconciliation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_reconciliation("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="a")
        eng.record_reconciliation(asset_name="b")
        assert len(eng.list_reconciliations()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_reconciliation(
            asset_name="a", reconciliation_status=ReconciliationStatus.MATCHED
        )
        eng.record_reconciliation(
            asset_name="b", reconciliation_status=ReconciliationStatus.MISMATCHED
        )
        assert (
            len(eng.list_reconciliations(reconciliation_status=ReconciliationStatus.MATCHED)) == 1
        )

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="a", asset_source=AssetSource.CMDB)
        eng.record_reconciliation(asset_name="b", asset_source=AssetSource.CLOUD_API)
        assert len(eng.list_reconciliations(asset_source=AssetSource.CMDB)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="a", team="sec")
        eng.record_reconciliation(asset_name="b", team="ops")
        assert len(eng.list_reconciliations(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_reconciliation(asset_name=f"t-{i}")
        assert len(eng.list_reconciliations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            asset_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(asset_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_reconciliation(
            asset_name="a",
            reconciliation_status=ReconciliationStatus.MATCHED,
            reconciliation_score=90.0,
        )
        eng.record_reconciliation(
            asset_name="b",
            reconciliation_status=ReconciliationStatus.MATCHED,
            reconciliation_score=70.0,
        )
        result = eng.analyze_distribution()
        assert ReconciliationStatus.MATCHED.value in result
        assert result[ReconciliationStatus.MATCHED.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_reconciliation(asset_name="a", reconciliation_score=60.0)
        eng.record_reconciliation(asset_name="b", reconciliation_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_reconciliation(asset_name="a", reconciliation_score=50.0)
        eng.record_reconciliation(asset_name="b", reconciliation_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["reconciliation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="a", service="auth", reconciliation_score=90.0)
        eng.record_reconciliation(asset_name="b", service="api", reconciliation_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(asset_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(asset_name="a", analysis_score=20.0)
        eng.add_analysis(asset_name="b", analysis_score=20.0)
        eng.add_analysis(asset_name="c", analysis_score=80.0)
        eng.add_analysis(asset_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_reconciliation(asset_name="test", reconciliation_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="test")
        eng.add_analysis(asset_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_reconciliation(asset_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
