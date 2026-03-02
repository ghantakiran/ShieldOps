"""Tests for shieldops.compliance.regulatory_impact_tracker — RegulatoryImpactTracker."""

from __future__ import annotations

from shieldops.compliance.regulatory_impact_tracker import (
    ChangeImpact,
    ComplianceReadiness,
    RegulationType,
    RegulatoryAnalysis,
    RegulatoryImpactReport,
    RegulatoryImpactTracker,
    RegulatoryRecord,
)


def _engine(**kw) -> RegulatoryImpactTracker:
    return RegulatoryImpactTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_data_privacy(self):
        assert RegulationType.DATA_PRIVACY == "data_privacy"

    def test_type_financial(self):
        assert RegulationType.FINANCIAL == "financial"

    def test_type_healthcare(self):
        assert RegulationType.HEALTHCARE == "healthcare"

    def test_type_cybersecurity(self):
        assert RegulationType.CYBERSECURITY == "cybersecurity"

    def test_type_environmental(self):
        assert RegulationType.ENVIRONMENTAL == "environmental"

    def test_impact_major(self):
        assert ChangeImpact.MAJOR == "major"

    def test_impact_significant(self):
        assert ChangeImpact.SIGNIFICANT == "significant"

    def test_impact_moderate(self):
        assert ChangeImpact.MODERATE == "moderate"

    def test_impact_minor(self):
        assert ChangeImpact.MINOR == "minor"

    def test_impact_no_impact(self):
        assert ChangeImpact.NO_IMPACT == "no_impact"

    def test_readiness_compliant(self):
        assert ComplianceReadiness.COMPLIANT == "compliant"

    def test_readiness_partially_compliant(self):
        assert ComplianceReadiness.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_readiness_in_progress(self):
        assert ComplianceReadiness.IN_PROGRESS == "in_progress"

    def test_readiness_gap_identified(self):
        assert ComplianceReadiness.GAP_IDENTIFIED == "gap_identified"

    def test_readiness_not_assessed(self):
        assert ComplianceReadiness.NOT_ASSESSED == "not_assessed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_regulatory_record_defaults(self):
        r = RegulatoryRecord()
        assert r.id
        assert r.regulation_name == ""
        assert r.regulation_type == RegulationType.DATA_PRIVACY
        assert r.change_impact == ChangeImpact.MAJOR
        assert r.compliance_readiness == ComplianceReadiness.COMPLIANT
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_regulatory_analysis_defaults(self):
        a = RegulatoryAnalysis()
        assert a.id
        assert a.regulation_name == ""
        assert a.regulation_type == RegulationType.DATA_PRIVACY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_regulatory_report_defaults(self):
        r = RegulatoryImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_type == {}
        assert r.by_impact == {}
        assert r.by_readiness == {}
        assert r.top_high_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_regulatory
# ---------------------------------------------------------------------------


