"""Tests for shieldops.observability.log_retention_optimizer — LogRetentionOptimizer."""

from __future__ import annotations

from shieldops.observability.log_retention_optimizer import (
    ComplianceRequirement,
    LogRetentionOptimizer,
    LogRetentionRecord,
    LogRetentionReport,
    LogValueLevel,
    RetentionPolicy,
    RetentionTier,
)


def _engine(**kw) -> LogRetentionOptimizer:
    return LogRetentionOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tier_hot(self):
        assert RetentionTier.HOT == "hot"

    def test_tier_warm(self):
        assert RetentionTier.WARM == "warm"

    def test_tier_cold(self):
        assert RetentionTier.COLD == "cold"

    def test_tier_archive(self):
        assert RetentionTier.ARCHIVE == "archive"

    def test_tier_delete(self):
        assert RetentionTier.DELETE == "delete"

    def test_value_critical(self):
        assert LogValueLevel.CRITICAL == "critical"

    def test_value_high(self):
        assert LogValueLevel.HIGH == "high"

    def test_value_medium(self):
        assert LogValueLevel.MEDIUM == "medium"

    def test_value_low(self):
        assert LogValueLevel.LOW == "low"

    def test_value_negligible(self):
        assert LogValueLevel.NEGLIGIBLE == "negligible"

    def test_compliance_regulatory(self):
        assert ComplianceRequirement.REGULATORY == "regulatory"

    def test_compliance_security(self):
        assert ComplianceRequirement.SECURITY == "security"

    def test_compliance_operational(self):
        assert ComplianceRequirement.OPERATIONAL == "operational"

    def test_compliance_audit(self):
        assert ComplianceRequirement.AUDIT == "audit"

    def test_compliance_none(self):
        assert ComplianceRequirement.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_log_retention_record_defaults(self):
        r = LogRetentionRecord()
        assert r.id
        assert r.source == ""
        assert r.current_tier == RetentionTier.HOT
        assert r.value_level == LogValueLevel.MEDIUM
        assert r.compliance == ComplianceRequirement.NONE
        assert r.retention_days == 90
        assert r.daily_volume_gb == 0.0
        assert r.cost_per_gb_month == 0.0
        assert r.created_at > 0

    def test_retention_policy_defaults(self):
        p = RetentionPolicy()
        assert p.id
        assert p.source_pattern == ""
        assert p.recommended_tier == RetentionTier.WARM
        assert p.recommended_days == 90
        assert p.compliance == ComplianceRequirement.NONE
        assert p.reason == ""
        assert p.created_at > 0

    def test_report_defaults(self):
        r = LogRetentionReport()
        assert r.total_sources == 0
        assert r.total_policies == 0
        assert r.avg_retention_days == 0.0
        assert r.by_tier == {}
        assert r.by_value == {}
        assert r.estimated_savings_pct == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_log_source
# ---------------------------------------------------------------------------


