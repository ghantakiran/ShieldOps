"""Tests for shieldops.operations.scaling_advisor — PredictiveScalingAdvisor."""

from __future__ import annotations

from shieldops.operations.scaling_advisor import (
    PredictiveScalingAdvisor,
    ScalingAction,
    ScalingAdvisorReport,
    ScalingConfidence,
    ScalingRecommendation,
    ScalingRecord,
    ScalingTrigger,
)


def _engine(**kw) -> PredictiveScalingAdvisor:
    return PredictiveScalingAdvisor(**kw)


class TestEnums:
    def test_action_scale_up(self):
        assert ScalingAction.SCALE_UP == "scale_up"

    def test_action_scale_down(self):
        assert ScalingAction.SCALE_DOWN == "scale_down"

    def test_action_scale_out(self):
        assert ScalingAction.SCALE_OUT == "scale_out"

    def test_action_scale_in(self):
        assert ScalingAction.SCALE_IN == "scale_in"

    def test_action_no_action(self):
        assert ScalingAction.NO_ACTION == "no_action"

    def test_trigger_cpu_threshold(self):
        assert ScalingTrigger.CPU_THRESHOLD == "cpu_threshold"

    def test_trigger_memory_threshold(self):
        assert ScalingTrigger.MEMORY_THRESHOLD == "memory_threshold"

    def test_trigger_request_rate(self):
        assert ScalingTrigger.REQUEST_RATE == "request_rate"

    def test_trigger_queue_depth(self):
        assert ScalingTrigger.QUEUE_DEPTH == "queue_depth"

    def test_trigger_scheduled(self):
        assert ScalingTrigger.SCHEDULED == "scheduled"

    def test_confidence_high(self):
        assert ScalingConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert ScalingConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ScalingConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ScalingConfidence.SPECULATIVE == "speculative"

    def test_confidence_insufficient_data(self):
        assert ScalingConfidence.INSUFFICIENT_DATA == "insufficient_data"


class TestModels:
    def test_scaling_record_defaults(self):
        r = ScalingRecord()
        assert r.id
        assert r.service_name == ""
        assert r.action == ScalingAction.NO_ACTION
        assert r.trigger == ScalingTrigger.CPU_THRESHOLD
        assert r.confidence == ScalingConfidence.MODERATE
        assert r.confidence_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_scaling_recommendation_defaults(self):
        r = ScalingRecommendation()
        assert r.id
        assert r.service_name == ""
        assert r.action == ScalingAction.NO_ACTION
        assert r.trigger == ScalingTrigger.CPU_THRESHOLD
        assert r.savings_potential == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ScalingAdvisorReport()
        assert r.total_records == 0
        assert r.total_recommendations == 0
        assert r.avg_confidence_pct == 0.0
        assert r.by_action == {}
        assert r.by_trigger == {}
        assert r.low_confidence_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordScaling:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scaling("svc-a", confidence_pct=90.0)
        assert r.service_name == "svc-a"
        assert r.confidence_pct == 90.0

    def test_with_action(self):
        eng = _engine()
        r = eng.record_scaling("svc-b", action=ScalingAction.SCALE_UP)
        assert r.action == ScalingAction.SCALE_UP

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scaling(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetScaling:
    def test_found(self):
        eng = _engine()
        r = eng.record_scaling("svc-a")
        assert eng.get_scaling(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scaling("nonexistent") is None


class TestListScalings:
    def test_list_all(self):
        eng = _engine()
        eng.record_scaling("svc-a")
        eng.record_scaling("svc-b")
        assert len(eng.list_scalings()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_scaling("svc-a")
        eng.record_scaling("svc-b")
        results = eng.list_scalings(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_scaling("svc-a", action=ScalingAction.SCALE_UP)
        eng.record_scaling("svc-b", action=ScalingAction.NO_ACTION)
        results = eng.list_scalings(action=ScalingAction.SCALE_UP)
        assert len(results) == 1


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_recommendation("svc-a", savings_potential=500.0)
        assert rec.service_name == "svc-a"
        assert rec.savings_potential == 500.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_recommendation(f"svc-{i}")
        assert len(eng._recommendations) == 2


class TestAnalyzeScalingPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_scaling("svc-a", confidence_pct=80.0)
        eng.record_scaling("svc-a", confidence_pct=90.0)
        result = eng.analyze_scaling_patterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_confidence_pct"] == 85.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_scaling_patterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyOverProvisioned:
    def test_with_over_provisioned(self):
        eng = _engine()
        eng.record_scaling("svc-a", action=ScalingAction.SCALE_DOWN)
        eng.record_scaling("svc-a", action=ScalingAction.SCALE_DOWN)
        eng.record_scaling("svc-b", action=ScalingAction.SCALE_UP)
        results = eng.identify_over_provisioned()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_provisioned() == []


class TestRankBySavingsPotential:
    def test_with_data(self):
        eng = _engine()
        eng.add_recommendation("svc-a", savings_potential=100.0)
        eng.add_recommendation("svc-b", savings_potential=800.0)
        results = eng.rank_by_savings_potential()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["total_savings_potential"] == 800.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings_potential() == []


class TestDetectScalingAnomalies:
    def test_with_anomalies(self):
        eng = _engine()
        for i in range(5):
            eng.record_scaling("svc-a", confidence_pct=float(50 + i * 10))
        results = eng.detect_scaling_anomalies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["confidence_pattern"] == "increasing"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_scaling_anomalies() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_scaling("svc-a", confidence_pct=30.0, confidence=ScalingConfidence.LOW)
        eng.record_scaling("svc-b", confidence_pct=90.0, confidence=ScalingConfidence.HIGH)
        eng.add_recommendation("svc-a", savings_potential=200.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_recommendations == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_scaling("svc-a")
        eng.add_recommendation("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_scaling("svc-a", action=ScalingAction.SCALE_UP)
        eng.record_scaling("svc-b", action=ScalingAction.SCALE_DOWN)
        eng.add_recommendation("svc-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_services"] == 2