class TestRecordRegulatory:
    def test_basic(self):
        eng = _engine()
        r = eng.record_regulatory(
            regulation_name="GDPR-2024",
            regulation_type=RegulationType.DATA_PRIVACY,
            change_impact=ChangeImpact.MAJOR,
            compliance_readiness=ComplianceReadiness.COMPLIANT,
            impact_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.regulation_name == "GDPR-2024"
        assert r.regulation_type == RegulationType.DATA_PRIVACY
        assert r.change_impact == ChangeImpact.MAJOR
        assert r.compliance_readiness == ComplianceReadiness.COMPLIANT
        assert r.impact_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_regulatory(regulation_name=f"REG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_regulatory
# ---------------------------------------------------------------------------


class TestGetRegulatory:
    def test_found(self):
        eng = _engine()
        r = eng.record_regulatory(
            regulation_name="GDPR-2024",
            regulation_type=RegulationType.FINANCIAL,
        )
        result = eng.get_regulatory(r.id)
        assert result is not None
        assert result.regulation_type == RegulationType.FINANCIAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_regulatory("nonexistent") is None


# ---------------------------------------------------------------------------
# list_regulatory_records
# ---------------------------------------------------------------------------


class TestListRegulatoryRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_regulatory(regulation_name="REG-001")
        eng.record_regulatory(regulation_name="REG-002")
        assert len(eng.list_regulatory_records()) == 2

    def test_filter_by_regulation_type(self):
        eng = _engine()
        eng.record_regulatory(
            regulation_name="REG-001",
            regulation_type=RegulationType.DATA_PRIVACY,
        )
        eng.record_regulatory(
            regulation_name="REG-002",
            regulation_type=RegulationType.FINANCIAL,
        )
        results = eng.list_regulatory_records(regulation_type=RegulationType.DATA_PRIVACY)
        assert len(results) == 1

    def test_filter_by_change_impact(self):
        eng = _engine()
        eng.record_regulatory(
            regulation_name="REG-001",
            change_impact=ChangeImpact.MAJOR,
        )
        eng.record_regulatory(
            regulation_name="REG-002",
            change_impact=ChangeImpact.MINOR,
        )
        results = eng.list_regulatory_records(change_impact=ChangeImpact.MAJOR)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_regulatory(regulation_name="REG-001", team="sre")
        eng.record_regulatory(regulation_name="REG-002", team="platform")
        results = eng.list_regulatory_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_regulatory(regulation_name=f"REG-{i}")
        assert len(eng.list_regulatory_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            regulation_name="GDPR-2024",
            regulation_type=RegulationType.CYBERSECURITY,
            analysis_score=72.0,
            threshold=70.0,
            breached=True,
            description="Impact above severity threshold",
        )
        assert a.regulation_name == "GDPR-2024"
        assert a.regulation_type == RegulationType.CYBERSECURITY
        assert a.analysis_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(regulation_name=f"REG-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_regulatory_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRegulatoryDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_regulatory(
            regulation_name="REG-001",
            regulation_type=RegulationType.DATA_PRIVACY,
            impact_score=80.0,
        )
        eng.record_regulatory(
            regulation_name="REG-002",
            regulation_type=RegulationType.DATA_PRIVACY,
            impact_score=90.0,
        )
        result = eng.analyze_regulatory_distribution()
        assert "data_privacy" in result
        assert result["data_privacy"]["count"] == 2
        assert result["data_privacy"]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_regulatory_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_regulations
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactRegulations:
    def test_detects_high(self):
        eng = _engine(impact_severity_threshold=60.0)
        eng.record_regulatory(
            regulation_name="REG-001",
            impact_score=80.0,
        )
        eng.record_regulatory(
            regulation_name="REG-002",
            impact_score=30.0,
        )
        results = eng.identify_high_impact_regulations()
        assert len(results) == 1
        assert results[0]["regulation_name"] == "REG-001"

    def test_sorted_descending(self):
        eng = _engine(impact_severity_threshold=60.0)
        eng.record_regulatory(regulation_name="REG-001", impact_score=70.0)
        eng.record_regulatory(regulation_name="REG-002", impact_score=90.0)
        results = eng.identify_high_impact_regulations()
        assert len(results) == 2
        assert results[0]["impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_regulations() == []


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankByImpact:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_regulatory(regulation_name="REG-001", impact_score=50.0, service="svc-a")
        eng.record_regulatory(regulation_name="REG-002", impact_score=90.0, service="svc-b")
        results = eng.rank_by_impact()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_regulatory_trends
# ---------------------------------------------------------------------------


class TestDetectRegulatoryTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(regulation_name="REG-001", analysis_score=70.0)
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(regulation_name="REG-001", analysis_score=50.0)
        eng.add_analysis(regulation_name="REG-002", analysis_score=50.0)
        eng.add_analysis(regulation_name="REG-003", analysis_score=80.0)
        eng.add_analysis(regulation_name="REG-004", analysis_score=80.0)
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(impact_severity_threshold=60.0)
        eng.record_regulatory(
            regulation_name="GDPR-2024",
            regulation_type=RegulationType.DATA_PRIVACY,
            change_impact=ChangeImpact.MAJOR,
            impact_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RegulatoryImpactReport)
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
        eng.record_regulatory(regulation_name="REG-001")
        eng.add_analysis(regulation_name="REG-001")
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
        assert stats["regulation_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_regulatory(
            regulation_name="GDPR-2024",
            regulation_type=RegulationType.DATA_PRIVACY,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "data_privacy" in stats["regulation_type_distribution"]
