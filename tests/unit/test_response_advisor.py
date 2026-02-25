"""Tests for shieldops.incidents.response_advisor — IncidentResponseAdvisor."""

from __future__ import annotations

from shieldops.incidents.response_advisor import (
    ConfidenceBand,
    IncidentContext,
    IncidentResponseAdvisor,
    ResponseAdvisorReport,
    ResponseRecommendation,
    ResponseStrategy,
    Urgency,
)


def _engine(**kw) -> IncidentResponseAdvisor:
    return IncidentResponseAdvisor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ResponseStrategy (5)
    def test_strategy_escalate(self):
        assert ResponseStrategy.ESCALATE == "escalate"

    def test_strategy_mitigate(self):
        assert ResponseStrategy.MITIGATE == "mitigate"

    def test_strategy_failover(self):
        assert ResponseStrategy.FAILOVER == "failover"

    def test_strategy_rollback(self):
        assert ResponseStrategy.ROLLBACK == "rollback"

    def test_strategy_observe(self):
        assert ResponseStrategy.OBSERVE == "observe"

    # Urgency (5)
    def test_urgency_immediate(self):
        assert Urgency.IMMEDIATE == "immediate"

    def test_urgency_high(self):
        assert Urgency.HIGH == "high"

    def test_urgency_moderate(self):
        assert Urgency.MODERATE == "moderate"

    def test_urgency_low(self):
        assert Urgency.LOW == "low"

    def test_urgency_deferred(self):
        assert Urgency.DEFERRED == "deferred"

    # ConfidenceBand (5)
    def test_confidence_very_high(self):
        assert ConfidenceBand.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert ConfidenceBand.HIGH == "high"

    def test_confidence_medium(self):
        assert ConfidenceBand.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ConfidenceBand.LOW == "low"

    def test_confidence_insufficient_data(self):
        assert ConfidenceBand.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_context_defaults(self):
        c = IncidentContext()
        assert c.id
        assert c.incident_id == ""
        assert c.service == ""
        assert c.severity == "medium"
        assert c.blast_radius == 1
        assert c.error_budget_remaining_pct == 100.0
        assert c.active_users_affected == 0
        assert c.created_at > 0

    def test_response_recommendation_defaults(self):
        r = ResponseRecommendation()
        assert r.id
        assert r.incident_id == ""
        assert r.strategy == ResponseStrategy.OBSERVE
        assert r.urgency == Urgency.MODERATE
        assert r.confidence == ConfidenceBand.MEDIUM
        assert r.confidence_score == 0.5
        assert r.estimated_resolution_minutes == 60.0
        assert r.rationale == ""
        assert r.created_at > 0

    def test_response_advisor_report_defaults(self):
        r = ResponseAdvisorReport()
        assert r.total_contexts == 0
        assert r.total_recommendations == 0
        assert r.by_strategy == {}
        assert r.by_urgency == {}
        assert r.avg_confidence_score == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_context
# ---------------------------------------------------------------------------


class TestRecordContext:
    def test_basic(self):
        eng = _engine()
        ctx = eng.record_context(incident_id="INC-001", service="api-gw")
        assert ctx.incident_id == "INC-001"
        assert ctx.service == "api-gw"
        assert ctx.severity == "medium"
        assert ctx.blast_radius == 1

    def test_with_params(self):
        eng = _engine()
        ctx = eng.record_context(
            incident_id="INC-002",
            service="payment-svc",
            severity="critical",
            blast_radius=120,
            error_budget_remaining_pct=3.0,
            active_users_affected=8000,
        )
        assert ctx.severity == "critical"
        assert ctx.blast_radius == 120
        assert ctx.error_budget_remaining_pct == 3.0
        assert ctx.active_users_affected == 8000

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_context(incident_id=f"INC-{i}", service="svc")
        assert len(eng._contexts) == 3


# ---------------------------------------------------------------------------
# get_context
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_found(self):
        eng = _engine()
        ctx = eng.record_context(incident_id="INC-001", service="api-gw")
        result = eng.get_context(ctx.id)
        assert result is not None
        assert result.incident_id == "INC-001"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_context("nonexistent") is None


# ---------------------------------------------------------------------------
# list_contexts
# ---------------------------------------------------------------------------


