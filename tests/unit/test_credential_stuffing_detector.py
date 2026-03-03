"""Tests for shieldops.security.credential_stuffing_detector — CredentialStuffingDetector."""

from __future__ import annotations

from shieldops.security.credential_stuffing_detector import (
    AttackVector,
    CredentialStuffingDetector,
    CredentialStuffingReport,
    DetectionSignal,
    StuffingAnalysis,
    StuffingRecord,
    TargetService,
)


def _engine(**kw) -> CredentialStuffingDetector:
    return CredentialStuffingDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert AttackVector.BRUTE_FORCE == "brute_force"

    def test_e1_v2(self):
        assert AttackVector.CREDENTIAL_SPRAY == "credential_spray"  # noqa: S105

    def test_e1_v3(self):
        assert AttackVector.DICTIONARY == "dictionary"

    def test_e1_v4(self):
        assert AttackVector.COMBO_LIST == "combo_list"

    def test_e1_v5(self):
        assert AttackVector.RAINBOW_TABLE == "rainbow_table"

    def test_e2_v1(self):
        assert TargetService.WEB_LOGIN == "web_login"

    def test_e2_v2(self):
        assert TargetService.API_ENDPOINT == "api_endpoint"

    def test_e2_v3(self):
        assert TargetService.SSH == "ssh"

    def test_e2_v4(self):
        assert TargetService.RDP == "rdp"

    def test_e2_v5(self):
        assert TargetService.VPN == "vpn"

    def test_e3_v1(self):
        assert DetectionSignal.RATE_ANOMALY == "rate_anomaly"

    def test_e3_v2(self):
        assert DetectionSignal.GEO_IMPOSSIBLE == "geo_impossible"

    def test_e3_v3(self):
        assert DetectionSignal.KNOWN_PROXY == "known_proxy"

    def test_e3_v4(self):
        assert DetectionSignal.FAILED_PATTERN == "failed_pattern"

    def test_e3_v5(self):
        assert DetectionSignal.BOT_BEHAVIOR == "bot_behavior"


class TestModels:
    def test_rec(self):
        r = StuffingRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = StuffingAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = CredentialStuffingReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_stuffing(
            stuffing_id="t",
            attack_vector=AttackVector.CREDENTIAL_SPRAY,
            target_service=TargetService.API_ENDPOINT,
            detection_signal=DetectionSignal.GEO_IMPOSSIBLE,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.stuffing_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_stuffing(stuffing_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_stuffing(stuffing_id="t")
        assert eng.get_stuffing(r.id) is not None

    def test_not_found(self):
        assert _engine().get_stuffing("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a")
        eng.record_stuffing(stuffing_id="b")
        assert len(eng.list_stuffings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a", attack_vector=AttackVector.BRUTE_FORCE)
        eng.record_stuffing(stuffing_id="b", attack_vector=AttackVector.CREDENTIAL_SPRAY)
        assert len(eng.list_stuffings(attack_vector=AttackVector.BRUTE_FORCE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a", target_service=TargetService.WEB_LOGIN)
        eng.record_stuffing(stuffing_id="b", target_service=TargetService.API_ENDPOINT)
        assert len(eng.list_stuffings(target_service=TargetService.WEB_LOGIN)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a", team="x")
        eng.record_stuffing(stuffing_id="b", team="y")
        assert len(eng.list_stuffings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_stuffing(stuffing_id=f"t-{i}")
        assert len(eng.list_stuffings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            stuffing_id="t",
            attack_vector=AttackVector.CREDENTIAL_SPRAY,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(stuffing_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_stuffing(
            stuffing_id="a", attack_vector=AttackVector.BRUTE_FORCE, detection_score=90.0
        )
        eng.record_stuffing(
            stuffing_id="b", attack_vector=AttackVector.BRUTE_FORCE, detection_score=70.0
        )
        assert "brute_force" in eng.analyze_vector_distribution()

    def test_empty(self):
        assert _engine().analyze_vector_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_stuffing(stuffing_id="a", detection_score=60.0)
        eng.record_stuffing(stuffing_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_stuffing(stuffing_id="a", detection_score=50.0)
        eng.record_stuffing(stuffing_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a", service="s1", detection_score=80.0)
        eng.record_stuffing(stuffing_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(stuffing_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(stuffing_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="t")
        eng.add_analysis(stuffing_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_stuffing(stuffing_id="a")
        eng.record_stuffing(stuffing_id="b")
        eng.add_analysis(stuffing_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
