"""Tests for shieldops.observability.suppression_manager — AlertSuppressionManager."""

from __future__ import annotations

from shieldops.observability.suppression_manager import (
    AlertSuppressionManager,
    AlertSuppressionReport,
    SuppressionRecord,
    SuppressionRule,
    SuppressionScope,
    SuppressionStatus,
    SuppressionType,
)


def _engine(**kw) -> AlertSuppressionManager:
    return AlertSuppressionManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_maintenance(self):
        assert SuppressionType.MAINTENANCE == "maintenance"

    def test_type_known_issue(self):
        assert SuppressionType.KNOWN_ISSUE == "known_issue"

    def test_type_false_positive(self):
        assert SuppressionType.FALSE_POSITIVE == "false_positive"

    def test_type_transient(self):
        assert SuppressionType.TRANSIENT == "transient"

    def test_type_planned_change(self):
        assert SuppressionType.PLANNED_CHANGE == "planned_change"

    def test_scope_service(self):
        assert SuppressionScope.SERVICE == "service"

    def test_scope_team(self):
        assert SuppressionScope.TEAM == "team"

    def test_scope_alert_type(self):
        assert SuppressionScope.ALERT_TYPE == "alert_type"

    def test_scope_environment(self):
        assert SuppressionScope.ENVIRONMENT == "environment"

    def test_scope_global(self):
        assert SuppressionScope.GLOBAL == "global"

    def test_status_active(self):
        assert SuppressionStatus.ACTIVE == "active"

    def test_status_expired(self):
        assert SuppressionStatus.EXPIRED == "expired"

    def test_status_cancelled(self):
        assert SuppressionStatus.CANCELLED == "cancelled"

    def test_status_extended(self):
        assert SuppressionStatus.EXTENDED == "extended"

    def test_status_pending(self):
        assert SuppressionStatus.PENDING == "pending"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_suppression_record_defaults(self):
        r = SuppressionRecord()
        assert r.id
        assert r.alert_type == ""
        assert r.suppression_type == SuppressionType.MAINTENANCE
        assert r.scope == SuppressionScope.SERVICE
        assert r.status == SuppressionStatus.PENDING
        assert r.suppressed_count == 0
        assert r.team == ""
        assert r.created_at > 0

    def test_suppression_rule_defaults(self):
        r = SuppressionRule()
        assert r.id
        assert r.alert_pattern == ""
        assert r.suppression_type == SuppressionType.MAINTENANCE
        assert r.scope == SuppressionScope.SERVICE
        assert r.duration_minutes == 0.0
        assert r.reason == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = AlertSuppressionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.active_suppressions == 0
        assert r.suppression_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_scope == {}
        assert r.by_status == {}
        assert r.over_suppressed == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_suppression
# ---------------------------------------------------------------------------


