"""Tests for PrivilegeEscalationRiskDetectorEngine."""

from __future__ import annotations

from shieldops.security.privilege_escalation_risk_detector_engine import (
    DetectionSource,
    EscalationAnalysis,
    EscalationRecord,
    EscalationReport,
    EscalationSeverity,
    EscalationType,
    PrivilegeEscalationRiskDetectorEngine,
)


def _engine(**kw) -> PrivilegeEscalationRiskDetectorEngine:
    return PrivilegeEscalationRiskDetectorEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        user_id="user-007",
        resource_id="res-001",
        escalation_type=EscalationType.VERTICAL,
        detection_source=DetectionSource.AUDIT_LOG,
        severity=EscalationSeverity.CRITICAL,
        risk_score=0.92,
        privilege_level_before=2,
        privilege_level_after=5,
    )
    assert isinstance(r, EscalationRecord)
    assert r.user_id == "user-007"
    assert r.risk_score == 0.92
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(user_id=f"u-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        user_id="u-1",
        severity=EscalationSeverity.CRITICAL,
        risk_score=0.85,
        privilege_level_before=1,
        privilege_level_after=4,
    )
    result = eng.process(r.id)
    assert isinstance(result, EscalationAnalysis)
    assert result.user_id == "u-1"
    assert result.composite_risk > 0
    assert result.privilege_delta == 3
    assert result.confirmed_attempt is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("xyz")
    assert result == {"status": "not_found", "key": "xyz"}


def test_generate_report():
    eng = _engine()
    eng.add_record(user_id="u1", severity=EscalationSeverity.CRITICAL, risk_score=0.9)
    eng.add_record(user_id="u2", severity=EscalationSeverity.HIGH, risk_score=0.7)
    eng.add_record(user_id="u3", severity=EscalationSeverity.LOW, risk_score=0.1)
    report = eng.generate_report()
    assert isinstance(report, EscalationReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_escalation_type) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(escalation_type=EscalationType.VERTICAL)
    eng.add_record(escalation_type=EscalationType.HORIZONTAL)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "escalation_type_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(user_id="u1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_detect_escalation_attempts():
    eng = _engine()
    eng.add_record(user_id="u1", risk_score=0.9, privilege_level_before=1, privilege_level_after=4)
    eng.add_record(user_id="u1", risk_score=0.8, privilege_level_before=2, privilege_level_after=5)
    eng.add_record(user_id="u2", risk_score=0.3, privilege_level_before=1, privilege_level_after=1)
    results = eng.detect_escalation_attempts()
    assert isinstance(results, list)
    assert len(results) == 2
    u1 = next(r for r in results if r["user_id"] == "u1")
    assert u1["max_risk_score"] == 0.9
    assert u1["confirmed"] is True


def test_classify_escalation_patterns():
    eng = _engine()
    eng.add_record(
        escalation_type=EscalationType.VERTICAL,
        detection_source=DetectionSource.BEHAVIOR,
        risk_score=0.8,
    )
    eng.add_record(
        escalation_type=EscalationType.VERTICAL,
        detection_source=DetectionSource.BEHAVIOR,
        risk_score=0.6,
    )
    eng.add_record(
        escalation_type=EscalationType.DIAGONAL,
        detection_source=DetectionSource.AUDIT_LOG,
        risk_score=0.5,
    )
    results = eng.classify_escalation_patterns()
    assert isinstance(results, list)
    assert len(results) >= 2
    assert "pattern_key" in results[0]
    assert results[0]["count"] >= results[-1]["count"]


def test_rank_escalations_by_severity():
    eng = _engine()
    eng.add_record(user_id="a", severity=EscalationSeverity.CRITICAL, risk_score=0.9)
    eng.add_record(user_id="b", severity=EscalationSeverity.LOW, risk_score=0.2)
    eng.add_record(user_id="c", severity=EscalationSeverity.HIGH, risk_score=0.7)
    results = eng.rank_escalations_by_severity()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["composite_score"] >= results[1]["composite_score"]
