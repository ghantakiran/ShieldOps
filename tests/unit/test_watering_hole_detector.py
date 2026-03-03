"""Tests for shieldops.security.watering_hole_detector — WateringHoleDetector."""

from __future__ import annotations

from shieldops.security.watering_hole_detector import (
    CompromiseType,
    IndicatorType,
    TargetProfile,
    WateringHoleAnalysis,
    WateringHoleDetector,
    WateringHoleRecord,
    WateringHoleReport,
)


def _engine(**kw) -> WateringHoleDetector:
    return WateringHoleDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert CompromiseType.SCRIPT_INJECTION == "script_injection"

    def test_e1_v2(self):
        assert CompromiseType.IFRAME_REDIRECT == "iframe_redirect"

    def test_e1_v3(self):
        assert CompromiseType.DRIVE_BY_DOWNLOAD == "drive_by_download"

    def test_e1_v4(self):
        assert CompromiseType.SUPPLY_CHAIN == "supply_chain"

    def test_e1_v5(self):
        assert CompromiseType.DNS_HIJACK == "dns_hijack"

    def test_e2_v1(self):
        assert TargetProfile.INDUSTRY_SPECIFIC == "industry_specific"

    def test_e2_v2(self):
        assert TargetProfile.GEOGRAPHIC == "geographic"

    def test_e2_v3(self):
        assert TargetProfile.ROLE_BASED == "role_based"

    def test_e2_v4(self):
        assert TargetProfile.TECHNOLOGY == "technology"

    def test_e2_v5(self):
        assert TargetProfile.GENERAL == "general"

    def test_e3_v1(self):
        assert IndicatorType.URL_PATTERN == "url_pattern"

    def test_e3_v2(self):
        assert IndicatorType.PAYLOAD_HASH == "payload_hash"

    def test_e3_v3(self):
        assert IndicatorType.NETWORK_SIGNATURE == "network_signature"

    def test_e3_v4(self):
        assert IndicatorType.BEHAVIORAL == "behavioral"

    def test_e3_v5(self):
        assert IndicatorType.INFRASTRUCTURE == "infrastructure"


class TestModels:
    def test_rec(self):
        r = WateringHoleRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = WateringHoleAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = WateringHoleReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_waterhole(
            waterhole_id="t",
            compromise_type=CompromiseType.IFRAME_REDIRECT,
            target_profile=TargetProfile.GEOGRAPHIC,
            indicator_type=IndicatorType.PAYLOAD_HASH,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.waterhole_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_waterhole(waterhole_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_waterhole(waterhole_id="t")
        assert eng.get_waterhole(r.id) is not None

    def test_not_found(self):
        assert _engine().get_waterhole("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a")
        eng.record_waterhole(waterhole_id="b")
        assert len(eng.list_waterholes()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a", compromise_type=CompromiseType.SCRIPT_INJECTION)
        eng.record_waterhole(waterhole_id="b", compromise_type=CompromiseType.IFRAME_REDIRECT)
        assert len(eng.list_waterholes(compromise_type=CompromiseType.SCRIPT_INJECTION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a", target_profile=TargetProfile.INDUSTRY_SPECIFIC)
        eng.record_waterhole(waterhole_id="b", target_profile=TargetProfile.GEOGRAPHIC)
        assert len(eng.list_waterholes(target_profile=TargetProfile.INDUSTRY_SPECIFIC)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a", team="x")
        eng.record_waterhole(waterhole_id="b", team="y")
        assert len(eng.list_waterholes(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_waterhole(waterhole_id=f"t-{i}")
        assert len(eng.list_waterholes(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            waterhole_id="t",
            compromise_type=CompromiseType.IFRAME_REDIRECT,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(waterhole_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_waterhole(
            waterhole_id="a", compromise_type=CompromiseType.SCRIPT_INJECTION, detection_score=90.0
        )
        eng.record_waterhole(
            waterhole_id="b", compromise_type=CompromiseType.SCRIPT_INJECTION, detection_score=70.0
        )
        assert "script_injection" in eng.analyze_compromise_distribution()

    def test_empty(self):
        assert _engine().analyze_compromise_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_waterhole(waterhole_id="a", detection_score=60.0)
        eng.record_waterhole(waterhole_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_waterhole(waterhole_id="a", detection_score=50.0)
        eng.record_waterhole(waterhole_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a", service="s1", detection_score=80.0)
        eng.record_waterhole(waterhole_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(waterhole_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(waterhole_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="t")
        eng.add_analysis(waterhole_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_waterhole(waterhole_id="a")
        eng.record_waterhole(waterhole_id="b")
        eng.add_analysis(waterhole_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
