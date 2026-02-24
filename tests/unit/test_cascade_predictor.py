"""Tests for shieldops.topology.cascade_predictor — CascadingFailurePredictor."""

from __future__ import annotations

from shieldops.topology.cascade_predictor import (
    CascadePrediction,
    CascadeReport,
    CascadeRisk,
    CascadingFailurePredictor,
    FailureType,
    PropagationMode,
    ServiceNode,
)


def _engine(**kw) -> CascadingFailurePredictor:
    return CascadingFailurePredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PropagationMode (5)
    def test_propagation_sequential(self):
        assert PropagationMode.SEQUENTIAL == "sequential"

    def test_propagation_parallel(self):
        assert PropagationMode.PARALLEL == "parallel"

    def test_propagation_exponential(self):
        assert PropagationMode.EXPONENTIAL == "exponential"

    def test_propagation_probabilistic(self):
        assert PropagationMode.PROBABILISTIC == "probabilistic"

    def test_propagation_bounded(self):
        assert PropagationMode.BOUNDED == "bounded"

    # FailureType (5)
    def test_failure_latency_spike(self):
        assert FailureType.LATENCY_SPIKE == "latency_spike"

    def test_failure_total_outage(self):
        assert FailureType.TOTAL_OUTAGE == "total_outage"

    def test_failure_partial_degradation(self):
        assert FailureType.PARTIAL_DEGRADATION == "partial_degradation"

    def test_failure_data_corruption(self):
        assert FailureType.DATA_CORRUPTION == "data_corruption"

    def test_failure_resource_exhaustion(self):
        assert FailureType.RESOURCE_EXHAUSTION == "resource_exhaustion"

    # CascadeRisk (5)
    def test_risk_negligible(self):
        assert CascadeRisk.NEGLIGIBLE == "negligible"

    def test_risk_low(self):
        assert CascadeRisk.LOW == "low"

    def test_risk_moderate(self):
        assert CascadeRisk.MODERATE == "moderate"

    def test_risk_high(self):
        assert CascadeRisk.HIGH == "high"

    def test_risk_critical(self):
        assert CascadeRisk.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_service_node_defaults(self):
        n = ServiceNode()
        assert n.id
        assert n.service_name == ""
        assert n.dependencies == []
        assert n.failure_type == FailureType.LATENCY_SPIKE
        assert n.propagation_mode == PropagationMode.SEQUENTIAL
        assert n.criticality_score == 0.0

    def test_cascade_prediction_defaults(self):
        p = CascadePrediction()
        assert p.id
        assert p.source_service_id == ""
        assert p.affected_services == []
        assert p.cascade_depth == 0
        assert p.propagation_mode == PropagationMode.SEQUENTIAL
        assert p.risk_level == CascadeRisk.LOW
        assert p.estimated_impact_pct == 0.0

    def test_cascade_report_defaults(self):
        r = CascadeReport()
        assert r.total_services == 0
        assert r.critical_paths == 0
        assert r.single_points_of_failure == 0
        assert r.avg_cascade_depth == 0.0
        assert r.max_cascade_depth == 0
        assert r.risk_distribution == {}
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_service
# ---------------------------------------------------------------------------


class TestRegisterService:
    def test_basic_register(self):
        eng = _engine()
        node = eng.register_service(
            service_name="api-gateway",
            dependencies=["auth-service", "user-service"],
            failure_type=FailureType.TOTAL_OUTAGE,
            propagation_mode=PropagationMode.PARALLEL,
            criticality_score=9.5,
        )
        assert node.service_name == "api-gateway"
        assert node.dependencies == ["auth-service", "user-service"]
        assert node.failure_type == FailureType.TOTAL_OUTAGE
        assert node.propagation_mode == PropagationMode.PARALLEL
        assert node.criticality_score == 9.5

    def test_eviction_at_max(self):
        eng = _engine(max_services=3)
        for i in range(5):
            eng.register_service(service_name=f"svc-{i}")
        assert len(eng._services) == 3


# ---------------------------------------------------------------------------
# get_service
# ---------------------------------------------------------------------------


class TestGetService:
    def test_found(self):
        eng = _engine()
        node = eng.register_service(service_name="db-primary")
        assert eng.get_service(node.id) is not None
        assert eng.get_service(node.id).service_name == "db-primary"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_service("nonexistent") is None


# ---------------------------------------------------------------------------
# list_services
# ---------------------------------------------------------------------------


class TestListServices:
    def test_list_all(self):
        eng = _engine()
        eng.register_service(service_name="a")
        eng.register_service(service_name="b")
        assert len(eng.list_services()) == 2

    def test_filter_by_failure_type(self):
        eng = _engine()
        eng.register_service(service_name="a", failure_type=FailureType.TOTAL_OUTAGE)
        eng.register_service(service_name="b", failure_type=FailureType.LATENCY_SPIKE)
        results = eng.list_services(failure_type=FailureType.TOTAL_OUTAGE)
        assert len(results) == 1
        assert results[0].service_name == "a"

    def test_filter_by_propagation_mode(self):
        eng = _engine()
        eng.register_service(service_name="a", propagation_mode=PropagationMode.EXPONENTIAL)
        eng.register_service(service_name="b", propagation_mode=PropagationMode.SEQUENTIAL)
        results = eng.list_services(propagation_mode=PropagationMode.EXPONENTIAL)
        assert len(results) == 1
        assert results[0].service_name == "a"


# ---------------------------------------------------------------------------
# predict_cascade
# ---------------------------------------------------------------------------


