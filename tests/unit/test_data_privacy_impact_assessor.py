"""Tests for shieldops.compliance.data_privacy_impact_assessor — DataPrivacyImpactAssessor."""

from __future__ import annotations

from shieldops.compliance.data_privacy_impact_assessor import (
    DataPrivacyImpactAssessor,
    MitigationStatus,
    PrivacyAnalysis,
    PrivacyRecord,
    PrivacyReport,
    PrivacyRisk,
    ProcessingType,
)


def _engine(**kw) -> DataPrivacyImpactAssessor:
    return DataPrivacyImpactAssessor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_processingtype_large_scale_profiling(self):
        assert ProcessingType.LARGE_SCALE_PROFILING == "large_scale_profiling"

    def test_processingtype_automated_decision(self):
        assert ProcessingType.AUTOMATED_DECISION == "automated_decision"

    def test_processingtype_sensitive_data(self):
        assert ProcessingType.SENSITIVE_DATA == "sensitive_data"

    def test_processingtype_public_monitoring(self):
        assert ProcessingType.PUBLIC_MONITORING == "public_monitoring"

    def test_processingtype_cross_border(self):
        assert ProcessingType.CROSS_BORDER == "cross_border"

    def test_privacyrisk_very_high(self):
        assert PrivacyRisk.VERY_HIGH == "very_high"

    def test_privacyrisk_high(self):
        assert PrivacyRisk.HIGH == "high"

    def test_privacyrisk_medium(self):
        assert PrivacyRisk.MEDIUM == "medium"

    def test_privacyrisk_low(self):
        assert PrivacyRisk.LOW == "low"

    def test_privacyrisk_negligible(self):
        assert PrivacyRisk.NEGLIGIBLE == "negligible"

    def test_mitigationstatus_mitigated(self):
        assert MitigationStatus.MITIGATED == "mitigated"

    def test_mitigationstatus_partially_mitigated(self):
        assert MitigationStatus.PARTIALLY_MITIGATED == "partially_mitigated"

    def test_mitigationstatus_planned(self):
        assert MitigationStatus.PLANNED == "planned"

    def test_mitigationstatus_unmitigated(self):
        assert MitigationStatus.UNMITIGATED == "unmitigated"

    def test_mitigationstatus_not_applicable(self):
        assert MitigationStatus.NOT_APPLICABLE == "not_applicable"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_privacyrecord_defaults(self):
        r = PrivacyRecord()
        assert r.id
        assert r.assessment_name == ""
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_privacyanalysis_defaults(self):
        c = PrivacyAnalysis()
        assert c.id
        assert c.assessment_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_privacyreport_defaults(self):
        r = PrivacyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0
        assert r.by_processing == {}
        assert r.by_risk == {}
        assert r.by_mitigation == {}
        assert r.top_high_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_assessment
# ---------------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment(
            assessment_name="test-item",
            processing_type=ProcessingType.AUTOMATED_DECISION,
            impact_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.assessment_name == "test-item"
        assert r.impact_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(assessment_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment(assessment_name="test-item")
        result = eng.get_assessment(r.id)
        assert result is not None
        assert result.assessment_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.record_assessment(assessment_name="ITEM-001")
        eng.record_assessment(assessment_name="ITEM-002")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_processing_type(self):
        eng = _engine()
        eng.record_assessment(
            assessment_name="ITEM-001", processing_type=ProcessingType.LARGE_SCALE_PROFILING
        )
        eng.record_assessment(
            assessment_name="ITEM-002", processing_type=ProcessingType.AUTOMATED_DECISION
        )
        results = eng.list_assessments(processing_type=ProcessingType.LARGE_SCALE_PROFILING)
        assert len(results) == 1

    def test_filter_by_privacy_risk(self):
        eng = _engine()
        eng.record_assessment(assessment_name="ITEM-001", privacy_risk=PrivacyRisk.VERY_HIGH)
        eng.record_assessment(assessment_name="ITEM-002", privacy_risk=PrivacyRisk.HIGH)
        results = eng.list_assessments(privacy_risk=PrivacyRisk.VERY_HIGH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_assessment(assessment_name="ITEM-001", team="security")
        eng.record_assessment(assessment_name="ITEM-002", team="platform")
        results = eng.list_assessments(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_assessment(assessment_name=f"ITEM-{i}")
        assert len(eng.list_assessments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            assessment_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.assessment_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(assessment_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_assessment_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            assessment_name="ITEM-001",
            processing_type=ProcessingType.LARGE_SCALE_PROFILING,
            impact_score=90.0,
        )
        eng.record_assessment(
            assessment_name="ITEM-002",
            processing_type=ProcessingType.LARGE_SCALE_PROFILING,
            impact_score=70.0,
        )
        result = eng.analyze_assessment_distribution()
        assert "large_scale_profiling" in result
        assert result["large_scale_profiling"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_assessment_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_assessments
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(privacy_impact_threshold=60.0)
        eng.record_assessment(assessment_name="ITEM-001", impact_score=90.0)
        eng.record_assessment(assessment_name="ITEM-002", impact_score=40.0)
        results = eng.identify_high_impact_assessments()
        assert len(results) == 1
        assert results[0]["assessment_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(privacy_impact_threshold=60.0)
        eng.record_assessment(assessment_name="ITEM-001", impact_score=80.0)
        eng.record_assessment(assessment_name="ITEM-002", impact_score=95.0)
        results = eng.identify_high_impact_assessments()
        assert len(results) == 2
        assert results[0]["impact_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_assessments() == []


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_assessment(assessment_name="ITEM-001", service="auth-svc", impact_score=90.0)
        eng.record_assessment(assessment_name="ITEM-002", service="api-gw", impact_score=50.0)
        results = eng.rank_by_impact()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_assessment_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(assessment_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_assessment_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(assessment_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(assessment_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(assessment_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(assessment_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_assessment_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_assessment_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(privacy_impact_threshold=60.0)
        eng.record_assessment(assessment_name="test-item", impact_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, PrivacyReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert len(report.top_high_impact) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_assessment(assessment_name="ITEM-001")
        eng.add_analysis(assessment_name="ITEM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_assessment(
            assessment_name="ITEM-001",
            processing_type=ProcessingType.LARGE_SCALE_PROFILING,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
