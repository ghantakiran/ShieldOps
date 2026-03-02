"""Tests for shieldops.security.insider_threat_ai_scorer — InsiderThreatAIScorer."""

from __future__ import annotations

from shieldops.security.insider_threat_ai_scorer import (
    BehaviorPattern,
    InsiderThreatAIScorer,
    InsiderThreatAnalysis,
    InsiderThreatRecord,
    InsiderThreatReport,
    RiskTier,
    ThreatIndicator,
)


def _engine(**kw) -> InsiderThreatAIScorer:
    return InsiderThreatAIScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_indicator_data_hoarding(self):
        assert ThreatIndicator.DATA_HOARDING == "data_hoarding"

    def test_indicator_unusual_access(self):
        assert ThreatIndicator.UNUSUAL_ACCESS == "unusual_access"

    def test_indicator_resignation_signal(self):
        assert ThreatIndicator.RESIGNATION_SIGNAL == "resignation_signal"

    def test_indicator_privilege_abuse(self):
        assert ThreatIndicator.PRIVILEGE_ABUSE == "privilege_abuse"

    def test_indicator_policy_violation(self):
        assert ThreatIndicator.POLICY_VIOLATION == "policy_violation"

    def test_tier_critical(self):
        assert RiskTier.CRITICAL == "critical"

    def test_tier_high(self):
        assert RiskTier.HIGH == "high"

    def test_tier_elevated(self):
        assert RiskTier.ELEVATED == "elevated"

    def test_tier_moderate(self):
        assert RiskTier.MODERATE == "moderate"

    def test_tier_low(self):
        assert RiskTier.LOW == "low"

    def test_pattern_consistent(self):
        assert BehaviorPattern.CONSISTENT == "consistent"

    def test_pattern_escalating(self):
        assert BehaviorPattern.ESCALATING == "escalating"

    def test_pattern_sporadic(self):
        assert BehaviorPattern.SPORADIC == "sporadic"

    def test_pattern_declining(self):
        assert BehaviorPattern.DECLINING == "declining"

    def test_pattern_new(self):
        assert BehaviorPattern.NEW == "new"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_insider_threat_record_defaults(self):
        r = InsiderThreatRecord()
        assert r.id
        assert r.subject_name == ""
        assert r.threat_indicator == ThreatIndicator.DATA_HOARDING
        assert r.risk_tier == RiskTier.CRITICAL
        assert r.behavior_pattern == BehaviorPattern.CONSISTENT
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_insider_threat_analysis_defaults(self):
        c = InsiderThreatAnalysis()
        assert c.id
        assert c.subject_name == ""
        assert c.threat_indicator == ThreatIndicator.DATA_HOARDING
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_insider_threat_report_defaults(self):
        r = InsiderThreatReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_threat_count == 0
        assert r.avg_threat_score == 0.0
        assert r.by_indicator == {}
        assert r.by_tier == {}
        assert r.by_pattern == {}
        assert r.top_high_threat == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_threat
# ---------------------------------------------------------------------------


