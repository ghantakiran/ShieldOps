"""Tests for shieldops.observability.alert_priority — AlertPriorityOptimizer."""

from __future__ import annotations

from shieldops.observability.alert_priority import (
    AlertPriorityOptimizer,
    AlertPriorityReport,
    OptimizationAction,
    PriorityLevel,
    PriorityRecord,
    PriorityRule,
    ResponsePattern,
)


def _engine(**kw) -> AlertPriorityOptimizer:
    return AlertPriorityOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_priority_critical(self):
        assert PriorityLevel.CRITICAL == "critical"

    def test_priority_high(self):
        assert PriorityLevel.HIGH == "high"

    def test_priority_medium(self):
        assert PriorityLevel.MEDIUM == "medium"

    def test_priority_low(self):
        assert PriorityLevel.LOW == "low"

    def test_priority_informational(self):
        assert PriorityLevel.INFORMATIONAL == "informational"

    def test_action_upgrade(self):
        assert OptimizationAction.UPGRADE == "upgrade"

    def test_action_maintain(self):
        assert OptimizationAction.MAINTAIN == "maintain"

    def test_action_downgrade(self):
        assert OptimizationAction.DOWNGRADE == "downgrade"

    def test_action_suppress(self):
        assert OptimizationAction.SUPPRESS == "suppress"

    def test_action_review(self):
        assert OptimizationAction.REVIEW == "review"

    def test_response_immediate(self):
        assert ResponsePattern.IMMEDIATE == "immediate"

    def test_response_delayed(self):
        assert ResponsePattern.DELAYED == "delayed"

    def test_response_ignored(self):
        assert ResponsePattern.IGNORED == "ignored"

    def test_response_escalated(self):
        assert ResponsePattern.ESCALATED == "escalated"

    def test_response_auto_resolved(self):
        assert ResponsePattern.AUTO_RESOLVED == "auto_resolved"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_priority_record_defaults(self):
        r = PriorityRecord()
        assert r.id
        assert r.alert_type == ""
        assert r.current_priority == PriorityLevel.INFORMATIONAL
        assert r.suggested_priority == PriorityLevel.INFORMATIONAL
        assert r.action == OptimizationAction.MAINTAIN
        assert r.response_pattern == ResponsePattern.IMMEDIATE
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_priority_rule_defaults(self):
        ru = PriorityRule()
        assert ru.id
        assert ru.alert_pattern == ""
        assert ru.priority_level == PriorityLevel.INFORMATIONAL
        assert ru.action == OptimizationAction.MAINTAIN
        assert ru.confidence_pct == 0.0
        assert ru.reason == ""
        assert ru.created_at > 0

    def test_report_defaults(self):
        r = AlertPriorityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.optimization_count == 0
        assert r.misalignment_rate_pct == 0.0
        assert r.by_priority == {}
        assert r.by_action == {}
        assert r.by_response == {}
        assert r.misaligned_alerts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_priority
# ---------------------------------------------------------------------------


class TestRecordPriority:
    def test_basic(self):
        eng = _engine()
        r = eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            suggested_priority=PriorityLevel.MEDIUM,
            action=OptimizationAction.DOWNGRADE,
            response_pattern=ResponsePattern.DELAYED,
            team="sre",
        )
        assert r.alert_type == "cpu-high"
        assert r.current_priority == PriorityLevel.HIGH
        assert r.suggested_priority == PriorityLevel.MEDIUM
        assert r.action == OptimizationAction.DOWNGRADE
        assert r.response_pattern == ResponsePattern.DELAYED
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_priority(alert_type=f"alert-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_priority
# ---------------------------------------------------------------------------


class TestGetPriority:
    def test_found(self):
        eng = _engine()
        r = eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.CRITICAL,
        )
        result = eng.get_priority(r.id)
        assert result is not None
        assert result.current_priority == PriorityLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_priority("nonexistent") is None


# ---------------------------------------------------------------------------
# list_priorities
# ---------------------------------------------------------------------------


