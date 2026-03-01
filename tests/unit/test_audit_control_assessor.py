"""Tests for shieldops.audit.audit_control_assessor — AuditControlAssessor."""

from __future__ import annotations

from shieldops.audit.audit_control_assessor import (
    AssessmentType,
    AuditControlAssessor,
    AuditControlReport,
    ControlAssessment,
    ControlDomain,
    ControlEffectiveness,
    ControlRecord,
)


def _engine(**kw) -> AuditControlAssessor:
    return AuditControlAssessor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_domain_access_control(self):
        assert ControlDomain.ACCESS_CONTROL == "access_control"

    def test_domain_data_protection(self):
        assert ControlDomain.DATA_PROTECTION == "data_protection"

    def test_domain_change_management(self):
        assert ControlDomain.CHANGE_MANAGEMENT == "change_management"

    def test_domain_monitoring(self):
        assert ControlDomain.MONITORING == "monitoring"

    def test_domain_incident_response(self):
        assert ControlDomain.INCIDENT_RESPONSE == "incident_response"

    def test_effectiveness_effective(self):
        assert ControlEffectiveness.EFFECTIVE == "effective"

    def test_effectiveness_partially_effective(self):
        assert ControlEffectiveness.PARTIALLY_EFFECTIVE == "partially_effective"

    def test_effectiveness_ineffective(self):
        assert ControlEffectiveness.INEFFECTIVE == "ineffective"

    def test_effectiveness_not_tested(self):
        assert ControlEffectiveness.NOT_TESTED == "not_tested"

    def test_effectiveness_not_applicable(self):
        assert ControlEffectiveness.NOT_APPLICABLE == "not_applicable"

    def test_assessment_automated(self):
        assert AssessmentType.AUTOMATED == "automated"

    def test_assessment_manual(self):
        assert AssessmentType.MANUAL == "manual"

    def test_assessment_hybrid(self):
        assert AssessmentType.HYBRID == "hybrid"

    def test_assessment_continuous(self):
        assert AssessmentType.CONTINUOUS == "continuous"

    def test_assessment_periodic(self):
        assert AssessmentType.PERIODIC == "periodic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_control_record_defaults(self):
        r = ControlRecord()
        assert r.id
        assert r.control_id == ""
        assert r.control_domain == ControlDomain.ACCESS_CONTROL
        assert r.control_effectiveness == ControlEffectiveness.NOT_TESTED
        assert r.assessment_type == AssessmentType.AUTOMATED
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_control_assessment_defaults(self):
        a = ControlAssessment()
        assert a.id
        assert a.control_id == ""
        assert a.control_domain == ControlDomain.ACCESS_CONTROL
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_audit_control_report_defaults(self):
        r = AuditControlReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.ineffective_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_domain == {}
        assert r.by_effectiveness == {}
        assert r.by_assessment_type == {}
        assert r.top_ineffective == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_control
# ---------------------------------------------------------------------------


