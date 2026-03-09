"""Tests for shieldops.security.security_orchestration_hub — SecurityOrchestrationHub."""

from __future__ import annotations

from shieldops.security.security_orchestration_hub import (
    OrchestrationAction,
    RoutingCondition,
    SecurityOrchestrationHub,
    WorkflowChainStatus,
)


def _engine(**kw) -> SecurityOrchestrationHub:
    return SecurityOrchestrationHub(**kw)


class TestEnums:
    def test_action(self):
        assert OrchestrationAction.ENRICH == "enrich"

    def test_routing(self):
        assert RoutingCondition.SEVERITY_BASED == "severity_based"

    def test_workflow_status(self):
        assert WorkflowChainStatus.COMPLETED == "completed"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(workflow_name="isolate-host", action=OrchestrationAction.ENRICH)
        assert rec.workflow_name == "isolate-host"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(workflow_name=f"wf-{i}")
        assert len(eng._records) == 3


class TestWorkflowPerformance:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1", execution_time_sec=30.0)
        result = eng.analyze_workflow_performance()
        assert isinstance(result, list)


class TestRoutingEffectiveness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1", routing_condition=RoutingCondition.SEVERITY_BASED)
        result = eng.evaluate_routing_effectiveness()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1", service="soc")
        result = eng.process("wf-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(workflow_name="wf-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
