"""Tests for shieldops.sla.slo_auto_scaler — SLOAutoScaler."""

from __future__ import annotations

from shieldops.sla.slo_auto_scaler import (
    ScaleDirection,
    ScaleOutcome,
    ScalePolicy,
    ScaleRecord,
    ScaleTrigger,
    SLOAutoScaler,
    SLOAutoScalerReport,
)


def _engine(**kw) -> SLOAutoScaler:
    return SLOAutoScaler(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ScaleDirection (5)
    def test_direction_scale_up(self):
        assert ScaleDirection.SCALE_UP == "scale_up"

    def test_direction_scale_down(self):
        assert ScaleDirection.SCALE_DOWN == "scale_down"

    def test_direction_scale_out(self):
        assert ScaleDirection.SCALE_OUT == "scale_out"

    def test_direction_scale_in(self):
        assert ScaleDirection.SCALE_IN == "scale_in"

    def test_direction_no_action(self):
        assert ScaleDirection.NO_ACTION == "no_action"

    # ScaleTrigger (5)
    def test_trigger_burn_rate(self):
        assert ScaleTrigger.BURN_RATE == "burn_rate"

    def test_trigger_error_budget(self):
        assert ScaleTrigger.ERROR_BUDGET == "error_budget"

    def test_trigger_latency(self):
        assert ScaleTrigger.LATENCY == "latency"

    def test_trigger_throughput(self):
        assert ScaleTrigger.THROUGHPUT == "throughput"

    def test_trigger_predictive(self):
        assert ScaleTrigger.PREDICTIVE == "predictive"

    # ScaleOutcome (5)
    def test_outcome_successful(self):
        assert ScaleOutcome.SUCCESSFUL == "successful"

    def test_outcome_partial(self):
        assert ScaleOutcome.PARTIAL == "partial"

    def test_outcome_failed(self):
        assert ScaleOutcome.FAILED == "failed"

    def test_outcome_cooldown(self):
        assert ScaleOutcome.COOLDOWN == "cooldown"

    def test_outcome_rejected(self):
        assert ScaleOutcome.REJECTED == "rejected"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_scale_record_defaults(self):
        r = ScaleRecord()
        assert r.id
        assert r.service_name == ""
        assert r.scale_direction == ScaleDirection.SCALE_UP
        assert r.scale_trigger == ScaleTrigger.BURN_RATE
        assert r.scale_outcome == ScaleOutcome.SUCCESSFUL
        assert r.replica_delta == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_scale_policy_defaults(self):
        r = ScalePolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.scale_direction == ScaleDirection.SCALE_OUT
        assert r.scale_trigger == ScaleTrigger.ERROR_BUDGET
        assert r.cooldown_seconds == 300.0
        assert r.created_at > 0

    def test_slo_auto_scaler_report_defaults(self):
        r = SLOAutoScalerReport()
        assert r.total_scales == 0
        assert r.total_policies == 0
        assert r.success_rate_pct == 0.0
        assert r.by_direction == {}
        assert r.by_outcome == {}
        assert r.failure_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_scale
# -------------------------------------------------------------------


class TestRecordScale:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scale("api-gateway", scale_direction=ScaleDirection.SCALE_UP)
        assert r.service_name == "api-gateway"
        assert r.scale_direction == ScaleDirection.SCALE_UP

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_scale(
            "worker-pool",
            scale_direction=ScaleDirection.SCALE_OUT,
            scale_trigger=ScaleTrigger.LATENCY,
            scale_outcome=ScaleOutcome.FAILED,
            replica_delta=5,
            details="Insufficient capacity",
        )
        assert r.scale_outcome == ScaleOutcome.FAILED
        assert r.scale_trigger == ScaleTrigger.LATENCY
        assert r.replica_delta == 5
        assert r.details == "Insufficient capacity"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scale(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_scale
# -------------------------------------------------------------------


class TestGetScale:
    def test_found(self):
        eng = _engine()
        r = eng.record_scale("api-gateway")
        assert eng.get_scale(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scale("nonexistent") is None


# -------------------------------------------------------------------
# list_scales
# -------------------------------------------------------------------


class TestListScales:
    def test_list_all(self):
        eng = _engine()
        eng.record_scale("svc-a")
        eng.record_scale("svc-b")
        assert len(eng.list_scales()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_scale("svc-a")
        eng.record_scale("svc-b")
        results = eng.list_scales(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_scale_direction(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_direction=ScaleDirection.SCALE_UP)
        eng.record_scale("svc-b", scale_direction=ScaleDirection.SCALE_DOWN)
        results = eng.list_scales(scale_direction=ScaleDirection.SCALE_DOWN)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "burn-rate-scaler",
            scale_direction=ScaleDirection.SCALE_OUT,
            scale_trigger=ScaleTrigger.BURN_RATE,
            cooldown_seconds=600.0,
        )
        assert p.policy_name == "burn-rate-scaler"
        assert p.scale_direction == ScaleDirection.SCALE_OUT
        assert p.cooldown_seconds == 600.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_scaling_efficiency
# -------------------------------------------------------------------


class TestAnalyzeScalingEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.SUCCESSFUL)
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.SUCCESSFUL)
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.FAILED)
        result = eng.analyze_scaling_efficiency("svc-a")
        assert result["success_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_scaling_efficiency("unknown-svc")
        assert result["status"] == "no_data"

    def test_full_success(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.SUCCESSFUL)
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.SUCCESSFUL)
        result = eng.analyze_scaling_efficiency("svc-a")
        assert result["success_rate"] == 100.0


# -------------------------------------------------------------------
# identify_scaling_failures
# -------------------------------------------------------------------


class TestIdentifyScalingFailures:
    def test_with_failures(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.FAILED)
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.REJECTED)
        eng.record_scale("svc-b", scale_outcome=ScaleOutcome.SUCCESSFUL)
        results = eng.identify_scaling_failures()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["failure_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_scaling_failures() == []

    def test_single_failed_not_returned(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.FAILED)
        assert eng.identify_scaling_failures() == []


# -------------------------------------------------------------------
# rank_by_scale_frequency
# -------------------------------------------------------------------


class TestRankByScaleFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.record_scale("svc-a", replica_delta=2)
        eng.record_scale("svc-b", replica_delta=8)
        results = eng.rank_by_scale_frequency()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_replica_delta"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_scale_frequency() == []


# -------------------------------------------------------------------
# detect_scaling_oscillations
# -------------------------------------------------------------------


class TestDetectScalingOscillations:
    def test_with_oscillations(self):
        eng = _engine()
        for _ in range(5):
            eng.record_scale("svc-a")
        eng.record_scale("svc-b")
        results = eng.detect_scaling_oscillations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_scaling_oscillations() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_scale("svc-a")
        assert eng.detect_scaling_oscillations() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_scale("svc-a", scale_outcome=ScaleOutcome.FAILED)
        eng.record_scale("svc-b", scale_outcome=ScaleOutcome.SUCCESSFUL)
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_scales == 2
        assert report.total_policies == 1
        assert report.failure_count == 1
        assert report.by_direction != {}
        assert report.by_outcome != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_scales == 0
        assert report.success_rate_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_scale("svc-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_scales"] == 0
        assert stats["total_policies"] == 0
        assert stats["direction_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_replica_delta=10)
        eng.record_scale("svc-a", scale_direction=ScaleDirection.SCALE_UP)
        eng.record_scale("svc-b", scale_direction=ScaleDirection.SCALE_OUT)
        eng.add_policy("policy-1")
        stats = eng.get_stats()
        assert stats["total_scales"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
        assert stats["max_replica_delta"] == 10
