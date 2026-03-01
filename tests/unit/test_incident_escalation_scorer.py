"""Tests for shieldops.incidents.incident_escalation_scorer — IncidentEscalationScorer."""

from __future__ import annotations

from shieldops.incidents.incident_escalation_scorer import (
    EscalationAssessment,
    EscalationQuality,
    EscalationScoreRecord,
    EscalationTarget,
    EscalationTrigger,
    IncidentEscalationReport,
    IncidentEscalationScorer,
)


def _engine(**kw) -> IncidentEscalationScorer:
    return IncidentEscalationScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_quality_excellent(self):
        assert EscalationQuality.EXCELLENT == "excellent"

    def test_quality_appropriate(self):
        assert EscalationQuality.APPROPRIATE == "appropriate"

    def test_quality_premature(self):
        assert EscalationQuality.PREMATURE == "premature"

    def test_quality_late(self):
        assert EscalationQuality.LATE == "late"

    def test_quality_unnecessary(self):
        assert EscalationQuality.UNNECESSARY == "unnecessary"

    def test_target_tier2(self):
        assert EscalationTarget.TIER2 == "tier2"

    def test_target_tier3(self):
        assert EscalationTarget.TIER3 == "tier3"

    def test_target_management(self):
        assert EscalationTarget.MANAGEMENT == "management"

    def test_target_vendor(self):
        assert EscalationTarget.VENDOR == "vendor"

    def test_target_executive(self):
        assert EscalationTarget.EXECUTIVE == "executive"

    def test_trigger_severity_threshold(self):
        assert EscalationTrigger.SEVERITY_THRESHOLD == "severity_threshold"

    def test_trigger_time_breach(self):
        assert EscalationTrigger.TIME_BREACH == "time_breach"

    def test_trigger_customer_impact(self):
        assert EscalationTrigger.CUSTOMER_IMPACT == "customer_impact"

    def test_trigger_manual(self):
        assert EscalationTrigger.MANUAL == "manual"

    def test_trigger_automated(self):
        assert EscalationTrigger.AUTOMATED == "automated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_escalation_score_record_defaults(self):
        r = EscalationScoreRecord()
        assert r.id
        assert r.escalation_id == ""
        assert r.escalation_quality == EscalationQuality.APPROPRIATE
        assert r.escalation_target == EscalationTarget.TIER2
        assert r.escalation_trigger == EscalationTrigger.MANUAL
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_escalation_assessment_defaults(self):
        a = EscalationAssessment()
        assert a.id
        assert a.escalation_id == ""
        assert a.escalation_quality == EscalationQuality.APPROPRIATE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_incident_escalation_report_defaults(self):
        r = IncidentEscalationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.poor_escalations == 0
        assert r.avg_quality_score == 0.0
        assert r.by_quality == {}
        assert r.by_target == {}
        assert r.by_trigger == {}
        assert r.top_poor == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_escalation
# ---------------------------------------------------------------------------


class TestRecordEscalation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
            escalation_target=EscalationTarget.TIER3,
            escalation_trigger=EscalationTrigger.SEVERITY_THRESHOLD,
            quality_score=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.escalation_id == "ESC-001"
        assert r.escalation_quality == EscalationQuality.PREMATURE
        assert r.escalation_target == EscalationTarget.TIER3
        assert r.escalation_trigger == EscalationTrigger.SEVERITY_THRESHOLD
        assert r.quality_score == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escalation(escalation_id=f"ESC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_escalation
# ---------------------------------------------------------------------------


class TestGetEscalation:
    def test_found(self):
        eng = _engine()
        r = eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.EXCELLENT,
        )
        result = eng.get_escalation(r.id)
        assert result is not None
        assert result.escalation_quality == EscalationQuality.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_escalation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_escalations
# ---------------------------------------------------------------------------


class TestListEscalations:
    def test_list_all(self):
        eng = _engine()
        eng.record_escalation(escalation_id="ESC-001")
        eng.record_escalation(escalation_id="ESC-002")
        assert len(eng.list_escalations()) == 2

    def test_filter_by_quality(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
        )
        eng.record_escalation(
            escalation_id="ESC-002",
            escalation_quality=EscalationQuality.EXCELLENT,
        )
        results = eng.list_escalations(
            escalation_quality=EscalationQuality.PREMATURE,
        )
        assert len(results) == 1

    def test_filter_by_target(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_target=EscalationTarget.TIER3,
        )
        eng.record_escalation(
            escalation_id="ESC-002",
            escalation_target=EscalationTarget.MANAGEMENT,
        )
        results = eng.list_escalations(
            escalation_target=EscalationTarget.TIER3,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_escalation(escalation_id="ESC-001", team="sre")
        eng.record_escalation(escalation_id="ESC-002", team="platform")
        results = eng.list_escalations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_escalation(escalation_id=f"ESC-{i}")
        assert len(eng.list_escalations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.LATE,
            assessment_score=35.0,
            threshold=70.0,
            breached=True,
            description="Late escalation detected",
        )
        assert a.escalation_id == "ESC-001"
        assert a.escalation_quality == EscalationQuality.LATE
        assert a.assessment_score == 35.0
        assert a.threshold == 70.0
        assert a.breached is True
        assert a.description == "Late escalation detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(escalation_id=f"ESC-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_escalation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeEscalationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
            quality_score=40.0,
        )
        eng.record_escalation(
            escalation_id="ESC-002",
            escalation_quality=EscalationQuality.PREMATURE,
            quality_score=50.0,
        )
        result = eng.analyze_escalation_distribution()
        assert "premature" in result
        assert result["premature"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_escalation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_poor_escalations
# ---------------------------------------------------------------------------


class TestIdentifyPoorEscalations:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
        )
        eng.record_escalation(
            escalation_id="ESC-002",
            escalation_quality=EscalationQuality.EXCELLENT,
        )
        results = eng.identify_poor_escalations()
        assert len(results) == 1
        assert results[0]["escalation_id"] == "ESC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_escalations() == []


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankByQuality:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            service="api-gateway",
            quality_score=90.0,
        )
        eng.record_escalation(
            escalation_id="ESC-002",
            service="payments",
            quality_score=30.0,
        )
        results = eng.rank_by_quality()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_quality_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality() == []


# ---------------------------------------------------------------------------
# detect_escalation_trends
# ---------------------------------------------------------------------------


class TestDetectEscalationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(
                escalation_id="ESC-001",
                assessment_score=50.0,
            )
        result = eng.detect_escalation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(escalation_id="ESC-001", assessment_score=30.0)
        eng.add_assessment(escalation_id="ESC-002", assessment_score=30.0)
        eng.add_assessment(escalation_id="ESC-003", assessment_score=80.0)
        eng.add_assessment(escalation_id="ESC-004", assessment_score=80.0)
        result = eng.detect_escalation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_escalation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
            escalation_target=EscalationTarget.TIER3,
            escalation_trigger=EscalationTrigger.SEVERITY_THRESHOLD,
            quality_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentEscalationReport)
        assert report.total_records == 1
        assert report.poor_escalations == 1
        assert len(report.top_poor) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_escalation(escalation_id="ESC-001")
        eng.add_assessment(escalation_id="ESC-001")
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
        assert stats["quality_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="ESC-001",
            escalation_quality=EscalationQuality.PREMATURE,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "premature" in stats["quality_distribution"]
