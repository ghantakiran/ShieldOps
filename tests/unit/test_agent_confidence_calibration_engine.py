"""Tests for AgentConfidenceCalibrationEngine."""

from __future__ import annotations

from shieldops.analytics.agent_confidence_calibration_engine import (
    AgentConfidenceCalibrationEngine,
    CalibrationMethod,
    CalibrationQuality,
    ConfidenceBand,
)


def _engine(**kw) -> AgentConfidenceCalibrationEngine:
    return AgentConfidenceCalibrationEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", predicted_confidence=0.8, actual_accuracy=0.75)
    assert r.agent_id == "a1"
    assert r.predicted_confidence == 0.8


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        agent_id="a1",
        calibration_method=CalibrationMethod.TEMPERATURE,
        predicted_confidence=0.9,
        calibration_error=0.05,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.calibration_score > 0


def test_process_not_found():
    result = _engine().process("ghost")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        calibration_method=CalibrationMethod.PLATT,
        calibration_quality=CalibrationQuality.OVERCONFIDENT,
        calibration_error=0.2,
    )
    eng.add_record(
        agent_id="a2",
        calibration_method=CalibrationMethod.ISOTONIC,
        calibration_quality=CalibrationQuality.MISCALIBRATED,
        calibration_error=0.35,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "overconfident" in rpt.by_calibration_quality
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", calibration_method=CalibrationMethod.HISTOGRAM)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "histogram" in stats["calibration_method_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_calibration_quality():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        predicted_confidence=0.9,
        actual_accuracy=0.88,
        calibration_error=0.02,
        confidence_band=ConfidenceBand.VERY_HIGH,
    )
    eng.add_record(
        agent_id="a2",
        predicted_confidence=0.9,
        actual_accuracy=0.5,
        calibration_error=0.4,
        confidence_band=ConfidenceBand.LOW,
    )
    result = eng.evaluate_calibration_quality()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "calibration_score" in result[0]
    assert result[0]["calibration_score"] >= result[1]["calibration_score"]


def test_detect_confidence_drift():
    eng = _engine()
    eng.add_record(agent_id="a1", predicted_confidence=0.5, calibration_error=0.05)
    eng.add_record(agent_id="a1", predicted_confidence=0.9, calibration_error=0.25)
    eng.add_record(agent_id="a2", predicted_confidence=0.7, calibration_error=0.1)
    eng.add_record(agent_id="a2", predicted_confidence=0.72, calibration_error=0.1)
    result = eng.detect_confidence_drift()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "is_drifting" in result[0]
    assert "drift_direction" in result[0]


def test_optimize_calibration_parameters():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        calibration_method=CalibrationMethod.TEMPERATURE,
        calibration_error=0.15,
    )
    eng.add_record(
        agent_id="a2",
        calibration_method=CalibrationMethod.PLATT,
        calibration_error=0.05,
    )
    result = eng.optimize_calibration_parameters()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "recommended_params" in result[0]
    assert "needs_tuning" in result[0]
