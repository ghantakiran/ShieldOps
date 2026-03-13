"""Tests for MultiVectorAttackRiskCorrelatorEngine."""

from __future__ import annotations

from shieldops.security.multi_vector_attack_risk_correlator_engine import (
    AttackCorrelationAnalysis,
    AttackCorrelationRecord,
    AttackCorrelationReport,
    AttackVector,
    CampaignStatus,
    CorrelationMethod,
    MultiVectorAttackRiskCorrelatorEngine,
)


def _engine(**kw) -> MultiVectorAttackRiskCorrelatorEngine:
    return MultiVectorAttackRiskCorrelatorEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        campaign_id="camp-001",
        attack_vector=AttackVector.NETWORK,
        correlation_method=CorrelationMethod.GRAPH,
        campaign_status=CampaignStatus.ESCALATING,
        risk_score=0.92,
        vector_count=4,
        target_count=15,
    )
    assert isinstance(r, AttackCorrelationRecord)
    assert r.campaign_id == "camp-001"
    assert r.vector_count == 4
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(campaign_id=f"c-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        campaign_id="c-1",
        campaign_status=CampaignStatus.ESCALATING,
        risk_score=0.9,
        vector_count=5,
        target_count=20,
    )
    result = eng.process(r.id)
    assert isinstance(result, AttackCorrelationAnalysis)
    assert result.campaign_id == "c-1"
    assert result.composite_risk > 0
    assert result.coordinated_attack is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("missing-key")
    assert result == {"status": "not_found", "key": "missing-key"}


def test_generate_report():
    eng = _engine()
    eng.add_record(campaign_id="c1", campaign_status=CampaignStatus.ESCALATING, risk_score=0.9)
    eng.add_record(campaign_id="c2", campaign_status=CampaignStatus.ACTIVE, risk_score=0.7)
    eng.add_record(campaign_id="c3", campaign_status=CampaignStatus.CONTAINED, risk_score=0.2)
    report = eng.generate_report()
    assert isinstance(report, AttackCorrelationReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_campaign_status) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(attack_vector=AttackVector.NETWORK)
    eng.add_record(attack_vector=AttackVector.IDENTITY)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "attack_vector_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(campaign_id="c1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_correlate_attack_vectors():
    eng = _engine()
    eng.add_record(
        campaign_id="camp-A",
        attack_vector=AttackVector.NETWORK,
        risk_score=0.9,
        target_count=10,
    )
    eng.add_record(
        campaign_id="camp-A",
        attack_vector=AttackVector.IDENTITY,
        risk_score=0.8,
        target_count=5,
    )
    eng.add_record(
        campaign_id="camp-B",
        attack_vector=AttackVector.APPLICATION,
        risk_score=0.4,
        target_count=2,
    )
    results = eng.correlate_attack_vectors()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["campaign_id"] == "camp-A"
    assert results[0]["vector_count"] == 2
    assert "correlation_methods" in results[0]


def test_detect_coordinated_campaigns():
    eng = _engine()
    eng.add_record(
        campaign_id="c1",
        campaign_status=CampaignStatus.ESCALATING,
        vector_count=4,
        risk_score=0.9,
    )
    eng.add_record(
        campaign_id="c2",
        campaign_status=CampaignStatus.DORMANT,
        vector_count=1,
        risk_score=0.3,
    )
    eng.add_record(
        campaign_id="c3",
        campaign_status=CampaignStatus.ACTIVE,
        vector_count=3,
        risk_score=0.75,
    )
    results = eng.detect_coordinated_campaigns()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["vector_count"] > 2 for r in results)
    assert all(r["status"] in ("active", "escalating") for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_campaigns_by_risk():
    eng = _engine()
    eng.add_record(campaign_id="a", campaign_status=CampaignStatus.ESCALATING, risk_score=0.9)
    eng.add_record(campaign_id="b", campaign_status=CampaignStatus.CONTAINED, risk_score=0.2)
    eng.add_record(campaign_id="c", campaign_status=CampaignStatus.ACTIVE, risk_score=0.7)
    results = eng.rank_campaigns_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["composite_risk"] >= results[1]["composite_risk"]
