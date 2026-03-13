"""Tests for MessageQueueHealthAnalyzer."""

from __future__ import annotations

from shieldops.observability.message_queue_health_analyzer import (
    HealthStatus,
    MessageQueueHealthAnalyzer,
    QueueType,
    SaturationLevel,
)


def _engine(**kw) -> MessageQueueHealthAnalyzer:
    return MessageQueueHealthAnalyzer(**kw)


class TestEnums:
    def test_queue_type_values(self):
        for v in QueueType:
            assert isinstance(v.value, str)

    def test_health_status_values(self):
        for v in HealthStatus:
            assert isinstance(v.value, str)

    def test_saturation_level_values(self):
        for v in SaturationLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(queue_name="q1")
        assert r.queue_name == "q1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(queue_name=f"q-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.queue_type == QueueType.KAFKA


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(queue_name="q1", error_rate=0.1)
        a = eng.process(r.id)
        assert hasattr(a, "queue_name")
        assert a.queue_name == "q1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(queue_name="q1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_critical_queues(self):
        eng = _engine()
        eng.add_record(
            queue_name="q1",
            health_status=HealthStatus.CRITICAL,
        )
        rpt = eng.generate_report()
        assert len(rpt.critical_queues) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(queue_name="q1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(queue_name="q1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeQueueHealthScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(queue_name="q1", error_rate=0.05)
        result = eng.compute_queue_health_score()
        assert len(result) == 1
        assert result[0]["health_score"] == 95.0

    def test_empty(self):
        assert _engine().compute_queue_health_score() == []


class TestDetectQueueSaturation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            queue_name="q1",
            saturation_level=SaturationLevel.DANGER,
            depth=5000,
        )
        result = eng.detect_queue_saturation()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_queue_saturation() == []


class TestRankQueuesByProcessingRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            queue_name="q1",
            error_rate=0.5,
            depth=1000,
        )
        eng.add_record(
            queue_name="q2",
            error_rate=0.1,
            depth=100,
        )
        result = eng.rank_queues_by_processing_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_queues_by_processing_risk()
        assert r == []
