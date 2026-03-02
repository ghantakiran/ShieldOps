"""Tests for shieldops.audit.audit_scope_optimizer — AuditScopeOptimizer."""

from __future__ import annotations

from shieldops.audit.audit_scope_optimizer import (
    AssessmentOutcome,
    AuditScopeOptimizer,
    AuditScopeReport,
    OptimizationAction,
    ScopeAnalysis,
    ScopeCategory,
    ScopeRecord,
)


def _engine(**kw) -> AuditScopeOptimizer:
    return AuditScopeOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scope_high_risk(self):
        assert ScopeCategory.HIGH_RISK == "high_risk"

    def test_scope_medium_risk(self):
        assert ScopeCategory.MEDIUM_RISK == "medium_risk"

    def test_scope_low_risk(self):
        assert ScopeCategory.LOW_RISK == "low_risk"

    def test_scope_compliance_required(self):
        assert ScopeCategory.COMPLIANCE_REQUIRED == "compliance_required"

    def test_scope_discretionary(self):
        assert ScopeCategory.DISCRETIONARY == "discretionary"

    def test_outcome_finding_dense(self):
        assert AssessmentOutcome.FINDING_DENSE == "finding_dense"

    def test_outcome_finding_sparse(self):
        assert AssessmentOutcome.FINDING_SPARSE == "finding_sparse"

    def test_outcome_clean(self):
        assert AssessmentOutcome.CLEAN == "clean"

    def test_outcome_deferred(self):
        assert AssessmentOutcome.DEFERRED == "deferred"

    def test_outcome_escalated(self):
        assert AssessmentOutcome.ESCALATED == "escalated"

    def test_action_expand_scope(self):
        assert OptimizationAction.EXPAND_SCOPE == "expand_scope"

    def test_action_reduce_scope(self):
        assert OptimizationAction.REDUCE_SCOPE == "reduce_scope"

    def test_action_maintain_scope(self):
        assert OptimizationAction.MAINTAIN_SCOPE == "maintain_scope"

    def test_action_automate(self):
        assert OptimizationAction.AUTOMATE == "automate"

    def test_action_delegate(self):
        assert OptimizationAction.DELEGATE == "delegate"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_scope_record_defaults(self):
        r = ScopeRecord()
        assert r.id
        assert r.audit_name == ""
        assert r.scope_category == ScopeCategory.HIGH_RISK
        assert r.assessment_outcome == AssessmentOutcome.FINDING_DENSE
        assert r.optimization_action == OptimizationAction.EXPAND_SCOPE
        assert r.efficiency_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_scope_analysis_defaults(self):
        a = ScopeAnalysis()
        assert a.id
        assert a.audit_name == ""
        assert a.scope_category == ScopeCategory.HIGH_RISK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_scope_report_defaults(self):
        r = AuditScopeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_efficiency_count == 0
        assert r.avg_efficiency_score == 0.0
        assert r.by_category == {}
        assert r.by_outcome == {}
        assert r.by_action == {}
        assert r.top_inefficient == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_scope
# ---------------------------------------------------------------------------


