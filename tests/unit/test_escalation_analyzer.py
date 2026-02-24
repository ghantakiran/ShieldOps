"""Tests for shieldops.incidents.escalation_analyzer — EscalationPatternAnalyzer."""

from __future__ import annotations

from shieldops.incidents.escalation_analyzer import (
    EscalationEfficiencyReport,
    EscalationEvent,
    EscalationOutcome,
    EscalationPattern,
    EscalationPatternAnalyzer,
    EscalationReason,
    EscalationTier,
)


def _engine(**kw) -> EscalationPatternAnalyzer:
    return EscalationPatternAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EscalationReason (6)
    def test_reason_timeout(self):
        assert EscalationReason.TIMEOUT == "timeout"

    def test_reason_severity_increase(self):
        assert EscalationReason.SEVERITY_INCREASE == "severity_increase"

    def test_reason_customer_impact(self):
        assert EscalationReason.CUSTOMER_IMPACT == "customer_impact"

    def test_reason_skill_gap(self):
        assert EscalationReason.SKILL_GAP == "skill_gap"

    def test_reason_policy_required(self):
        assert EscalationReason.POLICY_REQUIRED == "policy_required"

    def test_reason_manual(self):
        assert EscalationReason.MANUAL == "manual"

    # EscalationOutcome (5)
    def test_outcome_resolved(self):
        assert EscalationOutcome.RESOLVED == "resolved"

    def test_outcome_further_escalated(self):
        assert EscalationOutcome.FURTHER_ESCALATED == "further_escalated"

    def test_outcome_downgraded(self):
        assert EscalationOutcome.DOWNGRADED == "downgraded"

    def test_outcome_timed_out(self):
        assert EscalationOutcome.TIMED_OUT == "timed_out"

    def test_outcome_false_alarm(self):
        assert EscalationOutcome.FALSE_ALARM == "false_alarm"

    # EscalationTier (5)
    def test_tier_l1(self):
        assert EscalationTier.L1 == "L1"

    def test_tier_l2(self):
        assert EscalationTier.L2 == "L2"

    def test_tier_l3(self):
        assert EscalationTier.L3 == "L3"

    def test_tier_management(self):
        assert EscalationTier.MANAGEMENT == "management"

    def test_tier_executive(self):
        assert EscalationTier.EXECUTIVE == "executive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_escalation_event_defaults(self):
        e = EscalationEvent()
        assert e.id
        assert e.from_tier == EscalationTier.L1
        assert e.to_tier == EscalationTier.L2
        assert e.outcome is None

    def test_escalation_pattern_defaults(self):
        p = EscalationPattern(pattern_type="test")
        assert p.occurrence_count == 0
        assert p.services == []

    def test_escalation_efficiency_report_defaults(self):
        r = EscalationEfficiencyReport()
        assert r.total_escalations == 0
        assert r.false_alarm_rate == 0.0
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# record_escalation
# ---------------------------------------------------------------------------


class TestRecordEscalation:
    def test_basic_record(self):
        eng = _engine()
        e = eng.record_escalation(
            incident_id="INC-001",
            service="api-gateway",
            reason=EscalationReason.TIMEOUT,
        )
        assert e.incident_id == "INC-001"
        assert e.service == "api-gateway"

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.record_escalation(incident_id="INC-001")
        e2 = eng.record_escalation(incident_id="INC-002")
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_events=3)
        for i in range(5):
            eng.record_escalation(incident_id=f"INC-{i}")
        assert len(eng._escalations) == 3


# ---------------------------------------------------------------------------
# get_escalation
# ---------------------------------------------------------------------------