class TestRecordLogSource:
    def test_basic(self):
        eng = _engine()
        r = eng.record_log_source(
            source="app-logs",
            current_tier=RetentionTier.HOT,
            value_level=LogValueLevel.HIGH,
            retention_days=180,
        )
        assert r.source == "app-logs"
        assert r.current_tier == RetentionTier.HOT
        assert r.value_level == LogValueLevel.HIGH

    def test_with_cost(self):
        eng = _engine()
        r = eng.record_log_source(
            source="debug-logs",
            value_level=LogValueLevel.LOW,
            daily_volume_gb=50.0,
            cost_per_gb_month=0.10,
        )
        assert r.daily_volume_gb == 50.0
        assert r.cost_per_gb_month == 0.10

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_log_source(source=f"src-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get / list
# ---------------------------------------------------------------------------


class TestGetLogSource:
    def test_found(self):
        eng = _engine()
        r = eng.record_log_source(source="s1")
        result = eng.get_log_source(r.id)
        assert result is not None
        assert result.source == "s1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_log_source("nonexistent") is None


class TestListLogSources:
    def test_list_all(self):
        eng = _engine()
        eng.record_log_source(source="s1")
        eng.record_log_source(source="s2")
        assert len(eng.list_log_sources()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_log_source(source="s1")
        eng.record_log_source(source="s2")
        results = eng.list_log_sources(source="s1")
        assert len(results) == 1

    def test_filter_by_value(self):
        eng = _engine()
        eng.record_log_source(source="s1", value_level=LogValueLevel.HIGH)
        eng.record_log_source(source="s2", value_level=LogValueLevel.LOW)
        results = eng.list_log_sources(value_level=LogValueLevel.HIGH)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_policy
# ---------------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            source_pattern="debug-*",
            recommended_tier=RetentionTier.COLD,
            recommended_days=30,
            reason="Low value debug logs",
        )
        assert p.source_pattern == "debug-*"
        assert p.recommended_tier == RetentionTier.COLD

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_policy(source_pattern=f"p{i}")
        assert len(eng._policies) == 3


# ---------------------------------------------------------------------------
# recommend_retention
# ---------------------------------------------------------------------------


class TestRecommendRetention:
    def test_basic(self):
        eng = _engine()
        eng.record_log_source(source="app-logs", value_level=LogValueLevel.HIGH, retention_days=90)
        result = eng.recommend_retention("app-logs")
        assert result["recommended_retention_days"] == 180
        assert result["recommended_tier"] == "warm"

    def test_compliance_override(self):
        eng = _engine()
        eng.record_log_source(
            source="audit-logs",
            value_level=LogValueLevel.LOW,
            compliance=ComplianceRequirement.REGULATORY,
            retention_days=30,
        )
        result = eng.recommend_retention("audit-logs")
        assert result["recommended_retention_days"] >= 365

    def test_no_data(self):
        eng = _engine()
        result = eng.recommend_retention("unknown")
        assert result["recommendation"] == "no_data"


# ---------------------------------------------------------------------------
# identify_over_retained
# ---------------------------------------------------------------------------


class TestIdentifyOverRetained:
    def test_finds_over(self):
        eng = _engine()
        eng.record_log_source(
            source="debug-logs", value_level=LogValueLevel.NEGLIGIBLE, retention_days=365
        )
        results = eng.identify_over_retained()
        assert len(results) == 1
        assert results[0]["source"] == "debug-logs"

    def test_no_over(self):
        eng = _engine()
        eng.record_log_source(
            source="app-logs", value_level=LogValueLevel.CRITICAL, retention_days=365
        )
        assert eng.identify_over_retained() == []


# ---------------------------------------------------------------------------
# calculate_cost_savings
# ---------------------------------------------------------------------------


class TestCalculateCostSavings:
    def test_with_data(self):
        eng = _engine()
        eng.record_log_source(
            source="debug-logs",
            value_level=LogValueLevel.NEGLIGIBLE,
            retention_days=365,
            daily_volume_gb=10.0,
            cost_per_gb_month=0.10,
        )
        result = eng.calculate_cost_savings()
        assert result["estimated_savings"] > 0
        assert result["savings_pct"] > 0

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_cost_savings()
        assert result["estimated_savings"] == 0.0


# ---------------------------------------------------------------------------
# analyze_compliance_gaps
# ---------------------------------------------------------------------------


class TestAnalyzeComplianceGaps:
    def test_regulatory_gap(self):
        eng = _engine()
        eng.record_log_source(
            source="audit-logs",
            compliance=ComplianceRequirement.REGULATORY,
            retention_days=90,
        )
        results = eng.analyze_compliance_gaps()
        assert len(results) == 1
        assert results[0]["gap_days"] == 275

    def test_audit_gap(self):
        eng = _engine()
        eng.record_log_source(
            source="audit-logs",
            compliance=ComplianceRequirement.AUDIT,
            retention_days=30,
        )
        results = eng.analyze_compliance_gaps()
        assert len(results) == 1
        assert results[0]["required_days"] == 180

    def test_no_gaps(self):
        eng = _engine()
        eng.record_log_source(
            source="logs",
            compliance=ComplianceRequirement.REGULATORY,
            retention_days=400,
        )
        assert eng.analyze_compliance_gaps() == []


# ---------------------------------------------------------------------------
# report / clear / stats
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_log_source(source="s1", value_level=LogValueLevel.HIGH, retention_days=180)
        eng.record_log_source(source="s2", value_level=LogValueLevel.NEGLIGIBLE, retention_days=365)
        eng.add_policy(source_pattern="s*", recommended_tier=RetentionTier.COLD)
        report = eng.generate_report()
        assert isinstance(report, LogRetentionReport)
        assert report.total_sources == 2
        assert report.total_policies == 1
        assert report.avg_retention_days > 0
        assert len(report.by_tier) > 0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_sources == 0
        assert "Log retention policies are well-optimized" in report.recommendations


class TestClearDataLRO:
    def test_clears(self):
        eng = _engine()
        eng.record_log_source(source="s1")
        eng.add_policy(source_pattern="s*")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


class TestGetStatsLRO:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_sources"] == 0
        assert stats["total_policies"] == 0
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_log_source(source="s1")
        stats = eng.get_stats()
        assert stats["total_sources"] == 1
        assert stats["unique_sources"] == 1
