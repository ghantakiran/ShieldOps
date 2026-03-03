"""Tests for shieldops.security.namespace_isolation_validator — NamespaceIsolationValidator."""

from __future__ import annotations

from shieldops.security.namespace_isolation_validator import (
    IsolationAnalysis,
    IsolationRecord,
    IsolationStatus,
    IsolationType,
    NamespaceIsolationReport,
    NamespaceIsolationValidator,
    TenantModel,
)


def _engine(**kw) -> NamespaceIsolationValidator:
    return NamespaceIsolationValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert IsolationType.NETWORK == "network"

    def test_e1_v2(self):
        assert IsolationType.RESOURCE == "resource"

    def test_e1_v3(self):
        assert IsolationType.RBAC == "rbac"

    def test_e1_v4(self):
        assert IsolationType.STORAGE == "storage"

    def test_e1_v5(self):
        assert IsolationType.FULL == "full"

    def test_e2_v1(self):
        assert IsolationStatus.ISOLATED == "isolated"

    def test_e2_v2(self):
        assert IsolationStatus.PARTIAL == "partial"

    def test_e2_v3(self):
        assert IsolationStatus.SHARED == "shared"

    def test_e2_v4(self):
        assert IsolationStatus.VIOLATED == "violated"

    def test_e2_v5(self):
        assert IsolationStatus.UNKNOWN == "unknown"

    def test_e3_v1(self):
        assert TenantModel.SINGLE == "single"

    def test_e3_v2(self):
        assert TenantModel.MULTI == "multi"

    def test_e3_v3(self):
        assert TenantModel.HYBRID == "hybrid"

    def test_e3_v4(self):
        assert TenantModel.HIERARCHICAL == "hierarchical"

    def test_e3_v5(self):
        assert TenantModel.FLAT == "flat"


class TestModels:
    def test_rec(self):
        r = IsolationRecord()
        assert r.id and r.isolation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = IsolationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = NamespaceIsolationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_isolation(
            isolation_id="t",
            isolation_type=IsolationType.RESOURCE,
            isolation_status=IsolationStatus.PARTIAL,
            tenant_model=TenantModel.MULTI,
            isolation_score=92.0,
            service="s",
            team="t",
        )
        assert r.isolation_id == "t" and r.isolation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_isolation(isolation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_isolation(isolation_id="t")
        assert eng.get_isolation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_isolation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a")
        eng.record_isolation(isolation_id="b")
        assert len(eng.list_isolations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a", isolation_type=IsolationType.NETWORK)
        eng.record_isolation(isolation_id="b", isolation_type=IsolationType.RESOURCE)
        assert len(eng.list_isolations(isolation_type=IsolationType.NETWORK)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a", isolation_status=IsolationStatus.ISOLATED)
        eng.record_isolation(isolation_id="b", isolation_status=IsolationStatus.PARTIAL)
        assert len(eng.list_isolations(isolation_status=IsolationStatus.ISOLATED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a", team="x")
        eng.record_isolation(isolation_id="b", team="y")
        assert len(eng.list_isolations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_isolation(isolation_id=f"t-{i}")
        assert len(eng.list_isolations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            isolation_id="t",
            isolation_type=IsolationType.RESOURCE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(isolation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_isolation(
            isolation_id="a", isolation_type=IsolationType.NETWORK, isolation_score=90.0
        )
        eng.record_isolation(
            isolation_id="b", isolation_type=IsolationType.NETWORK, isolation_score=70.0
        )
        assert "network" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(isolation_gap_threshold=80.0)
        eng.record_isolation(isolation_id="a", isolation_score=60.0)
        eng.record_isolation(isolation_id="b", isolation_score=90.0)
        assert len(eng.identify_isolation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(isolation_gap_threshold=80.0)
        eng.record_isolation(isolation_id="a", isolation_score=50.0)
        eng.record_isolation(isolation_id="b", isolation_score=30.0)
        assert len(eng.identify_isolation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a", service="s1", isolation_score=80.0)
        eng.record_isolation(isolation_id="b", service="s2", isolation_score=60.0)
        assert eng.rank_by_isolation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_isolation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(isolation_id="t", analysis_score=float(v))
        assert eng.detect_isolation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(isolation_id="t", analysis_score=float(v))
        assert eng.detect_isolation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_isolation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_isolation(isolation_id="t", isolation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_isolation(isolation_id="t")
        eng.add_analysis(isolation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_isolation(isolation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_isolation(isolation_id="a")
        eng.record_isolation(isolation_id="b")
        eng.add_analysis(isolation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
