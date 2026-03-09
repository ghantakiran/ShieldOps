"""Tests for ZeroTrustPolicyEnforcer."""

from __future__ import annotations

from shieldops.security.zero_trust_policy_enforcer import (
    AccessDecision,
    AccessRequest,
    DevicePosture,
    PolicyViolation,
    TrustLevel,
    ViolationType,
    ZeroTrustPolicyEnforcer,
    ZeroTrustReport,
)


def _engine(**kw) -> ZeroTrustPolicyEnforcer:
    return ZeroTrustPolicyEnforcer(**kw)


# --- Enum tests ---


class TestEnums:
    def test_decision_allow(self):
        assert AccessDecision.ALLOW == "allow"

    def test_decision_deny(self):
        assert AccessDecision.DENY == "deny"

    def test_decision_challenge(self):
        assert AccessDecision.CHALLENGE == "challenge"

    def test_decision_step_up(self):
        assert AccessDecision.STEP_UP == "step_up"

    def test_posture_compliant(self):
        assert DevicePosture.COMPLIANT == "compliant"

    def test_posture_non_compliant(self):
        assert DevicePosture.NON_COMPLIANT == "non_compliant"

    def test_posture_unknown(self):
        assert DevicePosture.UNKNOWN == "unknown"

    def test_trust_zero(self):
        assert TrustLevel.ZERO == "zero"

    def test_trust_high(self):
        assert TrustLevel.HIGH == "high"

    def test_violation_unauthorized(self):
        assert ViolationType.UNAUTHORIZED_ACCESS == "unauthorized_access"

    def test_violation_segmentation(self):
        assert ViolationType.SEGMENTATION_BREACH == "segmentation_breach"


# --- Model tests ---


class TestModels:
    def test_request_defaults(self):
        r = AccessRequest()
        assert r.id
        assert r.user_id == ""
        assert r.decision == AccessDecision.DENY
        assert r.trust_score == 0.0

    def test_violation_defaults(self):
        v = PolicyViolation()
        assert v.id
        assert v.violation_type == ViolationType.UNAUTHORIZED_ACCESS

    def test_report_defaults(self):
        r = ZeroTrustReport()
        assert r.total_requests == 0
        assert r.by_decision == {}


# --- evaluate_access_request ---


class TestEvaluateAccess:
    def test_allow(self):
        eng = _engine(trust_threshold=50.0)
        r = eng.evaluate_access_request(
            user_id="u1",
            resource="db",
            trust_score=80.0,
            device_posture=DevicePosture.COMPLIANT,
        )
        assert r.decision == AccessDecision.ALLOW

    def test_deny_non_compliant(self):
        eng = _engine(trust_threshold=50.0)
        r = eng.evaluate_access_request(
            user_id="u1",
            resource="db",
            trust_score=20.0,
            device_posture=DevicePosture.NON_COMPLIANT,
        )
        assert r.decision == AccessDecision.DENY

    def test_step_up(self):
        eng = _engine(trust_threshold=50.0)
        r = eng.evaluate_access_request(
            user_id="u1",
            resource="db",
            trust_score=35.0,
            device_posture=DevicePosture.UNKNOWN,
        )
        assert r.decision == AccessDecision.STEP_UP

    def test_challenge(self):
        eng = _engine(trust_threshold=50.0)
        r = eng.evaluate_access_request(
            user_id="u1",
            resource="db",
            trust_score=10.0,
            device_posture=DevicePosture.UNKNOWN,
        )
        assert r.decision == AccessDecision.CHALLENGE

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.evaluate_access_request(user_id=f"u{i}", resource="db")
        assert len(eng._requests) == 2


# --- enforce_microsegmentation ---


class TestMicrosegmentation:
    def test_allowed(self):
        eng = _engine()
        result = eng.enforce_microsegmentation("svc-a", "svc-b", allowed_pairs=[("svc-a", "svc-b")])
        assert result["allowed"] is True

    def test_blocked(self):
        eng = _engine()
        result = eng.enforce_microsegmentation("svc-a", "svc-c", allowed_pairs=[])
        assert result["allowed"] is False
        assert len(eng._violations) == 1

    def test_no_pairs(self):
        eng = _engine()
        result = eng.enforce_microsegmentation("svc-a", "svc-b")
        assert result["allowed"] is False


# --- validate_device_posture ---


class TestDevicePostureValidation:
    def test_compliant(self):
        eng = _engine()
        r = eng.validate_device_posture("d1", True, True, True)
        assert r["posture"] == "compliant"

    def test_degraded(self):
        eng = _engine()
        r = eng.validate_device_posture("d1", True, False, False)
        assert r["posture"] == "degraded"

    def test_non_compliant(self):
        eng = _engine()
        r = eng.validate_device_posture("d1", False, False, False)
        assert r["posture"] == "non_compliant"

    def test_checks_count(self):
        eng = _engine()
        r = eng.validate_device_posture("d1", True, True, False)
        assert r["checks_passed"] == 2
        assert r["checks_total"] == 3


# --- score_trust_level ---


class TestScoreTrust:
    def test_high(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r", trust_score=90.0)
        result = eng.score_trust_level("u1")
        assert result["trust_level"] == "high"

    def test_zero_no_data(self):
        eng = _engine()
        result = eng.score_trust_level("unknown")
        assert result["trust_level"] == "zero"

    def test_medium(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r", trust_score=65.0)
        result = eng.score_trust_level("u1")
        assert result["trust_level"] == "medium"

    def test_low(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r", trust_score=35.0)
        result = eng.score_trust_level("u1")
        assert result["trust_level"] == "low"


# --- get_policy_violations ---


class TestViolations:
    def test_list(self):
        eng = _engine()
        eng.enforce_microsegmentation("a", "b")
        assert len(eng.get_policy_violations()) == 1

    def test_filter(self):
        eng = _engine()
        eng.enforce_microsegmentation("a", "b")
        r = eng.get_policy_violations(violation_type=ViolationType.UNAUTHORIZED_ACCESS)
        assert len(r) == 0

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.enforce_microsegmentation(f"a{i}", f"b{i}")
        assert len(eng.get_policy_violations(limit=3)) == 3


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r", trust_score=20.0)
        eng.enforce_microsegmentation("a", "b")
        report = eng.generate_report()
        assert isinstance(report, ZeroTrustReport)
        assert report.total_requests == 1
        assert report.total_violations == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r")
        stats = eng.get_stats()
        assert stats["total_requests"] == 1

    def test_clear(self):
        eng = _engine()
        eng.evaluate_access_request(user_id="u1", resource="r")
        eng.enforce_microsegmentation("a", "b")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._requests) == 0
        assert len(eng._violations) == 0
