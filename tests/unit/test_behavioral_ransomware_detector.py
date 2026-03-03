"""Tests for shieldops.security.behavioral_ransomware_detector — BehavioralRansomwareDetector."""

from __future__ import annotations

from shieldops.security.behavioral_ransomware_detector import (
    BehavioralRansomwareDetector,
    DetectionStage,
    RansomwareAnalysis,
    RansomwareBehavior,
    RansomwareDetectionReport,
    RansomwareRecord,
    ResponseUrgency,
)


def _engine(**kw) -> BehavioralRansomwareDetector:
    return BehavioralRansomwareDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert RansomwareBehavior.FILE_ENCRYPTION == "file_encryption"

    def test_e1_v2(self):
        assert RansomwareBehavior.KEY_EXCHANGE == "key_exchange"

    def test_e1_v3(self):
        assert RansomwareBehavior.SHADOW_DELETE == "shadow_delete"

    def test_e1_v4(self):
        assert RansomwareBehavior.LATERAL_SPREAD == "lateral_spread"

    def test_e1_v5(self):
        assert RansomwareBehavior.RANSOM_NOTE == "ransom_note"

    def test_e2_v1(self):
        assert DetectionStage.INITIAL_ACCESS == "initial_access"

    def test_e2_v2(self):
        assert DetectionStage.EXECUTION == "execution"

    def test_e2_v3(self):
        assert DetectionStage.ENCRYPTION == "encryption"

    def test_e2_v4(self):
        assert DetectionStage.EXFILTRATION == "exfiltration"

    def test_e2_v5(self):
        assert DetectionStage.RANSOM == "ransom"

    def test_e3_v1(self):
        assert ResponseUrgency.IMMEDIATE == "immediate"

    def test_e3_v2(self):
        assert ResponseUrgency.HIGH == "high"

    def test_e3_v3(self):
        assert ResponseUrgency.MEDIUM == "medium"

    def test_e3_v4(self):
        assert ResponseUrgency.LOW == "low"

    def test_e3_v5(self):
        assert ResponseUrgency.MONITORING == "monitoring"


class TestModels:
    def test_rec(self):
        r = RansomwareRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = RansomwareAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = RansomwareDetectionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_detection(
            ransomware_id="t",
            ransomware_behavior=RansomwareBehavior.KEY_EXCHANGE,
            detection_stage=DetectionStage.EXECUTION,
            response_urgency=ResponseUrgency.HIGH,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.ransomware_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_detection(ransomware_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_detection(ransomware_id="t")
        assert eng.get_detection(r.id) is not None

    def test_not_found(self):
        assert _engine().get_detection("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_detection(ransomware_id="a")
        eng.record_detection(ransomware_id="b")
        assert len(eng.list_detections()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_detection(
            ransomware_id="a", ransomware_behavior=RansomwareBehavior.FILE_ENCRYPTION
        )
        eng.record_detection(ransomware_id="b", ransomware_behavior=RansomwareBehavior.KEY_EXCHANGE)
        assert len(eng.list_detections(ransomware_behavior=RansomwareBehavior.FILE_ENCRYPTION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_detection(ransomware_id="a", detection_stage=DetectionStage.INITIAL_ACCESS)
        eng.record_detection(ransomware_id="b", detection_stage=DetectionStage.EXECUTION)
        assert len(eng.list_detections(detection_stage=DetectionStage.INITIAL_ACCESS)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_detection(ransomware_id="a", team="x")
        eng.record_detection(ransomware_id="b", team="y")
        assert len(eng.list_detections(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_detection(ransomware_id=f"t-{i}")
        assert len(eng.list_detections(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            ransomware_id="t",
            ransomware_behavior=RansomwareBehavior.KEY_EXCHANGE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(ransomware_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_detection(
            ransomware_id="a",
            ransomware_behavior=RansomwareBehavior.FILE_ENCRYPTION,
            detection_score=90.0,
        )
        eng.record_detection(
            ransomware_id="b",
            ransomware_behavior=RansomwareBehavior.FILE_ENCRYPTION,
            detection_score=70.0,
        )
        assert "file_encryption" in eng.analyze_behavior_distribution()

    def test_empty(self):
        assert _engine().analyze_behavior_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_detection(ransomware_id="a", detection_score=60.0)
        eng.record_detection(ransomware_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_detection(ransomware_id="a", detection_score=50.0)
        eng.record_detection(ransomware_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_detection(ransomware_id="a", service="s1", detection_score=80.0)
        eng.record_detection(ransomware_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(ransomware_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(ransomware_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_detection(ransomware_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_detection(ransomware_id="t")
        eng.add_analysis(ransomware_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_detection(ransomware_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_detection(ransomware_id="a")
        eng.record_detection(ransomware_id="b")
        eng.add_analysis(ransomware_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
