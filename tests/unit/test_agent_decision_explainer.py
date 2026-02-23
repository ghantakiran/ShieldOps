"""Tests for shieldops.agents.decision_explainer – AgentDecisionExplainer."""

from __future__ import annotations

import time

import pytest

from shieldops.agents.decision_explainer import (
    AgentDecisionExplainer,
    AlternativeConsidered,
    ConfidenceLevel,
    DecisionOutcome,
    DecisionRecord,
    DecisionStep,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _explainer(**kwargs) -> AgentDecisionExplainer:
    return AgentDecisionExplainer(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_decision_outcome_values(self):
        assert DecisionOutcome.EXECUTED == "executed"
        assert DecisionOutcome.REJECTED == "rejected"
        assert DecisionOutcome.DEFERRED == "deferred"
        assert DecisionOutcome.ESCALATED == "escalated"

    def test_confidence_level_values(self):
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.VERY_HIGH == "very_high"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_decision_step_defaults(self):
        step = DecisionStep(description="Analyze logs")
        assert step.id
        assert step.description == "Analyze logs"
        assert step.reasoning == ""
        assert step.inputs == {}
        assert step.output == ""
        assert step.confidence == ConfidenceLevel.MEDIUM
        assert step.timestamp > 0

    def test_alternative_considered_defaults(self):
        alt = AlternativeConsidered(description="Restart service")
        assert alt.id
        assert alt.description == "Restart service"
        assert alt.reason_rejected == ""
        assert alt.estimated_impact == ""
        assert alt.confidence == ConfidenceLevel.LOW

    def test_decision_record_defaults(self):
        rec = DecisionRecord(agent_id="agent-1", action="scale-up")
        assert rec.id
        assert rec.agent_id == "agent-1"
        assert rec.agent_type == ""
        assert rec.action == "scale-up"
        assert rec.outcome == DecisionOutcome.DEFERRED
        assert rec.confidence == ConfidenceLevel.MEDIUM
        assert rec.steps == []
        assert rec.alternatives == []
        assert rec.context == {}
        assert rec.summary == ""
        assert rec.finalized is False
        assert rec.created_at > 0
        assert rec.finalized_at is None


# ---------------------------------------------------------------------------
# Record decision
# ---------------------------------------------------------------------------


class TestRecordDecision:
    def test_basic(self):
        e = _explainer()
        rec = e.record_decision(agent_id="agent-1", action="restart-pod")
        assert rec.agent_id == "agent-1"
        assert rec.action == "restart-pod"
        assert rec.id

    def test_with_all_fields(self):
        e = _explainer()
        rec = e.record_decision(
            agent_id="agent-2",
            action="scale-hpa",
            agent_type="remediation",
            context={"namespace": "prod", "current_replicas": 3},
            confidence=ConfidenceLevel.HIGH,
        )
        assert rec.agent_type == "remediation"
        assert rec.context["namespace"] == "prod"
        assert rec.confidence == ConfidenceLevel.HIGH

    def test_max_records_limit(self):
        e = _explainer(max_records=2)
        e.record_decision(agent_id="a1", action="act1")
        e.record_decision(agent_id="a2", action="act2")
        with pytest.raises(ValueError, match="Maximum decision records"):
            e.record_decision(agent_id="a3", action="act3")


# ---------------------------------------------------------------------------
# Add step
# ---------------------------------------------------------------------------


class TestAddStep:
    def test_success(self):
        e = _explainer()
        rec = e.record_decision(agent_id="agent-1", action="restart")
        step = e.add_step(
            decision_id=rec.id,
            description="Check pod health",
            reasoning="Pod restarting frequently",
            inputs={"pod": "api-server-0"},
            output="unhealthy",
            confidence=ConfidenceLevel.HIGH,
        )
        assert step is not None
        assert step.description == "Check pod health"
        assert step.reasoning == "Pod restarting frequently"
        assert step.inputs["pod"] == "api-server-0"
        assert step.output == "unhealthy"
        assert step.confidence == ConfidenceLevel.HIGH

    def test_decision_not_found_raises_value_error(self):
        e = _explainer()
        with pytest.raises(ValueError, match="Decision not found"):
            e.add_step(decision_id="nonexistent", description="step")

    def test_finalized_decision_raises_value_error(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="restart")
        e.finalize_decision(rec.id, DecisionOutcome.EXECUTED)
        with pytest.raises(ValueError, match="already finalized"):
            e.add_step(decision_id=rec.id, description="late step")

    def test_multiple_steps_in_order(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="investigate")
        e.add_step(rec.id, "Step 1: Gather logs")
        e.add_step(rec.id, "Step 2: Analyze metrics")
        e.add_step(rec.id, "Step 3: Correlate events")
        decision = e.get_decision(rec.id)
        assert decision is not None
        assert len(decision.steps) == 3
        assert decision.steps[0].description == "Step 1: Gather logs"
        assert decision.steps[2].description == "Step 3: Correlate events"


# ---------------------------------------------------------------------------
# Add alternative
# ---------------------------------------------------------------------------


class TestAddAlternative:
    def test_success(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="scale-up")
        alt = e.add_alternative(
            decision_id=rec.id,
            description="Vertical scaling",
            reason_rejected="Cost too high",
            estimated_impact="30% cost increase",
            confidence=ConfidenceLevel.MEDIUM,
        )
        assert alt is not None
        assert alt.description == "Vertical scaling"
        assert alt.reason_rejected == "Cost too high"
        assert alt.estimated_impact == "30% cost increase"
        assert alt.confidence == ConfidenceLevel.MEDIUM

    def test_decision_not_found(self):
        e = _explainer()
        result = e.add_alternative(decision_id="nonexistent", description="alt")
        assert result is None

    def test_multiple_alternatives(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="mitigate")
        e.add_alternative(rec.id, "Option A")
        e.add_alternative(rec.id, "Option B")
        decision = e.get_decision(rec.id)
        assert decision is not None
        assert len(decision.alternatives) == 2


# ---------------------------------------------------------------------------
# Finalize decision
# ---------------------------------------------------------------------------


class TestFinalizeDecision:
    def test_success(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="restart")
        result = e.finalize_decision(rec.id, DecisionOutcome.EXECUTED, summary="Pod restarted")
        assert result is not None
        assert result.outcome == DecisionOutcome.EXECUTED
        assert result.summary == "Pod restarted"
        assert result.finalized is True

    def test_not_found(self):
        e = _explainer()
        result = e.finalize_decision("nonexistent", DecisionOutcome.REJECTED)
        assert result is None

    def test_sets_finalized_at(self):
        e = _explainer()
        before = time.time()
        rec = e.record_decision(agent_id="a1", action="scale")
        result = e.finalize_decision(rec.id, DecisionOutcome.ESCALATED)
        after = time.time()
        assert result is not None
        assert result.finalized_at is not None
        assert before <= result.finalized_at <= after

    def test_outcome_rejected(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="delete-pod")
        result = e.finalize_decision(rec.id, DecisionOutcome.REJECTED, summary="Policy denied")
        assert result is not None
        assert result.outcome == DecisionOutcome.REJECTED


# ---------------------------------------------------------------------------
# Get decision
# ---------------------------------------------------------------------------


class TestGetDecision:
    def test_found(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="restart")
        fetched = e.get_decision(rec.id)
        assert fetched is not None
        assert fetched.id == rec.id

    def test_not_found(self):
        e = _explainer()
        assert e.get_decision("nonexistent") is None


# ---------------------------------------------------------------------------
# List decisions
# ---------------------------------------------------------------------------


class TestListDecisions:
    def test_all(self):
        e = _explainer()
        e.record_decision(agent_id="a1", action="act1")
        e.record_decision(agent_id="a2", action="act2")
        decisions = e.list_decisions()
        assert len(decisions) == 2

    def test_filter_by_agent_id(self):
        e = _explainer()
        e.record_decision(agent_id="a1", action="act1")
        e.record_decision(agent_id="a2", action="act2")
        e.record_decision(agent_id="a1", action="act3")
        decisions = e.list_decisions(agent_id="a1")
        assert len(decisions) == 2
        assert all(d.agent_id == "a1" for d in decisions)

    def test_filter_by_outcome(self):
        e = _explainer()
        r1 = e.record_decision(agent_id="a1", action="act1")
        r2 = e.record_decision(agent_id="a2", action="act2")
        e.finalize_decision(r1.id, DecisionOutcome.EXECUTED)
        e.finalize_decision(r2.id, DecisionOutcome.REJECTED)
        decisions = e.list_decisions(outcome=DecisionOutcome.EXECUTED)
        assert len(decisions) == 1
        assert decisions[0].outcome == DecisionOutcome.EXECUTED

    def test_filter_no_match(self):
        e = _explainer()
        e.record_decision(agent_id="a1", action="act1")
        decisions = e.list_decisions(agent_id="nonexistent")
        assert len(decisions) == 0


# ---------------------------------------------------------------------------
# Get by agent
# ---------------------------------------------------------------------------


class TestGetByAgent:
    def test_with_results(self):
        e = _explainer()
        e.record_decision(agent_id="agent-x", action="act1")
        e.record_decision(agent_id="agent-x", action="act2")
        e.record_decision(agent_id="agent-y", action="act3")
        results = e.get_by_agent("agent-x")
        assert len(results) == 2
        assert all(d.agent_id == "agent-x" for d in results)

    def test_empty(self):
        e = _explainer()
        results = e.get_by_agent("nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Get explanation
# ---------------------------------------------------------------------------


class TestGetExplanation:
    def test_with_steps_and_alternatives(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="scale-up", agent_type="remediation")
        e.add_step(rec.id, "Analyzed metrics", reasoning="CPU > 90%", output="high load")
        e.add_alternative(rec.id, "Vertical scaling", reason_rejected="Too expensive")
        e.finalize_decision(rec.id, DecisionOutcome.EXECUTED, summary="Scaled HPA to 5")

        explanation = e.get_explanation(rec.id)
        assert explanation is not None
        assert explanation["decision_id"] == rec.id
        assert explanation["action"] == "scale-up"
        assert explanation["outcome"] == "executed"
        assert explanation["agent_id"] == "a1"
        assert explanation["agent_type"] == "remediation"
        assert explanation["finalized"] is True
        assert explanation["summary"] == "Scaled HPA to 5"
        assert len(explanation["steps"]) == 1
        assert explanation["steps"][0]["description"] == "Analyzed metrics"
        assert explanation["steps"][0]["reasoning"] == "CPU > 90%"
        assert len(explanation["alternatives"]) == 1
        assert explanation["alternatives"][0]["description"] == "Vertical scaling"
        assert explanation["alternatives"][0]["reason_rejected"] == "Too expensive"

    def test_not_found(self):
        e = _explainer()
        assert e.get_explanation("nonexistent") is None

    def test_empty_steps_and_alternatives(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="noop")
        explanation = e.get_explanation(rec.id)
        assert explanation is not None
        assert explanation["steps"] == []
        assert explanation["alternatives"] == []
        assert explanation["finalized"] is False


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _explainer()
        s = e.get_stats()
        assert s["total_decisions"] == 0
        assert s["finalized_decisions"] == 0
        assert s["pending_decisions"] == 0
        assert s["outcome_breakdown"] == {}
        assert s["unique_agents"] == 0

    def test_with_data(self):
        e = _explainer()
        r1 = e.record_decision(agent_id="a1", action="act1")
        r2 = e.record_decision(agent_id="a2", action="act2")
        e.record_decision(agent_id="a1", action="act3")
        e.finalize_decision(r1.id, DecisionOutcome.EXECUTED)
        e.finalize_decision(r2.id, DecisionOutcome.REJECTED)
        s = e.get_stats()
        assert s["total_decisions"] == 3
        assert s["finalized_decisions"] == 2
        assert s["pending_decisions"] == 1
        assert s["unique_agents"] == 2
        assert s["outcome_breakdown"]["executed"] == 1
        assert s["outcome_breakdown"]["rejected"] == 1
        assert s["outcome_breakdown"]["deferred"] == 1
        assert s["max_records"] == 50000
        assert s["retention_days"] == 90


# ---------------------------------------------------------------------------
# Additional coverage: edge cases and deeper scenarios
# ---------------------------------------------------------------------------


class TestDecisionRecordIsolation:
    def test_unique_decision_ids(self):
        e = _explainer()
        r1 = e.record_decision(agent_id="a1", action="act1")
        r2 = e.record_decision(agent_id="a1", action="act2")
        assert r1.id != r2.id

    def test_decision_created_at_set(self):
        before = time.time()
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        after = time.time()
        assert before <= rec.created_at <= after

    def test_default_outcome_is_deferred(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="pending-action")
        assert rec.outcome == DecisionOutcome.DEFERRED

    def test_context_is_stored(self):
        e = _explainer()
        ctx = {"incident_id": "INC-123", "severity": "critical"}
        rec = e.record_decision(agent_id="a1", action="investigate", context=ctx)
        fetched = e.get_decision(rec.id)
        assert fetched is not None
        assert fetched.context["incident_id"] == "INC-123"
        assert fetched.context["severity"] == "critical"

    def test_none_context_defaults_to_empty_dict(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        assert rec.context == {}


class TestStepEdgeCases:
    def test_step_default_confidence(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        step = e.add_step(rec.id, "basic step")
        assert step is not None
        assert step.confidence == ConfidenceLevel.MEDIUM

    def test_step_timestamp_set(self):
        before = time.time()
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        step = e.add_step(rec.id, "timed step")
        after = time.time()
        assert step is not None
        assert before <= step.timestamp <= after

    def test_step_with_empty_inputs(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        step = e.add_step(rec.id, "no inputs")
        assert step is not None
        assert step.inputs == {}

    def test_step_ids_unique(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        s1 = e.add_step(rec.id, "step 1")
        s2 = e.add_step(rec.id, "step 2")
        assert s1 is not None and s2 is not None
        assert s1.id != s2.id


class TestAlternativeEdgeCases:
    def test_alternative_default_confidence(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        alt = e.add_alternative(rec.id, "alt option")
        assert alt is not None
        assert alt.confidence == ConfidenceLevel.LOW

    def test_alternative_ids_unique(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        a1 = e.add_alternative(rec.id, "alt 1")
        a2 = e.add_alternative(rec.id, "alt 2")
        assert a1 is not None and a2 is not None
        assert a1.id != a2.id

    def test_alternative_with_all_fields(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="test")
        alt = e.add_alternative(
            rec.id,
            "rollback",
            reason_rejected="Would cause downtime",
            estimated_impact="15min outage",
            confidence=ConfidenceLevel.HIGH,
        )
        assert alt is not None
        assert alt.description == "rollback"
        assert alt.reason_rejected == "Would cause downtime"
        assert alt.estimated_impact == "15min outage"
        assert alt.confidence == ConfidenceLevel.HIGH


class TestExplanationConfidenceField:
    def test_explanation_includes_confidence(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="scale", confidence=ConfidenceLevel.VERY_HIGH)
        explanation = e.get_explanation(rec.id)
        assert explanation is not None
        assert explanation["confidence"] == "very_high"

    def test_explanation_step_confidence(self):
        e = _explainer()
        rec = e.record_decision(agent_id="a1", action="investigate")
        e.add_step(rec.id, "Check logs", confidence=ConfidenceLevel.LOW)
        explanation = e.get_explanation(rec.id)
        assert explanation is not None
        assert explanation["steps"][0]["confidence"] == "low"


class TestListDecisionsCombined:
    def test_filter_agent_and_outcome(self):
        e = _explainer()
        r1 = e.record_decision(agent_id="a1", action="act1")
        r2 = e.record_decision(agent_id="a1", action="act2")
        r3 = e.record_decision(agent_id="a2", action="act3")
        e.finalize_decision(r1.id, DecisionOutcome.EXECUTED)
        e.finalize_decision(r2.id, DecisionOutcome.REJECTED)
        e.finalize_decision(r3.id, DecisionOutcome.EXECUTED)
        decisions = e.list_decisions(agent_id="a1", outcome=DecisionOutcome.EXECUTED)
        assert len(decisions) == 1
        assert decisions[0].id == r1.id

    def test_list_empty_engine(self):
        e = _explainer()
        assert e.list_decisions() == []


class TestCustomExplainerConfig:
    def test_custom_max_records(self):
        e = _explainer(max_records=10)
        s = e.get_stats()
        assert s["max_records"] == 10

    def test_custom_retention_days(self):
        e = _explainer(retention_days=30)
        s = e.get_stats()
        assert s["retention_days"] == 30
