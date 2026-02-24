"""Tests for shieldops.sla.slo_advisor — SLOTargetAdvisor."""

from __future__ import annotations

import random

from shieldops.sla.slo_advisor import (
    AdvisorReport,
    BudgetPolicyAction,
    PerformanceSample,
    SLOMetricType,
    SLORecommendation,
    SLOTargetAdvisor,
    TargetConfidence,
)


def _engine(**kw) -> SLOTargetAdvisor:
    return SLOTargetAdvisor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # SLOMetricType (5)
    def test_metric_availability(self):
        assert SLOMetricType.AVAILABILITY == "availability"

    def test_metric_latency(self):
        assert SLOMetricType.LATENCY == "latency"

    def test_metric_throughput(self):
        assert SLOMetricType.THROUGHPUT == "throughput"

    def test_metric_error_rate(self):
        assert SLOMetricType.ERROR_RATE == "error_rate"

    def test_metric_saturation(self):
        assert SLOMetricType.SATURATION == "saturation"

    # TargetConfidence (4)
    def test_confidence_high(self):
        assert TargetConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert TargetConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert TargetConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert TargetConfidence.SPECULATIVE == "speculative"

    # BudgetPolicyAction (5)
    def test_action_alert(self):
        assert BudgetPolicyAction.ALERT == "alert"

    def test_action_throttle(self):
        assert BudgetPolicyAction.THROTTLE == "throttle"

    def test_action_freeze_deploys(self):
        assert BudgetPolicyAction.FREEZE_DEPLOYS == "freeze_deploys"

    def test_action_page_oncall(self):
        assert BudgetPolicyAction.PAGE_ONCALL == "page_oncall"

    def test_action_auto_rollback(self):
        assert BudgetPolicyAction.AUTO_ROLLBACK == "auto_rollback"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_performance_sample_defaults(self):
        s = PerformanceSample()
        assert s.id
        assert s.service == ""
        assert s.metric_type == SLOMetricType.AVAILABILITY
        assert s.value == 0.0
        assert s.unit == ""

    def test_slo_recommendation_defaults(self):
        rec = SLORecommendation()
        assert rec.id
        assert rec.service == ""
        assert rec.metric_type == SLOMetricType.AVAILABILITY
        assert rec.recommended_target == 0.0
        assert rec.confidence == TargetConfidence.SPECULATIVE
        assert rec.reasoning == ""

    def test_advisor_report_defaults(self):
        report = AdvisorReport()
        assert report.total_services == 0
        assert report.total_samples == 0
        assert report.recommendations_count == 0
        assert report.budget_policies == []
        assert report.service_readiness == {}


# ---------------------------------------------------------------------------
# record_sample
# ---------------------------------------------------------------------------


class TestRecordSample:
    def test_basic_record(self):
        eng = _engine()
        s = eng.record_sample(
            service="api-gateway",
            metric_type=SLOMetricType.LATENCY,
            value=150.0,
            unit="ms",
        )
        assert s.service == "api-gateway"
        assert s.metric_type == SLOMetricType.LATENCY
        assert s.value == 150.0
        assert s.unit == "ms"

    def test_eviction_at_max(self):
        eng = _engine(max_samples=3)
        for i in range(5):
            eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=float(i))
        assert len(eng._samples) == 3


# ---------------------------------------------------------------------------
# get_sample
# ---------------------------------------------------------------------------


class TestGetSample:
    def test_found(self):
        eng = _engine()
        s = eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=100.0)
        assert eng.get_sample(s.id) is not None
        assert eng.get_sample(s.id).value == 100.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_sample("nonexistent") is None


# ---------------------------------------------------------------------------
# list_samples
# ---------------------------------------------------------------------------


class TestListSamples:
    def test_list_all(self):
        eng = _engine()
        eng.record_sample(service="svc-a", metric_type=SLOMetricType.LATENCY, value=10.0)
        eng.record_sample(service="svc-b", metric_type=SLOMetricType.AVAILABILITY, value=99.9)
        assert len(eng.list_samples()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_sample(service="svc-a", metric_type=SLOMetricType.LATENCY, value=10.0)
        eng.record_sample(service="svc-b", metric_type=SLOMetricType.LATENCY, value=20.0)
        results = eng.list_samples(service="svc-a")
        assert len(results) == 1
        assert results[0].service == "svc-a"

    def test_filter_by_metric_type(self):
        eng = _engine()
        eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=10.0)
        eng.record_sample(service="svc", metric_type=SLOMetricType.AVAILABILITY, value=99.9)
        results = eng.list_samples(metric_type=SLOMetricType.AVAILABILITY)
        assert len(results) == 1
        assert results[0].metric_type == SLOMetricType.AVAILABILITY


# ---------------------------------------------------------------------------
# recommend_target
# ---------------------------------------------------------------------------


class TestRecommendTarget:
    def test_high_confidence_with_enough_data(self):
        eng = _engine(min_sample_count=100)
        random.seed(42)
        # Record 120 latency samples between 50ms and 250ms
        for _ in range(120):
            eng.record_sample(
                service="api",
                metric_type=SLOMetricType.LATENCY,
                value=random.uniform(50.0, 250.0),  # noqa: S311
            )
        rec = eng.recommend_target("api", SLOMetricType.LATENCY)
        assert rec is not None
        assert rec.confidence == TargetConfidence.HIGH
        assert rec.current_p50 > 0.0
        assert rec.current_p99 > 0.0
        # Latency target = p99 * 1.1
        assert rec.recommended_target == round(rec.current_p99 * 1.1, 4)

    def test_low_confidence_with_few_data(self):
        eng = _engine()
        for v in [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0]:
            eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=v)
        rec = eng.recommend_target("svc", SLOMetricType.LATENCY)
        assert rec is not None
        assert rec.confidence == TargetConfidence.LOW

    def test_no_data_returns_none(self):
        eng = _engine()
        assert eng.recommend_target("nonexistent", SLOMetricType.LATENCY) is None


