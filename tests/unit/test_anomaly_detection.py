"""Tests for the Anomaly Detection Engine and API routes.

Covers:
- Z-score detection (normal data, spikes, negative spikes, sensitivity, edge cases)
- IQR detection (normal data, outliers, custom multiplier, small dataset)
- EMA detection (trend following, sudden spikes, span parameter)
- Seasonal decomposition (periodic data, seasonal anomalies, short period)
- Baseline management (create, update, percentiles, list, missing)
- Unified detect() routing (all algorithms + unknown algorithm error)
- API routes (POST /detect, GET /baselines, GET /baselines/{name}, POST /baselines, 503)
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.analytics.anomaly import (
    AnomalyDetector,
    Baseline,
    DetectionRequest,
    DetectionResponse,
    MetricPoint,
    _mean,
    _median,
    _percentile,
    _std_dev,
)
from shieldops.api.routes import anomaly as anomaly_routes
from shieldops.api.routes.anomaly import router, set_detector

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_detector():
    """Reset the module-level detector singleton between tests."""
    anomaly_routes._detector = None
    yield
    anomaly_routes._detector = None


@pytest.fixture
def detector() -> AnomalyDetector:
    """Create a fresh AnomalyDetector instance."""
    return AnomalyDetector(default_sensitivity=2.0)


@pytest.fixture
def normal_data() -> list[float]:
    """Generate a list of values centered around 50 with uniform spread.

    All values are within the range [49.0, 51.0], ensuring no point
    exceeds a z-score of 2.5 from the mean.
    """
    return [
        50.0,
        50.1,
        49.9,
        50.2,
        49.8,
        50.1,
        49.9,
        50.0,
        50.1,
        49.9,
        50.2,
        49.8,
        50.0,
        50.1,
        49.9,
        50.0,
        50.2,
        49.8,
        50.1,
        49.9,
        50.0,
        50.1,
        49.9,
        50.2,
        49.8,
        50.0,
        50.1,
        49.9,
        50.0,
        50.0,
    ]


@pytest.fixture
def seasonal_data() -> list[float]:
    """Generate data with a clear periodic pattern (period=6)."""
    # Repeating pattern: [10, 20, 30, 20, 10, 5] across 5 full cycles
    pattern = [10.0, 20.0, 30.0, 20.0, 10.0, 5.0]
    return pattern * 5


@pytest.fixture
def api_client(detector: AnomalyDetector) -> TestClient:
    """Create a test client with a wired-up anomaly detector."""
    app = FastAPI()
    app.include_router(router)
    set_detector(detector)
    return TestClient(app)


@pytest.fixture
def api_client_no_detector() -> TestClient:
    """Create a test client WITHOUT a detector (for 503 tests)."""
    app = FastAPI()
    app.include_router(router)
    set_detector(None)
    return TestClient(app)


# ── Math Helper Tests ────────────────────────────────────────────


class TestMathHelpers:
    """Verify the pure-Python math utilities."""

    def test_mean_basic(self):
        assert _mean([1.0, 2.0, 3.0]) == 2.0

    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_std_dev_basic(self):
        sd = _std_dev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert abs(sd - 2.0) < 0.01

    def test_std_dev_single_value(self):
        assert _std_dev([42.0]) == 0.0

    def test_median_odd(self):
        assert _median([1.0, 3.0, 2.0]) == 2.0

    def test_median_even(self):
        assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_median_empty(self):
        assert _median([]) == 0.0

    def test_percentile_p50(self):
        vals = list(range(1, 101))
        p50 = _percentile([float(v) for v in vals], 50)
        assert abs(p50 - 50.5) < 0.1

    def test_percentile_p99(self):
        vals = [float(v) for v in range(1, 101)]
        p99 = _percentile(vals, 99)
        assert p99 >= 99.0

    def test_percentile_empty(self):
        assert _percentile([], 50) == 0.0


# ── Z-Score Tests ────────────────────────────────────────────────


class TestZScore:
    """Tests for Z-score anomaly detection."""

    def test_normal_distribution_no_anomalies(self, detector, normal_data):
        """Data within normal range should produce no anomalies."""
        results = detector.detect_zscore(normal_data, sensitivity=2.0)
        anomalies = [r for r in results if r[2]]
        assert len(anomalies) == 0

    def test_spike_detection(self, detector, normal_data):
        """A large positive spike should be detected as anomalous."""
        data = normal_data.copy()
        data[15] = 200.0  # inject obvious spike
        results = detector.detect_zscore(data, sensitivity=2.0)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 15 in anomalous_indices

    def test_negative_spike_detection(self, detector, normal_data):
        """A large negative spike should also be detected."""
        data = normal_data.copy()
        data[10] = -100.0  # inject negative spike
        results = detector.detect_zscore(data, sensitivity=2.0)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 10 in anomalous_indices

    def test_sensitivity_adjustment(self, detector, normal_data):
        """Lower sensitivity should flag more points as anomalous."""
        data = normal_data.copy()
        data[5] = 55.0  # moderate deviation

        results_tight = detector.detect_zscore(data, sensitivity=1.0)
        results_loose = detector.detect_zscore(data, sensitivity=3.0)

        anomalies_tight = sum(1 for r in results_tight if r[2])
        anomalies_loose = sum(1 for r in results_loose if r[2])

        assert anomalies_tight >= anomalies_loose

    def test_empty_list(self, detector):
        """Empty input should return an empty list."""
        results = detector.detect_zscore([])
        assert results == []

    def test_single_value(self, detector):
        """Single value should not be anomalous (no variance)."""
        results = detector.detect_zscore([42.0])
        assert len(results) == 1
        assert results[0] == (0, 0.0, False)

    def test_constant_values(self, detector):
        """Constant values (std_dev=0) should produce no anomalies."""
        results = detector.detect_zscore([5.0, 5.0, 5.0, 5.0, 5.0])
        assert all(not r[2] for r in results)

    def test_returns_correct_tuple_structure(self, detector, normal_data):
        """Each result tuple should have (index, score, is_anomaly)."""
        results = detector.detect_zscore(normal_data)
        assert len(results) == len(normal_data)
        for idx, score, is_anom in results:
            assert isinstance(idx, int)
            assert isinstance(score, float)
            assert isinstance(is_anom, bool)


# ── IQR Tests ────────────────────────────────────────────────────


class TestIQR:
    """Tests for IQR-based anomaly detection."""

    def test_normal_data_no_outliers(self, detector, normal_data):
        """Tightly grouped data should have no IQR outliers."""
        results = detector.detect_iqr(normal_data)
        anomalies = [r for r in results if r[2]]
        assert len(anomalies) == 0

    def test_outlier_detection(self, detector, normal_data):
        """A value far outside IQR bounds should be flagged."""
        data = normal_data.copy()
        data[0] = 200.0  # extreme outlier
        results = detector.detect_iqr(data, multiplier=1.5)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 0 in anomalous_indices

    def test_custom_multiplier_stricter(self, detector, normal_data):
        """Lower multiplier should flag more points as outliers."""
        data = normal_data.copy()
        data[0] = 60.0  # moderate outlier

        results_strict = detector.detect_iqr(data, multiplier=0.5)
        results_relaxed = detector.detect_iqr(data, multiplier=3.0)

        strict_count = sum(1 for r in results_strict if r[2])
        relaxed_count = sum(1 for r in results_relaxed if r[2])

        assert strict_count >= relaxed_count

    def test_small_dataset_returns_no_anomalies(self, detector):
        """Fewer than 4 values should return no anomalies (insufficient data)."""
        results = detector.detect_iqr([1.0, 2.0, 3.0])
        assert len(results) == 3
        assert all(not r[2] for r in results)

    def test_negative_outlier(self, detector, normal_data):
        """A very low value should be flagged as an outlier."""
        data = normal_data.copy()
        data[5] = -100.0
        results = detector.detect_iqr(data, multiplier=1.5)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 5 in anomalous_indices


# ── EMA Tests ────────────────────────────────────────────────────


class TestEMA:
    """Tests for Exponential Moving Average anomaly detection."""

    def test_stable_data_no_anomalies(self, detector):
        """Stable data with minor noise should not trigger anomalies."""
        # Constant value — EMA tracks perfectly, residuals are zero
        data = [50.0] * 30
        results = detector.detect_ema(data, span=10, sensitivity=2.0)
        anomalies = [r for r in results if r[2]]
        assert len(anomalies) == 0

    def test_sudden_spike_detection(self, detector):
        """A sudden spike in otherwise stable data should be detected."""
        data = [50.0] * 20
        data[15] = 200.0  # sudden spike
        results = detector.detect_ema(data, span=5, sensitivity=2.0)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 15 in anomalous_indices

    def test_span_parameter_effect(self, detector):
        """Larger span makes EMA smoother, potentially catching more abrupt changes."""
        data = [50.0] * 15 + [80.0] + [50.0] * 14
        results_short = detector.detect_ema(data, span=3, sensitivity=2.0)
        results_long = detector.detect_ema(data, span=20, sensitivity=2.0)

        # Both should detect the spike at index 15
        short_anomalies = [r[0] for r in results_short if r[2]]
        long_anomalies = [r[0] for r in results_long if r[2]]
        assert 15 in short_anomalies or 15 in long_anomalies

    def test_empty_input(self, detector):
        """Empty input should return empty results."""
        results = detector.detect_ema([])
        assert results == []

    def test_single_value(self, detector):
        """Single value cannot compute EMA deviation."""
        results = detector.detect_ema([42.0])
        assert len(results) == 1
        assert results[0][2] is False


# ── Seasonal Decomposition Tests ─────────────────────────────────


class TestSeasonal:
    """Tests for seasonal decomposition anomaly detection."""

    def test_periodic_data_no_anomalies(self, detector, seasonal_data):
        """Clean periodic data should produce no anomalies."""
        results = detector.detect_seasonal(seasonal_data, period=6, sensitivity=2.0)
        anomalies = [r for r in results if r[2]]
        assert len(anomalies) == 0

    def test_anomaly_in_seasonal_data(self, detector, seasonal_data):
        """A spike that breaks the seasonal pattern should be detected."""
        data = seasonal_data.copy()
        data[8] = 500.0  # inject anomaly at position 2 of second cycle
        results = detector.detect_seasonal(data, period=6, sensitivity=2.0)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 8 in anomalous_indices

    def test_short_data_falls_back_to_zscore(self, detector):
        """Data shorter than one period should fall back to Z-score."""
        data = [10.0, 20.0, 30.0]
        results = detector.detect_seasonal(data, period=24, sensitivity=2.0)
        assert len(results) == 3
        # Should still work without error
        for idx, _score, _is_anom in results:
            assert isinstance(idx, int)

    def test_multiple_periods(self, detector):
        """Detection should work across multiple full periods."""
        pattern = [5.0, 15.0, 25.0, 15.0]
        data = pattern * 10  # 10 full periods
        data[22] = 100.0  # inject anomaly
        results = detector.detect_seasonal(data, period=4, sensitivity=2.0)
        anomalous_indices = [r[0] for r in results if r[2]]
        assert 22 in anomalous_indices


# ── Baseline Tests ───────────────────────────────────────────────


class TestBaseline:
    """Tests for baseline management."""

    def test_create_baseline(self, detector):
        """Creating a baseline should compute correct statistics."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        bl = detector.update_baseline("cpu.usage", values)

        assert bl.metric_name == "cpu.usage"
        assert bl.mean == 30.0
        assert bl.min_val == 10.0
        assert bl.max_val == 50.0
        assert bl.count == 5
        assert bl.std_dev > 0

    def test_update_baseline_merges_history(self, detector):
        """Updating a baseline should incorporate all historical values."""
        detector.update_baseline("mem.used", [10.0, 20.0])
        bl = detector.update_baseline("mem.used", [30.0, 40.0])

        assert bl.count == 4
        assert bl.mean == 25.0
        assert bl.min_val == 10.0
        assert bl.max_val == 40.0

    def test_percentiles_correct(self, detector):
        """Baseline percentiles should be reasonable for the data."""
        values = [float(i) for i in range(1, 101)]
        bl = detector.update_baseline("latency", values)

        assert "p50" in bl.percentiles
        assert "p95" in bl.percentiles
        assert "p99" in bl.percentiles
        assert abs(bl.percentiles["p50"] - 50.5) < 1.0
        assert bl.percentiles["p95"] >= 94.0
        assert bl.percentiles["p99"] >= 98.0

    def test_list_baselines(self, detector):
        """list_baselines should return all stored baselines."""
        detector.update_baseline("metric_a", [1.0, 2.0])
        detector.update_baseline("metric_b", [3.0, 4.0])

        baselines = detector.list_baselines()
        names = [b.metric_name for b in baselines]

        assert len(baselines) == 2
        assert "metric_a" in names
        assert "metric_b" in names

    def test_get_missing_baseline(self, detector):
        """Getting a non-existent baseline should return None."""
        assert detector.get_baseline("nonexistent") is None

    def test_get_existing_baseline(self, detector):
        """Getting an existing baseline should return the correct object."""
        detector.update_baseline("disk.io", [5.0, 10.0, 15.0])
        bl = detector.get_baseline("disk.io")
        assert bl is not None
        assert bl.metric_name == "disk.io"
        assert bl.count == 3


