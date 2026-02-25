"""Tests for shieldops.billing.spot_instance_manager — SpotInstanceManager."""

from __future__ import annotations

from shieldops.billing.spot_instance_manager import (
    FallbackStrategy,
    InstanceStatus,
    InterruptionEvent,
    SpotInstance,
    SpotInstanceManager,
    SpotMarket,
    SpotReport,
)


def _engine(**kw) -> SpotInstanceManager:
    return SpotInstanceManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # InstanceStatus (5)
    def test_status_running(self):
        assert InstanceStatus.RUNNING == "running"

    def test_status_interrupted(self):
        assert InstanceStatus.INTERRUPTED == "interrupted"

    def test_status_migrating(self):
        assert InstanceStatus.MIGRATING == "migrating"

    def test_status_terminated(self):
        assert InstanceStatus.TERMINATED == "terminated"

    def test_status_pending(self):
        assert InstanceStatus.PENDING == "pending"

    # FallbackStrategy (5)
    def test_fallback_on_demand(self):
        assert FallbackStrategy.ON_DEMAND == "on_demand"

    def test_fallback_different_az(self):
        assert FallbackStrategy.DIFFERENT_AZ == "different_az"

    def test_fallback_different_type(self):
        assert FallbackStrategy.DIFFERENT_TYPE == "different_type"

    def test_fallback_scale_down(self):
        assert FallbackStrategy.SCALE_DOWN == "scale_down"

    def test_fallback_queue_work(self):
        assert FallbackStrategy.QUEUE_WORK == "queue_work"

    # SpotMarket (5)
    def test_market_aws_spot(self):
        assert SpotMarket.AWS_SPOT == "aws_spot"

    def test_market_gcp_preemptible(self):
        assert SpotMarket.GCP_PREEMPTIBLE == "gcp_preemptible"

    def test_market_azure_spot(self):
        assert SpotMarket.AZURE_SPOT == "azure_spot"

    def test_market_aws_spot_fleet(self):
        assert SpotMarket.AWS_SPOT_FLEET == "aws_spot_fleet"

    def test_market_gcp_spot(self):
        assert SpotMarket.GCP_SPOT == "gcp_spot"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_spot_instance_defaults(self):
        s = SpotInstance()
        assert s.id
        assert s.instance_id == ""
        assert s.instance_type == ""
        assert s.market == SpotMarket.AWS_SPOT
        assert s.status == InstanceStatus.PENDING
        assert s.hourly_rate == 0.0
        assert s.on_demand_rate == 0.0
        assert s.savings_pct == 0.0
        assert s.fallback_strategy == FallbackStrategy.ON_DEMAND
        assert s.launched_at > 0
        assert s.created_at > 0

    def test_interruption_event_defaults(self):
        e = InterruptionEvent()
        assert e.id
        assert e.spot_id == ""
        assert e.reason == ""
        assert e.warning_seconds == 0
        assert e.fallback_used == FallbackStrategy.ON_DEMAND
        assert e.recovery_success is False
        assert e.occurred_at > 0
        assert e.created_at > 0

    def test_spot_report_defaults(self):
        r = SpotReport()
        assert r.total_instances == 0
        assert r.total_interruptions == 0
        assert r.interruption_rate_pct == 0.0
        assert r.total_savings == 0.0
        assert r.avg_savings_pct == 0.0
        assert r.by_market == {}
        assert r.by_status == {}
        assert r.by_strategy == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_instance
# ---------------------------------------------------------------------------


class TestRegisterInstance:
    def test_basic_register(self):
        eng = _engine()
        inst = eng.register_instance(
            instance_id="i-abc123",
            instance_type="m5.large",
            market=SpotMarket.AWS_SPOT,
            hourly_rate=0.05,
            on_demand_rate=0.10,
        )
        assert inst.instance_id == "i-abc123"
        assert inst.instance_type == "m5.large"
        assert inst.market == SpotMarket.AWS_SPOT
        assert inst.status == InstanceStatus.RUNNING
        assert inst.savings_pct == 50.0

    def test_savings_calculation(self):
        eng = _engine()
        inst = eng.register_instance(
            instance_id="i-001",
            instance_type="c5.xlarge",
            market=SpotMarket.GCP_PREEMPTIBLE,
            hourly_rate=0.03,
            on_demand_rate=0.10,
        )
        assert inst.savings_pct == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_instances=3)
        for i in range(5):
            eng.register_instance(
                instance_id=f"i-{i}",
                instance_type="t3.micro",
                market=SpotMarket.AWS_SPOT,
                hourly_rate=0.01,
                on_demand_rate=0.02,
            )
        assert len(eng._items) == 3


# ---------------------------------------------------------------------------
# get_instance
# ---------------------------------------------------------------------------