class TestListContexts:
    def test_list_all(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="api-gw")
        eng.record_context(incident_id="INC-002", service="payment-svc")
        assert len(eng.list_contexts()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="api-gw")
        eng.record_context(incident_id="INC-002", service="payment-svc")
        results = eng.list_contexts(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_respects_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_context(incident_id=f"INC-{i}", service="svc")
        results = eng.list_contexts(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# generate_recommendation
# ---------------------------------------------------------------------------


class TestGenerateRecommendation:
    def test_no_context_defaults_observe(self):
        eng = _engine()
        rec = eng.generate_recommendation(incident_id="INC-MISSING")
        assert rec.strategy == ResponseStrategy.OBSERVE
        assert rec.urgency == Urgency.LOW
        assert rec.confidence == ConfidenceBand.INSUFFICIENT_DATA
        assert rec.confidence_score == 0.2

    def test_low_error_budget_triggers_rollback(self):
        eng = _engine()
        eng.record_context(
            incident_id="INC-001",
            service="svc",
            severity="high",
            error_budget_remaining_pct=5.0,
        )
        rec = eng.generate_recommendation(incident_id="INC-001")
        assert rec.strategy == ResponseStrategy.ROLLBACK
        assert rec.confidence_score == 0.85
        assert rec.estimated_resolution_minutes == 15.0

    def test_large_blast_radius_triggers_failover(self):
        eng = _engine()
        eng.record_context(
            incident_id="INC-002",
            service="svc",
            severity="medium",
            blast_radius=80,
        )
        rec = eng.generate_recommendation(incident_id="INC-002")
        assert rec.strategy == ResponseStrategy.FAILOVER
        assert rec.confidence_score == 0.8


# ---------------------------------------------------------------------------
# rank_strategies
# ---------------------------------------------------------------------------


class TestRankStrategies:
    def test_returns_ranked_list(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc", severity="critical")
        rankings = eng.rank_strategies("INC-001")
        assert len(rankings) == 5
        # Check descending score order
        scores = [r["score"] for r in rankings]
        assert scores == sorted(scores, reverse=True)

    def test_no_context_returns_empty(self):
        eng = _engine()
        assert eng.rank_strategies("INC-MISSING") == []


# ---------------------------------------------------------------------------
# assess_escalation_need
# ---------------------------------------------------------------------------


class TestAssessEscalationNeed:
    def test_needs_escalation_critical(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc", severity="critical")
        result = eng.assess_escalation_need("INC-001")
        assert result["needs_escalation"] is True
        assert "critical severity" in result["reason"]

    def test_no_escalation_needed(self):
        eng = _engine()
        eng.record_context(incident_id="INC-002", service="svc", severity="low")
        result = eng.assess_escalation_need("INC-002")
        assert result["needs_escalation"] is False
        assert result["reason"] == "within normal parameters"

    def test_no_context(self):
        eng = _engine()
        result = eng.assess_escalation_need("INC-MISSING")
        assert result["needs_escalation"] is False
        assert result["reason"] == "no context"


# ---------------------------------------------------------------------------
# estimate_resolution_time
# ---------------------------------------------------------------------------


class TestEstimateResolutionTime:
    def test_critical_severity(self):
        eng = _engine()
        eng.record_context(
            incident_id="INC-001",
            service="svc",
            severity="critical",
            blast_radius=50,
        )
        result = eng.estimate_resolution_time("INC-001")
        assert result["incident_id"] == "INC-001"
        # base 30 * (1 + 50/100) = 45.0
        assert result["estimated_minutes"] == 45.0
        assert result["confidence_score"] == 0.5

    def test_no_context(self):
        eng = _engine()
        result = eng.estimate_resolution_time("INC-MISSING")
        assert result["estimated_minutes"] == 0
        assert result["confidence"] == "insufficient_data"


# ---------------------------------------------------------------------------
# list_recommendations
# ---------------------------------------------------------------------------


class TestListRecommendations:
    def test_list_all(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc")
        eng.generate_recommendation("INC-001")
        eng.record_context(incident_id="INC-002", service="svc2")
        eng.generate_recommendation("INC-002")
        assert len(eng.list_recommendations()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc")
        eng.generate_recommendation("INC-001")
        eng.record_context(incident_id="INC-002", service="svc2")
        eng.generate_recommendation("INC-002")
        results = eng.list_recommendations(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_context(
            incident_id="INC-001",
            service="svc",
            severity="critical",
            blast_radius=120,
        )
        eng.generate_recommendation("INC-001")
        eng.record_context(
            incident_id="INC-002",
            service="svc2",
            severity="low",
        )
        eng.generate_recommendation("INC-002")
        report = eng.generate_report()
        assert isinstance(report, ResponseAdvisorReport)
        assert report.total_contexts == 2
        assert report.total_recommendations == 2
        assert len(report.by_strategy) > 0
        assert len(report.by_urgency) > 0
        assert report.avg_confidence_score > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_contexts == 0
        assert report.total_recommendations == 0
        # avg_confidence=0.0 < threshold=0.6, so threshold warning fires
        assert "Average confidence below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc")
        eng.generate_recommendation("INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._contexts) == 0
        assert len(eng._recommendations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_contexts"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["strategy_distribution"] == {}
        assert stats["unique_incidents"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_context(incident_id="INC-001", service="svc")
        eng.generate_recommendation("INC-001")
        stats = eng.get_stats()
        assert stats["total_contexts"] == 1
        assert stats["total_recommendations"] == 1
        assert stats["confidence_threshold"] == 0.6
        assert stats["unique_incidents"] == 1
        assert len(stats["strategy_distribution"]) > 0
