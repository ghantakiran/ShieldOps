"""Tests for shieldops.operations.scaling_efficiency — ScalingEfficiencyTracker."""

from __future__ import annotations

from shieldops.operations.scaling_efficiency import (
    ScalingEfficiencyReport,
    ScalingEfficiencyTracker,
    ScalingEventRecord,
    ScalingInefficiency,
    ScalingOutcome,
    ScalingTrigger,
    ScalingType,
)


def _engine(**kw) -> ScalingEfficiencyTracker:
    return ScalingEfficiencyTracker(**kw)


class TestEnums:
    def test_type_horizontal(self):
        assert ScalingType.HORIZONTAL == "horizontal"

    def test_type_vertical(self):
        assert ScalingType.VERTICAL == "vertical"

    def test_type_auto(self):
        assert ScalingType.AUTO == "auto"

    def test_type_manual(self):
        assert ScalingType.MANUAL == "manual"

    def test_type_scheduled(self):
        assert ScalingType.SCHEDULED == "scheduled"

    def test_outcome_optimal(self):
        assert ScalingOutcome.OPTIMAL == "optimal"

    def test_outcome_over_provisioned(self):
        assert ScalingOutcome.OVER_PROVISIONED == "over_provisioned"

    def test_outcome_under_provisioned(self):
        assert ScalingOutcome.UNDER_PROVISIONED == "under_provisioned"

    def test_outcome_delayed(self):
        assert ScalingOutcome.DELAYED == "delayed"

    def test_outcome_failed(self):
        assert ScalingOutcome.FAILED == "failed"

    def test_trigger_cpu(self):
        assert ScalingTrigger.CPU_THRESHOLD == "cpu_threshold"

    def test_trigger_memory(self):
        assert ScalingTrigger.MEMORY_THRESHOLD == "memory_threshold"

    def test_trigger_request_rate(self):
        assert ScalingTrigger.REQUEST_RATE == "request_rate"

    def test_trigger_schedule(self):
        assert ScalingTrigger.SCHEDULE == "schedule"

    def test_trigger_manual(self):
        assert ScalingTrigger.MANUAL == "manual"


class TestModels:
    def test_event_record_defaults(self):
        r = ScalingEventRecord()
        assert r.id
        assert r.service_name == ""
        assert r.scaling_type == ScalingType.AUTO
        assert r.outcome == ScalingOutcome.OPTIMAL
        assert r.trigger == ScalingTrigger.CPU_THRESHOLD
        assert r.duration_seconds == 0.0
        assert r.instances_before == 0
        assert r.instances_after == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_inefficiency_defaults(self):
        r = ScalingInefficiency()
        assert r.id
        assert r.service_name == ""
        assert r.inefficiency_type == ScalingOutcome.OVER_PROVISIONED
        assert r.waste_pct == 0.0
        assert r.estimated_cost_waste == 0.0
        assert r.recommendation == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ScalingEfficiencyReport()
        assert r.total_events == 0
        assert r.total_inefficiencies == 0
        assert r.avg_duration_seconds == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.over_provisioned_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordEvent:
    def test_basic(self):
        eng = _engine()
        r = eng.record_event(
            "svc-a",
            outcome=ScalingOutcome.OPTIMAL,
            instances_before=2,
            instances_after=4,
        )
        assert r.service_name == "svc-a"
        assert r.instances_after == 4

    def test_with_trigger(self):
        eng = _engine()
        r = eng.record_event("svc-b", trigger=ScalingTrigger.MEMORY_THRESHOLD)
        assert r.trigger == ScalingTrigger.MEMORY_THRESHOLD

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_event(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        r = eng.record_event("svc-a")
        assert eng.get_event(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_event("svc-a")
        eng.record_event("svc-b")
        assert len(eng.list_events()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_event("svc-a")
        eng.record_event("svc-b")
        results = eng.list_events(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_event("svc-a", scaling_type=ScalingType.HORIZONTAL)
        eng.record_event("svc-b", scaling_type=ScalingType.VERTICAL)
        results = eng.list_events(scaling_type=ScalingType.HORIZONTAL)
        assert len(results) == 1


class TestRecordInefficiency:
    def test_basic(self):
        eng = _engine()
        i = eng.record_inefficiency("svc-a", waste_pct=30.0)
        assert i.service_name == "svc-a"
        assert i.waste_pct == 30.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_inefficiency(f"svc-{i}")
        assert len(eng._inefficiencies) == 2


class TestAnalyzeScalingEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_event("svc-a", outcome=ScalingOutcome.OPTIMAL)
        eng.record_event("svc-a", outcome=ScalingOutcome.FAILED)
        result = eng.analyze_scaling_efficiency("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_events"] == 2
        assert result["optimal_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_scaling_efficiency("ghost")
        assert result["status"] == "no_data"


class TestIdentifyOverProvisioned:
    def test_with_over(self):
        eng = _engine()
        eng.record_event(
            "svc-a",
            outcome=ScalingOutcome.OVER_PROVISIONED,
            instances_before=2,
            instances_after=10,
        )
        eng.record_event("svc-b", outcome=ScalingOutcome.OPTIMAL)
        results = eng.identify_over_provisioned()
        assert len(results) == 1
        assert results[0]["excess"] == 8

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_provisioned() == []


class TestRankByWaste:
    def test_with_data(self):
        eng = _engine()
        eng.record_inefficiency("svc-a", waste_pct=10.0)
        eng.record_inefficiency("svc-b", waste_pct=50.0)
        results = eng.rank_by_waste()
        assert results[0]["waste_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_waste() == []


class TestDetectScalingDelays:
    def test_with_delays(self):
        eng = _engine(max_duration_seconds=300.0)
        eng.record_event("svc-a", duration_seconds=500.0)
        eng.record_event("svc-b", duration_seconds=100.0)
        results = eng.detect_scaling_delays()
        assert len(results) == 1
        assert results[0]["excess_seconds"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.detect_scaling_delays() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_duration_seconds=300.0)
        eng.record_event("svc-a", outcome=ScalingOutcome.OVER_PROVISIONED)
        eng.record_event("svc-b", duration_seconds=500.0)
        eng.record_inefficiency("svc-a")
        report = eng.generate_report()
        assert report.total_events == 2
        assert report.total_inefficiencies == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_events == 0
        assert "meets targets" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_event("svc-a")
        eng.record_inefficiency("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._inefficiencies) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_events"] == 0
        assert stats["total_inefficiencies"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_event("svc-a", scaling_type=ScalingType.AUTO)
        eng.record_event("svc-b", scaling_type=ScalingType.MANUAL)
        eng.record_inefficiency("svc-a")
        stats = eng.get_stats()
        assert stats["total_events"] == 2
        assert stats["total_inefficiencies"] == 1
        assert stats["unique_services"] == 2
