"""Tests for DeadLetterQueueForensics."""

from __future__ import annotations

from shieldops.incidents.dead_letter_queue_forensics import (
    DeadLetterQueueForensics,
    FailureReason,
    ReprocessingOutcome,
    UrgencyLevel,
)


def _engine(**kw) -> DeadLetterQueueForensics:
    return DeadLetterQueueForensics(**kw)


class TestEnums:
    def test_failure_reason_values(self):
        for v in FailureReason:
            assert isinstance(v.value, str)

    def test_reprocessing_outcome_values(self):
        for v in ReprocessingOutcome:
            assert isinstance(v.value, str)

    def test_urgency_level_values(self):
        for v in UrgencyLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(dlq_name="dlq1")
        assert r.dlq_name == "dlq1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(dlq_name=f"dlq-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.failure_reason == (FailureReason.VALIDATION)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(dlq_name="dlq1", message_count=50)
        a = eng.process(r.id)
        assert hasattr(a, "dlq_name")
        assert a.dlq_name == "dlq1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(dlq_name="dlq1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_critical_dlqs(self):
        eng = _engine()
        eng.add_record(
            dlq_name="dlq1",
            urgency_level=UrgencyLevel.CRITICAL,
        )
        rpt = eng.generate_report()
        assert len(rpt.critical_dlqs) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(dlq_name="dlq1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(dlq_name="dlq1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestClassifyFailurePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            dlq_name="dlq1",
            failure_reason=FailureReason.TIMEOUT,
        )
        result = eng.classify_failure_patterns()
        assert len(result) == 1
        assert result[0]["dominant_pattern"] == ("timeout")

    def test_empty(self):
        assert _engine().classify_failure_patterns() == []


class TestComputeReprocessingSuccessRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            dlq_name="dlq1",
            reprocessing_outcome=(ReprocessingOutcome.SUCCESS),
        )
        result = eng.compute_reprocessing_success_rate()
        assert len(result) == 1
        assert result[0]["success_rate"] == 100.0

    def test_empty(self):
        r = _engine().compute_reprocessing_success_rate()
        assert r == []


class TestRankDlqsByUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            dlq_name="dlq1",
            urgency_level=UrgencyLevel.CRITICAL,
            message_count=100,
        )
        eng.add_record(
            dlq_name="dlq2",
            urgency_level=UrgencyLevel.LOW,
            message_count=10,
        )
        result = eng.rank_dlqs_by_urgency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_dlqs_by_urgency() == []
