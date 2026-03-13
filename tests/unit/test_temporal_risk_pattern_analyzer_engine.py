"""Tests for TemporalRiskPatternAnalyzerEngine."""

from __future__ import annotations

from shieldops.security.temporal_risk_pattern_analyzer_engine import (
    PatternSignificance,
    TemporalPattern,
    TemporalRiskAnalysis,
    TemporalRiskPatternAnalyzerEngine,
    TemporalRiskRecord,
    TemporalRiskReport,
    TimeWindow,
)


def _engine(**kw) -> TemporalRiskPatternAnalyzerEngine:
    return TemporalRiskPatternAnalyzerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        entity_id="svc-001",
        temporal_pattern=TemporalPattern.PERIODIC,
        time_window=TimeWindow.DAILY,
        significance=PatternSignificance.HIGHLY_SIGNIFICANT,
        risk_score=0.87,
        pattern_frequency=3.5,
        peak_risk_hour=14,
    )
    assert isinstance(r, TemporalRiskRecord)
    assert r.entity_id == "svc-001"
    assert r.peak_risk_hour == 14
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(entity_id=f"e-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        entity_id="e-1",
        temporal_pattern=TemporalPattern.PERIODIC,
        significance=PatternSignificance.HIGHLY_SIGNIFICANT,
        risk_score=0.8,
        pattern_frequency=2.0,
        peak_risk_hour=9,
        time_window=TimeWindow.WEEKLY,
    )
    result = eng.process(r.id)
    assert isinstance(result, TemporalRiskAnalysis)
    assert result.entity_id == "e-1"
    assert result.composite_risk > 0
    assert result.periodicity_confirmed is True
    assert "weekly" in result.forecast_window


def test_process_not_found():
    eng = _engine()
    result = eng.process("ghost")
    assert result == {"status": "not_found", "key": "ghost"}


def test_generate_report():
    eng = _engine()
    eng.add_record(
        entity_id="e1",
        significance=PatternSignificance.HIGHLY_SIGNIFICANT,
        risk_score=0.85,
    )
    eng.add_record(
        entity_id="e2",
        significance=PatternSignificance.MARGINAL,
        risk_score=0.4,
    )
    eng.add_record(
        entity_id="e3",
        significance=PatternSignificance.INSIGNIFICANT,
        risk_score=0.1,
    )
    report = eng.generate_report()
    assert isinstance(report, TemporalRiskReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_temporal_pattern) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(temporal_pattern=TemporalPattern.BURST)
    eng.add_record(temporal_pattern=TemporalPattern.SEASONAL)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "temporal_pattern_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(entity_id="e1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_analyze_temporal_patterns():
    eng = _engine()
    eng.add_record(
        entity_id="e1",
        time_window=TimeWindow.DAILY,
        risk_score=0.8,
        temporal_pattern=TemporalPattern.PERIODIC,
        peak_risk_hour=10,
    )
    eng.add_record(
        entity_id="e1",
        time_window=TimeWindow.DAILY,
        risk_score=0.6,
        temporal_pattern=TemporalPattern.BURST,
        peak_risk_hour=10,
    )
    eng.add_record(
        entity_id="e2",
        time_window=TimeWindow.WEEKLY,
        risk_score=0.3,
        temporal_pattern=TemporalPattern.GRADUAL,
    )
    results = eng.analyze_temporal_patterns()
    assert isinstance(results, list)
    assert len(results) >= 2
    assert "avg_risk_score" in results[0]
    assert "common_peak_hour" in results[0]
    assert results[0]["avg_risk_score"] >= results[-1]["avg_risk_score"]


def test_detect_risk_periodicity():
    eng = _engine()
    eng.add_record(
        entity_id="e1",
        temporal_pattern=TemporalPattern.PERIODIC,
        significance=PatternSignificance.HIGHLY_SIGNIFICANT,
        pattern_frequency=4.0,
    )
    eng.add_record(
        entity_id="e2",
        temporal_pattern=TemporalPattern.GRADUAL,
        significance=PatternSignificance.INSIGNIFICANT,
    )
    eng.add_record(
        entity_id="e3",
        temporal_pattern=TemporalPattern.SEASONAL,
        significance=PatternSignificance.SIGNIFICANT,
        pattern_frequency=2.0,
    )
    results = eng.detect_risk_periodicity()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["pattern"] in ("periodic", "seasonal") for r in results)
    assert results[0]["pattern_frequency"] >= results[-1]["pattern_frequency"]


def test_forecast_risk_windows():
    eng = _engine()
    eng.add_record(
        entity_id="e1",
        risk_score=0.9,
        time_window=TimeWindow.HOURLY,
        pattern_frequency=6.0,
        peak_risk_hour=14,
    )
    eng.add_record(
        entity_id="e2",
        risk_score=0.4,
        time_window=TimeWindow.MONTHLY,
        pattern_frequency=0.5,
        peak_risk_hour=9,
    )
    results = eng.forecast_risk_windows()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["forecast_peak_risk"] >= results[1]["forecast_peak_risk"]
    assert "predicted_peak_hour" in results[0]
    assert "dominant_window" in results[0]
