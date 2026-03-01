"""Tests for shieldops.knowledge.knowledge_retention — KnowledgeRetentionTracker."""

from __future__ import annotations

from shieldops.knowledge.knowledge_retention import (
    KnowledgeDomain,
    KnowledgeRetentionReport,
    KnowledgeRetentionTracker,
    RetentionAssessment,
    RetentionRecord,
    RetentionRisk,
    RetentionStrategy,
)


def _engine(**kw) -> KnowledgeRetentionTracker:
    return KnowledgeRetentionTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_retention_risk_critical(self):
        assert RetentionRisk.CRITICAL == "critical"

    def test_retention_risk_high(self):
        assert RetentionRisk.HIGH == "high"

    def test_retention_risk_moderate(self):
        assert RetentionRisk.MODERATE == "moderate"

    def test_retention_risk_low(self):
        assert RetentionRisk.LOW == "low"

    def test_retention_risk_none(self):
        assert RetentionRisk.NONE == "none"

    def test_knowledge_domain_infrastructure(self):
        assert KnowledgeDomain.INFRASTRUCTURE == "infrastructure"

    def test_knowledge_domain_application(self):
        assert KnowledgeDomain.APPLICATION == "application"

    def test_knowledge_domain_security(self):
        assert KnowledgeDomain.SECURITY == "security"

    def test_knowledge_domain_networking(self):
        assert KnowledgeDomain.NETWORKING == "networking"

    def test_knowledge_domain_database(self):
        assert KnowledgeDomain.DATABASE == "database"

    def test_retention_strategy_documentation(self):
        assert RetentionStrategy.DOCUMENTATION == "documentation"

    def test_retention_strategy_cross_training(self):
        assert RetentionStrategy.CROSS_TRAINING == "cross_training"

    def test_retention_strategy_pairing(self):
        assert RetentionStrategy.PAIRING == "pairing"

    def test_retention_strategy_rotation(self):
        assert RetentionStrategy.ROTATION == "rotation"

    def test_retention_strategy_shadowing(self):
        assert RetentionStrategy.SHADOWING == "shadowing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_retention_record_defaults(self):
        r = RetentionRecord()
        assert r.id
        assert r.team_id == ""
        assert r.retention_risk == RetentionRisk.NONE
        assert r.knowledge_domain == KnowledgeDomain.INFRASTRUCTURE
        assert r.retention_strategy == RetentionStrategy.DOCUMENTATION
        assert r.retention_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_retention_assessment_defaults(self):
        a = RetentionAssessment()
        assert a.id
        assert a.team_id == ""
        assert a.retention_risk == RetentionRisk.NONE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_knowledge_retention_report_defaults(self):
        r = KnowledgeRetentionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.at_risk_count == 0
        assert r.avg_retention_score == 0.0
        assert r.by_risk == {}
        assert r.by_domain == {}
        assert r.by_strategy == {}
        assert r.top_at_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_retention
# ---------------------------------------------------------------------------


class TestRecordRetention:
    def test_basic(self):
        eng = _engine()
        r = eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.HIGH,
            knowledge_domain=KnowledgeDomain.INFRASTRUCTURE,
            retention_strategy=RetentionStrategy.CROSS_TRAINING,
            retention_score=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.team_id == "TEAM-001"
        assert r.retention_risk == RetentionRisk.HIGH
        assert r.knowledge_domain == KnowledgeDomain.INFRASTRUCTURE
        assert r.retention_strategy == RetentionStrategy.CROSS_TRAINING
        assert r.retention_score == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_retention(team_id=f"TEAM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_retention
# ---------------------------------------------------------------------------


class TestGetRetention:
    def test_found(self):
        eng = _engine()
        r = eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.MODERATE,
        )
        result = eng.get_retention(r.id)
        assert result is not None
        assert result.retention_risk == RetentionRisk.MODERATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_retention("nonexistent") is None


# ---------------------------------------------------------------------------
# list_retentions
# ---------------------------------------------------------------------------


