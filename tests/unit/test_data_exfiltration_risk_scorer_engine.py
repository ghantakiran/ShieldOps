"""Tests for DataExfiltrationRiskScorerEngine."""

from __future__ import annotations

from shieldops.security.data_exfiltration_risk_scorer_engine import (
    DataExfiltrationRiskScorerEngine,
    DataSensitivity,
    ExfilChannel,
    ExfilIndicator,
    ExfiltrationAnalysis,
    ExfiltrationRecord,
    ExfiltrationReport,
)


def _engine(**kw) -> DataExfiltrationRiskScorerEngine:
    return DataExfiltrationRiskScorerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        user_id="user-42",
        exfil_channel=ExfilChannel.CLOUD_STORAGE,
        data_sensitivity=DataSensitivity.RESTRICTED,
        exfil_indicator=ExfilIndicator.VOLUME_SPIKE,
        risk_score=0.88,
        data_volume_mb=500.0,
        destination="gdrive.example.com",
    )
    assert isinstance(r, ExfiltrationRecord)
    assert r.user_id == "user-42"
    assert r.data_volume_mb == 500.0
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(user_id=f"u-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        user_id="u1",
        data_sensitivity=DataSensitivity.RESTRICTED,
        risk_score=0.8,
        data_volume_mb=1000.0,
    )
    result = eng.process(r.id)
    assert isinstance(result, ExfiltrationAnalysis)
    assert result.user_id == "u1"
    assert result.composite_risk > 0
    assert result.exfil_confirmed is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("not-here")
    assert result == {"status": "not_found", "key": "not-here"}


def test_generate_report():
    eng = _engine()
    eng.add_record(
        user_id="u1",
        data_sensitivity=DataSensitivity.RESTRICTED,
        risk_score=0.9,
    )
    eng.add_record(
        user_id="u2",
        data_sensitivity=DataSensitivity.INTERNAL,
        risk_score=0.4,
    )
    eng.add_record(
        user_id="u3",
        exfil_channel=ExfilChannel.USB,
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        risk_score=0.75,
    )
    report = eng.generate_report()
    assert isinstance(report, ExfiltrationReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_exfil_channel) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(exfil_channel=ExfilChannel.EMAIL)
    eng.add_record(exfil_channel=ExfilChannel.USB)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "channel_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(user_id="u1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_score_exfiltration_risk():
    eng = _engine()
    eng.add_record(
        user_id="u1",
        exfil_channel=ExfilChannel.CLOUD_STORAGE,
        data_sensitivity=DataSensitivity.RESTRICTED,
        risk_score=0.9,
        data_volume_mb=800.0,
    )
    eng.add_record(
        user_id="u1",
        exfil_channel=ExfilChannel.CLOUD_STORAGE,
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        risk_score=0.7,
        data_volume_mb=200.0,
    )
    eng.add_record(
        user_id="u2",
        exfil_channel=ExfilChannel.EMAIL,
        data_sensitivity=DataSensitivity.INTERNAL,
        risk_score=0.3,
    )
    results = eng.score_exfiltration_risk()
    assert isinstance(results, list)
    assert len(results) >= 2
    assert results[0]["composite_risk"] >= results[-1]["composite_risk"]
    assert "total_volume_mb" in results[0]


def test_detect_exfil_indicators():
    eng = _engine()
    eng.add_record(
        user_id="u1",
        exfil_indicator=ExfilIndicator.VOLUME_SPIKE,
        risk_score=0.85,
        destination="evil.com",
    )
    eng.add_record(
        user_id="u2",
        exfil_indicator=ExfilIndicator.OFF_HOURS,
        risk_score=0.2,
    )
    eng.add_record(
        user_id="u3",
        exfil_indicator=ExfilIndicator.COMPRESSION,
        risk_score=0.75,
    )
    results = eng.detect_exfil_indicators()
    assert isinstance(results, list)
    assert all(r["risk_score"] > 0.5 for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_channels_by_risk():
    eng = _engine()
    eng.add_record(
        exfil_channel=ExfilChannel.CLOUD_STORAGE,
        data_sensitivity=DataSensitivity.RESTRICTED,
        risk_score=0.9,
    )
    eng.add_record(
        exfil_channel=ExfilChannel.USB,
        data_sensitivity=DataSensitivity.INTERNAL,
        risk_score=0.4,
    )
    eng.add_record(
        exfil_channel=ExfilChannel.NETWORK,
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        risk_score=0.7,
    )
    results = eng.rank_channels_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[-1]["total_risk_score"]