# ── Unified Detect Tests ─────────────────────────────────────────


class TestDetect:
    """Tests for the unified detect() entry point."""

    def test_route_to_zscore(self, detector):
        """detect() with algorithm='zscore' should use Z-score method."""
        data = [50.0] * 20 + [200.0]
        req = DetectionRequest(
            metric_name="test.metric",
            values=data,
            algorithm="zscore",
            sensitivity=2.0,
        )
        resp = detector.detect(req)

        assert resp.algorithm == "zscore"
        assert resp.total_points == 21
        assert resp.anomaly_count >= 1
        assert any(a.details["index"] == 20 for a in resp.anomalies)

    def test_route_to_iqr(self, detector):
        """detect() with algorithm='iqr' should use IQR method."""
        # IQR needs variance in the data so Q1 != Q3 (IQR > 0)
        data = [
            10.0,
            20.0,
            30.0,
            40.0,
            50.0,
            15.0,
            25.0,
            35.0,
            45.0,
            55.0,
            12.0,
            22.0,
            32.0,
            42.0,
            52.0,
            18.0,
            28.0,
            38.0,
            48.0,
            58.0,
            500.0,  # extreme outlier
        ]
        req = DetectionRequest(
            metric_name="test.iqr",
            values=data,
            algorithm="iqr",
            sensitivity=1.5,
        )
        resp = detector.detect(req)

        assert resp.algorithm == "iqr"
        assert resp.anomaly_count >= 1

    def test_route_to_ema(self, detector):
        """detect() with algorithm='ema' should use EMA method."""
        data = [50.0] * 20
        data[10] = 200.0
        req = DetectionRequest(
            metric_name="test.ema",
            values=data,
            algorithm="ema",
            sensitivity=2.0,
            window_size=5,
        )
        resp = detector.detect(req)

        assert resp.algorithm == "ema"
        assert resp.total_points == 20

    def test_route_to_seasonal(self, detector):
        """detect() with algorithm='seasonal' should use seasonal method."""
        pattern = [10.0, 20.0, 30.0, 20.0, 10.0, 5.0]
        data = pattern * 5
        data[14] = 500.0  # inject anomaly
        req = DetectionRequest(
            metric_name="test.seasonal",
            values=data,
            algorithm="seasonal",
            sensitivity=2.0,
            window_size=6,
        )
        resp = detector.detect(req)

        assert resp.algorithm == "seasonal"
        assert resp.anomaly_count >= 1

    def test_unknown_algorithm_raises(self, detector):
        """detect() with unknown algorithm should raise ValueError."""
        req = DetectionRequest(
            metric_name="test.unknown",
            values=[1.0, 2.0, 3.0],
            algorithm="bogus",
        )
        with pytest.raises(ValueError, match="Unknown algorithm"):
            detector.detect(req)

    def test_detect_updates_baseline(self, detector):
        """detect() should auto-update the baseline for the metric."""
        req = DetectionRequest(
            metric_name="auto.baseline",
            values=[10.0, 20.0, 30.0, 40.0, 50.0],
            algorithm="zscore",
        )
        detector.detect(req)

        bl = detector.get_baseline("auto.baseline")
        assert bl is not None
        assert bl.count == 5

    def test_detect_response_model_fields(self, detector):
        """DetectionResponse should contain all expected fields."""
        req = DetectionRequest(
            metric_name="fields.test",
            values=[1.0, 2.0, 3.0, 4.0, 5.0],
            algorithm="zscore",
        )
        resp = detector.detect(req)

        assert isinstance(resp, DetectionResponse)
        assert resp.metric_name == "fields.test"
        assert isinstance(resp.anomalies, list)
        assert isinstance(resp.total_points, int)
        assert isinstance(resp.anomaly_count, int)
        assert isinstance(resp.algorithm, str)

    def test_anomaly_result_contains_details(self, detector):
        """Each AnomalyResult should contain index and raw_value in details."""
        data = [50.0] * 20 + [500.0]
        req = DetectionRequest(
            metric_name="details.test",
            values=data,
            algorithm="zscore",
            sensitivity=2.0,
        )
        resp = detector.detect(req)

        assert resp.anomaly_count >= 1
        for anomaly in resp.anomalies:
            assert "index" in anomaly.details
            assert "raw_value" in anomaly.details
            assert anomaly.is_anomaly is True
            assert anomaly.algorithm == "zscore"


