"""Tests for shieldops.changes.deploy_gate_tracker — DeployGateTracker."""

from __future__ import annotations

from shieldops.changes.deploy_gate_tracker import (
    DeployGateReport,
    DeployGateTracker,
    GateImpact,
    GateMetric,
    GateRecord,
    GateResult,
    GateType,
)


def _engine(**kw) -> DeployGateTracker:
    return DeployGateTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_security_scan(self):
        assert GateType.SECURITY_SCAN == "security_scan"

    def test_type_test_coverage(self):
        assert GateType.TEST_COVERAGE == "test_coverage"

    def test_type_performance(self):
        assert GateType.PERFORMANCE == "performance"

    def test_type_compliance(self):
        assert GateType.COMPLIANCE == "compliance"

    def test_type_approval(self):
        assert GateType.APPROVAL == "approval"

    def test_result_passed(self):
        assert GateResult.PASSED == "passed"

    def test_result_failed(self):
        assert GateResult.FAILED == "failed"

    def test_result_bypassed(self):
        assert GateResult.BYPASSED == "bypassed"

    def test_result_pending(self):
        assert GateResult.PENDING == "pending"

    def test_result_expired(self):
        assert GateResult.EXPIRED == "expired"

    def test_impact_blocking(self):
        assert GateImpact.BLOCKING == "blocking"

    def test_impact_warning(self):
        assert GateImpact.WARNING == "warning"

    def test_impact_informational(self):
        assert GateImpact.INFORMATIONAL == "informational"

    def test_impact_advisory(self):
        assert GateImpact.ADVISORY == "advisory"

    def test_impact_none(self):
        assert GateImpact.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_gate_record_defaults(self):
        r = GateRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.gate_type == GateType.SECURITY_SCAN
        assert r.gate_result == GateResult.PENDING
        assert r.gate_impact == GateImpact.BLOCKING
        assert r.failure_rate == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_gate_metric_defaults(self):
        m = GateMetric()
        assert m.id
        assert m.deployment_id == ""
        assert m.gate_type == GateType.SECURITY_SCAN
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_deploy_gate_report_defaults(self):
        r = DeployGateReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.failed_gates == 0
        assert r.avg_failure_rate == 0.0
        assert r.by_type == {}
        assert r.by_result == {}
        assert r.by_impact == {}
        assert r.top_failing == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_gate
# ---------------------------------------------------------------------------


class TestRecordGate:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gate(
            deployment_id="DEP-001",
            gate_type=GateType.SECURITY_SCAN,
            gate_result=GateResult.FAILED,
            gate_impact=GateImpact.BLOCKING,
            failure_rate=25.0,
            service="api-gateway",
            team="sre",
        )
        assert r.deployment_id == "DEP-001"
        assert r.gate_type == GateType.SECURITY_SCAN
        assert r.gate_result == GateResult.FAILED
        assert r.gate_impact == GateImpact.BLOCKING
        assert r.failure_rate == 25.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gate(deployment_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_gate
# ---------------------------------------------------------------------------


class TestGetGate:
    def test_found(self):
        eng = _engine()
        r = eng.record_gate(
            deployment_id="DEP-001",
            gate_result=GateResult.FAILED,
        )
        result = eng.get_gate(r.id)
        assert result is not None
        assert result.gate_result == GateResult.FAILED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gate("nonexistent") is None


# ---------------------------------------------------------------------------
# list_gates
# ---------------------------------------------------------------------------


class TestListGates:
    def test_list_all(self):
        eng = _engine()
        eng.record_gate(deployment_id="DEP-001")
        eng.record_gate(deployment_id="DEP-002")
        assert len(eng.list_gates()) == 2

    def test_filter_by_gate_type(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_type=GateType.SECURITY_SCAN,
        )
        eng.record_gate(
            deployment_id="DEP-002",
            gate_type=GateType.TEST_COVERAGE,
        )
        results = eng.list_gates(gate_type=GateType.SECURITY_SCAN)
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_result=GateResult.PASSED,
        )
        eng.record_gate(
            deployment_id="DEP-002",
            gate_result=GateResult.FAILED,
        )
        results = eng.list_gates(result=GateResult.FAILED)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_gate(deployment_id="DEP-001", service="api-gateway")
        eng.record_gate(deployment_id="DEP-002", service="auth-svc")
        results = eng.list_gates(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gate(deployment_id="DEP-001", team="sre")
        eng.record_gate(deployment_id="DEP-002", team="platform")
        results = eng.list_gates(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gate(deployment_id=f"DEP-{i}")
        assert len(eng.list_gates(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            deployment_id="DEP-001",
            gate_type=GateType.PERFORMANCE,
            metric_score=85.0,
            threshold=90.0,
            breached=True,
            description="Performance gate threshold breached",
        )
        assert m.deployment_id == "DEP-001"
        assert m.gate_type == GateType.PERFORMANCE
        assert m.metric_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Performance gate threshold breached"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(deployment_id=f"DEP-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_gate_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeGateDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_type=GateType.SECURITY_SCAN,
            failure_rate=10.0,
        )
        eng.record_gate(
            deployment_id="DEP-002",
            gate_type=GateType.SECURITY_SCAN,
            failure_rate=20.0,
        )
        result = eng.analyze_gate_distribution()
        assert "security_scan" in result
        assert result["security_scan"]["count"] == 2
        assert result["security_scan"]["avg_failure_rate"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_gate_distribution() == {}


# ---------------------------------------------------------------------------
# identify_failed_gates
# ---------------------------------------------------------------------------


class TestIdentifyFailedGates:
    def test_detects(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_result=GateResult.FAILED,
        )
        eng.record_gate(
            deployment_id="DEP-002",
            gate_result=GateResult.PASSED,
        )
        results = eng.identify_failed_gates()
        assert len(results) == 1
        assert results[0]["deployment_id"] == "DEP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_gates() == []


# ---------------------------------------------------------------------------
# rank_by_failure_rate
# ---------------------------------------------------------------------------


class TestRankByFailureRate:
    def test_ranked(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            service="api-gateway",
            failure_rate=30.0,
        )
        eng.record_gate(
            deployment_id="DEP-002",
            service="auth-svc",
            failure_rate=10.0,
        )
        eng.record_gate(
            deployment_id="DEP-003",
            service="api-gateway",
            failure_rate=20.0,
        )
        results = eng.rank_by_failure_rate()
        assert len(results) == 2
        # descending: api-gateway (25.0) first, auth-svc (10.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_failure_rate"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_failure_rate() == []


# ---------------------------------------------------------------------------
# detect_gate_trends
# ---------------------------------------------------------------------------


class TestDetectGateTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_metric(deployment_id="DEP-1", metric_score=val)
        result = eng.detect_gate_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_metric(deployment_id="DEP-1", metric_score=val)
        result = eng.detect_gate_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_metric(deployment_id="DEP-1", metric_score=val)
        result = eng.detect_gate_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_gate_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_type=GateType.SECURITY_SCAN,
            gate_result=GateResult.FAILED,
            gate_impact=GateImpact.BLOCKING,
            failure_rate=25.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DeployGateReport)
        assert report.total_records == 1
        assert report.failed_gates == 1
        assert len(report.top_failing) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_gate(deployment_id="DEP-001")
        eng.add_metric(deployment_id="DEP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_gate(
            deployment_id="DEP-001",
            gate_type=GateType.SECURITY_SCAN,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "security_scan" in stats["type_distribution"]
