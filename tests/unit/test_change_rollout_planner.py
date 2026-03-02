"""Tests for shieldops.changes.change_rollout_planner — ChangeRolloutPlanner."""

from __future__ import annotations

from shieldops.changes.change_rollout_planner import (
    ChangeRolloutPlanner,
    ChangeRolloutReport,
    RolloutAssessment,
    RolloutRecord,
    RolloutRisk,
    RolloutStage,
    RolloutStrategy,
)


def _engine(**kw) -> ChangeRolloutPlanner:
    return ChangeRolloutPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_strategy_canary(self):
        assert RolloutStrategy.CANARY == "canary"

    def test_strategy_blue_green(self):
        assert RolloutStrategy.BLUE_GREEN == "blue_green"

    def test_strategy_rolling(self):
        assert RolloutStrategy.ROLLING == "rolling"

    def test_strategy_feature_flag(self):
        assert RolloutStrategy.FEATURE_FLAG == "feature_flag"

    def test_strategy_big_bang(self):
        assert RolloutStrategy.BIG_BANG == "big_bang"

    def test_stage_planning(self):
        assert RolloutStage.PLANNING == "planning"

    def test_stage_staged(self):
        assert RolloutStage.STAGED == "staged"

    def test_stage_executing(self):
        assert RolloutStage.EXECUTING == "executing"

    def test_stage_validating(self):
        assert RolloutStage.VALIDATING == "validating"

    def test_stage_completed(self):
        assert RolloutStage.COMPLETED == "completed"

    def test_risk_critical(self):
        assert RolloutRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert RolloutRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert RolloutRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert RolloutRisk.LOW == "low"

    def test_risk_minimal(self):
        assert RolloutRisk.MINIMAL == "minimal"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rollout_record_defaults(self):
        r = RolloutRecord()
        assert r.id
        assert r.change_id == ""
        assert r.rollout_strategy == RolloutStrategy.CANARY
        assert r.rollout_stage == RolloutStage.PLANNING
        assert r.rollout_risk == RolloutRisk.CRITICAL
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_rollout_assessment_defaults(self):
        a = RolloutAssessment()
        assert a.id
        assert a.change_id == ""
        assert a.rollout_strategy == RolloutStrategy.CANARY
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_change_rollout_report_defaults(self):
        r = ChangeRolloutReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_strategy == {}
        assert r.by_stage == {}
        assert r.by_risk == {}
        assert r.top_high_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_rollout
# ---------------------------------------------------------------------------


class TestRecordRollout:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rollout(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.BLUE_GREEN,
            rollout_stage=RolloutStage.EXECUTING,
            rollout_risk=RolloutRisk.HIGH,
            risk_score=75.0,
            service="api-gw",
            team="sre",
        )
        assert r.change_id == "CHG-001"
        assert r.rollout_strategy == RolloutStrategy.BLUE_GREEN
        assert r.rollout_stage == RolloutStage.EXECUTING
        assert r.rollout_risk == RolloutRisk.HIGH
        assert r.risk_score == 75.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rollout(change_id=f"CHG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_rollout
# ---------------------------------------------------------------------------


class TestGetRollout:
    def test_found(self):
        eng = _engine()
        r = eng.record_rollout(
            change_id="CHG-001",
            rollout_risk=RolloutRisk.CRITICAL,
        )
        result = eng.get_rollout(r.id)
        assert result is not None
        assert result.rollout_risk == RolloutRisk.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rollout("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rollouts
# ---------------------------------------------------------------------------


class TestListRollouts:
    def test_list_all(self):
        eng = _engine()
        eng.record_rollout(change_id="CHG-001")
        eng.record_rollout(change_id="CHG-002")
        assert len(eng.list_rollouts()) == 2

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_rollout(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.CANARY,
        )
        eng.record_rollout(
            change_id="CHG-002",
            rollout_strategy=RolloutStrategy.ROLLING,
        )
        results = eng.list_rollouts(rollout_strategy=RolloutStrategy.CANARY)
        assert len(results) == 1

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_rollout(
            change_id="CHG-001",
            rollout_stage=RolloutStage.PLANNING,
        )
        eng.record_rollout(
            change_id="CHG-002",
            rollout_stage=RolloutStage.COMPLETED,
        )
        results = eng.list_rollouts(rollout_stage=RolloutStage.PLANNING)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rollout(change_id="CHG-001", team="sre")
        eng.record_rollout(change_id="CHG-002", team="platform")
        results = eng.list_rollouts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rollout(change_id=f"CHG-{i}")
        assert len(eng.list_rollouts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.BLUE_GREEN,
            assessment_score=88.5,
            threshold=80.0,
            breached=True,
            description="risk threshold exceeded",
        )
        assert a.change_id == "CHG-001"
        assert a.rollout_strategy == RolloutStrategy.BLUE_GREEN
        assert a.assessment_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(change_id=f"CHG-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_rollout_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRolloutDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_rollout(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.CANARY,
            risk_score=40.0,
        )
        eng.record_rollout(
            change_id="CHG-002",
            rollout_strategy=RolloutStrategy.CANARY,
            risk_score=60.0,
        )
        result = eng.analyze_rollout_distribution()
        assert "canary" in result
        assert result["canary"]["count"] == 2
        assert result["canary"]["avg_risk_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_rollout_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_rollouts
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskRollouts:
    def test_detects_above_threshold(self):
        eng = _engine(risk_tolerance_threshold=30.0)
        eng.record_rollout(change_id="CHG-001", risk_score=50.0)
        eng.record_rollout(change_id="CHG-002", risk_score=20.0)
        results = eng.identify_high_risk_rollouts()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_sorted_descending(self):
        eng = _engine(risk_tolerance_threshold=30.0)
        eng.record_rollout(change_id="CHG-001", risk_score=50.0)
        eng.record_rollout(change_id="CHG-002", risk_score=90.0)
        results = eng.identify_high_risk_rollouts()
        assert len(results) == 2
        assert results[0]["risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_rollouts() == []


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankByRisk:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_rollout(change_id="CHG-001", service="api-gw", risk_score=40.0)
        eng.record_rollout(change_id="CHG-002", service="auth", risk_score=90.0)
        results = eng.rank_by_risk()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_rollout_trends
# ---------------------------------------------------------------------------


class TestDetectRolloutTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(change_id="CHG-001", assessment_score=50.0)
        result = eng.detect_rollout_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(change_id="CHG-001", assessment_score=20.0)
        eng.add_assessment(change_id="CHG-002", assessment_score=20.0)
        eng.add_assessment(change_id="CHG-003", assessment_score=80.0)
        eng.add_assessment(change_id="CHG-004", assessment_score=80.0)
        result = eng.detect_rollout_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_rollout_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_tolerance_threshold=30.0)
        eng.record_rollout(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.CANARY,
            rollout_stage=RolloutStage.EXECUTING,
            rollout_risk=RolloutRisk.HIGH,
            risk_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeRolloutReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_high_risk) == 1
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
        eng.record_rollout(change_id="CHG-001")
        eng.add_assessment(change_id="CHG-001")
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
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rollout(
            change_id="CHG-001",
            rollout_strategy=RolloutStrategy.CANARY,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "canary" in stats["strategy_distribution"]