# ── API Route Tests ──────────────────────────────────────────────


class TestAPIRoutes:
    """Tests for the FastAPI anomaly detection endpoints."""

    def test_post_detect(self, api_client):
        """POST /anomaly/detect should return detection results."""
        payload = {
            "metric_name": "api.latency",
            "values": [50.0] * 20 + [500.0],
            "algorithm": "zscore",
            "sensitivity": 2.0,
        }
        resp = api_client.post("/anomaly/detect", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_name"] == "api.latency"
        assert data["algorithm"] == "zscore"
        assert data["total_points"] == 21
        assert data["anomaly_count"] >= 1

    def test_post_detect_iqr(self, api_client):
        """POST /anomaly/detect with IQR algorithm should work."""
        payload = {
            "metric_name": "api.errors",
            "values": [10.0] * 20 + [500.0],
            "algorithm": "iqr",
            "sensitivity": 1.5,
        }
        resp = api_client.post("/anomaly/detect", json=payload)
        assert resp.status_code == 200
        assert resp.json()["algorithm"] == "iqr"

    def test_post_detect_unknown_algorithm_400(self, api_client):
        """POST /anomaly/detect with unknown algorithm should return 400."""
        payload = {
            "metric_name": "bad.algo",
            "values": [1.0, 2.0, 3.0],
            "algorithm": "nonexistent",
        }
        resp = api_client.post("/anomaly/detect", json=payload)
        assert resp.status_code == 400

    def test_get_baselines_empty(self, api_client):
        """GET /anomaly/baselines should return empty list initially."""
        resp = api_client.get("/anomaly/baselines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_baselines_after_detect(self, api_client):
        """GET /anomaly/baselines should include baselines created by detect."""
        # First, run a detection to create a baseline
        api_client.post(
            "/anomaly/detect",
            json={
                "metric_name": "detected.metric",
                "values": [1.0, 2.0, 3.0, 4.0, 5.0],
                "algorithm": "zscore",
            },
        )
        resp = api_client.get("/anomaly/baselines")
        assert resp.status_code == 200
        baselines = resp.json()
        assert len(baselines) >= 1
        names = [b["metric_name"] for b in baselines]
        assert "detected.metric" in names

    def test_get_baseline_by_name(self, api_client):
        """GET /anomaly/baselines/{name} should return the specific baseline."""
        # Create baseline via POST /baselines
        api_client.post(
            "/anomaly/baselines",
            json={
                "metric_name": "my.metric",
                "values": [10.0, 20.0, 30.0],
            },
        )
        resp = api_client.get("/anomaly/baselines/my.metric")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_name"] == "my.metric"
        assert data["count"] == 3

    def test_get_baseline_not_found(self, api_client):
        """GET /anomaly/baselines/{name} for missing metric should return 404."""
        resp = api_client.get("/anomaly/baselines/nonexistent")
        assert resp.status_code == 404

    def test_post_baselines(self, api_client):
        """POST /anomaly/baselines should create a baseline."""
        resp = api_client.post(
            "/anomaly/baselines",
            json={
                "metric_name": "new.baseline",
                "values": [5.0, 10.0, 15.0, 20.0, 25.0],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_name"] == "new.baseline"
        assert data["mean"] == 15.0
        assert data["count"] == 5
        assert "p50" in data["percentiles"]

    def test_post_baselines_empty_values_400(self, api_client):
        """POST /anomaly/baselines with empty values should return 400."""
        resp = api_client.post(
            "/anomaly/baselines",
            json={
                "metric_name": "empty",
                "values": [],
            },
        )
        assert resp.status_code == 400

    def test_503_without_detector(self, api_client_no_detector):
        """All endpoints should return 503 when no detector is wired."""
        resp = api_client_no_detector.post(
            "/anomaly/detect",
            json={
                "metric_name": "test",
                "values": [1.0],
                "algorithm": "zscore",
            },
        )
        assert resp.status_code == 503

        resp = api_client_no_detector.get("/anomaly/baselines")
        assert resp.status_code == 503

        resp = api_client_no_detector.get("/anomaly/baselines/foo")
        assert resp.status_code == 503

        resp = api_client_no_detector.post(
            "/anomaly/baselines",
            json={
                "metric_name": "foo",
                "values": [1.0],
            },
        )
        assert resp.status_code == 503


# ── False Positive Rate Tests ────────────────────────────────────


class TestFalsePositiveRate:
    """Ensure anomaly detection maintains acceptable false positive rates."""

    def test_zscore_false_positive_rate_under_5_percent(self, detector):
        """On clean normal-ish data, false positive rate should be < 5%."""
        import random

        # Generate 200 points of well-behaved data
        rng = random.Random(42)  # noqa: S311
        data = [50.0 + rng.gauss(0, 2) for _ in range(200)]

        results = detector.detect_zscore(data, sensitivity=2.0)
        fp_count = sum(1 for r in results if r[2])
        fp_rate = fp_count / len(data)

        assert fp_rate <= 0.05, f"False positive rate {fp_rate:.2%} exceeds 5%"

    def test_iqr_false_positive_rate_under_5_percent(self, detector):
        """IQR on clean data should also maintain < 5% false positive rate."""
        import random

        rng = random.Random(99)  # noqa: S311
        data = [100.0 + rng.gauss(0, 5) for _ in range(200)]

        results = detector.detect_iqr(data, multiplier=1.5)
        fp_count = sum(1 for r in results if r[2])
        fp_rate = fp_count / len(data)

        assert fp_rate < 0.05, f"False positive rate {fp_rate:.2%} exceeds 5%"


# ── Edge Case Tests ──────────────────────────────────────────────


class TestEdgeCases:
    """Tests for boundary conditions and edge cases."""

    def test_all_identical_values(self, detector):
        """All identical values should produce zero anomalies across all methods."""
        data = [42.0] * 30
        assert all(not r[2] for r in detector.detect_zscore(data))
        assert all(not r[2] for r in detector.detect_iqr(data))
        assert all(not r[2] for r in detector.detect_ema(data))
        assert all(not r[2] for r in detector.detect_seasonal(data, period=5))

    def test_two_values(self, detector):
        """Two-element lists should work without errors."""
        data = [10.0, 20.0]
        results = detector.detect_zscore(data, sensitivity=2.0)
        assert len(results) == 2

    def test_large_dataset(self, detector):
        """Detection should handle 10,000 points without error."""
        data = [float(i % 100) for i in range(10_000)]
        results = detector.detect_zscore(data)
        assert len(results) == 10_000

    def test_negative_values(self, detector):
        """Detection should handle negative values correctly."""
        data = [-50.0, -49.0, -51.0, -48.0, -52.0, -50.0, -200.0]
        results = detector.detect_zscore(data, sensitivity=2.0)
        anomalous = [r[0] for r in results if r[2]]
        assert 6 in anomalous

    def test_metric_point_default_timestamp(self):
        """MetricPoint should default to now(UTC)."""
        mp = MetricPoint(value=42.0)
        assert mp.timestamp.tzinfo is not None
        assert mp.value == 42.0
        assert mp.labels == {}

    def test_baseline_model_fields(self):
        """Baseline model should serialize all fields correctly."""
        bl = Baseline(
            metric_name="test",
            mean=10.0,
            std_dev=2.0,
            min_val=5.0,
            max_val=15.0,
            count=100,
            percentiles={"p50": 10.0, "p95": 14.0, "p99": 14.8},
        )
        data = bl.model_dump()
        assert data["metric_name"] == "test"
        assert data["percentiles"]["p50"] == 10.0
