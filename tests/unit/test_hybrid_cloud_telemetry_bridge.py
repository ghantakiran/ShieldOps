"""Tests for HybridCloudTelemetryBridge."""

from __future__ import annotations

from shieldops.observability.hybrid_cloud_telemetry_bridge import (
    BridgeStatus,
    CloudProvider,
    HybridCloudTelemetryBridge,
    NormalizationLevel,
)


def _engine(**kw) -> HybridCloudTelemetryBridge:
    return HybridCloudTelemetryBridge(**kw)


class TestEnums:
    def test_cloud_provider(self):
        assert CloudProvider.AWS == "aws"
        assert CloudProvider.ONPREM == "onprem"

    def test_bridge_status(self):
        assert BridgeStatus.ACTIVE == "active"
        assert BridgeStatus.OFFLINE == "offline"

    def test_normalization_level(self):
        assert NormalizationLevel.RAW == "raw"
        assert NormalizationLevel.ENRICHED == "enriched"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="b-1", service="api")
        assert rec.name == "b-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"b-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="b-1", score=75.0)
        result = eng.process("b-1")
        assert result["key"] == "b-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="b1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="b1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="b1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestDetectFormatMismatches:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="b1",
            provider=CloudProvider.AWS,
            format_match_pct=0.5,
        )
        result = eng.detect_format_mismatches()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_mismatches(self):
        eng = _engine()
        eng.add_record(name="b1", format_match_pct=0.95)
        result = eng.detect_format_mismatches()
        assert len(result) == 0


class TestComputeBridgeHealth:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="b1",
            provider=CloudProvider.AWS,
            score=80.0,
        )
        result = eng.compute_bridge_health()
        assert isinstance(result, dict)
        assert "aws" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_bridge_health()
        assert result["status"] == "no_data"


class TestReconcileCrossCloudMetrics:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="b1",
            service="api",
            provider=CloudProvider.AWS,
            score=80.0,
        )
        eng.add_record(
            name="b2",
            service="api",
            provider=CloudProvider.GCP,
            score=75.0,
        )
        result = eng.reconcile_cross_cloud_metrics()
        assert "multi_cloud_services" in result

    def test_empty(self):
        eng = _engine()
        result = eng.reconcile_cross_cloud_metrics()
        assert result["status"] == "no_data"