# ---------------------------------------------------------------------------
# recommend_all_targets
# ---------------------------------------------------------------------------


class TestRecommendAllTargets:
    def test_basic(self):
        eng = _engine()
        for _ in range(5):
            eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=100.0)
            eng.record_sample(service="svc", metric_type=SLOMetricType.AVAILABILITY, value=99.9)
        recs = eng.recommend_all_targets("svc")
        assert len(recs) == 2
        metric_types = {r.metric_type for r in recs}
        assert SLOMetricType.LATENCY in metric_types
        assert SLOMetricType.AVAILABILITY in metric_types


# ---------------------------------------------------------------------------
# suggest_budget_policy
# ---------------------------------------------------------------------------


class TestSuggestBudgetPolicy:
    def test_low_variance_alert_only(self):
        eng = _engine()
        # Very consistent values => low CV => only ALERT action
        for v in [100.0, 100.1, 99.9, 100.0, 100.2, 99.8, 100.0, 100.1, 99.9, 100.0]:
            eng.record_sample(service="stable-svc", metric_type=SLOMetricType.LATENCY, value=v)
        policies = eng.suggest_budget_policy("stable-svc")
        assert len(policies) >= 1
        latency_policy = [p for p in policies if p["metric_type"] == "latency"][0]
        assert latency_policy["risk_level"] == "low"
        assert BudgetPolicyAction.ALERT.value in latency_policy["actions"]

    def test_high_variance_aggressive_policy(self):
        eng = _engine()
        # Very spread out values => high CV => PAGE_ONCALL + FREEZE_DEPLOYS
        for v in [10.0, 500.0, 20.0, 480.0, 15.0, 510.0, 25.0, 490.0, 10.0, 505.0]:
            eng.record_sample(service="unstable-svc", metric_type=SLOMetricType.LATENCY, value=v)
        policies = eng.suggest_budget_policy("unstable-svc")
        assert len(policies) >= 1
        latency_policy = [p for p in policies if p["metric_type"] == "latency"][0]
        assert latency_policy["risk_level"] == "high"
        assert BudgetPolicyAction.PAGE_ONCALL.value in latency_policy["actions"]
        assert BudgetPolicyAction.FREEZE_DEPLOYS.value in latency_policy["actions"]


# ---------------------------------------------------------------------------
# analyze_historical_performance
# ---------------------------------------------------------------------------


class TestAnalyzeHistoricalPerformance:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_historical_performance("no-svc")
        assert result == {}

    def test_with_data(self):
        eng = _engine()
        for v in [100.0, 200.0, 300.0]:
            eng.record_sample(service="api", metric_type=SLOMetricType.LATENCY, value=v)
        result = eng.analyze_historical_performance("api")
        assert "latency" in result
        assert result["latency"]["sample_count"] == 3
        assert result["latency"]["min"] == 100.0
        assert result["latency"]["max"] == 300.0
        assert result["latency"]["p50"] > 0.0


# ---------------------------------------------------------------------------
# compare_targets
# ---------------------------------------------------------------------------


class TestCompareTargets:
    def test_basic_comparison(self):
        eng = _engine()
        for _ in range(5):
            eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=100.0)
        proposed = {"latency": 200.0}
        result = eng.compare_targets("svc", proposed)
        assert "latency" in result
        assert result["latency"]["proposed"] == 200.0
        assert result["latency"]["recommended"] is not None
        assert result["latency"]["verdict"] in ("aligned", "aggressive", "conservative")


# ---------------------------------------------------------------------------
# generate_advisor_report
# ---------------------------------------------------------------------------


class TestGenerateAdvisorReport:
    def test_basic_report(self):
        eng = _engine(min_sample_count=100)
        for _ in range(5):
            eng.record_sample(service="api", metric_type=SLOMetricType.LATENCY, value=100.0)
        report = eng.generate_advisor_report()
        assert report.total_services == 1
        assert report.total_samples == 5
        assert "api" in report.service_readiness
        # 5 samples < 10 min for "limited" => "insufficient"
        assert report.service_readiness["api"] == "insufficient"


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.record_sample(service="svc", metric_type=SLOMetricType.LATENCY, value=100.0)
        eng.recommend_target("svc", SLOMetricType.LATENCY)
        assert len(eng._samples) > 0
        assert len(eng._recommendations) > 0
        eng.clear_data()
        assert len(eng._samples) == 0
        assert len(eng._recommendations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_samples"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["unique_services"] == 0
        assert stats["unique_metric_types"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_sample(service="api", metric_type=SLOMetricType.LATENCY, value=100.0)
        eng.record_sample(service="web", metric_type=SLOMetricType.AVAILABILITY, value=99.9)
        stats = eng.get_stats()
        assert stats["total_samples"] == 2
        assert stats["unique_services"] == 2
        assert stats["unique_metric_types"] == 2
        assert "api" in stats["services"]
        assert "latency" in stats["metric_types"]
