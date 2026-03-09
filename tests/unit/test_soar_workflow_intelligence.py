"""Tests for shieldops.security.soar_workflow_intelligence — SoarWorkflowIntelligence."""

from __future__ import annotations

from shieldops.security.soar_workflow_intelligence import (
    BottleneckType,
    PlaybookStatus,
    SoarWorkflowIntelligence,
    WorkflowStage,
)


def _engine(**kw) -> SoarWorkflowIntelligence:
    return SoarWorkflowIntelligence(**kw)


class TestEnums:
    def test_playbook_status(self):
        assert PlaybookStatus.ACTIVE == "active"

    def test_workflow_stage(self):
        assert WorkflowStage.TRIAGE == "triage"

    def test_bottleneck_type(self):
        assert BottleneckType.HUMAN_APPROVAL == "human_approval"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(playbook_name="isolate-host", workflow_stage=WorkflowStage.TRIAGE)
        assert rec.playbook_name == "isolate-host"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(playbook_name=f"pb-{i}")
        assert len(eng._records) == 3


class TestBottlenecks:
    def test_basic(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1", execution_time_sec=600.0)
        result = eng.detect_bottlenecks()
        assert isinstance(result, list)


class TestAutomationCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1")
        result = eng.compute_automation_coverage()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1", service="api")
        result = eng.process("pb-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(playbook_name="pb-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
