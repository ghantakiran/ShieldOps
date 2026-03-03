"""Tests for shieldops.compliance.data_retention_enforcer — DataRetentionEnforcer."""

from __future__ import annotations

from shieldops.compliance.data_retention_enforcer import (
    DataCategory,
    DataRetentionEnforcer,
    EnforcementStatus,
    RetentionAnalysis,
    RetentionComplianceReport,
    RetentionPolicy,
    RetentionRecord,
)


def _engine(**kw) -> DataRetentionEnforcer:
    return DataRetentionEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_policy_legal_hold(self):
        assert RetentionPolicy.LEGAL_HOLD == "legal_hold"

    def test_policy_regulatory(self):
        assert RetentionPolicy.REGULATORY == "regulatory"

    def test_policy_business(self):
        assert RetentionPolicy.BUSINESS == "business"

    def test_policy_archive(self):
        assert RetentionPolicy.ARCHIVE == "archive"

    def test_policy_delete(self):
        assert RetentionPolicy.DELETE == "delete"

    def test_category_personal(self):
        assert DataCategory.PERSONAL == "personal"

    def test_category_financial(self):
        assert DataCategory.FINANCIAL == "financial"

    def test_category_health(self):
        assert DataCategory.HEALTH == "health"

    def test_category_biometric(self):
        assert DataCategory.BIOMETRIC == "biometric"

    def test_category_behavioral(self):
        assert DataCategory.BEHAVIORAL == "behavioral"

    def test_status_enforced(self):
        assert EnforcementStatus.ENFORCED == "enforced"

    def test_status_overdue(self):
        assert EnforcementStatus.OVERDUE == "overdue"

    def test_status_exempt(self):
        assert EnforcementStatus.EXEMPT == "exempt"

    def test_status_pending(self):
        assert EnforcementStatus.PENDING == "pending"

    def test_status_failed(self):
        assert EnforcementStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_retention_record_defaults(self):
        r = RetentionRecord()
        assert r.id
        assert r.data_asset == ""
        assert r.retention_policy == RetentionPolicy.REGULATORY
        assert r.data_category == DataCategory.PERSONAL
        assert r.enforcement_status == EnforcementStatus.ENFORCED
        assert r.compliance_score == 0.0
        assert r.storage_system == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_retention_analysis_defaults(self):
        a = RetentionAnalysis()
        assert a.id
        assert a.data_asset == ""
        assert a.data_category == DataCategory.PERSONAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = RetentionComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_policy == {}
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_retention / get_retention
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_retention(
            data_asset="customer-pii",
            retention_policy=RetentionPolicy.REGULATORY,
            data_category=DataCategory.PERSONAL,
            enforcement_status=EnforcementStatus.ENFORCED,
            compliance_score=95.0,
            storage_system="postgres",
            data_owner="dpo-team",
        )
        assert r.data_asset == "customer-pii"
        assert r.retention_policy == RetentionPolicy.REGULATORY
        assert r.compliance_score == 95.0
        assert r.storage_system == "postgres"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_retention(data_asset="asset-001", data_category=DataCategory.HEALTH)
        result = eng.get_retention(r.id)
        assert result is not None
        assert result.data_category == DataCategory.HEALTH

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_retention("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_retention(data_asset=f"asset-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_retentions
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_retention(data_asset="a-001")
        eng.record_retention(data_asset="a-002")
        assert len(eng.list_retentions()) == 2

    def test_filter_by_policy(self):
        eng = _engine()
        eng.record_retention(data_asset="a-001", retention_policy=RetentionPolicy.REGULATORY)
        eng.record_retention(data_asset="a-002", retention_policy=RetentionPolicy.ARCHIVE)
        results = eng.list_retentions(retention_policy=RetentionPolicy.REGULATORY)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_retention(data_asset="a-001", data_category=DataCategory.PERSONAL)
        eng.record_retention(data_asset="a-002", data_category=DataCategory.HEALTH)
        results = eng.list_retentions(data_category=DataCategory.PERSONAL)
        assert len(results) == 1

    def test_filter_by_owner(self):
        eng = _engine()
        eng.record_retention(data_asset="a-001", data_owner="team-a")
        eng.record_retention(data_asset="a-002", data_owner="team-b")
        results = eng.list_retentions(data_owner="team-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_retention(data_asset=f"a-{i}")
        assert len(eng.list_retentions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            data_asset="customer-pii",
            data_category=DataCategory.PERSONAL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="retention overdue",
        )
        assert a.data_asset == "customer-pii"
        assert a.data_category == DataCategory.PERSONAL
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(data_asset="asset-999", data_category=DataCategory.BIOMETRIC)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_category_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_retention(
            data_asset="a-001", data_category=DataCategory.PERSONAL, compliance_score=90.0
        )
        eng.record_retention(
            data_asset="a-002", data_category=DataCategory.PERSONAL, compliance_score=70.0
        )
        result = eng.analyze_category_distribution()
        assert "personal" in result
        assert result["personal"]["count"] == 2
        assert result["personal"]["avg_compliance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_retention_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_retention(data_asset="a-001", compliance_score=60.0)
        eng.record_retention(data_asset="a-002", compliance_score=90.0)
        results = eng.identify_retention_gaps()
        assert len(results) == 1
        assert results[0]["data_asset"] == "a-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_retention(data_asset="a-001", compliance_score=50.0)
        eng.record_retention(data_asset="a-002", compliance_score=30.0)
        results = eng.identify_retention_gaps()
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_retention(data_asset="a-001", storage_system="postgres", compliance_score=90.0)
        eng.record_retention(data_asset="a-002", storage_system="s3", compliance_score=50.0)
        results = eng.rank_by_compliance()
        assert results[0]["storage_system"] == "s3"
        assert results[0]["avg_compliance_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_retention_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(data_asset="a-001", analysis_score=50.0)
        result = eng.detect_retention_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(data_asset="a-001", analysis_score=20.0)
        eng.add_analysis(data_asset="a-002", analysis_score=20.0)
        eng.add_analysis(data_asset="a-003", analysis_score=80.0)
        eng.add_analysis(data_asset="a-004", analysis_score=80.0)
        result = eng.detect_retention_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_retention_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_retention(
            data_asset="customer-pii",
            retention_policy=RetentionPolicy.LEGAL_HOLD,
            data_category=DataCategory.PERSONAL,
            enforcement_status=EnforcementStatus.OVERDUE,
            compliance_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RetentionComplianceReport)
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
        eng.record_retention(data_asset="a-001")
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
        assert stats["category_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 3