class TestListPriorities:
    def test_list_all(self):
        eng = _engine()
        eng.record_priority(alert_type="alert-a")
        eng.record_priority(alert_type="alert-b")
        assert len(eng.list_priorities()) == 2

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_priority(
            alert_type="a",
            current_priority=PriorityLevel.HIGH,
        )
        eng.record_priority(
            alert_type="b",
            current_priority=PriorityLevel.LOW,
        )
        results = eng.list_priorities(priority=PriorityLevel.HIGH)
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_priority(
            alert_type="a",
            action=OptimizationAction.UPGRADE,
        )
        eng.record_priority(
            alert_type="b",
            action=OptimizationAction.DOWNGRADE,
        )
        results = eng.list_priorities(action=OptimizationAction.UPGRADE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_priority(alert_type="a", team="sre")
        eng.record_priority(alert_type="b", team="platform")
        results = eng.list_priorities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_priority(alert_type=f"alert-{i}")
        assert len(eng.list_priorities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            alert_pattern="cpu-*",
            priority_level=PriorityLevel.HIGH,
            action=OptimizationAction.UPGRADE,
            confidence_pct=85.0,
            reason="frequent escalation",
        )
        assert ru.alert_pattern == "cpu-*"
        assert ru.priority_level == PriorityLevel.HIGH
        assert ru.confidence_pct == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(alert_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_priority_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePriorityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_priority(
            alert_type="a",
            current_priority=PriorityLevel.HIGH,
            action=OptimizationAction.UPGRADE,
        )
        eng.record_priority(
            alert_type="b",
            current_priority=PriorityLevel.HIGH,
            action=OptimizationAction.DOWNGRADE,
        )
        result = eng.analyze_priority_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_priority_distribution() == {}


# ---------------------------------------------------------------------------
# identify_misaligned_priorities
# ---------------------------------------------------------------------------


class TestIdentifyMisalignedPriorities:
    def test_detects_misaligned(self):
        eng = _engine()
        eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            suggested_priority=PriorityLevel.LOW,
        )
        eng.record_priority(
            alert_type="disk-ok",
            current_priority=PriorityLevel.LOW,
            suggested_priority=PriorityLevel.LOW,
        )
        results = eng.identify_misaligned_priorities()
        assert len(results) == 1
        assert results[0]["alert_type"] == "cpu-high"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_misaligned_priorities() == []


# ---------------------------------------------------------------------------
# rank_by_misalignment
# ---------------------------------------------------------------------------


class TestRankByMisalignment:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            suggested_priority=PriorityLevel.LOW,
        )
        eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            suggested_priority=PriorityLevel.MEDIUM,
        )
        eng.record_priority(
            alert_type="disk-full",
            current_priority=PriorityLevel.CRITICAL,
            suggested_priority=PriorityLevel.HIGH,
        )
        results = eng.rank_by_misalignment()
        assert len(results) == 2
        assert results[0]["alert_type"] == "cpu-high"
        assert results[0]["misalignment_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_misalignment() == []


# ---------------------------------------------------------------------------
# detect_priority_trends
# ---------------------------------------------------------------------------


class TestDetectPriorityTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [50.0, 50.0, 50.0, 50.0]:
            eng.add_rule(
                alert_pattern="a",
                confidence_pct=pct,
            )
        result = eng.detect_priority_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for pct in [30.0, 30.0, 80.0, 80.0]:
            eng.add_rule(
                alert_pattern="a",
                confidence_pct=pct,
            )
        result = eng.detect_priority_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_priority_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            suggested_priority=PriorityLevel.LOW,
            action=OptimizationAction.DOWNGRADE,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, AlertPriorityReport)
        assert report.total_records == 1
        assert report.optimization_count == 1
        assert report.misalignment_rate_pct == 100.0
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
        eng.record_priority(alert_type="cpu-high")
        eng.add_rule(alert_pattern="cpu-*")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_priority(
            alert_type="cpu-high",
            current_priority=PriorityLevel.HIGH,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_alert_types"] == 1
        assert "high" in stats["priority_distribution"]
