"""Tests for shieldops.operations.runbook_effectiveness_scorer — RunbookEffectivenessScorer."""

from __future__ import annotations

from shieldops.operations.runbook_effectiveness_scorer import (
    EffectivenessLevel,
    EffectivenessMetric,
    EffectivenessRecord,
    ExecutionOutcome,
    RunbookCategory,
    RunbookEffectivenessReport,
    RunbookEffectivenessScorer,
)


def _engine(**kw) -> RunbookEffectivenessScorer:
    return RunbookEffectivenessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_excellent(self):
        assert EffectivenessLevel.EXCELLENT == "excellent"

    def test_level_good(self):
        assert EffectivenessLevel.GOOD == "good"

    def test_level_adequate(self):
        assert EffectivenessLevel.ADEQUATE == "adequate"

    def test_level_poor(self):
        assert EffectivenessLevel.POOR == "poor"

    def test_level_ineffective(self):
        assert EffectivenessLevel.INEFFECTIVE == "ineffective"

    def test_outcome_resolved(self):
        assert ExecutionOutcome.RESOLVED == "resolved"

    def test_outcome_partially_resolved(self):
        assert ExecutionOutcome.PARTIALLY_RESOLVED == "partially_resolved"

    def test_outcome_failed(self):
        assert ExecutionOutcome.FAILED == "failed"

    def test_outcome_skipped(self):
        assert ExecutionOutcome.SKIPPED == "skipped"

    def test_outcome_escalated(self):
        assert ExecutionOutcome.ESCALATED == "escalated"

    def test_category_incident_response(self):
        assert RunbookCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_maintenance(self):
        assert RunbookCategory.MAINTENANCE == "maintenance"

    def test_category_scaling(self):
        assert RunbookCategory.SCALING == "scaling"

    def test_category_recovery(self):
        assert RunbookCategory.RECOVERY == "recovery"

    def test_category_diagnostic(self):
        assert RunbookCategory.DIAGNOSTIC == "diagnostic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_effectiveness_record_defaults(self):
        r = EffectivenessRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.effectiveness_level == EffectivenessLevel.ADEQUATE
        assert r.execution_outcome == ExecutionOutcome.RESOLVED
        assert r.runbook_category == RunbookCategory.INCIDENT_RESPONSE
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_effectiveness_metric_defaults(self):
        m = EffectivenessMetric()
        assert m.id
        assert m.runbook_id == ""
        assert m.effectiveness_level == EffectivenessLevel.ADEQUATE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_runbook_effectiveness_report_defaults(self):
        r = RunbookEffectivenessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.poor_runbooks == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_level == {}
        assert r.by_outcome == {}
        assert r.by_category == {}
        assert r.top_poor_runbooks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_effectiveness
# ---------------------------------------------------------------------------


class TestRecordEffectiveness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
            execution_outcome=ExecutionOutcome.RESOLVED,
            runbook_category=RunbookCategory.RECOVERY,
            effectiveness_score=95.0,
            service="auth-svc",
            team="sre",
        )
        assert r.runbook_id == "RB-001"
        assert r.effectiveness_level == EffectivenessLevel.EXCELLENT
        assert r.execution_outcome == ExecutionOutcome.RESOLVED
        assert r.runbook_category == RunbookCategory.RECOVERY
        assert r.effectiveness_score == 95.0
        assert r.service == "auth-svc"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_effectiveness(runbook_id=f"RB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_effectiveness
# ---------------------------------------------------------------------------


class TestGetEffectiveness:
    def test_found(self):
        eng = _engine()
        r = eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.POOR,
        )
        result = eng.get_effectiveness(r.id)
        assert result is not None
        assert result.effectiveness_level == EffectivenessLevel.POOR

    def test_not_found(self):
        eng = _engine()
        assert eng.get_effectiveness("nonexistent") is None


# ---------------------------------------------------------------------------
# list_effectiveness
# ---------------------------------------------------------------------------


class TestListEffectiveness:
    def test_list_all(self):
        eng = _engine()
        eng.record_effectiveness(runbook_id="RB-001")
        eng.record_effectiveness(runbook_id="RB-002")
        assert len(eng.list_effectiveness()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
        )
        eng.record_effectiveness(
            runbook_id="RB-002",
            effectiveness_level=EffectivenessLevel.POOR,
        )
        results = eng.list_effectiveness(
            effectiveness_level=EffectivenessLevel.EXCELLENT,
        )
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            execution_outcome=ExecutionOutcome.RESOLVED,
        )
        eng.record_effectiveness(
            runbook_id="RB-002",
            execution_outcome=ExecutionOutcome.FAILED,
        )
        results = eng.list_effectiveness(
            execution_outcome=ExecutionOutcome.RESOLVED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_effectiveness(runbook_id="RB-001", team="sre")
        eng.record_effectiveness(runbook_id="RB-002", team="platform")
        results = eng.list_effectiveness(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_effectiveness(runbook_id=f"RB-{i}")
        assert len(eng.list_effectiveness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.GOOD,
            metric_score=80.0,
            threshold=70.0,
            breached=True,
            description="Above threshold",
        )
        assert m.runbook_id == "RB-001"
        assert m.effectiveness_level == EffectivenessLevel.GOOD
        assert m.metric_score == 80.0
        assert m.threshold == 70.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(runbook_id=f"RB-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_effectiveness_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeEffectivenessDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
            effectiveness_score=90.0,
        )
        eng.record_effectiveness(
            runbook_id="RB-002",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
            effectiveness_score=80.0,
        )
        result = eng.analyze_effectiveness_distribution()
        assert "excellent" in result
        assert result["excellent"]["count"] == 2
        assert result["excellent"]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_effectiveness_distribution() == {}


# ---------------------------------------------------------------------------
# identify_poor_runbooks
# ---------------------------------------------------------------------------


class TestIdentifyPoorRunbooks:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.POOR,
        )
        eng.record_effectiveness(
            runbook_id="RB-002",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
        )
        results = eng.identify_poor_runbooks()
        assert len(results) == 1
        assert results[0]["runbook_id"] == "RB-001"

    def test_detects_ineffective(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.INEFFECTIVE,
        )
        results = eng.identify_poor_runbooks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_runbooks() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            service="auth-svc",
            effectiveness_score=90.0,
        )
        eng.record_effectiveness(
            runbook_id="RB-002",
            service="pay-svc",
            effectiveness_score=30.0,
        )
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "pay-svc"
        assert results[0]["avg_effectiveness"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_effectiveness_trends
# ---------------------------------------------------------------------------


class TestDetectEffectivenessTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(runbook_id="RB-001", metric_score=50.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(runbook_id="RB-001", metric_score=30.0)
        eng.add_metric(runbook_id="RB-002", metric_score=30.0)
        eng.add_metric(runbook_id="RB-003", metric_score=80.0)
        eng.add_metric(runbook_id="RB-004", metric_score=80.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.POOR,
            execution_outcome=ExecutionOutcome.FAILED,
            runbook_category=RunbookCategory.INCIDENT_RESPONSE,
            effectiveness_score=25.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RunbookEffectivenessReport)
        assert report.total_records == 1
        assert report.poor_runbooks == 1
        assert len(report.top_poor_runbooks) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_effectiveness(runbook_id="RB-001")
        eng.add_metric(runbook_id="RB-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_effectiveness(
            runbook_id="RB-001",
            effectiveness_level=EffectivenessLevel.EXCELLENT,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_runbooks"] == 1
        assert "excellent" in stats["level_distribution"]
