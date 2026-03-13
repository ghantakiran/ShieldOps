"""Tests for InsiderThreatRiskQuantifierEngine."""

from __future__ import annotations

from shieldops.security.insider_threat_risk_quantifier_engine import (
    AssessmentMethod,
    InsiderThreatAnalysis,
    InsiderThreatRecord,
    InsiderThreatReport,
    InsiderThreatRiskQuantifierEngine,
    RiskCategory,
    ThreatIndicator,
)


def _engine(**kw) -> InsiderThreatRiskQuantifierEngine:
    return InsiderThreatRiskQuantifierEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        user_id="user-123",
        threat_indicator=ThreatIndicator.DATA_HOARDING,
        risk_category=RiskCategory.ELEVATED,
        assessment_method=AssessmentMethod.COMPOSITE,
        risk_score=0.78,
        indicator_weight=1.5,
        department="engineering",
    )
    assert isinstance(r, InsiderThreatRecord)
    assert r.user_id == "user-123"
    assert r.risk_score == 0.78
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(user_id=f"u-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        user_id="u-01",
        risk_category=RiskCategory.IMMINENT,
        risk_score=0.95,
        indicator_weight=2.0,
    )
    result = eng.process(r.id)
    assert isinstance(result, InsiderThreatAnalysis)
    assert result.user_id == "u-01"
    assert result.composite_risk_score > 0
    assert result.escalation_detected is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("bad-key")
    assert result == {"status": "not_found", "key": "bad-key"}


def test_generate_report():
    eng = _engine()
    eng.add_record(user_id="u1", risk_category=RiskCategory.IMMINENT, risk_score=0.9)
    eng.add_record(user_id="u2", risk_category=RiskCategory.ELEVATED, risk_score=0.7)
    eng.add_record(user_id="u3", risk_category=RiskCategory.BASELINE, risk_score=0.1)
    report = eng.generate_report()
    assert isinstance(report, InsiderThreatReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_risk_category) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(risk_category=RiskCategory.ELEVATED)
    eng.add_record(risk_category=RiskCategory.MODERATE)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "risk_category_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(user_id="u1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_quantify_insider_risk():
    eng = _engine()
    eng.add_record(
        user_id="u1",
        risk_category=RiskCategory.IMMINENT,
        risk_score=0.9,
        indicator_weight=2.0,
        threat_indicator=ThreatIndicator.DATA_HOARDING,
    )
    eng.add_record(
        user_id="u1",
        risk_category=RiskCategory.ELEVATED,
        risk_score=0.7,
        indicator_weight=1.0,
        threat_indicator=ThreatIndicator.PRIVILEGE_ABUSE,
    )
    eng.add_record(
        user_id="u2",
        risk_category=RiskCategory.BASELINE,
        risk_score=0.1,
        indicator_weight=1.0,
    )
    results = eng.quantify_insider_risk()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["user_id"] == "u1"
    assert results[0]["composite_risk"] > results[1]["composite_risk"]
    assert "indicators" in results[0]


def test_detect_threat_escalation():
    eng = _engine()
    eng.add_record(user_id="u1", risk_category=RiskCategory.IMMINENT, risk_score=0.95)
    eng.add_record(user_id="u2", risk_category=RiskCategory.MODERATE, risk_score=0.4)
    eng.add_record(user_id="u3", risk_category=RiskCategory.IMMINENT, risk_score=0.88)
    results = eng.detect_threat_escalation()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["escalation_level"] == "imminent" for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_users_by_risk():
    eng = _engine()
    eng.add_record(user_id="a", risk_category=RiskCategory.IMMINENT, risk_score=0.9)
    eng.add_record(user_id="b", risk_category=RiskCategory.BASELINE, risk_score=0.2)
    eng.add_record(user_id="c", risk_category=RiskCategory.ELEVATED, risk_score=0.7)
    results = eng.rank_users_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[1]["total_risk_score"]
