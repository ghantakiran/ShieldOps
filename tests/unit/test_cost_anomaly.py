"""Tests for cost anomaly detector."""

from __future__ import annotations

import pytest

from shieldops.analytics.cost_anomaly import (
    AnomalySeverity,
    AnomalyStatus,
    CostAnomaly,
    CostAnomalyDetector,
    CostDataPoint,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _build_detector(**kwargs) -> CostAnomalyDetector:
    return CostAnomalyDetector(**kwargs)


def _ingest_stable_series(
    detector: CostAnomalyDetector,
    service: str = "ec2",
    amount: float = 100.0,
    count: int = 10,
) -> None:
    """Ingest *count* data points with identical amounts."""
    for _ in range(count):
        detector.ingest(service, amount)


# ── Enum tests ───────────────────────────────────────────────────────


class TestAnomalySeverityEnum:
    def test_low_value(self) -> None:
        assert AnomalySeverity.LOW == "low"

    def test_medium_value(self) -> None:
        assert AnomalySeverity.MEDIUM == "medium"

    def test_high_value(self) -> None:
        assert AnomalySeverity.HIGH == "high"

    def test_critical_value(self) -> None:
        assert AnomalySeverity.CRITICAL == "critical"

    def test_member_count(self) -> None:
        assert len(AnomalySeverity) == 4


class TestAnomalyStatusEnum:
    def test_open_value(self) -> None:
        assert AnomalyStatus.OPEN == "open"

    def test_investigating_value(self) -> None:
        assert AnomalyStatus.INVESTIGATING == "investigating"

    def test_resolved_value(self) -> None:
        assert AnomalyStatus.RESOLVED == "resolved"

    def test_false_positive_value(self) -> None:
        assert AnomalyStatus.FALSE_POSITIVE == "false_positive"

    def test_member_count(self) -> None:
        assert len(AnomalyStatus) == 4


# ── Model tests ──────────────────────────────────────────────────────


class TestCostDataPointModel:
    def test_defaults(self) -> None:
        dp = CostDataPoint(service="s3", amount=42.0)
        assert dp.service == "s3"
        assert dp.amount == 42.0
        assert dp.currency == "USD"
        assert dp.date == ""
        assert dp.timestamp > 0
        assert dp.metadata == {}

    def test_custom_fields(self) -> None:
        dp = CostDataPoint(
            service="rds",
            amount=99.9,
            currency="EUR",
            date="2025-01-01",
            metadata={"region": "us-east-1"},
        )
        assert dp.currency == "EUR"
        assert dp.date == "2025-01-01"
        assert dp.metadata["region"] == "us-east-1"


class TestCostAnomalyModel:
    def test_defaults(self) -> None:
        a = CostAnomaly(service="lambda", amount=500.0)
        assert len(a.id) == 12
        assert a.service == "lambda"
        assert a.expected_amount == 0.0
        assert a.z_score == 0.0
        assert a.severity == AnomalySeverity.LOW
        assert a.status == AnomalyStatus.OPEN
        assert a.detected_at > 0
        assert a.description == ""
        assert a.metadata == {}


# ── Detector creation ────────────────────────────────────────────────


class TestDetectorCreation:
    def test_default_params(self) -> None:
        d = _build_detector()
        assert d._z_threshold == 2.5
        assert d._lookback_seconds == 30 * 86400

    def test_custom_threshold(self) -> None:
        d = _build_detector(z_threshold=3.0)
        assert d._z_threshold == 3.0

    def test_custom_lookback(self) -> None:
        d = _build_detector(lookback_days=7)
        assert d._lookback_seconds == 7 * 86400


# ── ingest ───────────────────────────────────────────────────────────


class TestIngest:
    def test_basic_ingest(self) -> None:
        d = _build_detector()
        pt = d.ingest("ec2", 120.0)
        assert isinstance(pt, CostDataPoint)
        assert pt.service == "ec2"
        assert pt.amount == 120.0

    def test_ingest_with_metadata(self) -> None:
        d = _build_detector()
        pt = d.ingest("s3", 50.0, metadata={"bucket": "logs"})
        assert pt.metadata["bucket"] == "logs"

    def test_ingest_multiple_points(self) -> None:
        d = _build_detector()
        for i in range(5):
            d.ingest("ec2", float(100 + i))
        assert len(d._data) == 5

    def test_ingest_default_currency(self) -> None:
        d = _build_detector()
        pt = d.ingest("ec2", 10.0)
        assert pt.currency == "USD"

    def test_ingest_custom_currency_and_date(self) -> None:
        d = _build_detector()
        pt = d.ingest("ec2", 10.0, currency="GBP", date="2025-06-01")
        assert pt.currency == "GBP"
        assert pt.date == "2025-06-01"


# ── detect_anomalies ─────────────────────────────────────────────────


class TestDetectAnomalies:
    def test_anomaly_present_large_outlier(self) -> None:
        d = _build_detector(z_threshold=2.0)
        # Stable baseline
        for _ in range(10):
            d.ingest("ec2", 100.0)
        # Huge outlier as last point
        d.ingest("ec2", 10000.0)
        anomalies = d.detect_anomalies()
        assert len(anomalies) == 1
        assert anomalies[0].service == "ec2"
        assert anomalies[0].amount == 10000.0
        assert anomalies[0].z_score > 0

    def test_no_anomaly_stable_data(self) -> None:
        d = _build_detector()
        _ingest_stable_series(d, amount=100.0, count=10)
        # identical amounts => std=0 => skip => no anomaly
        anomalies = d.detect_anomalies()
        assert anomalies == []

    def test_specific_service_filter(self) -> None:
        d = _build_detector(z_threshold=2.0)
        for _ in range(10):
            d.ingest("ec2", 100.0)
        d.ingest("ec2", 10000.0)
        # Also ingest a different service with an outlier
        for _ in range(10):
            d.ingest("s3", 50.0)
        d.ingest("s3", 5000.0)
        anomalies = d.detect_anomalies(service="s3")
        assert len(anomalies) == 1
        assert anomalies[0].service == "s3"

    def test_insufficient_data_less_than_3(self) -> None:
        d = _build_detector()
        d.ingest("ec2", 100.0)
        d.ingest("ec2", 200.0)
        anomalies = d.detect_anomalies()
        assert anomalies == []

    def test_zero_std_dev_skips(self) -> None:
        d = _build_detector()
        _ingest_stable_series(d, amount=50.0, count=5)
        # All identical => std=0 => no anomaly
        anomalies = d.detect_anomalies()
        assert anomalies == []

    def test_anomaly_stored_in_internal_dict(self) -> None:
        d = _build_detector(z_threshold=2.0)
        for _ in range(10):
            d.ingest("ec2", 100.0)
        d.ingest("ec2", 10000.0)
        anomalies = d.detect_anomalies()
        assert len(d._anomalies) == 1
        stored = list(d._anomalies.values())[0]
        assert stored.id == anomalies[0].id

    def test_anomaly_description_populated(self) -> None:
        d = _build_detector(z_threshold=2.0)
        for _ in range(10):
            d.ingest("ec2", 100.0)
        d.ingest("ec2", 10000.0)
        anomalies = d.detect_anomalies()
        assert "ec2" in anomalies[0].description
        assert "z-score" in anomalies[0].description

    def test_multiple_services_each_detected(self) -> None:
        d = _build_detector(z_threshold=2.0)
        for svc in ["ec2", "s3"]:
            for _ in range(10):
                d.ingest(svc, 100.0)
            d.ingest(svc, 10000.0)
        anomalies = d.detect_anomalies()
        services = {a.service for a in anomalies}
        assert "ec2" in services
        assert "s3" in services


# ── get_anomaly / update_status ──────────────────────────────────────


class TestGetAndUpdateAnomaly:
    def _create_anomaly(self) -> tuple[CostAnomalyDetector, CostAnomaly]:
        d = _build_detector(z_threshold=2.0)
        for _ in range(10):
            d.ingest("ec2", 100.0)
        d.ingest("ec2", 10000.0)
        anomalies = d.detect_anomalies()
        return d, anomalies[0]

    def test_get_anomaly_found(self) -> None:
        d, anomaly = self._create_anomaly()
        result = d.get_anomaly(anomaly.id)
        assert result is not None
        assert result.id == anomaly.id

    def test_get_anomaly_not_found(self) -> None:
        d = _build_detector()
        assert d.get_anomaly("nonexistent") is None

    def test_update_status_to_investigating(self) -> None:
        d, anomaly = self._create_anomaly()
        result = d.update_status(anomaly.id, AnomalyStatus.INVESTIGATING)
        assert result is not None
        assert result.status == AnomalyStatus.INVESTIGATING

    def test_update_status_to_resolved(self) -> None:
        d, anomaly = self._create_anomaly()
        result = d.update_status(anomaly.id, AnomalyStatus.RESOLVED)
        assert result is not None
        assert result.status == AnomalyStatus.RESOLVED

    def test_update_status_to_false_positive(self) -> None:
        d, anomaly = self._create_anomaly()
        result = d.update_status(anomaly.id, AnomalyStatus.FALSE_POSITIVE)
        assert result is not None
        assert result.status == AnomalyStatus.FALSE_POSITIVE

    def test_update_status_not_found(self) -> None:
        d = _build_detector()
        assert d.update_status("missing", AnomalyStatus.RESOLVED) is None


# ── list_anomalies ───────────────────────────────────────────────────


class TestListAnomalies:
    def _detector_with_anomalies(self) -> CostAnomalyDetector:
        d = _build_detector(z_threshold=2.0)
        for svc in ["ec2", "s3"]:
            for _ in range(10):
                d.ingest(svc, 100.0)
            d.ingest(svc, 10000.0)
        d.detect_anomalies()
        return d

    def test_list_all(self) -> None:
        d = self._detector_with_anomalies()
        result = d.list_anomalies()
        assert len(result) == 2

    def test_filter_by_status(self) -> None:
        d = self._detector_with_anomalies()
        result = d.list_anomalies(status=AnomalyStatus.OPEN)
        assert len(result) == 2
        # Resolve one
        aid = list(d._anomalies.keys())[0]
        d.update_status(aid, AnomalyStatus.RESOLVED)
        result = d.list_anomalies(status=AnomalyStatus.OPEN)
        assert len(result) == 1

    def test_filter_by_service(self) -> None:
        d = self._detector_with_anomalies()
        result = d.list_anomalies(service="ec2")
        assert len(result) == 1
        assert result[0].service == "ec2"

    def test_limit(self) -> None:
        d = self._detector_with_anomalies()
        result = d.list_anomalies(limit=1)
        assert len(result) == 1

    def test_empty_when_no_anomalies(self) -> None:
        d = _build_detector()
        assert d.list_anomalies() == []


# ── get_daily_summary ────────────────────────────────────────────────


class TestDailySummary:
    def test_summary_with_data(self) -> None:
        d = _build_detector()
        d.ingest("ec2", 100.0)
        d.ingest("s3", 50.0)
        summary = d.get_daily_summary()
        assert summary["period"] == "last_24h"
        assert summary["total_cost"] == pytest.approx(150.0, abs=0.01)
        assert "ec2" in summary["by_service"]
        assert "s3" in summary["by_service"]
        assert summary["data_points"] == 2

    def test_summary_empty(self) -> None:
        d = _build_detector()
        summary = d.get_daily_summary()
        assert summary["total_cost"] == 0.0
        assert summary["data_points"] == 0
        assert summary["by_service"] == {}


# ── get_stats ────────────────────────────────────────────────────────


class TestGetStats:
    def test_empty_stats(self) -> None:
        d = _build_detector()
        stats = d.get_stats()
        assert stats["total_data_points"] == 0
        assert stats["total_anomalies"] == 0
        assert stats["by_status"] == {}
        assert stats["by_severity"] == {}

    def test_stats_after_ingestion_and_detection(self) -> None:
        d = _build_detector(z_threshold=2.0)
        for _ in range(10):
            d.ingest("ec2", 100.0)
        d.ingest("ec2", 10000.0)
        d.detect_anomalies()
        stats = d.get_stats()
        assert stats["total_data_points"] == 11
        assert stats["total_anomalies"] == 1
        assert "open" in stats["by_status"]


# ── _classify_severity ───────────────────────────────────────────────


class TestClassifySeverity:
    def test_critical_at_4(self) -> None:
        d = _build_detector()
        assert d._classify_severity(4.0) == AnomalySeverity.CRITICAL

    def test_critical_above_4(self) -> None:
        d = _build_detector()
        assert d._classify_severity(5.5) == AnomalySeverity.CRITICAL

    def test_high_at_3_5(self) -> None:
        d = _build_detector()
        assert d._classify_severity(3.5) == AnomalySeverity.HIGH

    def test_high_at_3_9(self) -> None:
        d = _build_detector()
        assert d._classify_severity(3.9) == AnomalySeverity.HIGH

    def test_medium_at_3(self) -> None:
        d = _build_detector()
        assert d._classify_severity(3.0) == AnomalySeverity.MEDIUM

    def test_medium_at_3_4(self) -> None:
        d = _build_detector()
        assert d._classify_severity(3.4) == AnomalySeverity.MEDIUM

    def test_low_below_3(self) -> None:
        d = _build_detector()
        assert d._classify_severity(2.9) == AnomalySeverity.LOW

    def test_low_at_zero(self) -> None:
        d = _build_detector()
        assert d._classify_severity(0.0) == AnomalySeverity.LOW
