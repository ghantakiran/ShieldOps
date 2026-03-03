"""Tests for shieldops.security.runtime_protection_engine — RuntimeProtectionEngine."""

from __future__ import annotations

from shieldops.security.runtime_protection_engine import (
    ProtectionAnalysis,
    ProtectionMode,
    ProtectionRecord,
    ResponseAction,
    RuntimeProtectionEngine,
    RuntimeProtectionReport,
    ThreatCategory,
)


def _engine(**kw) -> RuntimeProtectionEngine:
    return RuntimeProtectionEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ProtectionMode.ENFORCE == "enforce"

    def test_e1_v2(self):
        assert ProtectionMode.DETECT == "detect"

    def test_e1_v3(self):
        assert ProtectionMode.MONITOR == "monitor"

    def test_e1_v4(self):
        assert ProtectionMode.LEARN == "learn"

    def test_e1_v5(self):
        assert ProtectionMode.DISABLED == "disabled"

    def test_e2_v1(self):
        assert ThreatCategory.PROCESS_INJECTION == "process_injection"

    def test_e2_v2(self):
        assert ThreatCategory.FILE_TAMPERING == "file_tampering"

    def test_e2_v3(self):
        assert ThreatCategory.NETWORK_ANOMALY == "network_anomaly"

    def test_e2_v4(self):
        assert ThreatCategory.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_e2_v5(self):
        assert ThreatCategory.CRYPTOMINING == "cryptomining"

    def test_e3_v1(self):
        assert ResponseAction.BLOCK == "block"

    def test_e3_v2(self):
        assert ResponseAction.ALERT == "alert"

    def test_e3_v3(self):
        assert ResponseAction.CONTAIN == "contain"

    def test_e3_v4(self):
        assert ResponseAction.KILL == "kill"

    def test_e3_v5(self):
        assert ResponseAction.LOG == "log"


class TestModels:
    def test_rec(self):
        r = ProtectionRecord()
        assert r.id and r.protection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ProtectionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = RuntimeProtectionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_protection(
            protection_id="t",
            protection_mode=ProtectionMode.DETECT,
            threat_category=ThreatCategory.FILE_TAMPERING,
            response_action=ResponseAction.ALERT,
            protection_score=92.0,
            service="s",
            team="t",
        )
        assert r.protection_id == "t" and r.protection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_protection(protection_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_protection(protection_id="t")
        assert eng.get_protection(r.id) is not None

    def test_not_found(self):
        assert _engine().get_protection("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_protection(protection_id="a")
        eng.record_protection(protection_id="b")
        assert len(eng.list_protections()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_protection(protection_id="a", protection_mode=ProtectionMode.ENFORCE)
        eng.record_protection(protection_id="b", protection_mode=ProtectionMode.DETECT)
        assert len(eng.list_protections(protection_mode=ProtectionMode.ENFORCE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_protection(protection_id="a", threat_category=ThreatCategory.PROCESS_INJECTION)
        eng.record_protection(protection_id="b", threat_category=ThreatCategory.FILE_TAMPERING)
        assert len(eng.list_protections(threat_category=ThreatCategory.PROCESS_INJECTION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_protection(protection_id="a", team="x")
        eng.record_protection(protection_id="b", team="y")
        assert len(eng.list_protections(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_protection(protection_id=f"t-{i}")
        assert len(eng.list_protections(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            protection_id="t",
            protection_mode=ProtectionMode.DETECT,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(protection_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_protection(
            protection_id="a", protection_mode=ProtectionMode.ENFORCE, protection_score=90.0
        )
        eng.record_protection(
            protection_id="b", protection_mode=ProtectionMode.ENFORCE, protection_score=70.0
        )
        assert "enforce" in eng.analyze_mode_distribution()

    def test_empty(self):
        assert _engine().analyze_mode_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(protection_gap_threshold=80.0)
        eng.record_protection(protection_id="a", protection_score=60.0)
        eng.record_protection(protection_id="b", protection_score=90.0)
        assert len(eng.identify_protection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(protection_gap_threshold=80.0)
        eng.record_protection(protection_id="a", protection_score=50.0)
        eng.record_protection(protection_id="b", protection_score=30.0)
        assert len(eng.identify_protection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_protection(protection_id="a", service="s1", protection_score=80.0)
        eng.record_protection(protection_id="b", service="s2", protection_score=60.0)
        assert eng.rank_by_protection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_protection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(protection_id="t", analysis_score=float(v))
        assert eng.detect_protection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(protection_id="t", analysis_score=float(v))
        assert eng.detect_protection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_protection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_protection(protection_id="t", protection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_protection(protection_id="t")
        eng.add_analysis(protection_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_protection(protection_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_protection(protection_id="a")
        eng.record_protection(protection_id="b")
        eng.add_analysis(protection_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