class TestListRetentions:
    def test_list_all(self):
        eng = _engine()
        eng.record_retention(team_id="TEAM-001")
        eng.record_retention(team_id="TEAM-002")
        assert len(eng.list_retentions()) == 2

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_retention(team_id="TEAM-001", retention_risk=RetentionRisk.CRITICAL)
        eng.record_retention(team_id="TEAM-002", retention_risk=RetentionRisk.LOW)
        results = eng.list_retentions(risk=RetentionRisk.CRITICAL)
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            knowledge_domain=KnowledgeDomain.SECURITY,
        )
        eng.record_retention(
            team_id="TEAM-002",
            knowledge_domain=KnowledgeDomain.DATABASE,
        )
        results = eng.list_retentions(domain=KnowledgeDomain.SECURITY)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_retention(team_id="TEAM-001", service="api-gateway")
        eng.record_retention(team_id="TEAM-002", service="auth-svc")
        results = eng.list_retentions(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_retention(team_id="TEAM-001", team="sre")
        eng.record_retention(team_id="TEAM-002", team="platform")
        results = eng.list_retentions(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_retention(team_id=f"TEAM-{i}")
        assert len(eng.list_retentions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.HIGH,
            assessment_score=85.0,
            threshold=90.0,
            breached=True,
            description="Knowledge silo detected",
        )
        assert a.team_id == "TEAM-001"
        assert a.retention_risk == RetentionRisk.HIGH
        assert a.assessment_score == 85.0
        assert a.threshold == 90.0
        assert a.breached is True
        assert a.description == "Knowledge silo detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(team_id=f"TEAM-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_retention_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRetentionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.HIGH,
            retention_score=10.0,
        )
        eng.record_retention(
            team_id="TEAM-002",
            retention_risk=RetentionRisk.HIGH,
            retention_score=20.0,
        )
        result = eng.analyze_retention_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_retention_score"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_retention_distribution() == {}


# ---------------------------------------------------------------------------
# identify_at_risk_teams
# ---------------------------------------------------------------------------


class TestIdentifyAtRiskTeams:
    def test_detects(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.CRITICAL,
        )
        eng.record_retention(
            team_id="TEAM-002",
            retention_risk=RetentionRisk.LOW,
        )
        results = eng.identify_at_risk_teams()
        assert len(results) == 1
        assert results[0]["team_id"] == "TEAM-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk_teams() == []


# ---------------------------------------------------------------------------
# rank_by_retention_score
# ---------------------------------------------------------------------------


class TestRankByRetentionScore:
    def test_ranked(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            service="api-gateway",
            retention_score=120.0,
        )
        eng.record_retention(
            team_id="TEAM-002",
            service="auth-svc",
            retention_score=30.0,
        )
        eng.record_retention(
            team_id="TEAM-003",
            service="api-gateway",
            retention_score=80.0,
        )
        results = eng.rank_by_retention_score()
        assert len(results) == 2
        # ascending: auth-svc (30.0) first, api-gateway (100.0) second
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_retention_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_retention_score() == []


# ---------------------------------------------------------------------------
# detect_retention_trends
# ---------------------------------------------------------------------------


class TestDetectRetentionTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_assessment(team_id="TEAM-1", assessment_score=val)
        result = eng.detect_retention_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_assessment(team_id="TEAM-1", assessment_score=val)
        result = eng.detect_retention_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_shrinking(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_assessment(team_id="TEAM-1", assessment_score=val)
        result = eng.detect_retention_trends()
        assert result["trend"] == "shrinking"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_retention_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.CRITICAL,
            knowledge_domain=KnowledgeDomain.INFRASTRUCTURE,
            retention_strategy=RetentionStrategy.CROSS_TRAINING,
            retention_score=5.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeRetentionReport)
        assert report.total_records == 1
        assert report.at_risk_count == 1
        assert len(report.top_at_risk) >= 1
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
        eng.record_retention(team_id="TEAM-001")
        eng.add_assessment(team_id="TEAM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["retention_risk_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_retention(
            team_id="TEAM-001",
            retention_risk=RetentionRisk.HIGH,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "high" in stats["retention_risk_distribution"]
