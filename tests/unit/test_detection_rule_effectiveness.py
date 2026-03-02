"""Tests for shieldops.security.detection_rule_effectiveness — DetectionRuleEffectiveness."""

from __future__ import annotations

from shieldops.security.detection_rule_effectiveness import (
    DetectionRuleEffectiveness,
    DetectionRuleReport,
    EffectivenessLevel,
    RuleAnalysis,
    RuleRecord,
    RuleStatus,
    RuleType,
)


def _engine(**kw) -> DetectionRuleEffectiveness:
    return DetectionRuleEffectiveness(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_signature(self):
        assert RuleType.SIGNATURE == "signature"

    def test_type_behavioral(self):
        assert RuleType.BEHAVIORAL == "behavioral"

    def test_type_anomaly(self):
        assert RuleType.ANOMALY == "anomaly"

    def test_type_correlation(self):
        assert RuleType.CORRELATION == "correlation"

    def test_type_custom(self):
        assert RuleType.CUSTOM == "custom"

    def test_status_active(self):
        assert RuleStatus.ACTIVE == "active"

    def test_status_tuning(self):
        assert RuleStatus.TUNING == "tuning"

    def test_status_deprecated(self):
        assert RuleStatus.DEPRECATED == "deprecated"

    def test_status_testing(self):
        assert RuleStatus.TESTING == "testing"

    def test_status_disabled(self):
        assert RuleStatus.DISABLED == "disabled"

    def test_effectiveness_high_performing(self):
        assert EffectivenessLevel.HIGH_PERFORMING == "high_performing"

    def test_effectiveness_effective(self):
        assert EffectivenessLevel.EFFECTIVE == "effective"

    def test_effectiveness_moderate(self):
        assert EffectivenessLevel.MODERATE == "moderate"

    def test_effectiveness_underperforming(self):
        assert EffectivenessLevel.UNDERPERFORMING == "underperforming"

    def test_effectiveness_ineffective(self):
        assert EffectivenessLevel.INEFFECTIVE == "ineffective"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rule_record_defaults(self):
        r = RuleRecord()
        assert r.id
        assert r.rule_name == ""
        assert r.rule_type == RuleType.SIGNATURE
        assert r.rule_status == RuleStatus.ACTIVE
        assert r.effectiveness_level == EffectivenessLevel.HIGH_PERFORMING
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_rule_analysis_defaults(self):
        c = RuleAnalysis()
        assert c.id
        assert c.rule_name == ""
        assert c.rule_type == RuleType.SIGNATURE
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_detection_rule_report_defaults(self):
        r = DetectionRuleReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_effectiveness == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_rule
# ---------------------------------------------------------------------------


class TestRecordRule:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rule(
            rule_name="brute-force-detection",
            rule_type=RuleType.BEHAVIORAL,
            rule_status=RuleStatus.ACTIVE,
            effectiveness_level=EffectivenessLevel.EFFECTIVE,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.rule_name == "brute-force-detection"
        assert r.rule_type == RuleType.BEHAVIORAL
        assert r.rule_status == RuleStatus.ACTIVE
        assert r.effectiveness_level == EffectivenessLevel.EFFECTIVE
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rule(rule_name=f"RULE-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------


class TestGetRule:
    def test_found(self):
        eng = _engine()
        r = eng.record_rule(
            rule_name="brute-force-detection",
            effectiveness_level=EffectivenessLevel.UNDERPERFORMING,
        )
        result = eng.get_rule(r.id)
        assert result is not None
        assert result.effectiveness_level == EffectivenessLevel.UNDERPERFORMING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rule("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_list_all(self):
        eng = _engine()
        eng.record_rule(rule_name="RULE-001")
        eng.record_rule(rule_name="RULE-002")
        assert len(eng.list_rules()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_rule(
            rule_name="RULE-001",
            rule_type=RuleType.CORRELATION,
        )
        eng.record_rule(
            rule_name="RULE-002",
            rule_type=RuleType.ANOMALY,
        )
        results = eng.list_rules(rule_type=RuleType.CORRELATION)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_rule(
            rule_name="RULE-001",
            rule_status=RuleStatus.ACTIVE,
        )
        eng.record_rule(
            rule_name="RULE-002",
            rule_status=RuleStatus.DISABLED,
        )
        results = eng.list_rules(
            rule_status=RuleStatus.ACTIVE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rule(rule_name="RULE-001", team="security")
        eng.record_rule(rule_name="RULE-002", team="platform")
        results = eng.list_rules(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rule(rule_name=f"RULE-{i}")
        assert len(eng.list_rules(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        c = eng.add_analysis(
            rule_name="brute-force-detection",
            rule_type=RuleType.SIGNATURE,
            analysis_score=88.5,
        )
        assert c.rule_name == "brute-force-detection"
        assert c.rule_type == RuleType.SIGNATURE
        assert c.analysis_score == 88.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(rule_name=f"RULE-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_rule_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_rule(
            rule_name="RULE-001",
            rule_type=RuleType.CORRELATION,
            effectiveness_score=90.0,
        )
        eng.record_rule(
            rule_name="RULE-002",
            rule_type=RuleType.CORRELATION,
            effectiveness_score=70.0,
        )
        result = eng.analyze_rule_distribution()
        assert "correlation" in result
        assert result["correlation"]["count"] == 2
        assert result["correlation"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_rule_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_rules
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessRules:
    def test_detects_below_threshold(self):
        eng = _engine(rule_effectiveness_threshold=80.0)
        eng.record_rule(rule_name="RULE-001", effectiveness_score=60.0)
        eng.record_rule(rule_name="RULE-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_rules()
        assert len(results) == 1
        assert results[0]["rule_name"] == "RULE-001"

    def test_sorted_ascending(self):
        eng = _engine(rule_effectiveness_threshold=80.0)
        eng.record_rule(rule_name="RULE-001", effectiveness_score=50.0)
        eng.record_rule(rule_name="RULE-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_rules()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_rules() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_rule(rule_name="RULE-001", service="auth-svc", effectiveness_score=90.0)
        eng.record_rule(rule_name="RULE-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_rule_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(rule_name="RULE-001", analysis_score=50.0)
        result = eng.detect_rule_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(rule_name="RULE-001", analysis_score=20.0)
        eng.add_analysis(rule_name="RULE-002", analysis_score=20.0)
        eng.add_analysis(rule_name="RULE-003", analysis_score=80.0)
        eng.add_analysis(rule_name="RULE-004", analysis_score=80.0)
        result = eng.detect_rule_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_rule_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(rule_effectiveness_threshold=80.0)
        eng.record_rule(
            rule_name="brute-force-detection",
            rule_type=RuleType.BEHAVIORAL,
            rule_status=RuleStatus.ACTIVE,
            effectiveness_level=EffectivenessLevel.UNDERPERFORMING,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DetectionRuleReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
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
        eng.record_rule(rule_name="RULE-001")
        eng.add_analysis(rule_name="RULE-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rule(
            rule_name="RULE-001",
            rule_type=RuleType.CORRELATION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "correlation" in stats["type_distribution"]
