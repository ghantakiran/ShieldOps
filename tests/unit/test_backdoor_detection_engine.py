"""Tests for shieldops.security.backdoor_detection_engine — BackdoorDetectionEngine."""

from __future__ import annotations

from shieldops.security.backdoor_detection_engine import (
    BackdoorAnalysis,
    BackdoorDetectionEngine,
    BackdoorDetectionReport,
    BackdoorRecord,
    BackdoorType,
    DetectionVector,
    PersistenceLevel,
)


def _engine(**kw) -> BackdoorDetectionEngine:
    return BackdoorDetectionEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert BackdoorType.WEB_SHELL == "web_shell"

    def test_e1_v2(self):
        assert BackdoorType.ROOTKIT == "rootkit"

    def test_e1_v3(self):
        assert BackdoorType.RAT == "rat"

    def test_e1_v4(self):
        assert BackdoorType.IMPLANT == "implant"

    def test_e1_v5(self):
        assert BackdoorType.BOOTKIT == "bootkit"

    def test_e2_v1(self):
        assert DetectionVector.FILE_SCAN == "file_scan"

    def test_e2_v2(self):
        assert DetectionVector.NETWORK_MONITOR == "network_monitor"

    def test_e2_v3(self):
        assert DetectionVector.BEHAVIORAL == "behavioral"

    def test_e2_v4(self):
        assert DetectionVector.MEMORY_SCAN == "memory_scan"

    def test_e2_v5(self):
        assert DetectionVector.INTEGRITY_CHECK == "integrity_check"

    def test_e3_v1(self):
        assert PersistenceLevel.KERNEL == "kernel"

    def test_e3_v2(self):
        assert PersistenceLevel.SERVICE == "service"

    def test_e3_v3(self):
        assert PersistenceLevel.SCHEDULED_TASK == "scheduled_task"

    def test_e3_v4(self):
        assert PersistenceLevel.REGISTRY == "registry"

    def test_e3_v5(self):
        assert PersistenceLevel.FIRMWARE == "firmware"


class TestModels:
    def test_rec(self):
        r = BackdoorRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = BackdoorAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = BackdoorDetectionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_backdoor(
            backdoor_id="t",
            backdoor_type=BackdoorType.ROOTKIT,
            detection_vector=DetectionVector.NETWORK_MONITOR,
            persistence_level=PersistenceLevel.SERVICE,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.backdoor_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_backdoor(backdoor_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_backdoor(backdoor_id="t")
        assert eng.get_backdoor(r.id) is not None

    def test_not_found(self):
        assert _engine().get_backdoor("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a")
        eng.record_backdoor(backdoor_id="b")
        assert len(eng.list_backdoors()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a", backdoor_type=BackdoorType.WEB_SHELL)
        eng.record_backdoor(backdoor_id="b", backdoor_type=BackdoorType.ROOTKIT)
        assert len(eng.list_backdoors(backdoor_type=BackdoorType.WEB_SHELL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a", detection_vector=DetectionVector.FILE_SCAN)
        eng.record_backdoor(backdoor_id="b", detection_vector=DetectionVector.NETWORK_MONITOR)
        assert len(eng.list_backdoors(detection_vector=DetectionVector.FILE_SCAN)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a", team="x")
        eng.record_backdoor(backdoor_id="b", team="y")
        assert len(eng.list_backdoors(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_backdoor(backdoor_id=f"t-{i}")
        assert len(eng.list_backdoors(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            backdoor_id="t", backdoor_type=BackdoorType.ROOTKIT, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(backdoor_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_backdoor(
            backdoor_id="a", backdoor_type=BackdoorType.WEB_SHELL, detection_score=90.0
        )
        eng.record_backdoor(
            backdoor_id="b", backdoor_type=BackdoorType.WEB_SHELL, detection_score=70.0
        )
        assert "web_shell" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_backdoor(backdoor_id="a", detection_score=60.0)
        eng.record_backdoor(backdoor_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_backdoor(backdoor_id="a", detection_score=50.0)
        eng.record_backdoor(backdoor_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a", service="s1", detection_score=80.0)
        eng.record_backdoor(backdoor_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(backdoor_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(backdoor_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="t")
        eng.add_analysis(backdoor_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_backdoor(backdoor_id="a")
        eng.record_backdoor(backdoor_id="b")
        eng.add_analysis(backdoor_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
