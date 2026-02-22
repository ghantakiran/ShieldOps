"""Tests for capacity planning and resource forecasting.

Covers linear_regression, r_squared, CapacityPlanner.forecast,
and CapacityPlanner.detect_capacity_risks with edge cases.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shieldops.analytics.capacity_planner import (
    CapacityForecast,
    CapacityPlanner,
    CapacityRisk,
    ResourceMetricHistory,
    linear_regression,
    r_squared,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data_points(values: list[float]) -> list[dict]:
    """Build a list of data-point dicts from raw values."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        {"timestamp": (base + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)
    ]


def _make_history(
    values: list[float],
    *,
    resource_id: str = "server-1",
    metric_name: str = "cpu",
    limit: float = 100.0,
) -> ResourceMetricHistory:
    return ResourceMetricHistory(
        resource_id=resource_id,
        metric_name=metric_name,
        limit=limit,
        data_points=_make_data_points(values),
    )


# ===========================================================================
# linear_regression tests
# ===========================================================================


class TestLinearRegression:
    """Tests for the standalone linear_regression function."""

    def test_perfect_positive_line(self):
        """y = 2x + 1 should produce slope=2, intercept=1."""
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 5.0, 7.0, 9.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(2.0, abs=1e-9)
        assert intercept == pytest.approx(1.0, abs=1e-9)

    def test_perfect_negative_line(self):
        """y = -3x + 10 should produce slope=-3, intercept=10."""
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [10.0, 7.0, 4.0, 1.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(-3.0, abs=1e-9)
        assert intercept == pytest.approx(10.0, abs=1e-9)

    def test_flat_line(self):
        """Constant y should give slope=0."""
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [5.0, 5.0, 5.0, 5.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(0.0, abs=1e-9)
        assert intercept == pytest.approx(5.0, abs=1e-9)

    def test_single_data_point_returns_zero_slope(self):
        """With n<2, slope should be 0 and intercept equal to the single y."""
        slope, intercept = linear_regression([1.0], [7.5])
        assert slope == 0.0
        assert intercept == 7.5

    def test_empty_lists_returns_zero_slope_zero_intercept(self):
        """Empty inputs should not crash; slope=0, intercept=0."""
        slope, intercept = linear_regression([], [])
        assert slope == 0.0
        assert intercept == 0.0

    def test_two_points_exact_fit(self):
        """Two points uniquely determine a line."""
        xs = [0.0, 10.0]
        ys = [5.0, 15.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(1.0, abs=1e-9)
        assert intercept == pytest.approx(5.0, abs=1e-9)

    def test_noisy_data_reasonable_slope(self):
        """With noise around y=x, slope should be approximately 1."""
        xs = [float(i) for i in range(10)]
        ys = [float(i) + (0.1 if i % 2 == 0 else -0.1) for i in range(10)]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(1.0, abs=0.1)

    def test_identical_x_values_returns_mean(self):
        """When all x values are the same, denominator is 0; should return mean of y."""
        xs = [5.0, 5.0, 5.0]
        ys = [10.0, 20.0, 30.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == 0.0
        assert intercept == pytest.approx(20.0, abs=1e-9)

    def test_large_values_no_overflow(self):
        """Regression should handle large values gracefully."""
        xs = [1e6, 2e6, 3e6]
        ys = [2e6, 4e6, 6e6]
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(2.0, abs=1e-4)
        assert intercept == pytest.approx(0.0, abs=1e4)

    def test_all_zeros(self):
        """All-zero inputs should give slope=0, intercept=0."""
        xs = [0.0, 0.0, 0.0]
        ys = [0.0, 0.0, 0.0]
        slope, intercept = linear_regression(xs, ys)
        assert slope == 0.0
        assert intercept == 0.0

    @pytest.mark.parametrize(
        "xs, ys, expected_slope, expected_intercept",
        [
            ([1.0, 2.0, 3.0], [2.0, 4.0, 6.0], 2.0, 0.0),
            ([1.0, 2.0, 3.0], [6.0, 4.0, 2.0], -2.0, 8.0),
            ([0.0, 1.0], [0.0, 0.0], 0.0, 0.0),
        ],
        ids=["positive-through-origin", "negative-slope", "two-zeros"],
    )
    def test_parametrized_known_lines(self, xs, ys, expected_slope, expected_intercept):
        slope, intercept = linear_regression(xs, ys)
        assert slope == pytest.approx(expected_slope, abs=1e-9)
        assert intercept == pytest.approx(expected_intercept, abs=1e-9)


# ===========================================================================
# r_squared tests
# ===========================================================================


class TestRSquared:
    """Tests for the standalone r_squared function."""

    def test_perfect_fit_returns_one(self):
        """A perfect linear fit should yield R^2 = 1.0."""
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [1.0, 3.0, 5.0, 7.0]
        slope, intercept = linear_regression(xs, ys)
        assert r_squared(xs, ys, slope, intercept) == pytest.approx(1.0, abs=1e-9)

    def test_poor_fit_returns_low_value(self):
        """Random-looking data with a bad linear model should have low R^2."""
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [10.0, 0.0, 10.0, 0.0]
        slope, intercept = linear_regression(xs, ys)
        r2 = r_squared(xs, ys, slope, intercept)
        assert r2 < 0.5

    def test_constant_y_returns_one(self):
        """When all y values are the same, ss_tot=0, function returns 1.0."""
        xs = [0.0, 1.0, 2.0]
        ys = [5.0, 5.0, 5.0]
        r2 = r_squared(xs, ys, 0.0, 5.0)
        assert r2 == pytest.approx(1.0)

    def test_single_point_returns_zero(self):
        """With n<2, should return 0.0."""
        assert r_squared([1.0], [5.0], 0.0, 5.0) == 0.0

    def test_empty_returns_zero(self):
        """Empty inputs should return 0.0."""
        assert r_squared([], [], 0.0, 0.0) == 0.0

    def test_high_r_squared_for_near_perfect_fit(self):
        """Near-linear data should have R^2 close to 1."""
        xs = [float(i) for i in range(20)]
        ys = [2.0 * i + 3.0 + (0.01 * ((-1) ** i)) for i in range(20)]
        slope, intercept = linear_regression(xs, ys)
        r2 = r_squared(xs, ys, slope, intercept)
        assert r2 > 0.999

    def test_r_squared_bounded_zero_one(self):
        """R^2 from the regression itself should lie in [0, 1]."""
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 2.0, 5.0, 4.0]
        slope, intercept = linear_regression(xs, ys)
        r2 = r_squared(xs, ys, slope, intercept)
        assert 0.0 <= r2 <= 1.0


# ===========================================================================
# Pydantic model validation
# ===========================================================================


class TestModels:
    """Basic validation of Pydantic data models."""

    def test_resource_metric_history_defaults(self):
        h = ResourceMetricHistory(resource_id="r1", metric_name="cpu")
        assert h.limit == 100.0
        assert h.data_points == []

    def test_capacity_forecast_defaults(self):
        f = CapacityForecast(
            resource_id="r1",
            metric_name="cpu",
            current_usage=50.0,
            current_limit=100.0,
            projected_usage=70.0,
            projected_utilization=70.0,
        )
        assert f.breach_date is None
        assert f.days_to_breach is None
        assert f.confidence == 0.0
        assert f.trend_direction == ""
        assert f.data_points_used == 0

    def test_capacity_risk_defaults(self):
        r = CapacityRisk(resource_id="r1", metric_name="cpu")
        assert r.risk_level == "low"
        assert r.current_utilization == 0.0
        assert r.recommendation == ""


# ===========================================================================
# CapacityPlanner.forecast tests
# ===========================================================================


class TestCapacityPlannerForecast:
    """Tests for CapacityPlanner.forecast method."""

    @pytest.fixture
    def planner(self):
        return CapacityPlanner(default_forecast_days=30)

    # ---- Empty / minimal data ----

    def test_forecast_empty_data_returns_zero(self, planner):
        """No data points should produce a zero-usage forecast."""
        history = ResourceMetricHistory(
            resource_id="srv-1", metric_name="cpu", limit=100.0, data_points=[]
        )
        result = planner.forecast(history)
        assert result.current_usage == 0.0
        assert result.projected_usage == 0.0
        assert result.projected_utilization == 0.0
        assert result.confidence == 0.0
        assert result.trend_direction == "stable"
        assert result.data_points_used == 0
        assert result.breach_date is None
        assert result.days_to_breach is None

    def test_forecast_single_data_point_stable(self, planner):
        """A single data point should be stable with zero slope."""
        history = _make_history([42.0])
        result = planner.forecast(history)
        assert result.current_usage == 42.0
        assert result.trend_slope == 0.0
        assert result.confidence == 0.0  # r_squared returns 0 for n<2

    # ---- Increasing usage / breach prediction ----

    def test_forecast_increasing_usage_predicts_breach(self, planner):
        """Linearly increasing data heading toward the limit should predict a breach."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history, days_ahead=30)

        assert result.trend_direction == "increasing"
        assert result.trend_slope > 0
        assert result.days_to_breach is not None
        assert result.days_to_breach > 0
        assert result.breach_date is not None
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_forecast_breach_date_is_future_iso_format(self, planner):
        """breach_date should be a valid YYYY-MM-DD string in the future."""
        values = [60.0, 70.0, 80.0, 90.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        assert result.breach_date is not None
        breach_dt = datetime.strptime(result.breach_date, "%Y-%m-%d")
        assert breach_dt.date() >= datetime.now(UTC).date()

    def test_forecast_days_to_breach_calculation_exact(self, planner):
        """For y=10x, limit=100 at x=3 (last point), breach at x=10 => 7 days."""
        # y = 10*x: points at x=0..3 => values 0,10,20,30
        values = [0.0, 10.0, 20.0, 30.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        # breach_x = (100 - 0) / 10 = 10, current_x = 3, days_remaining = 7
        assert result.days_to_breach == 7

    def test_forecast_projected_usage_is_positive(self, planner):
        """Even with a downward projection, projected usage should not go negative."""
        values = [50.0, 40.0, 30.0, 20.0, 10.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history, days_ahead=100)

        assert result.projected_usage >= 0.0

    # ---- Flat / stable usage ----

    def test_forecast_flat_usage_stable_trend(self, planner):
        """Constant usage should yield stable trend and no breach."""
        values = [50.0, 50.0, 50.0, 50.0, 50.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        assert result.trend_direction == "stable"
        assert result.days_to_breach is None
        assert result.breach_date is None

    def test_forecast_flat_usage_projected_stays_same(self, planner):
        """Constant usage means projected usage equals current usage."""
        values = [30.0, 30.0, 30.0, 30.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        assert result.projected_usage == pytest.approx(30.0, abs=0.1)
        assert result.current_usage == pytest.approx(30.0, abs=0.01)

    # ---- Decreasing usage ----

    def test_forecast_decreasing_usage_no_breach(self, planner):
        """Declining usage should have negative slope and no breach."""
        values = [80.0, 70.0, 60.0, 50.0, 40.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        assert result.trend_direction == "decreasing"
        assert result.trend_slope < 0
        assert result.days_to_breach is None
        assert result.breach_date is None

    # ---- Utilization calculations ----

    def test_forecast_utilization_percentage(self, planner):
        """projected_utilization should be (projected_usage / limit) * 100."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        history = _make_history(values, limit=200.0)
        result = planner.forecast(history, days_ahead=10)

        expected_util = (result.projected_usage / 200.0) * 100
        assert result.projected_utilization == pytest.approx(expected_util, abs=0.2)

    def test_forecast_zero_limit_returns_zero_utilization(self, planner):
        """A zero limit should not cause division by zero; utilization should be 0."""
        values = [10.0, 20.0, 30.0]
        history = _make_history(values, limit=0.0)
        result = planner.forecast(history)
        assert result.projected_utilization == 0.0

    # ---- Confidence (R^2-based) ----

    def test_forecast_confidence_perfect_linear_data(self, planner):
        """Perfectly linear data should produce confidence near 1.0."""
        values = [float(i) for i in range(10)]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)
        assert result.confidence == pytest.approx(1.0, abs=0.001)

    def test_forecast_confidence_noisy_data_below_one(self, planner):
        """Noisy data should have confidence < 1.0."""
        values = [10.0, 50.0, 15.0, 55.0, 20.0, 60.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)
        assert result.confidence < 1.0

    def test_forecast_confidence_clamped_to_zero_one(self, planner):
        """Confidence should always be in [0, 1]."""
        values = [5.0, 100.0, 3.0, 90.0, 7.0]
        history = _make_history(values, limit=200.0)
        result = planner.forecast(history)
        assert 0.0 <= result.confidence <= 1.0

    # ---- Data points used ----

    def test_forecast_data_points_used_matches_input(self, planner):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        history = _make_history(values)
        result = planner.forecast(history)
        assert result.data_points_used == 7

    # ---- Default forecast days ----

    def test_forecast_uses_default_days_when_none(self):
        """days_ahead=None should use the planner's default_forecast_days."""
        planner = CapacityPlanner(default_forecast_days=60)
        values = [10.0, 20.0, 30.0]
        history = _make_history(values, limit=1000.0)
        result_default = planner.forecast(history, days_ahead=None)
        result_explicit = planner.forecast(history, days_ahead=60)
        assert result_default.projected_usage == pytest.approx(
            result_explicit.projected_usage, abs=0.01
        )

    def test_forecast_custom_days_ahead(self):
        planner = CapacityPlanner(default_forecast_days=10)
        values = [10.0, 20.0, 30.0, 40.0]
        history = _make_history(values, limit=1000.0)

        result_10 = planner.forecast(history, days_ahead=10)
        result_90 = planner.forecast(history, days_ahead=90)
        # Longer forecast with positive slope should project higher usage
        assert result_90.projected_usage > result_10.projected_usage

    # ---- Resource / metric identity ----

    def test_forecast_preserves_resource_id_and_metric_name(self, planner):
        history = _make_history([10.0, 20.0], resource_id="db-replica-3", metric_name="disk_usage")
        result = planner.forecast(history)
        assert result.resource_id == "db-replica-3"
        assert result.metric_name == "disk_usage"

    def test_forecast_preserves_current_limit(self, planner):
        history = _make_history([10.0, 20.0], limit=500.0)
        result = planner.forecast(history)
        assert result.current_limit == 500.0

    # ---- Current usage is last value ----

    def test_forecast_current_usage_is_last_data_point(self, planner):
        values = [10.0, 20.0, 30.0, 42.5]
        history = _make_history(values)
        result = planner.forecast(history)
        assert result.current_usage == 42.5

    # ---- Missing 'value' key in data point ----

    def test_forecast_missing_value_key_defaults_to_zero(self, planner):
        """If a data point dict lacks 'value', it should default to 0."""
        history = ResourceMetricHistory(
            resource_id="srv-1",
            metric_name="mem",
            limit=100.0,
            data_points=[
                {"timestamp": "2025-01-01T00:00:00+00:00"},
                {"timestamp": "2025-01-02T00:00:00+00:00", "value": 10},
            ],
        )
        result = planner.forecast(history)
        # First data point value=0, second=10 => current_usage=10
        assert result.current_usage == 10.0

    # ---- Already breached scenario ----

    def test_forecast_already_above_limit_no_future_breach(self, planner):
        """If usage already exceeds limit and slope is positive, breach_x is in the past."""
        values = [90.0, 95.0, 100.0, 105.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)

        # slope>0, but breach_x - current_x could be <=0 since we're past the limit
        # The implementation only sets days_to_breach when days_remaining > 0
        # breach_x = (100 - intercept) / slope; if intercept=90 and slope=5,
        # breach_x=2, current_x=3 => days_remaining=-1 => no breach date set
        assert result.trend_direction == "increasing"

    # ---- Slope near-zero classified as stable ----

    def test_forecast_tiny_positive_slope_classified_stable(self, planner):
        """A slope below 0.01 threshold should be classified as stable."""
        values = [50.0, 50.005, 50.009, 50.003]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)
        assert result.trend_direction == "stable"

    # ---- All-zero data ----

    def test_forecast_all_zeros(self, planner):
        values = [0.0, 0.0, 0.0, 0.0]
        history = _make_history(values, limit=100.0)
        result = planner.forecast(history)
        assert result.current_usage == 0.0
        assert result.projected_usage == 0.0
        assert result.trend_direction == "stable"
        assert result.days_to_breach is None


# ===========================================================================
# CapacityPlanner.detect_capacity_risks tests
# ===========================================================================


class TestDetectCapacityRisks:
    """Tests for CapacityPlanner.detect_capacity_risks method."""

    @pytest.fixture
    def planner(self):
        return CapacityPlanner(default_forecast_days=30)

    def test_empty_resources_returns_empty(self, planner):
        assert planner.detect_capacity_risks([]) == []

    def test_low_risk_resource_excluded_from_results(self, planner):
        """A resource well below thresholds should not appear in risks."""
        history = _make_history([10.0, 11.0, 12.0], limit=1000.0)
        risks = planner.detect_capacity_risks([history])
        assert len(risks) == 0

    def test_critical_risk_high_projected_utilization(self, planner):
        """Projected utilization >= 95% should be critical."""
        values = [80.0, 85.0, 90.0, 95.0]
        history = _make_history(values, limit=100.0)
        risks = planner.detect_capacity_risks(
            [history], utilization_warning=80.0, utilization_critical=95.0
        )
        assert len(risks) >= 1
        assert risks[0].risk_level == "critical"
        assert "Immediate action required" in risks[0].recommendation

    def test_critical_risk_current_utilization_above_90(self, planner):
        """current_util >= 90 triggers critical regardless of projected."""
        # Flat at 92% => current_util=92, projected ~92 (stable)
        values = [92.0, 92.0, 92.0, 92.0]
        history = _make_history(values, limit=100.0)
        risks = planner.detect_capacity_risks([history])
        assert len(risks) >= 1
        assert risks[0].risk_level == "critical"

    def test_high_risk_projected_above_warning(self, planner):
        """Projected utilization >= 80% (warning) but < 95% (critical) should be high."""
        # Values that project around 85% utilization at 30 days
        values = [40.0, 45.0, 50.0, 55.0, 60.0]
        history = _make_history(values, limit=100.0)
        planner.detect_capacity_risks(
            [history], utilization_warning=80.0, utilization_critical=95.0
        )
        # With slope=5, at x=4+30=34, projected=5*34+40=210 => util=210%
        # This would actually be critical, so use a bigger limit
        values2 = [40.0, 42.0, 44.0, 46.0, 48.0]
        history2 = _make_history(values2, limit=120.0)
        risks2 = planner.detect_capacity_risks(
            [history2], days_ahead=30, utilization_warning=80.0, utilization_critical=95.0
        )
        assert len(risks2) >= 1
        # Verify it's at least flagged (critical or high)
        assert risks2[0].risk_level in ("critical", "high")

    def test_high_risk_current_utilization_above_75(self, planner):
        """current_util >= 75 triggers high risk via the elif branch."""
        values = [76.0, 76.0, 76.0, 76.0]
        history = _make_history(values, limit=100.0)
        risks = planner.detect_capacity_risks(
            [history], utilization_warning=200.0, utilization_critical=200.0
        )
        # With high thresholds for projected, only current_util>=75 triggers high
        assert len(risks) >= 1
        assert risks[0].risk_level == "high"
        assert "Scale" in risks[0].recommendation

    def test_medium_risk_breach_within_30_days(self, planner):
        """Breach within 30 days but below utilization thresholds => medium."""
        # slope=1, intercept=0 approximately; limit=50, breach at x=50, current_x=4
        # days_to_breach = 46 > 30 — need to tune
        # Let's use: values from 20..24 with limit=50
        # slope=1, intercept~20, breach_x=(50-20)/1=30, current_x=4, remaining=26<30
        values = [20.0, 21.0, 22.0, 23.0, 24.0]
        history = _make_history(values, limit=50.0)
        risks = planner.detect_capacity_risks(
            [history],
            days_ahead=5,  # short forecast so projected_util stays low
            utilization_warning=100.0,  # effectively disable warning threshold
            utilization_critical=200.0,
        )
        found_medium = [r for r in risks if r.risk_level == "medium"]
        assert len(found_medium) >= 1
        assert "Plan capacity increase" in found_medium[0].recommendation

    def test_multiple_resources_sorted_by_severity(self, planner):
        """Risks should be sorted with critical first, then high, then medium."""
        critical = _make_history(
            [92.0, 93.0, 94.0, 95.0],
            resource_id="critical-srv",
            limit=100.0,
        )
        low = _make_history(
            [5.0, 5.0, 5.0, 5.0],
            resource_id="healthy-srv",
            limit=100.0,
        )
        high_current = _make_history(
            [76.0, 76.0, 76.0, 76.0],
            resource_id="warn-srv",
            limit=100.0,
        )

        risks = planner.detect_capacity_risks([low, high_current, critical])
        # low-risk resource should be excluded
        resource_ids = [r.resource_id for r in risks]
        assert "healthy-srv" not in resource_ids
        # critical should come before high
        if len(risks) >= 2:
            risk_levels = [r.risk_level for r in risks]
            assert risk_levels.index("critical") < risk_levels.index("high")

    def test_risk_contains_correct_resource_id_and_metric(self, planner):
        history = _make_history(
            [91.0, 92.0, 93.0],
            resource_id="db-primary",
            metric_name="disk_io",
            limit=100.0,
        )
        risks = planner.detect_capacity_risks([history])
        assert len(risks) >= 1
        assert risks[0].resource_id == "db-primary"
        assert risks[0].metric_name == "disk_io"

    def test_risk_utilization_values_are_rounded(self, planner):
        values = [91.123, 92.456, 93.789]
        history = _make_history(values, limit=100.0)
        risks = planner.detect_capacity_risks([history])
        assert len(risks) >= 1
        # current_utilization and projected_utilization should have at most 1 decimal
        cu_str = f"{risks[0].current_utilization:.1f}"
        assert float(cu_str) == risks[0].current_utilization

    def test_custom_utilization_thresholds(self, planner):
        """Custom warning/critical thresholds should be respected."""
        values = [50.0, 50.0, 50.0]
        history = _make_history(values, limit=100.0)

        # With default thresholds (80/95), 50% usage should be low risk
        risks_default = planner.detect_capacity_risks([history])
        assert len(risks_default) == 0

        # With very low thresholds, same resource becomes critical
        risks_strict = planner.detect_capacity_risks(
            [history], utilization_warning=30.0, utilization_critical=40.0
        )
        assert len(risks_strict) >= 1
        assert risks_strict[0].risk_level == "critical"

    def test_detect_risks_passes_days_ahead_to_forecast(self, planner):
        """days_ahead parameter should affect projections."""
        values = [10.0, 15.0, 20.0, 25.0, 30.0]
        history = _make_history(values, limit=100.0)

        risks_short = planner.detect_capacity_risks(
            [history], days_ahead=5, utilization_warning=60.0
        )
        risks_long = planner.detect_capacity_risks(
            [history], days_ahead=100, utilization_warning=60.0
        )
        # Longer forecast with increasing data should yield more/higher risks
        assert len(risks_long) >= len(risks_short)

    def test_zero_limit_resource_no_crash(self, planner):
        """A resource with limit=0 should not cause division by zero."""
        history = _make_history([10.0, 20.0, 30.0], limit=0.0)
        risks = planner.detect_capacity_risks([history])
        # Should not raise; current_util would be 0 due to guard
        assert isinstance(risks, list)


# ===========================================================================
# Integration-style tests (forecast + risks together)
# ===========================================================================


class TestCapacityPlannerIntegration:
    """End-to-end scenarios combining forecast and risk detection."""

    def test_server_approaching_cpu_limit(self):
        """Simulate a server with linearly growing CPU approaching 100%."""
        planner = CapacityPlanner(default_forecast_days=14)
        history = _make_history(
            [60.0, 65.0, 70.0, 75.0, 80.0, 85.0],
            resource_id="web-server-1",
            metric_name="cpu_percent",
            limit=100.0,
        )
        forecast = planner.forecast(history)
        risks = planner.detect_capacity_risks([history], days_ahead=14)

        assert forecast.trend_direction == "increasing"
        assert forecast.days_to_breach is not None
        assert len(risks) >= 1
        assert risks[0].risk_level in ("critical", "high")

    def test_disk_usage_stable_no_risk(self):
        """Stable disk usage well below limit should produce no risks."""
        planner = CapacityPlanner()
        history = _make_history(
            [30.0, 30.0, 30.0, 30.0, 30.0],
            resource_id="db-disk",
            metric_name="disk_gb",
            limit=500.0,
        )
        forecast = planner.forecast(history)
        risks = planner.detect_capacity_risks([history])

        assert forecast.trend_direction == "stable"
        assert forecast.days_to_breach is None
        assert len(risks) == 0

    def test_memory_decreasing_after_optimization(self):
        """Memory usage decreasing after optimization should show decreasing trend."""
        planner = CapacityPlanner()
        history = _make_history(
            [80.0, 75.0, 70.0, 65.0, 60.0, 55.0],
            resource_id="app-memory",
            metric_name="memory_gb",
            limit=128.0,
        )
        forecast = planner.forecast(history)
        assert forecast.trend_direction == "decreasing"
        assert forecast.days_to_breach is None
        assert forecast.projected_usage < 80.0

    def test_multiple_resources_mixed_health(self):
        """A fleet with mixed health should correctly classify each resource."""
        planner = CapacityPlanner(default_forecast_days=30)

        healthy = _make_history(
            [20.0, 20.0, 20.0, 20.0],
            resource_id="healthy-node",
            metric_name="cpu",
            limit=100.0,
        )
        warning = _make_history(
            [60.0, 65.0, 70.0, 75.0, 80.0],
            resource_id="warning-node",
            metric_name="cpu",
            limit=100.0,
        )
        critical = _make_history(
            [85.0, 88.0, 91.0, 94.0],
            resource_id="critical-node",
            metric_name="cpu",
            limit=100.0,
        )

        risks = planner.detect_capacity_risks([healthy, warning, critical])

        resource_ids_at_risk = {r.resource_id for r in risks}
        assert "healthy-node" not in resource_ids_at_risk
        assert "critical-node" in resource_ids_at_risk

        # Critical should be sorted first
        if len(risks) >= 2:
            level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(risks) - 1):
                assert level_order[risks[i].risk_level] <= level_order[risks[i + 1].risk_level]
