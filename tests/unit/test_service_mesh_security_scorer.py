"""Tests for shieldops.security.service_mesh_security_scorer — ServiceMeshSecurityScorer."""

from __future__ import annotations

from shieldops.security.service_mesh_security_scorer import (
    MeshComponent,
    MeshSecurityAnalysis,
    MeshSecurityRecord,
    MeshType,
    SecurityPosture,
    ServiceMeshSecurityReport,
    ServiceMeshSecurityScorer,
)


def _engine(**kw) -> ServiceMeshSecurityScorer:
    return ServiceMeshSecurityScorer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert MeshComponent.MTLS == "mtls"

    def test_e1_v2(self):
        assert MeshComponent.AUTHORIZATION == "authorization"

    def test_e1_v3(self):
        assert MeshComponent.RATE_LIMITING == "rate_limiting"

    def test_e1_v4(self):
        assert MeshComponent.OBSERVABILITY == "observability"

    def test_e1_v5(self):
        assert MeshComponent.ENCRYPTION == "encryption"

    def test_e2_v1(self):
        assert SecurityPosture.HARDENED == "hardened"

    def test_e2_v2(self):
        assert SecurityPosture.SECURE == "secure"

    def test_e2_v3(self):
        assert SecurityPosture.PARTIAL == "partial"

    def test_e2_v4(self):
        assert SecurityPosture.WEAK == "weak"

    def test_e2_v5(self):
        assert SecurityPosture.INSECURE == "insecure"

    def test_e3_v1(self):
        assert MeshType.ISTIO == "istio"

    def test_e3_v2(self):
        assert MeshType.LINKERD == "linkerd"

    def test_e3_v3(self):
        assert MeshType.CONSUL == "consul"

    def test_e3_v4(self):
        assert MeshType.ENVOY == "envoy"

    def test_e3_v5(self):
        assert MeshType.CUSTOM == "custom"


class TestModels:
    def test_rec(self):
        r = MeshSecurityRecord()
        assert r.id and r.security_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = MeshSecurityAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ServiceMeshSecurityReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_mesh(
            mesh_id="t",
            mesh_component=MeshComponent.AUTHORIZATION,
            security_posture=SecurityPosture.SECURE,
            mesh_type=MeshType.LINKERD,
            security_score=92.0,
            service="s",
            team="t",
        )
        assert r.mesh_id == "t" and r.security_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mesh(mesh_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_mesh(mesh_id="t")
        assert eng.get_mesh(r.id) is not None

    def test_not_found(self):
        assert _engine().get_mesh("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a")
        eng.record_mesh(mesh_id="b")
        assert len(eng.list_meshes()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a", mesh_component=MeshComponent.MTLS)
        eng.record_mesh(mesh_id="b", mesh_component=MeshComponent.AUTHORIZATION)
        assert len(eng.list_meshes(mesh_component=MeshComponent.MTLS)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a", security_posture=SecurityPosture.HARDENED)
        eng.record_mesh(mesh_id="b", security_posture=SecurityPosture.SECURE)
        assert len(eng.list_meshes(security_posture=SecurityPosture.HARDENED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a", team="x")
        eng.record_mesh(mesh_id="b", team="y")
        assert len(eng.list_meshes(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mesh(mesh_id=f"t-{i}")
        assert len(eng.list_meshes(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            mesh_id="t",
            mesh_component=MeshComponent.AUTHORIZATION,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(mesh_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a", mesh_component=MeshComponent.MTLS, security_score=90.0)
        eng.record_mesh(mesh_id="b", mesh_component=MeshComponent.MTLS, security_score=70.0)
        assert "mtls" in eng.analyze_component_distribution()

    def test_empty(self):
        assert _engine().analyze_component_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(security_gap_threshold=80.0)
        eng.record_mesh(mesh_id="a", security_score=60.0)
        eng.record_mesh(mesh_id="b", security_score=90.0)
        assert len(eng.identify_security_gaps()) == 1

    def test_sorted(self):
        eng = _engine(security_gap_threshold=80.0)
        eng.record_mesh(mesh_id="a", security_score=50.0)
        eng.record_mesh(mesh_id="b", security_score=30.0)
        assert len(eng.identify_security_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a", service="s1", security_score=80.0)
        eng.record_mesh(mesh_id="b", service="s2", security_score=60.0)
        assert eng.rank_by_security()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_security() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(mesh_id="t", analysis_score=float(v))
        assert eng.detect_security_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(mesh_id="t", analysis_score=float(v))
        assert eng.detect_security_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_security_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_mesh(mesh_id="t", security_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_mesh(mesh_id="t")
        eng.add_analysis(mesh_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_mesh(mesh_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_mesh(mesh_id="a")
        eng.record_mesh(mesh_id="b")
        eng.add_analysis(mesh_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
