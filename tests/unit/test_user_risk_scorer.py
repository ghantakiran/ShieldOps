"""Tests for shieldops.analytics.user_risk_scorer — UserRiskScorer."""

from __future__ import annotations

from shieldops.analytics.user_risk_scorer import (
    RiskFactor,
    RiskLevel,
    ScoringModel,
    UserRiskAnalysis,
    UserRiskRecord,
    UserRiskReport,
    UserRiskScorer,
)


def _engine(**kw) -> UserRiskScorer:
    return UserRiskScorer(**kw)


class TestEnums:
    def test_factor_access_pattern(self):
        assert RiskFactor.ACCESS_PATTERN == "access_pattern"

    def test_factor_data_handling(self):
        assert RiskFactor.DATA_HANDLING == "data_handling"

    def test_factor_authentication_anomaly(self):
        assert RiskFactor.AUTHENTICATION_ANOMALY == "authentication_anomaly"

    def test_factor_policy_violation(self):
        assert RiskFactor.POLICY_VIOLATION == "policy_violation"

    def test_factor_behavioral_change(self):
        assert RiskFactor.BEHAVIORAL_CHANGE == "behavioral_change"

    def test_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_level_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_level_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_model_rule_based(self):
        assert ScoringModel.RULE_BASED == "rule_based"

    def test_model_ml_based(self):
        assert ScoringModel.ML_BASED == "ml_based"

    def test_model_hybrid(self):
        assert ScoringModel.HYBRID == "hybrid"

    def test_model_peer_comparison(self):
        assert ScoringModel.PEER_COMPARISON == "peer_comparison"

    def test_model_contextual(self):
        assert ScoringModel.CONTEXTUAL == "contextual"


class TestModels:
    def test_record_defaults(self):
        r = UserRiskRecord()
        assert r.id
        assert r.user_name == ""
        assert r.risk_factor == RiskFactor.ACCESS_PATTERN
        assert r.risk_level == RiskLevel.MINIMAL
        assert r.scoring_model == ScoringModel.RULE_BASED
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = UserRiskAnalysis()
        assert a.id
        assert a.user_name == ""
        assert a.risk_factor == RiskFactor.ACCESS_PATTERN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = UserRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_risk_factor == {}
        assert r.by_risk_level == {}
        assert r.by_scoring_model == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_risk(
            user_name="admin-user",
            risk_factor=RiskFactor.POLICY_VIOLATION,
            risk_level=RiskLevel.HIGH,
            scoring_model=ScoringModel.HYBRID,
            risk_score=85.0,
            service="auth-svc",
            team="security",
        )
        assert r.user_name == "admin-user"
        assert r.risk_factor == RiskFactor.POLICY_VIOLATION
        assert r.risk_score == 85.0
        assert r.service == "auth-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(user_name=f"user-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk(user_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk(user_name="a")
        eng.record_risk(user_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_risk_factor(self):
        eng = _engine()
        eng.record_risk(user_name="a", risk_factor=RiskFactor.ACCESS_PATTERN)
        eng.record_risk(user_name="b", risk_factor=RiskFactor.DATA_HANDLING)
        assert len(eng.list_records(risk_factor=RiskFactor.ACCESS_PATTERN)) == 1

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_risk(user_name="a", risk_level=RiskLevel.LOW)
        eng.record_risk(user_name="b", risk_level=RiskLevel.HIGH)
        assert len(eng.list_records(risk_level=RiskLevel.LOW)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_risk(user_name="a", team="sec")
        eng.record_risk(user_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_risk(user_name=f"u-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            user_name="test", analysis_score=88.5, breached=True, description="high risk"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(user_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk(user_name="a", risk_factor=RiskFactor.ACCESS_PATTERN, risk_score=90.0)
        eng.record_risk(user_name="b", risk_factor=RiskFactor.ACCESS_PATTERN, risk_score=70.0)
        result = eng.analyze_distribution()
        assert "access_pattern" in result
        assert result["access_pattern"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(user_name="a", risk_score=60.0)
        eng.record_risk(user_name="b", risk_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(user_name="a", risk_score=50.0)
        eng.record_risk(user_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_risk(user_name="a", service="auth", risk_score=90.0)
        eng.record_risk(user_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(user_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(user_name="a", analysis_score=20.0)
        eng.add_analysis(user_name="b", analysis_score=20.0)
        eng.add_analysis(user_name="c", analysis_score=80.0)
        eng.add_analysis(user_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(user_name="test", risk_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_risk(user_name="test")
        eng.add_analysis(user_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_risk(user_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
