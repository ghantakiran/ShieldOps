"""Tests for shieldops.security.privilege_escalation_detector — PrivilegeEscalationDetector."""

from __future__ import annotations

from shieldops.security.privilege_escalation_detector import (
    DetectionSource,
    EscalationAnalysis,
    EscalationRecord,
    EscalationType,
    PrivilegeEscalationDetector,
    PrivilegeEscalationReport,
    SeverityLevel,
)


def _engine(**kw) -> PrivilegeEscalationDetector:
    return PrivilegeEscalationDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert EscalationType.VERTICAL == "vertical"

    def test_e1_v2(self):
        assert EscalationType.HORIZONTAL == "horizontal"

    def test_e1_v3(self):
        assert EscalationType.LATERAL == "lateral"

    def test_e1_v4(self):
        assert EscalationType.PRIVILEGE_ABUSE == "privilege_abuse"

    def test_e1_v5(self):
        assert EscalationType.TOKEN_MANIPULATION == "token_manipulation"  # noqa: S105

    def test_e2_v1(self):
        assert DetectionSource.AUDIT_LOG == "audit_log"

    def test_e2_v2(self):
        assert DetectionSource.BEHAVIORAL == "behavioral"

    def test_e2_v3(self):
        assert DetectionSource.RULE_BASED == "rule_based"

    def test_e2_v4(self):
        assert DetectionSource.ML_BASED == "ml_based"

    def test_e2_v5(self):
        assert DetectionSource.HONEYPOT == "honeypot"

    def test_e3_v1(self):
        assert SeverityLevel.CRITICAL == "critical"

    def test_e3_v2(self):
        assert SeverityLevel.HIGH == "high"

    def test_e3_v3(self):
        assert SeverityLevel.MEDIUM == "medium"

    def test_e3_v4(self):
        assert SeverityLevel.LOW == "low"

    def test_e3_v5(self):
        assert SeverityLevel.INFORMATIONAL == "informational"


class TestModels:
    def test_rec(self):
        r = EscalationRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = EscalationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = PrivilegeEscalationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_escalation(
            escalation_id="t",
            escalation_type=EscalationType.HORIZONTAL,
            detection_source=DetectionSource.BEHAVIORAL,
            severity_level=SeverityLevel.HIGH,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.escalation_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escalation(escalation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_escalation(escalation_id="t")
        assert eng.get_escalation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_escalation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a")
        eng.record_escalation(escalation_id="b")
        assert len(eng.list_escalations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a", escalation_type=EscalationType.VERTICAL)
        eng.record_escalation(escalation_id="b", escalation_type=EscalationType.HORIZONTAL)
        assert len(eng.list_escalations(escalation_type=EscalationType.VERTICAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a", detection_source=DetectionSource.AUDIT_LOG)
        eng.record_escalation(escalation_id="b", detection_source=DetectionSource.BEHAVIORAL)
        assert len(eng.list_escalations(detection_source=DetectionSource.AUDIT_LOG)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a", team="x")
        eng.record_escalation(escalation_id="b", team="y")
        assert len(eng.list_escalations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_escalation(escalation_id=f"t-{i}")
        assert len(eng.list_escalations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            escalation_id="t",
            escalation_type=EscalationType.HORIZONTAL,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(escalation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_escalation(
            escalation_id="a", escalation_type=EscalationType.VERTICAL, detection_score=90.0
        )
        eng.record_escalation(
            escalation_id="b", escalation_type=EscalationType.VERTICAL, detection_score=70.0
        )
        assert "vertical" in eng.analyze_escalation_distribution()

    def test_empty(self):
        assert _engine().analyze_escalation_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_gap_threshold=80.0)
        eng.record_escalation(escalation_id="a", detection_score=60.0)
        eng.record_escalation(escalation_id="b", detection_score=90.0)
        assert len(eng.identify_escalation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_gap_threshold=80.0)
        eng.record_escalation(escalation_id="a", detection_score=50.0)
        eng.record_escalation(escalation_id="b", detection_score=30.0)
        assert len(eng.identify_escalation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a", service="s1", detection_score=80.0)
        eng.record_escalation(escalation_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_escalation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_escalation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(escalation_id="t", analysis_score=float(v))
        assert eng.detect_escalation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(escalation_id="t", analysis_score=float(v))
        assert eng.detect_escalation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_escalation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_escalation(escalation_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_escalation(escalation_id="t")
        eng.add_analysis(escalation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_escalation(escalation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_escalation(escalation_id="a")
        eng.record_escalation(escalation_id="b")
        eng.add_analysis(escalation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
