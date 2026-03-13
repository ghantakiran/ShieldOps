"""Tests for BehavioralBaselineDeviationEngine."""

from __future__ import annotations

from shieldops.security.behavioral_baseline_deviation_engine import (
    BaselineDeviationAnalysis,
    BaselineDeviationRecord,
    BaselineDeviationReport,
    BaselineMethod,
    BehavioralBaselineDeviationEngine,
    DeviationSeverity,
    DeviationType,
)


def _engine(**kw) -> BehavioralBaselineDeviationEngine:
    return BehavioralBaselineDeviationEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        entity_id="user-001",
        deviation_type=DeviationType.ACCESS_PATTERN,
        baseline_method=BaselineMethod.STATISTICAL,
        severity=DeviationSeverity.HIGH,
        deviation_score=0.82,
        baseline_value=100.0,
        observed_value=210.0,
    )
    assert isinstance(r, BaselineDeviationRecord)
    assert r.entity_id == "user-001"
    assert r.deviation_score == 0.82
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(entity_id=f"e-{i}", deviation_score=float(i))
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        entity_id="e-001",
        severity=DeviationSeverity.CRITICAL,
        deviation_score=0.9,
        baseline_value=50.0,
        observed_value=150.0,
    )
    result = eng.process(r.id)
    assert isinstance(result, BaselineDeviationAnalysis)
    assert result.entity_id == "e-001"
    assert result.risk_score > 0
    assert result.anomaly_confirmed is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("nonexistent-id")
    assert result == {"status": "not_found", "key": "nonexistent-id"}


def test_generate_report():
    eng = _engine()
    eng.add_record(entity_id="e1", severity=DeviationSeverity.CRITICAL, deviation_score=0.9)
    eng.add_record(entity_id="e2", severity=DeviationSeverity.HIGH, deviation_score=0.7)
    eng.add_record(entity_id="e3", severity=DeviationSeverity.LOW, deviation_score=0.2)
    report = eng.generate_report()
    assert isinstance(report, BaselineDeviationReport)
    assert report.total_records == 3
    assert report.avg_deviation_score > 0
    assert "critical" in report.by_severity or "low" in report.by_severity
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(deviation_type=DeviationType.GEO_ANOMALY)
    eng.add_record(deviation_type=DeviationType.TIME_ANOMALY)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "deviation_type_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(entity_id="e1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0
    assert len(eng._analyses) == 0


def test_detect_baseline_deviations():
    eng = _engine()
    eng.add_record(entity_id="u1", deviation_score=0.9, severity=DeviationSeverity.CRITICAL)
    eng.add_record(entity_id="u1", deviation_score=0.8, severity=DeviationSeverity.HIGH)
    eng.add_record(entity_id="u2", deviation_score=0.3, severity=DeviationSeverity.LOW)
    eng.add_record(entity_id="u3", deviation_score=0.75, severity=DeviationSeverity.HIGH)
    results = eng.detect_baseline_deviations()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["entity_id"] == "u1"
    assert results[0]["max_deviation_score"] == 0.9
    assert "deviation_count" in results[0]


def test_classify_deviation_patterns():
    eng = _engine()
    eng.add_record(
        deviation_type=DeviationType.ACCESS_PATTERN,
        baseline_method=BaselineMethod.ML_MODEL,
        deviation_score=0.7,
    )
    eng.add_record(
        deviation_type=DeviationType.ACCESS_PATTERN,
        baseline_method=BaselineMethod.ML_MODEL,
        deviation_score=0.6,
    )
    eng.add_record(
        deviation_type=DeviationType.DATA_VOLUME,
        baseline_method=BaselineMethod.STATISTICAL,
        deviation_score=0.5,
    )
    results = eng.classify_deviation_patterns()
    assert isinstance(results, list)
    assert len(results) >= 2
    assert "pattern_key" in results[0]
    assert "avg_score" in results[0]
    assert results[0]["count"] >= results[-1]["count"]


def test_rank_deviations_by_risk():
    eng = _engine()
    eng.add_record(entity_id="a", severity=DeviationSeverity.CRITICAL, deviation_score=0.9)
    eng.add_record(entity_id="b", severity=DeviationSeverity.LOW, deviation_score=0.3)
    eng.add_record(entity_id="c", severity=DeviationSeverity.HIGH, deviation_score=0.7)
    results = eng.rank_deviations_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["composite_risk"] >= results[1]["composite_risk"]
    assert "entity_id" in results[0]
