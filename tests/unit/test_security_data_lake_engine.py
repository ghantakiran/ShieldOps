"""Tests for shieldops.security.security_data_lake_engine — SecurityDataLakeEngine."""

from __future__ import annotations

from shieldops.security.security_data_lake_engine import (
    DataSourceType,
    NormalizationStatus,
    RetentionTier,
    SecurityDataLakeEngine,
)


def _engine(**kw) -> SecurityDataLakeEngine:
    return SecurityDataLakeEngine(**kw)


class TestEnums:
    def test_source_type(self):
        assert DataSourceType.SIEM == "siem"

    def test_normalization(self):
        assert NormalizationStatus.NORMALIZED == "normalized"

    def test_retention_tier(self):
        assert RetentionTier.HOT == "hot"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(source_name="splunk-prod", source_type=DataSourceType.SIEM)
        assert rec.source_name == "splunk-prod"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(source_name=f"src-{i}")
        assert len(eng._records) == 3


class TestIngestionVolume:
    def test_basic(self):
        eng = _engine()
        eng.add_record(source_name="splunk", volume_gb=500.0)
        result = eng.analyze_ingestion_volume()
        assert isinstance(result, dict)


class TestQueryPerformance:
    def test_basic(self):
        eng = _engine()
        eng.add_record(source_name="splunk", query_latency_ms=200.0)
        result = eng.evaluate_query_performance()
        assert isinstance(result, list)


class TestRetention:
    def test_basic(self):
        eng = _engine()
        eng.add_record(source_name="splunk", retention_tier=RetentionTier.HOT, volume_gb=100.0)
        result = eng.compute_retention_summary()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(source_name="splunk", service="siem")
        result = eng.process("splunk")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(source_name="splunk")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(source_name="splunk")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(source_name="splunk")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
