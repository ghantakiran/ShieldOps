"""Tests for shieldops.security.dns_tunneling_detector — DNSTunnelingDetector."""

from __future__ import annotations

from shieldops.security.dns_tunneling_detector import (
    DNSTunnelingDetector,
    DNSTunnelingReport,
    QueryPattern,
    TunnelingAnalysis,
    TunnelingMethod,
    TunnelingRecord,
    TunnelingRisk,
)


def _engine(**kw) -> DNSTunnelingDetector:
    return DNSTunnelingDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert TunnelingMethod.TXT_RECORD == "txt_record"

    def test_e1_v2(self):
        assert TunnelingMethod.CNAME_CHAIN == "cname_chain"

    def test_e1_v3(self):
        assert TunnelingMethod.SUBDOMAIN_ENCODING == "subdomain_encoding"

    def test_e1_v4(self):
        assert TunnelingMethod.NULL_RECORD == "null_record"

    def test_e1_v5(self):
        assert TunnelingMethod.MX_ABUSE == "mx_abuse"

    def test_e2_v1(self):
        assert QueryPattern.HIGH_FREQUENCY == "high_frequency"

    def test_e2_v2(self):
        assert QueryPattern.UNUSUAL_LENGTH == "unusual_length"

    def test_e2_v3(self):
        assert QueryPattern.ENCODED_PAYLOAD == "encoded_payload"

    def test_e2_v4(self):
        assert QueryPattern.RARE_TYPE == "rare_type"

    def test_e2_v5(self):
        assert QueryPattern.ENTROPY_ANOMALY == "entropy_anomaly"

    def test_e3_v1(self):
        assert TunnelingRisk.ACTIVE_EXFIL == "active_exfil"

    def test_e3_v2(self):
        assert TunnelingRisk.SUSPECTED == "suspected"

    def test_e3_v3(self):
        assert TunnelingRisk.ELEVATED == "elevated"

    def test_e3_v4(self):
        assert TunnelingRisk.NORMAL == "normal"

    def test_e3_v5(self):
        assert TunnelingRisk.BENIGN == "benign"


class TestModels:
    def test_rec(self):
        r = TunnelingRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = TunnelingAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DNSTunnelingReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_tunneling(
            tunneling_id="t",
            tunneling_method=TunnelingMethod.CNAME_CHAIN,
            query_pattern=QueryPattern.UNUSUAL_LENGTH,
            tunneling_risk=TunnelingRisk.SUSPECTED,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.tunneling_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_tunneling(tunneling_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_tunneling(tunneling_id="t")
        assert eng.get_tunneling(r.id) is not None

    def test_not_found(self):
        assert _engine().get_tunneling("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a")
        eng.record_tunneling(tunneling_id="b")
        assert len(eng.list_tunnelings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a", tunneling_method=TunnelingMethod.TXT_RECORD)
        eng.record_tunneling(tunneling_id="b", tunneling_method=TunnelingMethod.CNAME_CHAIN)
        assert len(eng.list_tunnelings(tunneling_method=TunnelingMethod.TXT_RECORD)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a", query_pattern=QueryPattern.HIGH_FREQUENCY)
        eng.record_tunneling(tunneling_id="b", query_pattern=QueryPattern.UNUSUAL_LENGTH)
        assert len(eng.list_tunnelings(query_pattern=QueryPattern.HIGH_FREQUENCY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a", team="x")
        eng.record_tunneling(tunneling_id="b", team="y")
        assert len(eng.list_tunnelings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_tunneling(tunneling_id=f"t-{i}")
        assert len(eng.list_tunnelings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            tunneling_id="t",
            tunneling_method=TunnelingMethod.CNAME_CHAIN,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(tunneling_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_tunneling(
            tunneling_id="a", tunneling_method=TunnelingMethod.TXT_RECORD, detection_score=90.0
        )
        eng.record_tunneling(
            tunneling_id="b", tunneling_method=TunnelingMethod.TXT_RECORD, detection_score=70.0
        )
        assert "txt_record" in eng.analyze_method_distribution()

    def test_empty(self):
        assert _engine().analyze_method_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_tunneling(tunneling_id="a", detection_score=60.0)
        eng.record_tunneling(tunneling_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_tunneling(tunneling_id="a", detection_score=50.0)
        eng.record_tunneling(tunneling_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a", service="s1", detection_score=80.0)
        eng.record_tunneling(tunneling_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(tunneling_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(tunneling_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="t")
        eng.add_analysis(tunneling_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_tunneling(tunneling_id="a")
        eng.record_tunneling(tunneling_id="b")
        eng.add_analysis(tunneling_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
