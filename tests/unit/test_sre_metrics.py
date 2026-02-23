"""Tests for shieldops.analytics.sre_metrics — SREMetricsAggregator."""

from __future__ import annotations

from shieldops.analytics.sre_metrics import (
    AggregationPeriod,
    MetricCategory,
    MetricDataPoint,
    ServiceScorecard,
    SREMetricsAggregator,
)


def _aggregator(**kw) -> SREMetricsAggregator:
    return SREMetricsAggregator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # MetricCategory (5 values)

    def test_metric_category_availability(self):
        assert MetricCategory.AVAILABILITY == "availability"

    def test_metric_category_reliability(self):
        assert MetricCategory.RELIABILITY == "reliability"

    def test_metric_category_performance(self):
        assert MetricCategory.PERFORMANCE == "performance"

    def test_metric_category_deployment(self):
        assert MetricCategory.DEPLOYMENT == "deployment"

    def test_metric_category_cost(self):
        assert MetricCategory.COST == "cost"

    # AggregationPeriod (4 values)

    def test_aggregation_period_hourly(self):
        assert AggregationPeriod.HOURLY == "hourly"

    def test_aggregation_period_daily(self):
        assert AggregationPeriod.DAILY == "daily"

    def test_aggregation_period_weekly(self):
        assert AggregationPeriod.WEEKLY == "weekly"

    def test_aggregation_period_monthly(self):
        assert AggregationPeriod.MONTHLY == "monthly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_metric_datapoint_defaults(self):
        dp = MetricDataPoint(
            service="web",
            category=MetricCategory.AVAILABILITY,
            metric_name="uptime",
            value=99.9,
        )
        assert dp.id
        assert dp.service == "web"
        assert dp.unit == ""
        assert dp.period == AggregationPeriod.DAILY
        assert dp.recorded_at > 0

    def test_service_scorecard_defaults(self):
        card = ServiceScorecard(service="api")
        assert card.service == "api"
        assert card.availability_pct == 0.0
        assert card.mttr_minutes == 0.0
        assert card.error_rate_pct == 0.0
        assert card.deploy_frequency == 0.0
        assert card.cost_per_request == 0.0
        assert card.overall_score == 0.0
        assert card.generated_at > 0


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------


class TestRecordMetric:
    def test_basic_record(self):
        agg = _aggregator()
        dp = agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "uptime",
            99.9,
        )
        assert dp.service == "web"
        assert dp.category == MetricCategory.AVAILABILITY
        assert dp.metric_name == "uptime"
        assert dp.value == 99.9

    def test_record_returns_datapoint_in_store(self):
        agg = _aggregator()
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "uptime",
            99.9,
        )
        metrics = agg.get_metrics()
        assert len(metrics) == 1

    def test_trims_to_max_datapoints(self):
        agg = _aggregator(max_datapoints=3)
        for i in range(5):
            agg.record_metric(
                "web",
                MetricCategory.COST,
                f"m{i}",
                float(i),
            )
        metrics = agg.get_metrics(limit=100)
        assert len(metrics) == 3
        # Oldest two trimmed — values 0,1 gone, 2,3,4 remain
        assert metrics[0].value == 2.0

    def test_accepts_string_category(self):
        agg = _aggregator()
        dp = agg.record_metric(
            "api",
            "performance",
            "latency_p99",
            42.5,
        )
        assert dp.category == MetricCategory.PERFORMANCE

    def test_accepts_string_period(self):
        agg = _aggregator()
        dp = agg.record_metric(
            "api",
            MetricCategory.COST,
            "spend",
            1.5,
            period="monthly",
        )
        assert dp.period == AggregationPeriod.MONTHLY


# ---------------------------------------------------------------------------
# generate_scorecard
# ---------------------------------------------------------------------------


class TestGenerateScorecard:
    def test_scorecard_from_no_data_returns_zeros(self):
        agg = _aggregator()
        card = agg.generate_scorecard("web")
        assert card.service == "web"
        assert card.availability_pct == 0.0
        assert card.mttr_minutes == 0.0
        assert card.error_rate_pct == 0.0
        assert card.deploy_frequency == 0.0
        assert card.cost_per_request == 0.0

    def test_scorecard_from_metrics_uses_latest_values(self):
        agg = _aggregator()
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "avail",
            95.0,
        )
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "avail",
            99.5,
        )
        card = agg.generate_scorecard("web")
        assert card.availability_pct == 99.5

    def test_overall_score_computed_weighted(self):
        import pytest

        agg = _aggregator()
        # availability=100, reliability(mttr)=0, performance(error)=0,
        # deployment=10 (maps to 100), cost=0 (maps to 100)
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "a",
            100.0,
        )
        agg.record_metric(
            "web",
            MetricCategory.RELIABILITY,
            "r",
            0.0,
        )
        agg.record_metric(
            "web",
            MetricCategory.PERFORMANCE,
            "p",
            0.0,
        )
        agg.record_metric(
            "web",
            MetricCategory.DEPLOYMENT,
            "d",
            10.0,
        )
        agg.record_metric(
            "web",
            MetricCategory.COST,
            "c",
            0.0,
        )
        card = agg.generate_scorecard("web")
        # avail: 100*0.30=30
        # mttr: max(0,100-0/14.4)=100 => 100*0.25=25
        # error: max(0,100-0)=100 => 100*0.25=25
        # deploy: min(10*10,100)=100 => 100*0.10=10
        # cost: max(0,100-0*100)=100 => 100*0.10=10
        expected = 30.0 + 25.0 + 25.0 + 10.0 + 10.0
        assert card.overall_score == pytest.approx(expected, abs=0.01)

    def test_scorecard_evicts_at_max_scorecards(self):
        agg = _aggregator(max_scorecards=2)
        agg.generate_scorecard("svc1")
        agg.generate_scorecard("svc2")
        agg.generate_scorecard("svc3")
        cards = agg.list_scorecards()
        assert len(cards) == 2
        services = {c.service for c in cards}
        assert "svc1" not in services

    def test_scorecard_replaces_same_service(self):
        agg = _aggregator(max_scorecards=2)
        agg.generate_scorecard("svc1")
        agg.generate_scorecard("svc1")
        assert len(agg.list_scorecards()) == 1


