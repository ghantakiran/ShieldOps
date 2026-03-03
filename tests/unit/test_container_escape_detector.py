"""Tests for shieldops.security.container_escape_detector — ContainerEscapeDetector."""

from __future__ import annotations

from shieldops.security.container_escape_detector import (
    ContainerEscapeDetector,
    ContainerEscapeReport,
    DetectionMethod,
    EscapeAnalysis,
    EscapeRecord,
    EscapeVector,
    ThreatLevel,
)


def _engine(**kw) -> ContainerEscapeDetector:
    return ContainerEscapeDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert EscapeVector.PRIVILEGED_CONTAINER == "privileged_container"

    def test_e1_v2(self):
        assert EscapeVector.HOST_PID == "host_pid"

    def test_e1_v3(self):
        assert EscapeVector.HOST_NETWORK == "host_network"

    def test_e1_v4(self):
        assert EscapeVector.VOLUME_MOUNT == "volume_mount"

    def test_e1_v5(self):
        assert EscapeVector.KERNEL_EXPLOIT == "kernel_exploit"

    def test_e2_v1(self):
        assert DetectionMethod.SYSCALL_MONITORING == "syscall_monitoring"

    def test_e2_v2(self):
        assert DetectionMethod.BEHAVIORAL == "behavioral"

    def test_e2_v3(self):
        assert DetectionMethod.POLICY_CHECK == "policy_check"

    def test_e2_v4(self):
        assert DetectionMethod.RUNTIME_SCAN == "runtime_scan"

    def test_e2_v5(self):
        assert DetectionMethod.HONEYPOT == "honeypot"

    def test_e3_v1(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_e3_v2(self):
        assert ThreatLevel.HIGH == "high"

    def test_e3_v3(self):
        assert ThreatLevel.MEDIUM == "medium"

    def test_e3_v4(self):
        assert ThreatLevel.LOW == "low"

    def test_e3_v5(self):
        assert ThreatLevel.BENIGN == "benign"


class TestModels:
    def test_rec(self):
        r = EscapeRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = EscapeAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ContainerEscapeReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_escape(
            escape_id="t",
            escape_vector=EscapeVector.HOST_PID,
            detection_method=DetectionMethod.BEHAVIORAL,
            threat_level=ThreatLevel.HIGH,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.escape_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escape(escape_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_escape(escape_id="t")
        assert eng.get_escape(r.id) is not None

    def test_not_found(self):
        assert _engine().get_escape("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_escape(escape_id="a")
        eng.record_escape(escape_id="b")
        assert len(eng.list_escapes()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_escape(escape_id="a", escape_vector=EscapeVector.PRIVILEGED_CONTAINER)
        eng.record_escape(escape_id="b", escape_vector=EscapeVector.HOST_PID)
        assert len(eng.list_escapes(escape_vector=EscapeVector.PRIVILEGED_CONTAINER)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_escape(escape_id="a", detection_method=DetectionMethod.SYSCALL_MONITORING)
        eng.record_escape(escape_id="b", detection_method=DetectionMethod.BEHAVIORAL)
        assert len(eng.list_escapes(detection_method=DetectionMethod.SYSCALL_MONITORING)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_escape(escape_id="a", team="x")
        eng.record_escape(escape_id="b", team="y")
        assert len(eng.list_escapes(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_escape(escape_id=f"t-{i}")
        assert len(eng.list_escapes(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            escape_id="t", escape_vector=EscapeVector.HOST_PID, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(escape_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_escape(
            escape_id="a", escape_vector=EscapeVector.PRIVILEGED_CONTAINER, detection_score=90.0
        )
        eng.record_escape(
            escape_id="b", escape_vector=EscapeVector.PRIVILEGED_CONTAINER, detection_score=70.0
        )
        assert "privileged_container" in eng.analyze_vector_distribution()

    def test_empty(self):
        assert _engine().analyze_vector_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_gap_threshold=80.0)
        eng.record_escape(escape_id="a", detection_score=60.0)
        eng.record_escape(escape_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_gap_threshold=80.0)
        eng.record_escape(escape_id="a", detection_score=50.0)
        eng.record_escape(escape_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_escape(escape_id="a", service="s1", detection_score=80.0)
        eng.record_escape(escape_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(escape_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(escape_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_escape(escape_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_escape(escape_id="t")
        eng.add_analysis(escape_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_escape(escape_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_escape(escape_id="a")
        eng.record_escape(escape_id="b")
        eng.add_analysis(escape_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