class TestGetInstance:
    def test_found(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-001",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        result = eng.get_instance(inst.id)
        assert result is not None
        assert result.instance_id == "i-001"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_instance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_instances
# ---------------------------------------------------------------------------


class TestListInstances:
    def test_list_all(self):
        eng = _engine()
        eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "n1-standard",
            SpotMarket.GCP_PREEMPTIBLE,
            0.03,
            0.08,
        )
        assert len(eng.list_instances()) == 2

    def test_filter_by_market(self):
        eng = _engine()
        eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "n1-std",
            SpotMarket.GCP_PREEMPTIBLE,
            0.03,
            0.08,
        )
        results = eng.list_instances(
            market=SpotMarket.AWS_SPOT,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        results = eng.list_instances(
            status=InstanceStatus.INTERRUPTED,
        )
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_interruption
# ---------------------------------------------------------------------------


class TestRecordInterruption:
    def test_basic_interruption(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        event = eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        assert event is not None
        assert event.spot_id == inst.id
        assert event.reason == "capacity"
        assert event.warning_seconds == 120
        assert inst.status == InstanceStatus.INTERRUPTED

    def test_not_found(self):
        eng = _engine()
        assert (
            eng.record_interruption(
                "bad",
                "capacity",
                120,
            )
            is None
        )

    def test_multiple_interruptions(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        eng.record_interruption(
            inst.id,
            "price",
            60,
        )
        assert len(eng._interruptions) == 2


# ---------------------------------------------------------------------------
# execute_fallback
# ---------------------------------------------------------------------------


class TestExecuteFallback:
    def test_successful_fallback(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        result = eng.execute_fallback(
            inst.id,
            FallbackStrategy.DIFFERENT_AZ,
        )
        assert result is not None
        assert result.status == InstanceStatus.MIGRATING
        assert result.fallback_strategy == (FallbackStrategy.DIFFERENT_AZ)

    def test_not_found(self):
        eng = _engine()
        assert (
            eng.execute_fallback(
                "bad",
                FallbackStrategy.ON_DEMAND,
            )
            is None
        )


# ---------------------------------------------------------------------------
# calculate_savings
# ---------------------------------------------------------------------------


class TestCalculateSavings:
    def test_total_savings(self):
        eng = _engine()
        eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "c5.xlarge",
            SpotMarket.GCP_PREEMPTIBLE,
            0.03,
            0.08,
        )
        savings = eng.calculate_savings()
        assert savings["total_hourly_savings"] == 0.10
        assert savings["instance_count"] == 2
        assert len(savings["by_market"]) == 2

    def test_empty(self):
        eng = _engine()
        savings = eng.calculate_savings()
        assert savings["total_hourly_savings"] == 0.0


# ---------------------------------------------------------------------------
# predict_interruption_risk
# ---------------------------------------------------------------------------


class TestPredictInterruptionRisk:
    def test_low_risk(self):
        eng = _engine()
        eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        risk = eng.predict_interruption_risk("m5.large")
        assert risk["risk_level"] == "low"
        assert risk["total_instances"] == 1

    def test_high_risk(self):
        eng = _engine()
        for i in range(3):
            inst = eng.register_instance(
                f"i-{i}",
                "t3.micro",
                SpotMarket.AWS_SPOT,
                0.01,
                0.02,
            )
            eng.record_interruption(
                inst.id,
                "capacity",
                120,
            )
        risk = eng.predict_interruption_risk("t3.micro")
        assert risk["risk_level"] == "high"
        assert risk["interruption_rate_pct"] == 100.0

    def test_unknown_type(self):
        eng = _engine()
        risk = eng.predict_interruption_risk("unknown")
        assert risk["total_instances"] == 0
        assert risk["risk_level"] == "low"


# ---------------------------------------------------------------------------
# identify_optimal_markets
# ---------------------------------------------------------------------------


class TestIdentifyOptimalMarkets:
    def test_ranks_by_savings(self):
        eng = _engine()
        eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "n1-std",
            SpotMarket.GCP_PREEMPTIBLE,
            0.02,
            0.10,
        )
        ranked = eng.identify_optimal_markets()
        assert len(ranked) == 2
        assert ranked[0]["market"] == "gcp_preemptible"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_optimal_markets() == []


# ---------------------------------------------------------------------------
# generate_spot_report
# ---------------------------------------------------------------------------


class TestGenerateSpotReport:
    def test_basic_report(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.register_instance(
            "i-2",
            "c5.xlarge",
            SpotMarket.GCP_PREEMPTIBLE,
            0.03,
            0.08,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        report = eng.generate_spot_report()
        assert report.total_instances == 2
        assert report.total_interruptions == 1
        assert report.total_savings > 0
        assert report.avg_savings_pct > 0
        assert len(report.by_market) == 2
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_spot_report()
        assert report.total_instances == 0
        assert report.total_interruptions == 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        assert len(eng._items) == 1
        assert len(eng._interruptions) == 1
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._interruptions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_instances"] == 0
        assert stats["total_interruptions"] == 0
        assert stats["market_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        inst = eng.register_instance(
            "i-1",
            "m5.large",
            SpotMarket.AWS_SPOT,
            0.05,
            0.10,
        )
        eng.record_interruption(
            inst.id,
            "capacity",
            120,
        )
        stats = eng.get_stats()
        assert stats["total_instances"] == 1
        assert stats["total_interruptions"] == 1
        assert stats["max_instances"] == 100000
        assert stats["min_savings_pct"] == 30.0
