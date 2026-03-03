"""Tests for shieldops.security.living_off_the_land_detector — LivingOffTheLandDetector."""

from __future__ import annotations

from shieldops.security.living_off_the_land_detector import (
    AbusePattern,
    DetectionMethod,
    LivingOffTheLandDetector,
    LOLAnalysis,
    LOLBinary,
    LOLDetectionReport,
    LOLRecord,
)


def _engine(**kw) -> LivingOffTheLandDetector:
    return LivingOffTheLandDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert LOLBinary.POWERSHELL == "powershell"

    def test_e1_v2(self):
        assert LOLBinary.CERTUTIL == "certutil"

    def test_e1_v3(self):
        assert LOLBinary.MSHTA == "mshta"

    def test_e1_v4(self):
        assert LOLBinary.REGSVR32 == "regsvr32"

    def test_e1_v5(self):
        assert LOLBinary.RUNDLL32 == "rundll32"

    def test_e2_v1(self):
        assert AbusePattern.DOWNLOAD == "download"

    def test_e2_v2(self):
        assert AbusePattern.EXECUTION == "execution"

    def test_e2_v3(self):
        assert AbusePattern.ENCODING == "encoding"

    def test_e2_v4(self):
        assert AbusePattern.BYPASS == "bypass"  # noqa: S105

    def test_e2_v5(self):
        assert AbusePattern.PERSISTENCE == "persistence"

    def test_e3_v1(self):
        assert DetectionMethod.COMMAND_LINE == "command_line"

    def test_e3_v2(self):
        assert DetectionMethod.PARENT_CHILD == "parent_child"

    def test_e3_v3(self):
        assert DetectionMethod.BEHAVIORAL == "behavioral"

    def test_e3_v4(self):
        assert DetectionMethod.SIGNATURE == "signature"

    def test_e3_v5(self):
        assert DetectionMethod.HEURISTIC == "heuristic"


class TestModels:
    def test_rec(self):
        r = LOLRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = LOLAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = LOLDetectionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_lol(
            lol_id="t",
            lol_binary=LOLBinary.CERTUTIL,
            abuse_pattern=AbusePattern.EXECUTION,
            detection_method=DetectionMethod.PARENT_CHILD,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.lol_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lol(lol_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_lol(lol_id="t")
        assert eng.get_lol(r.id) is not None

    def test_not_found(self):
        assert _engine().get_lol("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_lol(lol_id="a")
        eng.record_lol(lol_id="b")
        assert len(eng.list_lols()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_lol(lol_id="a", lol_binary=LOLBinary.POWERSHELL)
        eng.record_lol(lol_id="b", lol_binary=LOLBinary.CERTUTIL)
        assert len(eng.list_lols(lol_binary=LOLBinary.POWERSHELL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_lol(lol_id="a", abuse_pattern=AbusePattern.DOWNLOAD)
        eng.record_lol(lol_id="b", abuse_pattern=AbusePattern.EXECUTION)
        assert len(eng.list_lols(abuse_pattern=AbusePattern.DOWNLOAD)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_lol(lol_id="a", team="x")
        eng.record_lol(lol_id="b", team="y")
        assert len(eng.list_lols(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_lol(lol_id=f"t-{i}")
        assert len(eng.list_lols(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            lol_id="t", lol_binary=LOLBinary.CERTUTIL, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(lol_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_lol(lol_id="a", lol_binary=LOLBinary.POWERSHELL, detection_score=90.0)
        eng.record_lol(lol_id="b", lol_binary=LOLBinary.POWERSHELL, detection_score=70.0)
        assert "powershell" in eng.analyze_binary_distribution()

    def test_empty(self):
        assert _engine().analyze_binary_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_lol(lol_id="a", detection_score=60.0)
        eng.record_lol(lol_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_lol(lol_id="a", detection_score=50.0)
        eng.record_lol(lol_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_lol(lol_id="a", service="s1", detection_score=80.0)
        eng.record_lol(lol_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(lol_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(lol_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_lol(lol_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_lol(lol_id="t")
        eng.add_analysis(lol_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_lol(lol_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_lol(lol_id="a")
        eng.record_lol(lol_id="b")
        eng.add_analysis(lol_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
