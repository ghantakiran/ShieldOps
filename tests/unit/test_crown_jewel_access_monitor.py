"""Tests for shieldops.security.crown_jewel_access_monitor — CrownJewelAccessMonitor."""

from __future__ import annotations

from shieldops.security.crown_jewel_access_monitor import (
    AccessRisk,
    AccessType,
    CrownJewelAccessMonitor,
    JewelAccessAnalysis,
    JewelAccessRecord,
    JewelAccessReport,
    JewelType,
)


def _engine(**kw) -> CrownJewelAccessMonitor:
    return CrownJewelAccessMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert JewelType.DATABASE == "database"

    def test_e1_v2(self):
        assert JewelType.SECRET_STORE == "secret_store"  # noqa: S105

    def test_e1_v3(self):
        assert JewelType.SOURCE_CODE == "source_code"

    def test_e1_v4(self):
        assert JewelType.CUSTOMER_DATA == "customer_data"

    def test_e1_v5(self):
        assert JewelType.FINANCIAL_SYSTEM == "financial_system"

    def test_e2_v1(self):
        assert AccessType.READ == "read"

    def test_e2_v2(self):
        assert AccessType.WRITE == "write"

    def test_e2_v3(self):
        assert AccessType.ADMIN == "admin"

    def test_e2_v4(self):
        assert AccessType.EXPORT == "export"

    def test_e2_v5(self):
        assert AccessType.DELETE == "delete"

    def test_e3_v1(self):
        assert AccessRisk.UNAUTHORIZED == "unauthorized"

    def test_e3_v2(self):
        assert AccessRisk.SUSPICIOUS == "suspicious"

    def test_e3_v3(self):
        assert AccessRisk.ELEVATED == "elevated"

    def test_e3_v4(self):
        assert AccessRisk.NORMAL == "normal"

    def test_e3_v5(self):
        assert AccessRisk.PRIVILEGED == "privileged"


class TestModels:
    def test_rec(self):
        r = JewelAccessRecord()
        assert r.id and r.access_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = JewelAccessAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = JewelAccessReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_access(
            access_id="t",
            jewel_type=JewelType.SECRET_STORE,
            access_type_val=AccessType.WRITE,
            access_risk=AccessRisk.SUSPICIOUS,
            access_score=92.0,
            service="s",
            team="t",
        )
        assert r.access_id == "t" and r.access_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_access(access_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_access(access_id="t")
        assert eng.get_access(r.id) is not None

    def test_not_found(self):
        assert _engine().get_access("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_access(access_id="a")
        eng.record_access(access_id="b")
        assert len(eng.list_accesses()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_access(access_id="a", jewel_type=JewelType.DATABASE)
        eng.record_access(access_id="b", jewel_type=JewelType.SECRET_STORE)
        assert len(eng.list_accesses(jewel_type=JewelType.DATABASE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_access(access_id="a", access_type_val=AccessType.READ)
        eng.record_access(access_id="b", access_type_val=AccessType.WRITE)
        assert len(eng.list_accesses(access_type_val=AccessType.READ)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_access(access_id="a", team="x")
        eng.record_access(access_id="b", team="y")
        assert len(eng.list_accesses(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_access(access_id=f"t-{i}")
        assert len(eng.list_accesses(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            access_id="t", jewel_type=JewelType.SECRET_STORE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(access_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_access(access_id="a", jewel_type=JewelType.DATABASE, access_score=90.0)
        eng.record_access(access_id="b", jewel_type=JewelType.DATABASE, access_score=70.0)
        assert "database" in eng.analyze_jewel_distribution()

    def test_empty(self):
        assert _engine().analyze_jewel_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(access_threshold=80.0)
        eng.record_access(access_id="a", access_score=60.0)
        eng.record_access(access_id="b", access_score=90.0)
        assert len(eng.identify_access_gaps()) == 1

    def test_sorted(self):
        eng = _engine(access_threshold=80.0)
        eng.record_access(access_id="a", access_score=50.0)
        eng.record_access(access_id="b", access_score=30.0)
        assert len(eng.identify_access_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_access(access_id="a", service="s1", access_score=80.0)
        eng.record_access(access_id="b", service="s2", access_score=60.0)
        assert eng.rank_by_access()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_access() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(access_id="t", analysis_score=float(v))
        assert eng.detect_access_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(access_id="t", analysis_score=float(v))
        assert eng.detect_access_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_access_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_access(access_id="t", access_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_access(access_id="t")
        eng.add_analysis(access_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_access(access_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_access(access_id="a")
        eng.record_access(access_id="b")
        eng.add_analysis(access_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