class TestRecordControl:
    def test_basic(self):
        eng = _engine()
        r = eng.record_control(
            control_id="CTL-001",
            control_domain=ControlDomain.ACCESS_CONTROL,
            control_effectiveness=ControlEffectiveness.EFFECTIVE,
            assessment_type=AssessmentType.AUTOMATED,
            effectiveness_score=95.0,
            service="auth",
            team="security",
        )
        assert r.control_id == "CTL-001"
        assert r.control_domain == ControlDomain.ACCESS_CONTROL
        assert r.control_effectiveness == ControlEffectiveness.EFFECTIVE
        assert r.assessment_type == AssessmentType.AUTOMATED
        assert r.effectiveness_score == 95.0
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_control(control_id=f"CTL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_control
# ---------------------------------------------------------------------------


class TestGetControl:
    def test_found(self):
        eng = _engine()
        r = eng.record_control(
            control_id="CTL-001",
            control_effectiveness=ControlEffectiveness.EFFECTIVE,
        )
        result = eng.get_control(r.id)
        assert result is not None
        assert result.control_effectiveness == ControlEffectiveness.EFFECTIVE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_control("nonexistent") is None


# ---------------------------------------------------------------------------
# list_controls
# ---------------------------------------------------------------------------


class TestListControls:
    def test_list_all(self):
        eng = _engine()
        eng.record_control(control_id="CTL-001")
        eng.record_control(control_id="CTL-002")
        assert len(eng.list_controls()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_domain=ControlDomain.ACCESS_CONTROL,
        )
        eng.record_control(
            control_id="CTL-002",
            control_domain=ControlDomain.MONITORING,
        )
        results = eng.list_controls(domain=ControlDomain.ACCESS_CONTROL)
        assert len(results) == 1

    def test_filter_by_effectiveness(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_effectiveness=ControlEffectiveness.EFFECTIVE,
        )
        eng.record_control(
            control_id="CTL-002",
            control_effectiveness=ControlEffectiveness.INEFFECTIVE,
        )
        results = eng.list_controls(
            effectiveness=ControlEffectiveness.EFFECTIVE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_control(control_id="CTL-001", team="security")
        eng.record_control(control_id="CTL-002", team="platform")
        results = eng.list_controls(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_control(control_id=f"CTL-{i}")
        assert len(eng.list_controls(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            control_id="CTL-001",
            control_domain=ControlDomain.DATA_PROTECTION,
            assessment_score=80.0,
            threshold=75.0,
            breached=False,
            description="Meets threshold",
        )
        assert a.control_id == "CTL-001"
        assert a.control_domain == ControlDomain.DATA_PROTECTION
        assert a.assessment_score == 80.0
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(control_id=f"CTL-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_control_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeControlDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_domain=ControlDomain.ACCESS_CONTROL,
            effectiveness_score=90.0,
        )
        eng.record_control(
            control_id="CTL-002",
            control_domain=ControlDomain.ACCESS_CONTROL,
            effectiveness_score=80.0,
        )
        result = eng.analyze_control_distribution()
        assert "access_control" in result
        assert result["access_control"]["count"] == 2
        assert result["access_control"]["avg_effectiveness_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_control_distribution() == {}


# ---------------------------------------------------------------------------
# identify_ineffective_controls
# ---------------------------------------------------------------------------


class TestIdentifyIneffectiveControls:
    def test_detects_ineffective(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_effectiveness=ControlEffectiveness.INEFFECTIVE,
        )
        eng.record_control(
            control_id="CTL-002",
            control_effectiveness=ControlEffectiveness.EFFECTIVE,
        )
        results = eng.identify_ineffective_controls()
        assert len(results) == 1
        assert results[0]["control_id"] == "CTL-001"

    def test_detects_not_tested(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_effectiveness=ControlEffectiveness.NOT_TESTED,
        )
        results = eng.identify_ineffective_controls()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_ineffective_controls() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            service="auth",
            effectiveness_score=90.0,
        )
        eng.record_control(
            control_id="CTL-002",
            service="api-gw",
            effectiveness_score=40.0,
        )
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_control_trends
# ---------------------------------------------------------------------------


class TestDetectControlTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(control_id="CTL-001", assessment_score=50.0)
        result = eng.detect_control_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(control_id="CTL-001", assessment_score=30.0)
        eng.add_assessment(control_id="CTL-002", assessment_score=30.0)
        eng.add_assessment(control_id="CTL-003", assessment_score=50.0)
        eng.add_assessment(control_id="CTL-004", assessment_score=50.0)
        result = eng.detect_control_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_control_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_domain=ControlDomain.ACCESS_CONTROL,
            control_effectiveness=ControlEffectiveness.INEFFECTIVE,
            effectiveness_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditControlReport)
        assert report.total_records == 1
        assert report.ineffective_count == 1
        assert len(report.top_ineffective) == 1
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
        eng.record_control(control_id="CTL-001")
        eng.add_assessment(control_id="CTL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["control_domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_domain=ControlDomain.ACCESS_CONTROL,
            service="auth",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "access_control" in stats["control_domain_distribution"]