# ---------------------------------------------------------------------------
# get_scorecard
# ---------------------------------------------------------------------------


class TestGetScorecard:
    def test_returns_none_for_unknown(self):
        agg = _aggregator()
        assert agg.get_scorecard("nope") is None

    def test_returns_cached_scorecard(self):
        agg = _aggregator()
        agg.generate_scorecard("web")
        card = agg.get_scorecard("web")
        assert card is not None
        assert card.service == "web"


# ---------------------------------------------------------------------------
# list_scorecards
# ---------------------------------------------------------------------------


class TestListScorecards:
    def test_lists_all_cached(self):
        agg = _aggregator()
        agg.generate_scorecard("web")
        agg.generate_scorecard("api")
        cards = agg.list_scorecards()
        assert len(cards) == 2
        services = {c.service for c in cards}
        assert services == {"web", "api"}

    def test_empty_when_none_generated(self):
        agg = _aggregator()
        assert agg.list_scorecards() == []


# ---------------------------------------------------------------------------
# get_metrics
# ---------------------------------------------------------------------------


class TestGetMetrics:
    def test_filter_by_service(self):
        agg = _aggregator()
        agg.record_metric("web", MetricCategory.COST, "m1", 1.0)
        agg.record_metric("api", MetricCategory.COST, "m2", 2.0)
        results = agg.get_metrics(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_filter_by_category(self):
        agg = _aggregator()
        agg.record_metric("web", MetricCategory.COST, "m1", 1.0)
        agg.record_metric("web", MetricCategory.PERFORMANCE, "m2", 2.0)
        results = agg.get_metrics(category=MetricCategory.COST)
        assert len(results) == 1
        assert results[0].category == MetricCategory.COST

    def test_filter_by_string_category(self):
        agg = _aggregator()
        agg.record_metric("web", MetricCategory.COST, "m1", 1.0)
        agg.record_metric("web", MetricCategory.PERFORMANCE, "m2", 2.0)
        results = agg.get_metrics(category="cost")
        assert len(results) == 1

    def test_respects_limit(self):
        agg = _aggregator()
        for i in range(10):
            agg.record_metric(
                "web",
                MetricCategory.COST,
                f"m{i}",
                float(i),
            )
        results = agg.get_metrics(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------


class TestGetTrend:
    def test_returns_matching_datapoints(self):
        agg = _aggregator()
        agg.record_metric("web", MetricCategory.COST, "latency", 10.0)
        agg.record_metric("web", MetricCategory.COST, "latency", 12.0)
        agg.record_metric("web", MetricCategory.COST, "other", 1.0)
        trend = agg.get_trend("web", "latency")
        assert len(trend) == 2

    def test_trend_respects_limit(self):
        agg = _aggregator()
        for i in range(10):
            agg.record_metric(
                "web",
                MetricCategory.COST,
                "latency",
                float(i),
            )
        trend = agg.get_trend("web", "latency", limit=3)
        assert len(trend) == 3

    def test_trend_empty_for_nonexistent(self):
        agg = _aggregator()
        assert agg.get_trend("web", "nope") == []


# ---------------------------------------------------------------------------
# compare_services
# ---------------------------------------------------------------------------


class TestCompareServices:
    def test_compares_multiple_services(self):
        agg = _aggregator()
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "a",
            99.0,
        )
        agg.record_metric(
            "api",
            MetricCategory.AVAILABILITY,
            "a",
            95.0,
        )
        cards = agg.compare_services(["web", "api"])
        assert len(cards) == 2
        services = {c.service for c in cards}
        assert services == {"web", "api"}

    def test_uses_cached_scorecards_when_available(self):
        agg = _aggregator()
        existing = agg.generate_scorecard("web")
        cards = agg.compare_services(["web"])
        assert len(cards) == 1
        assert cards[0].generated_at == existing.generated_at

    def test_generates_scorecard_for_unknown_service(self):
        agg = _aggregator()
        cards = agg.compare_services(["new-svc"])
        assert len(cards) == 1
        assert cards[0].service == "new-svc"


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        agg = _aggregator()
        stats = agg.get_stats()
        assert stats["total_datapoints"] == 0
        assert stats["total_scorecards"] == 0
        assert stats["services_tracked"] == 0
        assert stats["category_distribution"] == {}

    def test_populated_stats(self):
        agg = _aggregator()
        agg.record_metric("web", MetricCategory.COST, "m1", 1.0)
        agg.record_metric("api", MetricCategory.COST, "m2", 2.0)
        agg.record_metric(
            "web",
            MetricCategory.AVAILABILITY,
            "m3",
            99.0,
        )
        agg.generate_scorecard("web")
        stats = agg.get_stats()
        assert stats["total_datapoints"] == 3
        assert stats["total_scorecards"] == 1
        assert stats["services_tracked"] == 2
        cat_dist = stats["category_distribution"]
        assert cat_dist[MetricCategory.COST] == 2
        assert cat_dist[MetricCategory.AVAILABILITY] == 1
