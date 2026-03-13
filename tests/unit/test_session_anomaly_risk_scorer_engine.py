"""Tests for SessionAnomalyRiskScorerEngine."""

from __future__ import annotations

from shieldops.security.session_anomaly_risk_scorer_engine import (
    AnomalyType,
    RiskLevel,
    SessionAnomalyAnalysis,
    SessionAnomalyRecord,
    SessionAnomalyReport,
    SessionAnomalyRiskScorerEngine,
    SessionType,
)


def _engine(**kw) -> SessionAnomalyRiskScorerEngine:
    return SessionAnomalyRiskScorerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        session_id="sess-001",
        user_id="u-55",
        anomaly_type=AnomalyType.GEO_IMPOSSIBLE,
        session_type=SessionType.WEB,
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.92,
        session_duration_s=3600.0,
        source_ip="5.6.7.8",
    )
    assert isinstance(r, SessionAnomalyRecord)
    assert r.session_id == "sess-001"
    assert r.risk_score == 0.92
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(session_id=f"s-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        session_id="s-1",
        user_id="u-1",
        anomaly_type=AnomalyType.GEO_IMPOSSIBLE,
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.85,
    )
    result = eng.process(r.id)
    assert isinstance(result, SessionAnomalyAnalysis)
    assert result.session_id == "s-1"
    assert result.composite_risk > 0
    assert result.hijacking_suspected is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("ghost-id")
    assert result == {"status": "not_found", "key": "ghost-id"}


def test_generate_report():
    eng = _engine()
    eng.add_record(session_id="s1", risk_level=RiskLevel.CRITICAL, risk_score=0.9)
    eng.add_record(session_id="s2", risk_level=RiskLevel.MEDIUM, risk_score=0.5)
    eng.add_record(session_id="s3", risk_level=RiskLevel.LOW, risk_score=0.1)
    report = eng.generate_report()
    assert isinstance(report, SessionAnomalyReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_anomaly_type) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(anomaly_type=AnomalyType.GEO_IMPOSSIBLE)
    eng.add_record(anomaly_type=AnomalyType.DEVICE_CHANGE)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "anomaly_type_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(session_id="s1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_score_session_anomaly_risk():
    eng = _engine()
    eng.add_record(
        user_id="u1",
        session_type=SessionType.API,
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.9,
        anomaly_type=AnomalyType.GEO_IMPOSSIBLE,
    )
    eng.add_record(
        user_id="u1",
        session_type=SessionType.WEB,
        risk_level=RiskLevel.HIGH,
        risk_score=0.7,
        anomaly_type=AnomalyType.BEHAVIOR_SHIFT,
    )
    eng.add_record(
        user_id="u2",
        session_type=SessionType.SSH,
        risk_level=RiskLevel.LOW,
        risk_score=0.2,
    )
    results = eng.score_session_anomaly_risk()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["user_id"] == "u1"
    assert results[0]["total_risk"] > results[1]["total_risk"]
    assert "session_count" in results[0]


def test_detect_session_hijacking():
    eng = _engine()
    eng.add_record(
        session_id="s1",
        anomaly_type=AnomalyType.GEO_IMPOSSIBLE,
        risk_score=0.9,
        source_ip="1.1.1.1",
    )
    eng.add_record(
        session_id="s2",
        anomaly_type=AnomalyType.DEVICE_CHANGE,
        risk_score=0.75,
        source_ip="2.2.2.2",
    )
    eng.add_record(
        session_id="s3",
        anomaly_type=AnomalyType.DURATION_ANOMALY,
        risk_score=0.3,
    )
    results = eng.detect_session_hijacking()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["anomaly_type"] in ("geo_impossible", "device_change") for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_sessions_by_risk():
    eng = _engine()
    eng.add_record(session_id="a", risk_level=RiskLevel.CRITICAL, risk_score=0.9)
    eng.add_record(session_id="b", risk_level=RiskLevel.LOW, risk_score=0.2)
    eng.add_record(session_id="c", risk_level=RiskLevel.HIGH, risk_score=0.7)
    results = eng.rank_sessions_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[1]["total_risk_score"]
