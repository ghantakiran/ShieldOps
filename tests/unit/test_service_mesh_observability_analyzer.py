"""Tests for shieldops.topology.service_mesh_observability_analyzer

ServiceMeshObservabilityAnalyzer.
"""

from __future__ import annotations

from shieldops.topology.service_mesh_observability_analyzer import (
    MeshAnalysis,
    MeshComponent,
    MeshHealth,
    MeshRecord,
    MeshSource,
    ServiceMeshObservabilityAnalyzer,
    ServiceMeshObservabilityReport,
)


def _engine(**kw) -> ServiceMeshObservabilityAnalyzer:
    return ServiceMeshObservabilityAnalyzer(**kw)


class TestEnums:
    def test_mesh_component_sidecar(self):
        assert MeshComponent.SIDECAR == "sidecar"

    def test_mesh_component_control_plane(self):
        assert MeshComponent.CONTROL_PLANE == "control_plane"

    def test_mesh_component_data_plane(self):
        assert MeshComponent.DATA_PLANE == "data_plane"

    def test_mesh_component_gateway(self):
        assert MeshComponent.GATEWAY == "gateway"

    def test_mesh_component_policy_engine(self):
        assert MeshComponent.POLICY_ENGINE == "policy_engine"

    def test_mesh_source_istio(self):
        assert MeshSource.ISTIO == "istio"

    def test_mesh_source_linkerd(self):
        assert MeshSource.LINKERD == "linkerd"

    def test_mesh_source_consul_connect(self):
        assert MeshSource.CONSUL_CONNECT == "consul_connect"

    def test_mesh_source_envoy(self):
        assert MeshSource.ENVOY == "envoy"

    def test_mesh_source_custom(self):
        assert MeshSource.CUSTOM == "custom"

    def test_mesh_health_healthy(self):
        assert MeshHealth.HEALTHY == "healthy"

    def test_mesh_health_degraded(self):
        assert MeshHealth.DEGRADED == "degraded"

    def test_mesh_health_partial(self):
        assert MeshHealth.PARTIAL == "partial"

    def test_mesh_health_failing(self):
        assert MeshHealth.FAILING == "failing"

    def test_mesh_health_unknown(self):
        assert MeshHealth.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = MeshRecord()
        assert r.id
        assert r.name == ""
        assert r.mesh_component == MeshComponent.SIDECAR
        assert r.mesh_source == MeshSource.ISTIO
        assert r.mesh_health == MeshHealth.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MeshAnalysis()
        assert a.id
        assert a.name == ""
        assert a.mesh_component == MeshComponent.SIDECAR
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ServiceMeshObservabilityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_mesh_component == {}
        assert r.by_mesh_source == {}
        assert r.by_mesh_health == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            mesh_component=MeshComponent.SIDECAR,
            mesh_source=MeshSource.LINKERD,
            mesh_health=MeshHealth.HEALTHY,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.mesh_component == MeshComponent.SIDECAR
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_mesh_component(self):
        eng = _engine()
        eng.record_entry(name="a", mesh_component=MeshComponent.SIDECAR)
        eng.record_entry(name="b", mesh_component=MeshComponent.CONTROL_PLANE)
        assert len(eng.list_records(mesh_component=MeshComponent.SIDECAR)) == 1

    def test_filter_by_mesh_source(self):
        eng = _engine()
        eng.record_entry(name="a", mesh_source=MeshSource.ISTIO)
        eng.record_entry(name="b", mesh_source=MeshSource.LINKERD)
        assert len(eng.list_records(mesh_source=MeshSource.ISTIO)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", mesh_component=MeshComponent.CONTROL_PLANE, score=90.0)
        eng.record_entry(name="b", mesh_component=MeshComponent.CONTROL_PLANE, score=70.0)
        result = eng.analyze_distribution()
        assert "control_plane" in result
        assert result["control_plane"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
