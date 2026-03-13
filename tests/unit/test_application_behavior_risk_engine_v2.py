"""Tests for ApplicationBehaviorRiskEngineV2."""

from __future__ import annotations

from shieldops.security.application_behavior_risk_engine_v2 import (
    AppBehaviorAnalysis,
    AppBehaviorRecord,
    AppBehaviorReport,
    ApplicationBehaviorRiskEngineV2,
    BehaviorType,
    DetectionLayer,
    RiskScore,
)


def _engine(**kw) -> ApplicationBehaviorRiskEngineV2:
    return ApplicationBehaviorRiskEngineV2(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        application_id="app-web-01",
        behavior_type=BehaviorType.INJECTION_ATTEMPT,
        detection_layer=DetectionLayer.WAF,
        risk_score_level=RiskScore.CRITICAL,
        risk_score=0.93,
        request_count=1500,
        error_rate=0.25,
        endpoint="/api/login",
    )
    assert isinstance(r, AppBehaviorRecord)
    assert r.application_id == "app-web-01"
    assert r.request_count == 1500
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(application_id=f"app-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        application_id="app-1",
        behavior_type=BehaviorType.INJECTION_ATTEMPT,
        risk_score_level=RiskScore.CRITICAL,
        risk_score=0.85,
        error_rate=0.3,
    )
    result = eng.process(r.id)
    assert isinstance(result, AppBehaviorAnalysis)
    assert result.application_id == "app-1"
    assert result.composite_risk > 0
    assert result.attack_pattern_detected is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("nope")
    assert result == {"status": "not_found", "key": "nope"}


def test_generate_report():
    eng = _engine()
    eng.add_record(application_id="a1", risk_score_level=RiskScore.CRITICAL, risk_score=0.9)
    eng.add_record(application_id="a2", risk_score_level=RiskScore.MEDIUM, risk_score=0.5)
    eng.add_record(application_id="a3", risk_score_level=RiskScore.LOW, risk_score=0.1)
    report = eng.generate_report()
    assert isinstance(report, AppBehaviorReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_behavior_type) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(behavior_type=BehaviorType.API_ABUSE)
    eng.add_record(behavior_type=BehaviorType.RESOURCE_ABUSE)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "behavior_type_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(application_id="a1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_analyze_application_behavior():
    eng = _engine()
    eng.add_record(
        application_id="app-A",
        behavior_type=BehaviorType.INJECTION_ATTEMPT,
        risk_score_level=RiskScore.CRITICAL,
        risk_score=0.9,
        error_rate=0.4,
        endpoint="/api/v1/users",
    )
    eng.add_record(
        application_id="app-A",
        behavior_type=BehaviorType.AUTH_BYPASS,
        risk_score_level=RiskScore.HIGH,
        risk_score=0.75,
        error_rate=0.2,
        endpoint="/api/v1/admin",
    )
    eng.add_record(
        application_id="app-B",
        behavior_type=BehaviorType.API_ABUSE,
        risk_score_level=RiskScore.LOW,
        risk_score=0.2,
    )
    results = eng.analyze_application_behavior()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["application_id"] == "app-A"
    assert results[0]["composite_risk"] > results[1]["composite_risk"]
    assert "endpoints_affected" in results[0]


def test_detect_attack_patterns():
    eng = _engine()
    eng.add_record(
        application_id="a1",
        behavior_type=BehaviorType.INJECTION_ATTEMPT,
        risk_score=0.9,
        endpoint="/api/login",
    )
    eng.add_record(
        application_id="a2",
        behavior_type=BehaviorType.RESOURCE_ABUSE,
        risk_score=0.3,
    )
    eng.add_record(
        application_id="a3",
        behavior_type=BehaviorType.AUTH_BYPASS,
        risk_score=0.75,
        endpoint="/api/admin",
    )
    results = eng.detect_attack_patterns()
    assert isinstance(results, list)
    assert all(r["behavior_type"] in ("injection_attempt", "auth_bypass") for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_applications_by_risk():
    eng = _engine()
    eng.add_record(application_id="a1", risk_score_level=RiskScore.CRITICAL, risk_score=0.9)
    eng.add_record(application_id="a2", risk_score_level=RiskScore.LOW, risk_score=0.1)
    eng.add_record(application_id="a3", risk_score_level=RiskScore.HIGH, risk_score=0.7)
    results = eng.rank_applications_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[1]["total_risk_score"]