class TestRecordSuppression:
    def test_basic(self):
        eng = _engine()
        r = eng.record_suppression(
            alert_type="HighCPU",
            suppression_type=SuppressionType.MAINTENANCE,
            scope=SuppressionScope.SERVICE,
            suppressed_count=42,
            team="sre",
        )
        assert r.alert_type == "HighCPU"
        assert r.suppression_type == SuppressionType.MAINTENANCE
        assert r.suppressed_count == 42
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_suppression(alert_type=f"Alert-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_suppression
# ---------------------------------------------------------------------------


class TestGetSuppression:
    def test_found(self):
        eng = _engine()
        r = eng.record_suppression(alert_type="DiskFull", suppressed_count=10)
        result = eng.get_suppression(r.id)
        assert result is not None
        assert result.alert_type == "DiskFull"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_suppression("nonexistent") is None


# ---------------------------------------------------------------------------
# list_suppressions
# ---------------------------------------------------------------------------


class TestListSuppressions:
    def test_list_all(self):
        eng = _engine()
        eng.record_suppression(alert_type="A1")
        eng.record_suppression(alert_type="A2")
        assert len(eng.list_suppressions()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_suppression(alert_type="A1", suppression_type=SuppressionType.MAINTENANCE)
        eng.record_suppression(alert_type="A2", suppression_type=SuppressionType.FALSE_POSITIVE)
        results = eng.list_suppressions(suppression_type=SuppressionType.MAINTENANCE)
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_suppression(alert_type="A1", scope=SuppressionScope.GLOBAL)
        eng.record_suppression(alert_type="A2", scope=SuppressionScope.TEAM)
        results = eng.list_suppressions(scope=SuppressionScope.GLOBAL)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_suppression(alert_type="A1", status=SuppressionStatus.ACTIVE)
        eng.record_suppression(alert_type="A2", status=SuppressionStatus.EXPIRED)
        results = eng.list_suppressions(status=SuppressionStatus.ACTIVE)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_suppression(alert_type=f"Alert-{i}")
        assert len(eng.list_suppressions(limit=4)) == 4


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rule = eng.add_rule(
            alert_pattern="^HighCPU.*",
            suppression_type=SuppressionType.MAINTENANCE,
            duration_minutes=60.0,
            reason="Planned maintenance",
        )
        assert rule.alert_pattern == "^HighCPU.*"
        assert rule.duration_minutes == 60.0
        assert rule.reason == "Planned maintenance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(alert_pattern=f"pattern-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_suppression_effectiveness
# ---------------------------------------------------------------------------


class TestAnalyzeSuppressionEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_suppression(
            alert_type="A1",
            suppression_type=SuppressionType.MAINTENANCE,
            suppressed_count=20,
        )
        eng.record_suppression(
            alert_type="A2",
            suppression_type=SuppressionType.MAINTENANCE,
            suppressed_count=40,
        )
        result = eng.analyze_suppression_effectiveness()
        assert "maintenance" in result
        assert result["maintenance"]["count"] == 2
        assert result["maintenance"]["avg_suppressed_count"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_suppression_effectiveness() == {}


# ---------------------------------------------------------------------------
# identify_over_suppressed
# ---------------------------------------------------------------------------


class TestIdentifyOverSuppressed:
    def test_detects_over_suppressed(self):
        eng = _engine(max_suppression_rate_pct=30.0)
        eng.record_suppression(alert_type="A1", team="sre", suppressed_count=1000)
        results = eng.identify_over_suppressed()
        assert len(results) == 1
        assert results[0]["team"] == "sre"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_suppressed() == []


# ---------------------------------------------------------------------------
# rank_by_suppressed_count
# ---------------------------------------------------------------------------


class TestRankBySuppressedCount:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_suppression(alert_type="A1", team="sre", suppressed_count=100)
        eng.record_suppression(alert_type="A2", team="platform", suppressed_count=50)
        results = eng.rank_by_suppressed_count()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_suppressed"] == 100

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_suppressed_count() == []


# ---------------------------------------------------------------------------
# detect_suppression_trends
# ---------------------------------------------------------------------------


class TestDetectSuppressionTrends:
    def test_stable(self):
        eng = _engine()
        for count in [10, 10, 10, 10]:
            eng.record_suppression(alert_type="A", suppressed_count=count)
        result = eng.detect_suppression_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for count in [2, 2, 50, 50]:
            eng.record_suppression(alert_type="A", suppressed_count=count)
        result = eng.detect_suppression_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_suppression_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_suppression(
            alert_type="A1",
            suppression_type=SuppressionType.FALSE_POSITIVE,
            status=SuppressionStatus.ACTIVE,
            suppressed_count=5,
        )
        report = eng.generate_report()
        assert isinstance(report, AlertSuppressionReport)
        assert report.total_records == 1
        assert report.active_suppressions == 1
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
        eng.record_suppression(alert_type="A1")
        eng.add_rule(alert_pattern="pattern")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_suppression(
            alert_type="HighCPU",
            suppression_type=SuppressionType.MAINTENANCE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_alert_types"] == 1
        assert "maintenance" in stats["type_distribution"]
