"""Tests for TraceAnomalyDetectionEngine."""

from __future__ import annotations

from shieldops.observability.trace_anomaly_detection_engine import (
    AnomalySeverity,
    AnomalyType,
    DetectionMethod,
    TraceAnomalyAnalysis,
    TraceAnomalyDetectionEngine,
    TraceAnomalyRecord,
    TraceAnomalyReport,
)


def test_add_record() -> None:
    engine = TraceAnomalyDetectionEngine()
    rec = engine.add_record(
        trace_id="t1",
        service_name="svc-a",
        anomaly_type=AnomalyType.LATENCY_SPIKE,
        detection_method=DetectionMethod.STATISTICAL,
        anomaly_severity=AnomalySeverity.HIGH,
        anomaly_score=80.0,
        latency_ms=2000.0,
        error_rate=0.05,
    )
    assert isinstance(rec, TraceAnomalyRecord)
    assert rec.trace_id == "t1"
    assert rec.service_name == "svc-a"
    assert rec.anomaly_score == 80.0


def test_process() -> None:
    engine = TraceAnomalyDetectionEngine()
    rec = engine.add_record(
        trace_id="t2",
        service_name="svc-b",
        anomaly_type=AnomalyType.ERROR_BURST,
        anomaly_severity=AnomalySeverity.CRITICAL,
        anomaly_score=90.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceAnomalyAnalysis)
    assert result.trace_id == "t2"
    assert result.is_critical is True
    assert result.impact_score > 0


def test_process_not_found() -> None:
    engine = TraceAnomalyDetectionEngine()
    result = engine.process("nonexistent-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceAnomalyDetectionEngine()
    for svc, atype, sev in [
        ("svc-a", AnomalyType.LATENCY_SPIKE, AnomalySeverity.HIGH),
        ("svc-b", AnomalyType.ERROR_BURST, AnomalySeverity.CRITICAL),
        ("svc-c", AnomalyType.VOLUME_SHIFT, AnomalySeverity.MEDIUM),
        ("svc-a", AnomalyType.TOPOLOGY_CHANGE, AnomalySeverity.LOW),
    ]:
        engine.add_record(
            service_name=svc,
            anomaly_type=atype,
            anomaly_severity=sev,
            anomaly_score=50.0,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceAnomalyReport)
    assert report.total_records == 4
    assert "latency_spike" in report.by_anomaly_type


def test_get_stats() -> None:
    engine = TraceAnomalyDetectionEngine()
    engine.add_record(anomaly_type=AnomalyType.LATENCY_SPIKE, anomaly_score=10.0)
    engine.add_record(anomaly_type=AnomalyType.ERROR_BURST, anomaly_score=20.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "anomaly_type_distribution" in stats


def test_clear_data() -> None:
    engine = TraceAnomalyDetectionEngine()
    engine.add_record(service_name="svc-x", anomaly_score=5.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_detect_trace_anomalies() -> None:
    engine = TraceAnomalyDetectionEngine()
    engine.add_record(
        service_name="svc-a", anomaly_score=70.0, anomaly_type=AnomalyType.LATENCY_SPIKE
    )
    engine.add_record(
        service_name="svc-b", anomaly_score=30.0, anomaly_type=AnomalyType.ERROR_BURST
    )
    engine.add_record(
        service_name="svc-a", anomaly_score=90.0, anomaly_type=AnomalyType.VOLUME_SHIFT
    )
    results = engine.detect_trace_anomalies()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "service_name" in results[0]
    assert "avg_anomaly_score" in results[0]


def test_classify_anomaly_patterns() -> None:
    engine = TraceAnomalyDetectionEngine()
    engine.add_record(
        anomaly_type=AnomalyType.LATENCY_SPIKE,
        detection_method=DetectionMethod.STATISTICAL,
        anomaly_score=50.0,
    )
    engine.add_record(
        anomaly_type=AnomalyType.ERROR_BURST,
        detection_method=DetectionMethod.ML_BASED,
        anomaly_score=60.0,
    )
    engine.add_record(
        anomaly_type=AnomalyType.LATENCY_SPIKE,
        detection_method=DetectionMethod.STATISTICAL,
        anomaly_score=40.0,
    )
    results = engine.classify_anomaly_patterns()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "pattern" in results[0]
    assert "count" in results[0]


def test_rank_anomalies_by_impact() -> None:
    engine = TraceAnomalyDetectionEngine()
    engine.add_record(
        trace_id="t1",
        service_name="svc-a",
        anomaly_severity=AnomalySeverity.CRITICAL,
        anomaly_score=80.0,
    )
    engine.add_record(
        trace_id="t2",
        service_name="svc-b",
        anomaly_severity=AnomalySeverity.LOW,
        anomaly_score=10.0,
    )
    engine.add_record(
        trace_id="t3",
        service_name="svc-c",
        anomaly_severity=AnomalySeverity.HIGH,
        anomaly_score=50.0,
    )
    results = engine.rank_anomalies_by_impact()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["impact_score"] >= results[-1]["impact_score"]
