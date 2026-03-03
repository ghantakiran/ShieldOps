"""Tests for shieldops.compliance.privacy_impact_generator — PrivacyImpactGenerator."""

from __future__ import annotations

from shieldops.compliance.privacy_impact_generator import (
    ImpactAnalysis,
    ImpactLevel,
    ImpactRecord,
    PrivacyImpactGenerator,
    PrivacyImpactReport,
    ProcessingActivity,
    RiskMitigation,
)


def _engine(**kw) -> PrivacyImpactGenerator:
    return PrivacyImpactGenerator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_impact_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    def test_impact_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_impact_medium(self):
        assert ImpactLevel.MEDIUM == "medium"

    def test_impact_low(self):
        assert ImpactLevel.LOW == "low"

    def test_impact_negligible(self):
        assert ImpactLevel.NEGLIGIBLE == "negligible"

    def test_activity_collection(self):
        assert ProcessingActivity.COLLECTION == "collection"

    def test_activity_storage(self):
        assert ProcessingActivity.STORAGE == "storage"

    def test_activity_analysis(self):
        assert ProcessingActivity.ANALYSIS == "analysis"

    def test_activity_sharing(self):
        assert ProcessingActivity.SHARING == "sharing"

    def test_activity_deletion(self):
        assert ProcessingActivity.DELETION == "deletion"

    def test_mitigation_encryption(self):
        assert RiskMitigation.ENCRYPTION == "encryption"

    def test_mitigation_anonymization(self):
        assert RiskMitigation.ANONYMIZATION == "anonymization"

    def test_mitigation_access_control(self):
        assert RiskMitigation.ACCESS_CONTROL == "access_control"

    def test_mitigation_minimization(self):
        assert RiskMitigation.MINIMIZATION == "minimization"

    def test_mitigation_consent(self):
        assert RiskMitigation.CONSENT == "consent"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_impact_record_defaults(self):
        r = ImpactRecord()
        assert r.id
        assert r.processing_id == ""
        assert r.impact_level == ImpactLevel.MEDIUM
        assert r.processing_activity == ProcessingActivity.COLLECTION
        assert r.risk_mitigation == RiskMitigation.ENCRYPTION
        assert r.risk_score == 0.0
        assert r.business_unit == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_impact_analysis_defaults(self):
        a = ImpactAnalysis()
        assert a.id
        assert a.processing_id == ""
        assert a.impact_level == ImpactLevel.MEDIUM
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PrivacyImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_impact_level == {}
        assert r.by_activity == {}
        assert r.by_mitigation == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_impact / get_impact
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            processing_id="proc-001",
            impact_level=ImpactLevel.HIGH,
            processing_activity=ProcessingActivity.SHARING,
            risk_mitigation=RiskMitigation.ANONYMIZATION,
            risk_score=85.0,
            business_unit="marketing",
            data_owner="dpo-team",
        )
        assert r.processing_id == "proc-001"
        assert r.impact_level == ImpactLevel.HIGH
        assert r.risk_score == 85.0
        assert r.business_unit == "marketing"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_impact(processing_id="proc-001", impact_level=ImpactLevel.CRITICAL)
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.impact_level == ImpactLevel.CRITICAL

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(processing_id=f"proc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001")
        eng.record_impact(processing_id="p-002")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_impact_level(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001", impact_level=ImpactLevel.HIGH)
        eng.record_impact(processing_id="p-002", impact_level=ImpactLevel.LOW)
        results = eng.list_impacts(impact_level=ImpactLevel.HIGH)
        assert len(results) == 1

    def test_filter_by_activity(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001", processing_activity=ProcessingActivity.SHARING)
        eng.record_impact(processing_id="p-002", processing_activity=ProcessingActivity.STORAGE)
        results = eng.list_impacts(processing_activity=ProcessingActivity.SHARING)
        assert len(results) == 1

    def test_filter_by_unit(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001", business_unit="marketing")
        eng.record_impact(processing_id="p-002", business_unit="engineering")
        results = eng.list_impacts(business_unit="marketing")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(processing_id=f"p-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            processing_id="proc-001",
            impact_level=ImpactLevel.CRITICAL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high risk processing",
        )
        assert a.processing_id == "proc-001"
        assert a.impact_level == ImpactLevel.CRITICAL
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(processing_id=f"p-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(processing_id="proc-999", impact_level=ImpactLevel.NEGLIGIBLE)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_impact_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001", impact_level=ImpactLevel.HIGH, risk_score=90.0)
        eng.record_impact(processing_id="p-002", impact_level=ImpactLevel.HIGH, risk_score=70.0)
        result = eng.analyze_impact_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_impact_distribution() == {}


# ---------------------------------------------------------------------------
# identify_impact_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_impact(processing_id="p-001", risk_score=60.0)
        eng.record_impact(processing_id="p-002", risk_score=90.0)
        results = eng.identify_impact_gaps()
        assert len(results) == 1
        assert results[0]["processing_id"] == "p-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_impact(processing_id="p-001", risk_score=50.0)
        eng.record_impact(processing_id="p-002", risk_score=30.0)
        results = eng.identify_impact_gaps()
        assert results[0]["risk_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_impact(processing_id="p-001", business_unit="marketing", risk_score=90.0)
        eng.record_impact(processing_id="p-002", business_unit="engineering", risk_score=50.0)
        results = eng.rank_by_risk()
        assert results[0]["business_unit"] == "engineering"
        assert results[0]["avg_risk_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(processing_id="p-001", analysis_score=50.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(processing_id="p-001", analysis_score=20.0)
        eng.add_analysis(processing_id="p-002", analysis_score=20.0)
        eng.add_analysis(processing_id="p-003", analysis_score=80.0)
        eng.add_analysis(processing_id="p-004", analysis_score=80.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_impact(
            processing_id="proc-001",
            impact_level=ImpactLevel.CRITICAL,
            processing_activity=ProcessingActivity.SHARING,
            risk_mitigation=RiskMitigation.CONSENT,
            risk_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PrivacyImpactReport)
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
        eng.record_impact(processing_id="p-001")
        eng.add_analysis(processing_id="p-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["impact_level_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(processing_id=f"p-{i}")
        assert len(eng._analyses) == 3
