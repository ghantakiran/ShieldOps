"""Tests for shieldops.security.data_flow_mapper — DataFlowMapper."""

from __future__ import annotations

from shieldops.security.data_flow_mapper import (
    DataFlowAnalysis,
    DataFlowMapper,
    DataFlowRecord,
    DataFlowReport,
    DataSensitivity,
    FlowCompliance,
    FlowType,
)


def _engine(**kw) -> DataFlowMapper:
    return DataFlowMapper(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert FlowType.INTERNAL == "internal"

    def test_e1_v2(self):
        assert FlowType.EXTERNAL == "external"

    def test_e1_v3(self):
        assert FlowType.CROSS_REGION == "cross_region"

    def test_e1_v4(self):
        assert FlowType.CROSS_CLOUD == "cross_cloud"

    def test_e1_v5(self):
        assert FlowType.HYBRID == "hybrid"

    def test_e2_v1(self):
        assert DataSensitivity.CRITICAL == "critical"

    def test_e2_v2(self):
        assert DataSensitivity.HIGH == "high"

    def test_e2_v3(self):
        assert DataSensitivity.MEDIUM == "medium"

    def test_e2_v4(self):
        assert DataSensitivity.LOW == "low"

    def test_e2_v5(self):
        assert DataSensitivity.PUBLIC == "public"

    def test_e3_v1(self):
        assert FlowCompliance.COMPLIANT == "compliant"

    def test_e3_v2(self):
        assert FlowCompliance.NON_COMPLIANT == "non_compliant"

    def test_e3_v3(self):
        assert FlowCompliance.EXEMPT == "exempt"

    def test_e3_v4(self):
        assert FlowCompliance.UNKNOWN == "unknown"

    def test_e3_v5(self):
        assert FlowCompliance.PENDING == "pending"


class TestModels:
    def test_rec(self):
        r = DataFlowRecord()
        assert r.id and r.flow_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = DataFlowAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DataFlowReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_flow(
            flow_id="t",
            flow_type=FlowType.EXTERNAL,
            data_sensitivity=DataSensitivity.HIGH,
            flow_compliance=FlowCompliance.NON_COMPLIANT,
            flow_score=92.0,
            service="s",
            team="t",
        )
        assert r.flow_id == "t" and r.flow_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_flow(flow_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_flow(flow_id="t")
        assert eng.get_flow(r.id) is not None

    def test_not_found(self):
        assert _engine().get_flow("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_flow(flow_id="a")
        eng.record_flow(flow_id="b")
        assert len(eng.list_flows()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_flow(flow_id="a", flow_type=FlowType.INTERNAL)
        eng.record_flow(flow_id="b", flow_type=FlowType.EXTERNAL)
        assert len(eng.list_flows(flow_type=FlowType.INTERNAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_flow(flow_id="a", data_sensitivity=DataSensitivity.CRITICAL)
        eng.record_flow(flow_id="b", data_sensitivity=DataSensitivity.HIGH)
        assert len(eng.list_flows(data_sensitivity=DataSensitivity.CRITICAL)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_flow(flow_id="a", team="x")
        eng.record_flow(flow_id="b", team="y")
        assert len(eng.list_flows(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_flow(flow_id=f"t-{i}")
        assert len(eng.list_flows(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            flow_id="t", flow_type=FlowType.EXTERNAL, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(flow_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_flow(flow_id="a", flow_type=FlowType.INTERNAL, flow_score=90.0)
        eng.record_flow(flow_id="b", flow_type=FlowType.INTERNAL, flow_score=70.0)
        assert "internal" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(flow_threshold=80.0)
        eng.record_flow(flow_id="a", flow_score=60.0)
        eng.record_flow(flow_id="b", flow_score=90.0)
        assert len(eng.identify_flow_gaps()) == 1

    def test_sorted(self):
        eng = _engine(flow_threshold=80.0)
        eng.record_flow(flow_id="a", flow_score=50.0)
        eng.record_flow(flow_id="b", flow_score=30.0)
        assert len(eng.identify_flow_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_flow(flow_id="a", service="s1", flow_score=80.0)
        eng.record_flow(flow_id="b", service="s2", flow_score=60.0)
        assert eng.rank_by_flow()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_flow() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(flow_id="t", analysis_score=float(v))
        assert eng.detect_flow_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(flow_id="t", analysis_score=float(v))
        assert eng.detect_flow_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_flow_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_flow(flow_id="t", flow_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_flow(flow_id="t")
        eng.add_analysis(flow_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_flow(flow_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_flow(flow_id="a")
        eng.record_flow(flow_id="b")
        eng.add_analysis(flow_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
