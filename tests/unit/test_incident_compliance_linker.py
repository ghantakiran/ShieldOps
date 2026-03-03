"""Tests for shieldops.compliance.incident_compliance_linker — IncidentComplianceLinker."""

from __future__ import annotations

from shieldops.compliance.incident_compliance_linker import (
    ComplianceImpact,
    IncidentCategory,
    IncidentComplianceLinker,
    IncidentComplianceReport,
    LinkAnalysis,
    LinkRecord,
    NotificationRequirement,
)


def _engine(**kw) -> IncidentComplianceLinker:
    return IncidentComplianceLinker(**kw)


class TestEnums:
    def test_category_data_breach(self):
        assert IncidentCategory.DATA_BREACH == "data_breach"

    def test_category_unauthorized_access(self):
        assert IncidentCategory.UNAUTHORIZED_ACCESS == "unauthorized_access"

    def test_category_service_disruption(self):
        assert IncidentCategory.SERVICE_DISRUPTION == "service_disruption"

    def test_category_policy_violation(self):
        assert IncidentCategory.POLICY_VIOLATION == "policy_violation"

    def test_category_regulatory_failure(self):
        assert IncidentCategory.REGULATORY_FAILURE == "regulatory_failure"

    def test_impact_critical(self):
        assert ComplianceImpact.CRITICAL == "critical"

    def test_impact_major(self):
        assert ComplianceImpact.MAJOR == "major"

    def test_impact_moderate(self):
        assert ComplianceImpact.MODERATE == "moderate"

    def test_impact_minor(self):
        assert ComplianceImpact.MINOR == "minor"

    def test_impact_none(self):
        assert ComplianceImpact.NONE == "none"

    def test_notification_mandatory(self):
        assert NotificationRequirement.MANDATORY == "mandatory"

    def test_notification_conditional(self):
        assert NotificationRequirement.CONDITIONAL == "conditional"

    def test_notification_recommended(self):
        assert NotificationRequirement.RECOMMENDED == "recommended"

    def test_notification_none_required(self):
        assert NotificationRequirement.NONE_REQUIRED == "none_required"

    def test_notification_tbd(self):
        assert NotificationRequirement.TBD == "tbd"


class TestModels:
    def test_record_defaults(self):
        r = LinkRecord()
        assert r.id
        assert r.incident_name == ""
        assert r.incident_category == IncidentCategory.DATA_BREACH
        assert r.compliance_impact == ComplianceImpact.CRITICAL
        assert r.notification_requirement == NotificationRequirement.MANDATORY
        assert r.link_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = LinkAnalysis()
        assert a.id
        assert a.incident_name == ""
        assert a.incident_category == IncidentCategory.DATA_BREACH
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = IncidentComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_link_score == 0.0
        assert r.by_category == {}
        assert r.by_impact == {}
        assert r.by_notification == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_link(
            incident_name="data-breach-2024-q1",
            incident_category=IncidentCategory.DATA_BREACH,
            compliance_impact=ComplianceImpact.CRITICAL,
            notification_requirement=NotificationRequirement.MANDATORY,
            link_score=85.0,
            service="incident-svc",
            team="security",
        )
        assert r.incident_name == "data-breach-2024-q1"
        assert r.incident_category == IncidentCategory.DATA_BREACH
        assert r.link_score == 85.0
        assert r.service == "incident-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_link(incident_name=f"inc-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_link(incident_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_link(incident_name="a")
        eng.record_link(incident_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_incident_category(self):
        eng = _engine()
        eng.record_link(incident_name="a", incident_category=IncidentCategory.DATA_BREACH)
        eng.record_link(incident_name="b", incident_category=IncidentCategory.SERVICE_DISRUPTION)
        assert len(eng.list_records(incident_category=IncidentCategory.DATA_BREACH)) == 1

    def test_filter_by_compliance_impact(self):
        eng = _engine()
        eng.record_link(incident_name="a", compliance_impact=ComplianceImpact.CRITICAL)
        eng.record_link(incident_name="b", compliance_impact=ComplianceImpact.MINOR)
        assert len(eng.list_records(compliance_impact=ComplianceImpact.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_link(incident_name="a", team="sec")
        eng.record_link(incident_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_link(incident_name=f"l-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            incident_name="test",
            analysis_score=88.5,
            breached=True,
            description="compliance link gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(incident_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_link(
            incident_name="a",
            incident_category=IncidentCategory.DATA_BREACH,
            link_score=90.0,
        )
        eng.record_link(
            incident_name="b",
            incident_category=IncidentCategory.DATA_BREACH,
            link_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "data_breach" in result
        assert result["data_breach"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_link(incident_name="a", link_score=60.0)
        eng.record_link(incident_name="b", link_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_link(incident_name="a", link_score=50.0)
        eng.record_link(incident_name="b", link_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["link_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_link(incident_name="a", service="auth", link_score=90.0)
        eng.record_link(incident_name="b", service="api", link_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(incident_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(incident_name="a", analysis_score=20.0)
        eng.add_analysis(incident_name="b", analysis_score=20.0)
        eng.add_analysis(incident_name="c", analysis_score=80.0)
        eng.add_analysis(incident_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_link(incident_name="test", link_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_link(incident_name="test")
        eng.add_analysis(incident_name="test")
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
        eng.record_link(incident_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