class TestRecordScope:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.HIGH_RISK,
            assessment_outcome=AssessmentOutcome.FINDING_DENSE,
            optimization_action=OptimizationAction.EXPAND_SCOPE,
            efficiency_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.audit_name == "AUD-001"
        assert r.scope_category == ScopeCategory.HIGH_RISK
        assert r.assessment_outcome == AssessmentOutcome.FINDING_DENSE
        assert r.optimization_action == OptimizationAction.EXPAND_SCOPE
        assert r.efficiency_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scope(audit_name=f"AUD-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_scope
# ---------------------------------------------------------------------------


class TestGetScope:
    def test_found(self):
        eng = _engine()
        r = eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.MEDIUM_RISK,
        )
        result = eng.get_scope(r.id)
        assert result is not None
        assert result.scope_category == ScopeCategory.MEDIUM_RISK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scope("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scopes
# ---------------------------------------------------------------------------


class TestListScopes:
    def test_list_all(self):
        eng = _engine()
        eng.record_scope(audit_name="AUD-001")
        eng.record_scope(audit_name="AUD-002")
        assert len(eng.list_scopes()) == 2

    def test_filter_by_scope_category(self):
        eng = _engine()
        eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.HIGH_RISK,
        )
        eng.record_scope(
            audit_name="AUD-002",
            scope_category=ScopeCategory.LOW_RISK,
        )
        results = eng.list_scopes(scope_category=ScopeCategory.HIGH_RISK)
        assert len(results) == 1

    def test_filter_by_assessment_outcome(self):
        eng = _engine()
        eng.record_scope(
            audit_name="AUD-001",
            assessment_outcome=AssessmentOutcome.FINDING_DENSE,
        )
        eng.record_scope(
            audit_name="AUD-002",
            assessment_outcome=AssessmentOutcome.CLEAN,
        )
        results = eng.list_scopes(assessment_outcome=AssessmentOutcome.FINDING_DENSE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scope(audit_name="AUD-001", team="sre")
        eng.record_scope(audit_name="AUD-002", team="platform")
        results = eng.list_scopes(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_scope(audit_name=f"AUD-{i}")
        assert len(eng.list_scopes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            audit_name="AUD-001",
            scope_category=ScopeCategory.COMPLIANCE_REQUIRED,
            analysis_score=72.0,
            threshold=70.0,
            breached=True,
            description="Efficiency below target",
        )
        assert a.audit_name == "AUD-001"
        assert a.scope_category == ScopeCategory.COMPLIANCE_REQUIRED
        assert a.analysis_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(audit_name=f"AUD-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_scope_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeScopeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.HIGH_RISK,
            efficiency_score=80.0,
        )
        eng.record_scope(
            audit_name="AUD-002",
            scope_category=ScopeCategory.HIGH_RISK,
            efficiency_score=90.0,
        )
        result = eng.analyze_scope_distribution()
        assert "high_risk" in result
        assert result["high_risk"]["count"] == 2
        assert result["high_risk"]["avg_efficiency_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_scope_distribution() == {}


# ---------------------------------------------------------------------------
# identify_inefficient_scopes
# ---------------------------------------------------------------------------


class TestIdentifyInefficientScopes:
    def test_detects_inefficient(self):
        eng = _engine(scope_efficiency_threshold=70.0)
        eng.record_scope(
            audit_name="AUD-001",
            efficiency_score=30.0,
        )
        eng.record_scope(
            audit_name="AUD-002",
            efficiency_score=80.0,
        )
        results = eng.identify_inefficient_scopes()
        assert len(results) == 1
        assert results[0]["audit_name"] == "AUD-001"

    def test_sorted_ascending(self):
        eng = _engine(scope_efficiency_threshold=70.0)
        eng.record_scope(audit_name="AUD-001", efficiency_score=40.0)
        eng.record_scope(audit_name="AUD-002", efficiency_score=20.0)
        results = eng.identify_inefficient_scopes()
        assert len(results) == 2
        assert results[0]["efficiency_score"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inefficient_scopes() == []


# ---------------------------------------------------------------------------
# rank_by_efficiency
# ---------------------------------------------------------------------------


class TestRankByEfficiency:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_scope(audit_name="AUD-001", efficiency_score=90.0, service="svc-a")
        eng.record_scope(audit_name="AUD-002", efficiency_score=50.0, service="svc-b")
        results = eng.rank_by_efficiency()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_efficiency_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency() == []


# ---------------------------------------------------------------------------
# detect_scope_trends
# ---------------------------------------------------------------------------


class TestDetectScopeTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(audit_name="AUD-001", analysis_score=70.0)
        result = eng.detect_scope_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(audit_name="AUD-001", analysis_score=50.0)
        eng.add_analysis(audit_name="AUD-002", analysis_score=50.0)
        eng.add_analysis(audit_name="AUD-003", analysis_score=80.0)
        eng.add_analysis(audit_name="AUD-004", analysis_score=80.0)
        result = eng.detect_scope_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_scope_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(scope_efficiency_threshold=70.0)
        eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.HIGH_RISK,
            assessment_outcome=AssessmentOutcome.FINDING_DENSE,
            efficiency_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditScopeReport)
        assert report.total_records == 1
        assert report.low_efficiency_count == 1
        assert len(report.top_inefficient) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_scope(audit_name="AUD-001")
        eng.add_analysis(audit_name="AUD-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["scope_category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_scope(
            audit_name="AUD-001",
            scope_category=ScopeCategory.HIGH_RISK,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "high_risk" in stats["scope_category_distribution"]
