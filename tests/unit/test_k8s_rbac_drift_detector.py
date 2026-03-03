"""Tests for shieldops.security.k8s_rbac_drift_detector — K8sRBACDriftDetector."""

from __future__ import annotations

from shieldops.security.k8s_rbac_drift_detector import (
    DriftSeverity,
    DriftType,
    K8sRBACDriftDetector,
    RBACDriftAnalysis,
    RBACDriftRecord,
    RBACDriftReport,
    RBACResource,
)


def _engine(**kw) -> K8sRBACDriftDetector:
    return K8sRBACDriftDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert RBACResource.ROLE == "role"

    def test_e1_v2(self):
        assert RBACResource.CLUSTER_ROLE == "cluster_role"

    def test_e1_v3(self):
        assert RBACResource.BINDING == "binding"

    def test_e1_v4(self):
        assert RBACResource.SERVICE_ACCOUNT == "service_account"

    def test_e1_v5(self):
        assert RBACResource.NAMESPACE == "namespace"

    def test_e2_v1(self):
        assert DriftType.ADDED == "added"

    def test_e2_v2(self):
        assert DriftType.REMOVED == "removed"

    def test_e2_v3(self):
        assert DriftType.MODIFIED == "modified"

    def test_e2_v4(self):
        assert DriftType.ESCALATED == "escalated"

    def test_e2_v5(self):
        assert DriftType.UNAUTHORIZED == "unauthorized"

    def test_e3_v1(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_e3_v2(self):
        assert DriftSeverity.HIGH == "high"

    def test_e3_v3(self):
        assert DriftSeverity.MEDIUM == "medium"

    def test_e3_v4(self):
        assert DriftSeverity.LOW == "low"

    def test_e3_v5(self):
        assert DriftSeverity.INFORMATIONAL == "informational"


class TestModels:
    def test_rec(self):
        r = RBACDriftRecord()
        assert r.id and r.drift_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = RBACDriftAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = RBACDriftReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_drift(
            drift_id="t",
            rbac_resource=RBACResource.CLUSTER_ROLE,
            drift_type=DriftType.REMOVED,
            drift_severity=DriftSeverity.HIGH,
            drift_score=92.0,
            service="s",
            team="t",
        )
        assert r.drift_id == "t" and r.drift_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(drift_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift(drift_id="t")
        assert eng.get_drift(r.id) is not None

    def test_not_found(self):
        assert _engine().get_drift("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_drift(drift_id="a")
        eng.record_drift(drift_id="b")
        assert len(eng.list_drifts()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_drift(drift_id="a", rbac_resource=RBACResource.ROLE)
        eng.record_drift(drift_id="b", rbac_resource=RBACResource.CLUSTER_ROLE)
        assert len(eng.list_drifts(rbac_resource=RBACResource.ROLE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_drift(drift_id="a", drift_type=DriftType.ADDED)
        eng.record_drift(drift_id="b", drift_type=DriftType.REMOVED)
        assert len(eng.list_drifts(drift_type=DriftType.ADDED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_drift(drift_id="a", team="x")
        eng.record_drift(drift_id="b", team="y")
        assert len(eng.list_drifts(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(drift_id=f"t-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            drift_id="t",
            rbac_resource=RBACResource.CLUSTER_ROLE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(drift_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_drift(drift_id="a", rbac_resource=RBACResource.ROLE, drift_score=90.0)
        eng.record_drift(drift_id="b", rbac_resource=RBACResource.ROLE, drift_score=70.0)
        assert "role" in eng.analyze_resource_distribution()

    def test_empty(self):
        assert _engine().analyze_resource_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(drift_gap_threshold=80.0)
        eng.record_drift(drift_id="a", drift_score=60.0)
        eng.record_drift(drift_id="b", drift_score=90.0)
        assert len(eng.identify_drift_gaps()) == 1

    def test_sorted(self):
        eng = _engine(drift_gap_threshold=80.0)
        eng.record_drift(drift_id="a", drift_score=50.0)
        eng.record_drift(drift_id="b", drift_score=30.0)
        assert len(eng.identify_drift_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_drift(drift_id="a", service="s1", drift_score=80.0)
        eng.record_drift(drift_id="b", service="s2", drift_score=60.0)
        assert eng.rank_by_drift()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_drift() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(drift_id="t", analysis_score=float(v))
        assert eng.detect_drift_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(drift_id="t", analysis_score=float(v))
        assert eng.detect_drift_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_drift_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_drift(drift_id="t", drift_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_drift(drift_id="t")
        eng.add_analysis(drift_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_drift(drift_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_drift(drift_id="a")
        eng.record_drift(drift_id="b")
        eng.add_analysis(drift_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
