"""Tests for shieldops.audit.security_audit_trail_analyzer — SecurityAuditTrailAnalyzer."""

from __future__ import annotations

from shieldops.audit.security_audit_trail_analyzer import (
    AnalysisMethod,
    AuditEventType,
    AuditTrailAnalysis,
    AuditTrailRecord,
    FindingSeverity,
    SecurityAuditTrailAnalyzer,
    SecurityAuditTrailReport,
)


def _engine(**kw) -> SecurityAuditTrailAnalyzer:
    return SecurityAuditTrailAnalyzer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert AuditEventType.ACCESS == "access"

    def test_e1_v2(self):
        assert AuditEventType.CHANGE == "change"

    def test_e1_v3(self):
        assert AuditEventType.POLICY == "policy"

    def test_e1_v4(self):
        assert AuditEventType.INCIDENT == "incident"

    def test_e1_v5(self):
        assert AuditEventType.COMPLIANCE == "compliance"

    def test_e2_v1(self):
        assert AnalysisMethod.PATTERN_MATCHING == "pattern_matching"

    def test_e2_v2(self):
        assert AnalysisMethod.ANOMALY_DETECTION == "anomaly_detection"

    def test_e2_v3(self):
        assert AnalysisMethod.CORRELATION == "correlation"

    def test_e2_v4(self):
        assert AnalysisMethod.TIMELINE == "timeline"

    def test_e2_v5(self):
        assert AnalysisMethod.STATISTICAL == "statistical"

    def test_e3_v1(self):
        assert FindingSeverity.CRITICAL == "critical"

    def test_e3_v2(self):
        assert FindingSeverity.HIGH == "high"

    def test_e3_v3(self):
        assert FindingSeverity.MEDIUM == "medium"

    def test_e3_v4(self):
        assert FindingSeverity.LOW == "low"

    def test_e3_v5(self):
        assert FindingSeverity.INFORMATIONAL == "informational"


class TestModels:
    def test_rec(self):
        r = AuditTrailRecord()
        assert r.id and r.analysis_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AuditTrailAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SecurityAuditTrailReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_trail(
            trail_id="t",
            audit_event_type=AuditEventType.CHANGE,
            analysis_method=AnalysisMethod.ANOMALY_DETECTION,
            finding_severity=FindingSeverity.HIGH,
            analysis_score=92.0,
            service="s",
            team="t",
        )
        assert r.trail_id == "t" and r.analysis_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trail(trail_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_trail(trail_id="t")
        assert eng.get_trail(r.id) is not None

    def test_not_found(self):
        assert _engine().get_trail("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_trail(trail_id="a")
        eng.record_trail(trail_id="b")
        assert len(eng.list_trails()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_trail(trail_id="a", audit_event_type=AuditEventType.ACCESS)
        eng.record_trail(trail_id="b", audit_event_type=AuditEventType.CHANGE)
        assert len(eng.list_trails(audit_event_type=AuditEventType.ACCESS)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_trail(trail_id="a", analysis_method=AnalysisMethod.PATTERN_MATCHING)
        eng.record_trail(trail_id="b", analysis_method=AnalysisMethod.ANOMALY_DETECTION)
        assert len(eng.list_trails(analysis_method=AnalysisMethod.PATTERN_MATCHING)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_trail(trail_id="a", team="x")
        eng.record_trail(trail_id="b", team="y")
        assert len(eng.list_trails(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_trail(trail_id=f"t-{i}")
        assert len(eng.list_trails(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            trail_id="t", audit_event_type=AuditEventType.CHANGE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(trail_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_trail(trail_id="a", audit_event_type=AuditEventType.ACCESS, analysis_score=90.0)
        eng.record_trail(trail_id="b", audit_event_type=AuditEventType.ACCESS, analysis_score=70.0)
        assert "access" in eng.analyze_trail_distribution()

    def test_empty(self):
        assert _engine().analyze_trail_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(analysis_gap_threshold=80.0)
        eng.record_trail(trail_id="a", analysis_score=60.0)
        eng.record_trail(trail_id="b", analysis_score=90.0)
        assert len(eng.identify_trail_gaps()) == 1

    def test_sorted(self):
        eng = _engine(analysis_gap_threshold=80.0)
        eng.record_trail(trail_id="a", analysis_score=50.0)
        eng.record_trail(trail_id="b", analysis_score=30.0)
        assert len(eng.identify_trail_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_trail(trail_id="a", service="s1", analysis_score=80.0)
        eng.record_trail(trail_id="b", service="s2", analysis_score=60.0)
        assert eng.rank_by_trail()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_trail() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(trail_id="t", analysis_score=float(v))
        assert eng.detect_trail_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(trail_id="t", analysis_score=float(v))
        assert eng.detect_trail_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_trail_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_trail(trail_id="t", analysis_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_trail(trail_id="t")
        eng.add_analysis(trail_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_trail(trail_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_trail(trail_id="a")
        eng.record_trail(trail_id="b")
        eng.add_analysis(trail_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
