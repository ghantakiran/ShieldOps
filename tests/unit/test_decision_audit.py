"""Tests for shieldops.audit.decision_audit — DecisionAuditLogger."""

from __future__ import annotations

from shieldops.audit.decision_audit import (
    ConfidenceLevel,
    DecisionAuditLogger,
    DecisionAuditReport,
    DecisionOutcome,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
)


def _engine(**kw) -> DecisionAuditLogger:
    return DecisionAuditLogger(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DecisionType (5)
    def test_type_remediation(self):
        assert DecisionType.REMEDIATION == "remediation"

    def test_type_escalation(self):
        assert DecisionType.ESCALATION == "escalation"

    def test_type_scaling(self):
        assert DecisionType.SCALING == "scaling"

    def test_type_rollback(self):
        assert DecisionType.ROLLBACK == "rollback"

    def test_type_alert_suppression(self):
        assert DecisionType.ALERT_SUPPRESSION == "alert_suppression"

    # DecisionOutcome (5)
    def test_outcome_approved(self):
        assert DecisionOutcome.APPROVED == "approved"

    def test_outcome_executed(self):
        assert DecisionOutcome.EXECUTED == "executed"

    def test_outcome_rejected(self):
        assert DecisionOutcome.REJECTED == "rejected"

    def test_outcome_overridden(self):
        assert DecisionOutcome.OVERRIDDEN == "overridden"

    def test_outcome_pending(self):
        assert DecisionOutcome.PENDING == "pending"

    # ConfidenceLevel (5)
    def test_confidence_very_high(self):
        assert ConfidenceLevel.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert ConfidenceLevel.HIGH == "high"

    def test_confidence_moderate(self):
        assert ConfidenceLevel.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ConfidenceLevel.LOW == "low"

    def test_confidence_uncertain(self):
        assert ConfidenceLevel.UNCERTAIN == "uncertain"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_decision_record_defaults(self):
        r = DecisionRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.decision_type == DecisionType.REMEDIATION
        assert r.outcome == DecisionOutcome.PENDING
        assert r.confidence == ConfidenceLevel.MODERATE
        assert r.confidence_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_decision_rationale_defaults(self):
        r = DecisionRationale()
        assert r.id
        assert r.rationale_name == ""
        assert r.decision_type == DecisionType.REMEDIATION
        assert r.confidence == ConfidenceLevel.MODERATE
        assert r.weight == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = DecisionAuditReport()
        assert r.total_decisions == 0
        assert r.total_rationales == 0
        assert r.avg_confidence_pct == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.low_confidence_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_decision
# -------------------------------------------------------------------


class TestRecordDecision:
    def test_basic(self):
        eng = _engine()
        r = eng.record_decision(
            "agent-a",
            decision_type=DecisionType.ESCALATION,
            outcome=DecisionOutcome.APPROVED,
        )
        assert r.agent_name == "agent-a"
        assert r.decision_type == DecisionType.ESCALATION

    def test_with_confidence_score(self):
        eng = _engine()
        r = eng.record_decision("agent-b", confidence_score=92.5)
        assert r.confidence_score == 92.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_decision(f"agent-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_decision
# -------------------------------------------------------------------


class TestGetDecision:
    def test_found(self):
        eng = _engine()
        r = eng.record_decision("agent-a")
        assert eng.get_decision(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_decision("nonexistent") is None


# -------------------------------------------------------------------
# list_decisions
# -------------------------------------------------------------------


class TestListDecisions:
    def test_list_all(self):
        eng = _engine()
        eng.record_decision("agent-a")
        eng.record_decision("agent-b")
        assert len(eng.list_decisions()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_decision("agent-a")
        eng.record_decision("agent-b")
        results = eng.list_decisions(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_decision("agent-a", decision_type=DecisionType.ROLLBACK)
        eng.record_decision("agent-b", decision_type=DecisionType.SCALING)
        results = eng.list_decisions(decision_type=DecisionType.ROLLBACK)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rationale
# -------------------------------------------------------------------


class TestAddRationale:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rationale(
            "rationale-1",
            decision_type=DecisionType.REMEDIATION,
            confidence=ConfidenceLevel.HIGH,
            weight=0.85,
        )
        assert r.rationale_name == "rationale-1"
        assert r.weight == 0.85

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rationale(f"rationale-{i}")
        assert len(eng._rationales) == 2


# -------------------------------------------------------------------
# analyze_agent_decisions
# -------------------------------------------------------------------


class TestAnalyzeAgentDecisions:
    def test_with_data(self):
        eng = _engine()
        eng.record_decision("agent-a", confidence_score=80.0, confidence=ConfidenceLevel.HIGH)
        eng.record_decision("agent-a", confidence_score=60.0, confidence=ConfidenceLevel.LOW)
        result = eng.analyze_agent_decisions("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["total_records"] == 2
        assert result["avg_confidence"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_decisions("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=70.0)
        eng.record_decision("agent-a", confidence_score=75.0)
        result = eng.analyze_agent_decisions("agent-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_low_confidence_decisions
# -------------------------------------------------------------------


class TestIdentifyLowConfidenceDecisions:
    def test_with_low(self):
        eng = _engine()
        eng.record_decision("agent-a", confidence=ConfidenceLevel.LOW)
        eng.record_decision("agent-a", confidence=ConfidenceLevel.UNCERTAIN)
        eng.record_decision("agent-b", confidence=ConfidenceLevel.HIGH)
        results = eng.identify_low_confidence_decisions()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_decisions() == []


# -------------------------------------------------------------------
# rank_by_confidence
# -------------------------------------------------------------------


class TestRankByConfidence:
    def test_with_data(self):
        eng = _engine()
        eng.record_decision("agent-a", confidence_score=90.0)
        eng.record_decision("agent-a", confidence_score=80.0)
        eng.record_decision("agent-b", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["avg_confidence"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# -------------------------------------------------------------------
# detect_decision_patterns
# -------------------------------------------------------------------


class TestDetectDecisionPatterns:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_decision("agent-a")
        eng.record_decision("agent-b")
        results = eng.detect_decision_patterns()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_decision("agent-a")
        assert eng.detect_decision_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_decision("agent-a", confidence=ConfidenceLevel.HIGH, confidence_score=80.0)
        eng.record_decision("agent-b", confidence=ConfidenceLevel.LOW, confidence_score=30.0)
        eng.add_rationale("rationale-1")
        report = eng.generate_report()
        assert report.total_decisions == 2
        assert report.total_rationales == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_decisions == 0
        assert "below" in report.recommendations[0]

    def test_meets_targets(self):
        eng = _engine(min_confidence_pct=50.0)
        eng.record_decision("agent-a", confidence_score=80.0, confidence=ConfidenceLevel.HIGH)
        report = eng.generate_report()
        assert report.recommendations[0] == "Decision audit analysis meets targets"


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_decision("agent-a")
        eng.add_rationale("rationale-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rationales) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_decisions"] == 0
        assert stats["total_rationales"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_decision("agent-a", decision_type=DecisionType.REMEDIATION)
        eng.record_decision("agent-b", decision_type=DecisionType.SCALING)
        eng.add_rationale("r1")
        stats = eng.get_stats()
        assert stats["total_decisions"] == 2
        assert stats["total_rationales"] == 1
        assert stats["unique_agents"] == 2