class TestGetEscalation:
    def test_found(self):
        eng = _engine()
        e = eng.record_escalation(incident_id="INC-001")
        assert eng.get_escalation(e.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_escalation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_escalations
# ---------------------------------------------------------------------------


class TestListEscalations:
    def test_list_all(self):
        eng = _engine()
        eng.record_escalation(incident_id="INC-001")
        eng.record_escalation(incident_id="INC-002")
        assert len(eng.list_escalations()) == 2

    def test_filter_service(self):
        eng = _engine()
        eng.record_escalation(service="api-gateway")
        eng.record_escalation(service="auth-service")
        results = eng.list_escalations(service="api-gateway")
        assert len(results) == 1
        assert results[0].service == "api-gateway"

    def test_filter_reason(self):
        eng = _engine()
        eng.record_escalation(reason=EscalationReason.TIMEOUT)
        eng.record_escalation(reason=EscalationReason.MANUAL)
        results = eng.list_escalations(reason=EscalationReason.TIMEOUT)
        assert len(results) == 1
        assert results[0].reason == EscalationReason.TIMEOUT


# ---------------------------------------------------------------------------
# resolve_escalation
# ---------------------------------------------------------------------------


class TestResolveEscalation:
    def test_success(self):
        eng = _engine()
        e = eng.record_escalation(incident_id="INC-001")
        result = eng.resolve_escalation(e.id, EscalationOutcome.RESOLVED)
        assert result is True
        assert e.outcome == EscalationOutcome.RESOLVED
        assert e.resolved_at is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.resolve_escalation("bad-id", EscalationOutcome.RESOLVED) is False


# ---------------------------------------------------------------------------
# detect_patterns
# ---------------------------------------------------------------------------


class TestDetectPatterns:
    def test_no_patterns(self):
        eng = _engine()
        eng.record_escalation(service="svc-a", reason=EscalationReason.TIMEOUT)
        eng.record_escalation(service="svc-b", reason=EscalationReason.MANUAL)
        assert len(eng.detect_patterns()) == 0

    def test_with_patterns(self):
        eng = _engine()
        for _ in range(3):
            eng.record_escalation(service="svc-a", reason=EscalationReason.TIMEOUT)
        patterns = eng.detect_patterns()
        assert len(patterns) == 1
        assert patterns[0].occurrence_count == 3
        assert "svc-a" in patterns[0].pattern_type


# ---------------------------------------------------------------------------
# analyze_tier_bottlenecks
# ---------------------------------------------------------------------------


class TestAnalyzeTierBottlenecks:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_tier_bottlenecks()
        assert result["bottleneck_tier"] == ""

    def test_with_data(self):
        eng = _engine()
        eng.record_escalation(to_tier=EscalationTier.L2)
        eng.record_escalation(to_tier=EscalationTier.L2)
        eng.record_escalation(to_tier=EscalationTier.L3)
        result = eng.analyze_tier_bottlenecks()
        assert result["bottleneck_tier"] == EscalationTier.L2


# ---------------------------------------------------------------------------
# compute_false_alarm_rate
# ---------------------------------------------------------------------------


class TestComputeFalseAlarmRate:
    def test_no_data(self):
        eng = _engine()
        assert eng.compute_false_alarm_rate() == 0.0

    def test_with_false_alarms(self):
        eng = _engine()
        e1 = eng.record_escalation(incident_id="INC-001")
        e2 = eng.record_escalation(incident_id="INC-002")
        eng.resolve_escalation(e1.id, EscalationOutcome.FALSE_ALARM)
        eng.resolve_escalation(e2.id, EscalationOutcome.RESOLVED)
        rate = eng.compute_false_alarm_rate()
        assert rate == 0.5


# ---------------------------------------------------------------------------
# generate_efficiency_report
# ---------------------------------------------------------------------------


class TestGenerateEfficiencyReport:
    def test_basic_report(self):
        eng = _engine()
        e = eng.record_escalation(service="api", reason=EscalationReason.TIMEOUT)
        eng.resolve_escalation(e.id, EscalationOutcome.RESOLVED)
        report = eng.generate_efficiency_report()
        assert report.total_escalations == 1
        assert report.resolved_count == 1
        assert report.false_alarm_count == 0


# ---------------------------------------------------------------------------
# get_repeat_escalation_rate
# ---------------------------------------------------------------------------


class TestGetRepeatEscalationRate:
    def test_no_repeats(self):
        eng = _engine()
        eng.record_escalation(incident_id="INC-001")
        eng.record_escalation(incident_id="INC-002")
        assert eng.get_repeat_escalation_rate() == 0.0

    def test_with_repeats(self):
        eng = _engine()
        eng.record_escalation(incident_id="INC-001")
        eng.record_escalation(incident_id="INC-001")  # repeat
        eng.record_escalation(incident_id="INC-002")
        rate = eng.get_repeat_escalation_rate()
        # 1 repeated / 2 unique incidents = 0.5
        assert rate == 0.5


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_list(self):
        eng = _engine()
        eng.record_escalation(incident_id="INC-001")
        eng.clear_data()
        assert len(eng._escalations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_escalations"] == 0
        assert stats["unresolved_count"] == 0

    def test_populated(self):
        eng = _engine()
        e = eng.record_escalation(incident_id="INC-001")
        eng.resolve_escalation(e.id, EscalationOutcome.RESOLVED)
        eng.record_escalation(incident_id="INC-002")
        stats = eng.get_stats()
        assert stats["total_escalations"] == 2
        assert stats["unresolved_count"] == 1
