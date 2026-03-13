"""Tests for AdaptiveRetryStrategyEngine."""

from __future__ import annotations

from shieldops.analytics.adaptive_retry_strategy_engine import (
    AdaptiveRetryStrategyEngine,
    FailureCategory,
    RetryOutcome,
    RetryPolicy,
)


def _engine(**kw) -> AdaptiveRetryStrategyEngine:
    return AdaptiveRetryStrategyEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(service_id="svc1", success_rate=0.9)
    assert r.service_id == "svc1"
    assert r.success_rate == 0.9


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(service_id=f"svc{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        service_id="svc1",
        retry_policy=RetryPolicy.JITTERED,
        success_rate=0.85,
        retry_count=3,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "service_id")
    assert analysis.service_id == "svc1"
    assert analysis.best_policy == RetryPolicy.JITTERED


def test_process_not_found():
    result = _engine().process("unknown")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        service_id="svc1",
        retry_policy=RetryPolicy.ADAPTIVE,
        failure_category=FailureCategory.PERSISTENT,
        outcome=RetryOutcome.ESCALATED,
        success_rate=0.3,
    )
    eng.add_record(
        service_id="svc2",
        retry_policy=RetryPolicy.EXPONENTIAL,
        failure_category=FailureCategory.CASCADING,
        outcome=RetryOutcome.CIRCUIT_BROKEN,
        success_rate=0.6,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "persistent" in rpt.by_failure_category
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(service_id="svc1", retry_policy=RetryPolicy.FIXED)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "fixed" in stats["retry_policy_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(service_id="svc1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_retry_policies():
    eng = _engine()
    eng.add_record(
        service_id="svc1",
        retry_policy=RetryPolicy.EXPONENTIAL,
        success_rate=0.9,
        retry_count=2,
        total_delay_ms=200.0,
    )
    eng.add_record(
        service_id="svc2",
        retry_policy=RetryPolicy.FIXED,
        success_rate=0.5,
        retry_count=5,
        total_delay_ms=5000.0,
    )
    result = eng.evaluate_retry_policies()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "efficiency" in result[0]
    assert result[0]["efficiency"] >= result[1]["efficiency"]


def test_detect_persistent_failures():
    eng = _engine()
    eng.add_record(
        service_id="svc1",
        failure_category=FailureCategory.PERSISTENT,
        outcome=RetryOutcome.EXHAUSTED,
        success_rate=0.2,
    )
    eng.add_record(
        service_id="svc1",
        failure_category=FailureCategory.PERSISTENT,
        outcome=RetryOutcome.EXHAUSTED,
        success_rate=0.15,
    )
    eng.add_record(service_id="svc2", failure_category=FailureCategory.TRANSIENT, success_rate=0.95)
    result = eng.detect_persistent_failures()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "is_persistent_failure" in result[0]
    assert result[0]["service_id"] == "svc1"


def test_optimize_backoff_parameters():
    eng = _engine()
    eng.add_record(
        service_id="svc1",
        failure_category=FailureCategory.TRANSIENT,
        success_rate=0.8,
        total_delay_ms=100.0,
    )
    eng.add_record(
        service_id="svc2",
        failure_category=FailureCategory.CASCADING,
        success_rate=0.3,
        total_delay_ms=5000.0,
    )
    result = eng.optimize_backoff_parameters()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "recommended_base_delay_ms" in result[0]
    assert "recommended_policy" in result[0]
