"""Tests for CredentialAbuseRiskScorerEngine."""

from __future__ import annotations

from shieldops.security.credential_abuse_risk_scorer_engine import (
    AbuseConfidence,
    AbuseType,
    CredentialAbuseAnalysis,
    CredentialAbuseRecord,
    CredentialAbuseReport,
    CredentialAbuseRiskScorerEngine,
    DetectionSource,
)


def _engine(**kw) -> CredentialAbuseRiskScorerEngine:
    return CredentialAbuseRiskScorerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        credential_id="cred-001",
        user_id="u-100",
        abuse_type=AbuseType.BRUTE_FORCE,
        detection_source=DetectionSource.AUTH_LOG,
        confidence=AbuseConfidence.CONFIRMED,
        risk_score=0.95,
        attempt_count=500,
        source_ip="1.2.3.4",
    )
    assert isinstance(r, CredentialAbuseRecord)
    assert r.credential_id == "cred-001"
    assert r.attempt_count == 500
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(credential_id=f"c-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        credential_id="c-1",
        confidence=AbuseConfidence.CONFIRMED,
        risk_score=0.9,
        attempt_count=100,
    )
    result = eng.process(r.id)
    assert isinstance(result, CredentialAbuseAnalysis)
    assert result.credential_id == "c-1"
    assert result.composite_risk > 0
    assert result.abuse_confirmed is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("no-id")
    assert result == {"status": "not_found", "key": "no-id"}


def test_generate_report():
    eng = _engine()
    eng.add_record(
        credential_id="c1",
        confidence=AbuseConfidence.CONFIRMED,
        risk_score=0.9,
    )
    eng.add_record(
        credential_id="c2",
        confidence=AbuseConfidence.PROBABLE,
        risk_score=0.7,
    )
    eng.add_record(
        credential_id="c3",
        confidence=AbuseConfidence.UNLIKELY,
        risk_score=0.1,
    )
    report = eng.generate_report()
    assert isinstance(report, CredentialAbuseReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.compromised_credentials) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(abuse_type=AbuseType.BRUTE_FORCE)
    eng.add_record(abuse_type=AbuseType.TOKEN_THEFT)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "abuse_type_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(credential_id="c1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_score_credential_abuse_risk():
    eng = _engine()
    eng.add_record(
        credential_id="cred-A",
        confidence=AbuseConfidence.CONFIRMED,
        risk_score=0.9,
        attempt_count=200,
        abuse_type=AbuseType.BRUTE_FORCE,
    )
    eng.add_record(
        credential_id="cred-A",
        confidence=AbuseConfidence.PROBABLE,
        risk_score=0.7,
        attempt_count=50,
        abuse_type=AbuseType.CREDENTIAL_STUFFING,
    )
    eng.add_record(
        credential_id="cred-B",
        confidence=AbuseConfidence.UNLIKELY,
        risk_score=0.1,
        attempt_count=2,
    )
    results = eng.score_credential_abuse_risk()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["credential_id"] == "cred-A"
    assert results[0]["composite_risk"] > results[1]["composite_risk"]
    assert "total_attempts" in results[0]


def test_detect_abuse_patterns():
    eng = _engine()
    eng.add_record(
        abuse_type=AbuseType.BRUTE_FORCE,
        confidence=AbuseConfidence.CONFIRMED,
        source_ip="10.0.0.1",
        risk_score=0.95,
    )
    eng.add_record(
        abuse_type=AbuseType.TOKEN_THEFT,
        confidence=AbuseConfidence.UNLIKELY,
        source_ip="10.0.0.2",
        risk_score=0.2,
    )
    eng.add_record(
        abuse_type=AbuseType.CREDENTIAL_STUFFING,
        confidence=AbuseConfidence.PROBABLE,
        source_ip="10.0.0.3",
        risk_score=0.75,
    )
    results = eng.detect_abuse_patterns()
    assert isinstance(results, list)
    assert all(r["confidence"] in ("confirmed", "probable") for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_credentials_by_risk():
    eng = _engine()
    eng.add_record(credential_id="c1", confidence=AbuseConfidence.CONFIRMED, risk_score=0.9)
    eng.add_record(credential_id="c2", confidence=AbuseConfidence.UNLIKELY, risk_score=0.1)
    eng.add_record(credential_id="c3", confidence=AbuseConfidence.PROBABLE, risk_score=0.7)
    results = eng.rank_credentials_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[1]["total_risk_score"]