class TestRecordThreat:
    def test_basic(self):
        eng = _engine()
        r = eng.record_threat(
            subject_name="user-123",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
            risk_tier=RiskTier.HIGH,
            behavior_pattern=BehaviorPattern.ESCALATING,
            threat_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.subject_name == "user-123"
        assert r.threat_indicator == ThreatIndicator.UNUSUAL_ACCESS
        assert r.risk_tier == RiskTier.HIGH
        assert r.behavior_pattern == BehaviorPattern.ESCALATING
        assert r.threat_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(subject_name=f"S-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_threat
# ---------------------------------------------------------------------------


class TestGetThreat:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat(
            subject_name="user-123",
            risk_tier=RiskTier.CRITICAL,
        )
        result = eng.get_threat(r.id)
        assert result is not None
        assert result.risk_tier == RiskTier.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threat("nonexistent") is None


# ---------------------------------------------------------------------------
# list_threats
# ---------------------------------------------------------------------------


class TestListThreats:
    def test_list_all(self):
        eng = _engine()
        eng.record_threat(subject_name="S-001")
        eng.record_threat(subject_name="S-002")
        assert len(eng.list_threats()) == 2

    def test_filter_by_threat_indicator(self):
        eng = _engine()
        eng.record_threat(
            subject_name="S-001",
            threat_indicator=ThreatIndicator.DATA_HOARDING,
        )
        eng.record_threat(
            subject_name="S-002",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
        )
        results = eng.list_threats(threat_indicator=ThreatIndicator.DATA_HOARDING)
        assert len(results) == 1

    def test_filter_by_risk_tier(self):
        eng = _engine()
        eng.record_threat(
            subject_name="S-001",
            risk_tier=RiskTier.CRITICAL,
        )
        eng.record_threat(
            subject_name="S-002",
            risk_tier=RiskTier.LOW,
        )
        results = eng.list_threats(
            risk_tier=RiskTier.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threat(subject_name="S-001", team="security")
        eng.record_threat(subject_name="S-002", team="platform")
        results = eng.list_threats(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threat(subject_name=f"S-{i}")
        assert len(eng.list_threats(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            subject_name="user-123",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="threat escalation detected",
        )
        assert a.subject_name == "user-123"
        assert a.threat_indicator == ThreatIndicator.UNUSUAL_ACCESS
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(subject_name=f"S-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_threat_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_threat(
            subject_name="S-001",
            threat_indicator=ThreatIndicator.DATA_HOARDING,
            threat_score=90.0,
        )
        eng.record_threat(
            subject_name="S-002",
            threat_indicator=ThreatIndicator.DATA_HOARDING,
            threat_score=70.0,
        )
        result = eng.analyze_threat_distribution()
        assert "data_hoarding" in result
        assert result["data_hoarding"]["count"] == 2
        assert result["data_hoarding"]["avg_threat_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_threat_subjects
# ---------------------------------------------------------------------------


class TestIdentifyHighThreatSubjects:
    def test_detects_above_threshold(self):
        eng = _engine(insider_threat_threshold=65.0)
        eng.record_threat(subject_name="S-001", threat_score=90.0)
        eng.record_threat(subject_name="S-002", threat_score=40.0)
        results = eng.identify_high_threat_subjects()
        assert len(results) == 1
        assert results[0]["subject_name"] == "S-001"

    def test_sorted_descending(self):
        eng = _engine(insider_threat_threshold=65.0)
        eng.record_threat(subject_name="S-001", threat_score=80.0)
        eng.record_threat(subject_name="S-002", threat_score=95.0)
        results = eng.identify_high_threat_subjects()
        assert len(results) == 2
        assert results[0]["threat_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_threat_subjects() == []


# ---------------------------------------------------------------------------
# rank_by_threat_score
# ---------------------------------------------------------------------------


class TestRankByThreatScore:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_threat(subject_name="S-001", service="auth-svc", threat_score=50.0)
        eng.record_threat(subject_name="S-002", service="api-gw", threat_score=90.0)
        results = eng.rank_by_threat_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_threat_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat_score() == []


# ---------------------------------------------------------------------------
# detect_threat_trends
# ---------------------------------------------------------------------------


class TestDetectThreatTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(subject_name="S-001", analysis_score=50.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(subject_name="S-001", analysis_score=20.0)
        eng.add_analysis(subject_name="S-002", analysis_score=20.0)
        eng.add_analysis(subject_name="S-003", analysis_score=80.0)
        eng.add_analysis(subject_name="S-004", analysis_score=80.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_threat_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(insider_threat_threshold=50.0)
        eng.record_threat(
            subject_name="user-123",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
            risk_tier=RiskTier.HIGH,
            behavior_pattern=BehaviorPattern.ESCALATING,
            threat_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, InsiderThreatReport)
        assert report.total_records == 1
        assert report.high_threat_count == 1
        assert len(report.top_high_threat) == 1
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
        eng.record_threat(subject_name="S-001")
        eng.add_analysis(subject_name="S-001")
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
        assert stats["indicator_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            subject_name="S-001",
            threat_indicator=ThreatIndicator.DATA_HOARDING,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "data_hoarding" in stats["indicator_distribution"]
