"""Tests for shieldops.compliance.data_residency_enforcer — DataResidencyEnforcer."""

from __future__ import annotations

from shieldops.compliance.data_residency_enforcer import (
    DataResidencyEnforcer,
    EnforcementAction,
    Region,
    ResidencyAnalysis,
    ResidencyComplianceReport,
    ResidencyRecord,
    ResidencyStatus,
)


def _engine(**kw) -> DataResidencyEnforcer:
    return DataResidencyEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_region_us(self):
        assert Region.US == "us"

    def test_region_eu(self):
        assert Region.EU == "eu"

    def test_region_apac(self):
        assert Region.APAC == "apac"

    def test_region_latam(self):
        assert Region.LATAM == "latam"

    def test_region_global(self):
        assert Region.GLOBAL == "global"

    def test_status_compliant(self):
        assert ResidencyStatus.COMPLIANT == "compliant"

    def test_status_violation(self):
        assert ResidencyStatus.VIOLATION == "violation"

    def test_status_pending(self):
        assert ResidencyStatus.PENDING == "pending"

    def test_status_exempt(self):
        assert ResidencyStatus.EXEMPT == "exempt"

    def test_status_unknown(self):
        assert ResidencyStatus.UNKNOWN == "unknown"

    def test_action_block(self):
        assert EnforcementAction.BLOCK == "block"

    def test_action_redirect(self):
        assert EnforcementAction.REDIRECT == "redirect"

    def test_action_encrypt(self):
        assert EnforcementAction.ENCRYPT == "encrypt"

    def test_action_log(self):
        assert EnforcementAction.LOG == "log"

    def test_action_alert(self):
        assert EnforcementAction.ALERT == "alert"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_residency_record_defaults(self):
        r = ResidencyRecord()
        assert r.id
        assert r.data_asset == ""
        assert r.region == Region.US
        assert r.residency_status == ResidencyStatus.COMPLIANT
        assert r.enforcement_action == EnforcementAction.LOG
        assert r.compliance_score == 0.0
        assert r.tenant == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_residency_analysis_defaults(self):
        a = ResidencyAnalysis()
        assert a.id
        assert a.data_asset == ""
        assert a.region == Region.US
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ResidencyComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_region == {}
        assert r.by_status == {}
        assert r.by_action == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_residency / get_residency
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_residency(
            data_asset="customer-db",
            region=Region.EU,
            residency_status=ResidencyStatus.COMPLIANT,
            enforcement_action=EnforcementAction.BLOCK,
            compliance_score=95.0,
            tenant="tenant-a",
            data_owner="dpo-team",
        )
        assert r.data_asset == "customer-db"
        assert r.region == Region.EU
        assert r.compliance_score == 95.0
        assert r.tenant == "tenant-a"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_residency(data_asset="asset-001", region=Region.APAC)
        result = eng.get_residency(r.id)
        assert result is not None
        assert result.region == Region.APAC

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_residency("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_residency(data_asset=f"asset-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_residencies
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001")
        eng.record_residency(data_asset="a-002")
        assert len(eng.list_residencies()) == 2

    def test_filter_by_region(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001", region=Region.US)
        eng.record_residency(data_asset="a-002", region=Region.EU)
        results = eng.list_residencies(region=Region.US)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001", residency_status=ResidencyStatus.COMPLIANT)
        eng.record_residency(data_asset="a-002", residency_status=ResidencyStatus.VIOLATION)
        results = eng.list_residencies(residency_status=ResidencyStatus.COMPLIANT)
        assert len(results) == 1

    def test_filter_by_tenant(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001", tenant="tenant-a")
        eng.record_residency(data_asset="a-002", tenant="tenant-b")
        results = eng.list_residencies(tenant="tenant-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_residency(data_asset=f"a-{i}")
        assert len(eng.list_residencies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            data_asset="customer-db",
            region=Region.EU,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="residency violation",
        )
        assert a.data_asset == "customer-db"
        assert a.region == Region.EU
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(data_asset="asset-001", region=Region.APAC)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_region_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001", region=Region.US, compliance_score=90.0)
        eng.record_residency(data_asset="a-002", region=Region.US, compliance_score=70.0)
        result = eng.analyze_region_distribution()
        assert "us" in result
        assert result["us"]["count"] == 2
        assert result["us"]["avg_compliance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_region_distribution() == {}


# ---------------------------------------------------------------------------
# identify_residency_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_residency(data_asset="a-001", compliance_score=60.0)
        eng.record_residency(data_asset="a-002", compliance_score=90.0)
        results = eng.identify_residency_gaps()
        assert len(results) == 1
        assert results[0]["data_asset"] == "a-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_residency(data_asset="a-001", compliance_score=50.0)
        eng.record_residency(data_asset="a-002", compliance_score=30.0)
        results = eng.identify_residency_gaps()
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001", tenant="t-a", compliance_score=90.0)
        eng.record_residency(data_asset="a-002", tenant="t-b", compliance_score=50.0)
        results = eng.rank_by_compliance()
        assert results[0]["tenant"] == "t-b"
        assert results[0]["avg_compliance_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_residency_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(data_asset="a-001", analysis_score=50.0)
        result = eng.detect_residency_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(data_asset="a-001", analysis_score=20.0)
        eng.add_analysis(data_asset="a-002", analysis_score=20.0)
        eng.add_analysis(data_asset="a-003", analysis_score=80.0)
        eng.add_analysis(data_asset="a-004", analysis_score=80.0)
        result = eng.detect_residency_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_residency_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_residency(
            data_asset="customer-db",
            region=Region.EU,
            residency_status=ResidencyStatus.VIOLATION,
            enforcement_action=EnforcementAction.BLOCK,
            compliance_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ResidencyComplianceReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_residency(data_asset="a-001")
        eng.add_analysis(data_asset="a-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["region_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 3
