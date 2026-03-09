"""Tests for shieldops.observability.log_pattern_intelligence — LogPatternIntelligence."""

from __future__ import annotations

from shieldops.observability.log_pattern_intelligence import (
    ClusterStatus,
    LogLevel,
    LogPatternIntelligence,
    LogPatternRecord,
    PatternType,
)


def _engine(**kw) -> LogPatternIntelligence:
    return LogPatternIntelligence(**kw)


class TestEnums:
    def test_log_level_error(self):
        assert LogLevel.ERROR == "error"

    def test_pattern_type(self):
        assert PatternType.KNOWN == "known"

    def test_cluster_status(self):
        assert ClusterStatus.STABLE == "stable"


class TestModels:
    def test_record_defaults(self):
        r = LogPatternRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            template="Connection refused to {host}", log_level=LogLevel.ERROR, service="api"
        )
        assert rec.template == "Connection refused to {host}"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(template=f"pattern-{i}", service=f"svc-{i}")
        assert len(eng._records) == 3


class TestTopTemplates:
    def test_basic(self):
        eng = _engine()
        for _ in range(5):
            eng.add_record(template="Connection refused", service="api")
        eng.add_record(template="Timeout", service="api")
        result = eng.extract_top_templates()
        assert isinstance(result, list)
        assert len(result) > 0


class TestAnomalousPatterns:
    def test_basic(self):
        eng = _engine()
        eng.add_record(template="OOM Killed", log_level=LogLevel.ERROR, service="worker")
        result = eng.detect_anomalous_patterns()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(template="test", service="api")
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(template="test", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(template="test", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(template="test", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