class TestPredictCascade:
    def test_basic_cascade_prediction(self):
        eng = _engine()
        # Build a chain: db -> api -> frontend
        db = eng.register_service(service_name="db")
        eng.register_service(service_name="api", dependencies=["db"])
        eng.register_service(service_name="frontend", dependencies=["api"])

        prediction = eng.predict_cascade(db.id)
        assert prediction.source_service_id == db.id
        assert len(prediction.affected_services) >= 1
        assert prediction.cascade_depth >= 1

    def test_empty_deps(self):
        eng = _engine()
        isolated = eng.register_service(service_name="isolated")
        prediction = eng.predict_cascade(isolated.id)
        assert prediction.source_service_id == isolated.id
        assert len(prediction.affected_services) == 0
        assert prediction.cascade_depth == 0
        assert prediction.risk_level == CascadeRisk.NEGLIGIBLE


# ---------------------------------------------------------------------------
# identify_critical_paths
# ---------------------------------------------------------------------------


class TestIdentifyCriticalPaths:
    def test_with_critical_paths(self):
        eng = _engine()
        # Create a hub that many services depend on (>30% impact)
        eng.register_service(service_name="hub")
        for i in range(5):
            eng.register_service(service_name=f"consumer-{i}", dependencies=["hub"])
        # Total 6 services; hub failure affects 5/6 = 83%
        critical = eng.identify_critical_paths()
        assert len(critical) >= 1
        assert critical[0]["service_name"] == "hub"
        assert critical[0]["impact_pct"] > 30.0

    def test_without_critical_paths(self):
        eng = _engine()
        # Independent services — no dependencies, no cascades
        for i in range(5):
            eng.register_service(service_name=f"standalone-{i}")
        critical = eng.identify_critical_paths()
        assert len(critical) == 0


# ---------------------------------------------------------------------------
# calculate_blast_radius
# ---------------------------------------------------------------------------


class TestCalculateBlastRadius:
    def test_basic_blast_radius(self):
        eng = _engine()
        db = eng.register_service(service_name="db")
        eng.register_service(service_name="api", dependencies=["db"])
        eng.register_service(service_name="web", dependencies=["api"])
        result = eng.calculate_blast_radius(db.id)
        assert result["service_id"] == db.id
        assert result["service_name"] == "db"
        assert result["affected_count"] >= 1
        assert result["affected_pct"] > 0.0
        assert result["cascade_depth"] >= 1
        assert result["risk_level"] in [r.value for r in CascadeRisk]


# ---------------------------------------------------------------------------
# detect_single_points_of_failure
# ---------------------------------------------------------------------------


class TestDetectSinglePointsOfFailure:
    def test_with_spofs(self):
        eng = _engine()
        # Create a service that >3 others depend on directly
        eng.register_service(service_name="shared-db")
        for i in range(5):
            eng.register_service(service_name=f"svc-{i}", dependencies=["shared-db"])
        spofs = eng.detect_single_points_of_failure()
        assert len(spofs) >= 1
        assert spofs[0].service_name == "shared-db"

    def test_without_spofs(self):
        eng = _engine()
        # Each service depends on a unique dep — no shared critical dep
        for i in range(4):
            eng.register_service(service_name=f"svc-{i}")
        spofs = eng.detect_single_points_of_failure()
        assert len(spofs) == 0


# ---------------------------------------------------------------------------
# rank_services_by_cascade_risk
# ---------------------------------------------------------------------------


class TestRankServicesByCascadeRisk:
    def test_ranking(self):
        eng = _engine()
        eng.register_service(service_name="hub")
        for i in range(4):
            eng.register_service(service_name=f"leaf-{i}", dependencies=["hub"])
        rankings = eng.rank_services_by_cascade_risk()
        assert len(rankings) == 5
        # Hub should rank highest because it has the most downstream impact
        assert rankings[0]["service_name"] == "hub"
        assert rankings[0]["risk_rank"] >= rankings[-1]["risk_rank"]


# ---------------------------------------------------------------------------
# generate_cascade_report
# ---------------------------------------------------------------------------


class TestGenerateCascadeReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_service(service_name="hub")
        for i in range(4):
            eng.register_service(service_name=f"consumer-{i}", dependencies=["hub"])
        report = eng.generate_cascade_report()
        assert report.total_services == 5
        assert report.max_cascade_depth >= 0
        assert isinstance(report.risk_distribution, dict)
        assert isinstance(report.recommendations, list)


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_lists(self):
        eng = _engine()
        hub = eng.register_service(service_name="hub")
        eng.register_service(service_name="leaf", dependencies=["hub"])
        eng.predict_cascade(hub.id)
        assert len(eng._services) > 0
        assert len(eng._predictions) > 0
        eng.clear_data()
        assert len(eng._services) == 0
        assert len(eng._predictions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_services"] == 0
        assert stats["total_predictions"] == 0
        assert stats["unique_service_names"] == 0
        assert stats["failure_types"] == []
        assert stats["propagation_modes"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_service(
            service_name="api",
            failure_type=FailureType.TOTAL_OUTAGE,
            propagation_mode=PropagationMode.PARALLEL,
        )
        eng.register_service(
            service_name="db",
            failure_type=FailureType.LATENCY_SPIKE,
            propagation_mode=PropagationMode.SEQUENTIAL,
        )
        stats = eng.get_stats()
        assert stats["total_services"] == 2
        assert stats["unique_service_names"] == 2
        assert "total_outage" in stats["failure_types"]
        assert "latency_spike" in stats["failure_types"]
        assert "parallel" in stats["propagation_modes"]
        assert "sequential" in stats["propagation_modes"]
