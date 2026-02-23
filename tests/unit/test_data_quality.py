"""Tests for shieldops.compliance.data_quality — DataQualityMonitor.

Covers QualityDimension, QualityStatus enums, QualityRule / QualityCheckResult /
QualityAlert models, and all DataQualityMonitor operations including rule management,
check execution, alert generation, dataset health, and statistics.
"""

from __future__ import annotations

import pytest

from shieldops.compliance.data_quality import (
    DataQualityMonitor,
    QualityAlert,
    QualityCheckResult,
    QualityDimension,
    QualityRule,
    QualityStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _monitor(**kw) -> DataQualityMonitor:
    return DataQualityMonitor(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of QualityDimension and QualityStatus."""

    # -- QualityDimension (6 members) ----------------------------------------

    def test_dimension_completeness(self):
        assert QualityDimension.COMPLETENESS == "completeness"

    def test_dimension_accuracy(self):
        assert QualityDimension.ACCURACY == "accuracy"

    def test_dimension_consistency(self):
        assert QualityDimension.CONSISTENCY == "consistency"

    def test_dimension_timeliness(self):
        assert QualityDimension.TIMELINESS == "timeliness"

    def test_dimension_uniqueness(self):
        assert QualityDimension.UNIQUENESS == "uniqueness"

    def test_dimension_validity(self):
        assert QualityDimension.VALIDITY == "validity"

    # -- QualityStatus (4 members) -------------------------------------------

    def test_status_healthy(self):
        assert QualityStatus.HEALTHY == "healthy"

    def test_status_warning(self):
        assert QualityStatus.WARNING == "warning"

    def test_status_critical(self):
        assert QualityStatus.CRITICAL == "critical"

    def test_status_unknown(self):
        assert QualityStatus.UNKNOWN == "unknown"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_quality_rule_defaults(self):
        rule = QualityRule(
            name="r1",
            dataset="ds1",
            dimension=QualityDimension.ACCURACY,
        )
        assert rule.id  # auto-generated UUID
        assert rule.expression == ""
        assert rule.threshold == 0.95
        assert rule.enabled is True
        assert rule.owner == ""
        assert rule.created_at > 0

    def test_quality_check_result_defaults(self):
        result = QualityCheckResult(
            rule_id="r1",
            dataset="ds1",
            dimension=QualityDimension.ACCURACY,
        )
        assert result.id
        assert result.score == 1.0
        assert result.records_checked == 0
        assert result.records_failed == 0
        assert result.status == QualityStatus.HEALTHY
        assert result.details == ""
        assert result.checked_at > 0

    def test_quality_alert_defaults(self):
        alert = QualityAlert(
            rule_id="r1",
            dataset="ds1",
            dimension=QualityDimension.COMPLETENESS,
            previous_score=1.0,
            current_score=0.5,
            threshold=0.95,
        )
        assert alert.id
        assert alert.message == ""
        assert alert.triggered_at > 0


# ===========================================================================
# create_rule
# ===========================================================================


class TestCreateRule:
    """Tests for DataQualityMonitor.create_rule."""

    def test_basic_create(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        assert rule.name == "r1"
        assert rule.dataset == "ds1"
        assert rule.dimension == QualityDimension.ACCURACY
        assert mon.get_rule(rule.id) is rule

    def test_create_with_all_fields(self):
        mon = _monitor()
        rule = mon.create_rule(
            "r2",
            "ds2",
            QualityDimension.TIMELINESS,
            expression="col IS NOT NULL",
            threshold=0.99,
            enabled=False,
            owner="team-a",
        )
        assert rule.expression == "col IS NOT NULL"
        assert rule.threshold == 0.99
        assert rule.enabled is False
        assert rule.owner == "team-a"

    def test_create_rule_max_limit(self):
        mon = _monitor(max_rules=2)
        mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        with pytest.raises(ValueError, match="Maximum rules limit reached"):
            mon.create_rule("r3", "ds3", QualityDimension.COMPLETENESS)

    def test_unique_ids(self):
        mon = _monitor()
        r1 = mon.create_rule("a", "ds1", QualityDimension.ACCURACY)
        r2 = mon.create_rule("b", "ds1", QualityDimension.ACCURACY)
        assert r1.id != r2.id


# ===========================================================================
# run_check
# ===========================================================================


class TestRunCheck:
    """Tests for DataQualityMonitor.run_check."""

    def test_healthy_score(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=0.95)
        result = mon.run_check(rule.id, score=0.98)
        assert result.status == QualityStatus.HEALTHY
        assert result.score == 0.98
        assert result.dataset == "ds1"

    def test_warning_score(self):
        """Score between threshold*0.8 and threshold => WARNING."""
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        # threshold*0.8 = 0.8; score 0.85 is >= 0.8 but < 1.0
        result = mon.run_check(rule.id, score=0.85)
        assert result.status == QualityStatus.WARNING

    def test_critical_score(self):
        """Score below threshold*0.8 => CRITICAL."""
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        # threshold*0.8 = 0.8; score 0.5 < 0.8
        result = mon.run_check(rule.id, score=0.5)
        assert result.status == QualityStatus.CRITICAL

    def test_run_check_not_found(self):
        mon = _monitor()
        with pytest.raises(ValueError, match="Rule not found"):
            mon.run_check("nonexistent", score=0.9)

    def test_generates_alert_on_critical(self):
        mon = _monitor(alert_cooldown_seconds=0)
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        mon.run_check(rule.id, score=0.5)
        alerts = mon.list_alerts()
        assert len(alerts) == 1
        assert alerts[0].rule_id == rule.id
        assert alerts[0].current_score == 0.5

    def test_respects_cooldown(self):
        """Within cooldown period, no second alert should be generated."""
        mon = _monitor(alert_cooldown_seconds=9999)
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        mon.run_check(rule.id, score=0.5)  # triggers alert
        mon.run_check(rule.id, score=0.5)  # within cooldown — no new alert
        alerts = mon.list_alerts()
        assert len(alerts) == 1

    def test_trims_results(self):
        mon = _monitor(max_results=3)
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=0.95)
        for _ in range(5):
            mon.run_check(rule.id, score=0.99)
        history = mon.get_check_history()
        assert len(history) == 3


# ===========================================================================
# get_rule
# ===========================================================================


class TestGetRule:
    """Tests for DataQualityMonitor.get_rule."""

    def test_found(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        assert mon.get_rule(rule.id) is rule

    def test_not_found(self):
        mon = _monitor()
        assert mon.get_rule("nonexistent") is None


# ===========================================================================
# list_rules
# ===========================================================================


class TestListRules:
    """Tests for DataQualityMonitor.list_rules."""

    def test_list_all(self):
        mon = _monitor()
        mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        assert len(mon.list_rules()) == 2

    def test_list_by_dataset(self):
        mon = _monitor()
        mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        result = mon.list_rules(dataset="ds1")
        assert len(result) == 1
        assert result[0].dataset == "ds1"

    def test_list_by_dimension(self):
        mon = _monitor()
        mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        result = mon.list_rules(dimension=QualityDimension.ACCURACY)
        assert len(result) == 1
        assert result[0].dimension == QualityDimension.ACCURACY

    def test_list_empty(self):
        mon = _monitor()
        assert mon.list_rules() == []


# ===========================================================================
# delete_rule
# ===========================================================================


class TestDeleteRule:
    """Tests for DataQualityMonitor.delete_rule."""

    def test_delete_existing(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        assert mon.delete_rule(rule.id) is True
        assert mon.get_rule(rule.id) is None

    def test_delete_nonexistent(self):
        mon = _monitor()
        assert mon.delete_rule("nonexistent") is False


# ===========================================================================
# get_check_history
# ===========================================================================


class TestCheckHistory:
    """Tests for DataQualityMonitor.get_check_history."""

    def test_all_history(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        mon.run_check(rule.id, score=0.99)
        mon.run_check(rule.id, score=0.97)
        assert len(mon.get_check_history()) == 2

    def test_by_rule_id(self):
        mon = _monitor()
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        mon.run_check(r1.id, score=0.99)
        mon.run_check(r2.id, score=0.88)
        results = mon.get_check_history(rule_id=r1.id)
        assert len(results) == 1
        assert results[0].rule_id == r1.id

    def test_by_dataset(self):
        mon = _monitor()
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY)
        mon.run_check(r1.id, score=0.99)
        mon.run_check(r2.id, score=0.88)
        results = mon.get_check_history(dataset="ds2")
        assert len(results) == 1
        assert results[0].dataset == "ds2"

    def test_limit(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY)
        for i in range(10):
            mon.run_check(rule.id, score=0.99 - i * 0.01)
        results = mon.get_check_history(limit=3)
        assert len(results) == 3


# ===========================================================================
# list_alerts
# ===========================================================================


class TestAlerts:
    """Tests for DataQualityMonitor.list_alerts."""

    def test_all_alerts(self):
        mon = _monitor(alert_cooldown_seconds=0)
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY, threshold=1.0)
        mon.run_check(r1.id, score=0.5)
        mon.run_check(r2.id, score=0.5)
        assert len(mon.list_alerts()) == 2

    def test_alerts_by_dataset(self):
        mon = _monitor(alert_cooldown_seconds=0)
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY, threshold=1.0)
        mon.run_check(r1.id, score=0.5)
        mon.run_check(r2.id, score=0.5)
        alerts = mon.list_alerts(dataset="ds1")
        assert len(alerts) == 1
        assert alerts[0].dataset == "ds1"

    def test_alerts_limit(self):
        mon = _monitor(alert_cooldown_seconds=0)
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY, threshold=1.0)
        r3 = mon.create_rule("r3", "ds3", QualityDimension.COMPLETENESS, threshold=1.0)
        mon.run_check(r1.id, score=0.5)
        mon.run_check(r2.id, score=0.5)
        mon.run_check(r3.id, score=0.5)
        alerts = mon.list_alerts(limit=2)
        assert len(alerts) == 2


# ===========================================================================
# get_dataset_health
# ===========================================================================


class TestDatasetHealth:
    """Tests for DataQualityMonitor.get_dataset_health."""

    def test_basic_health(self):
        mon = _monitor()
        rule = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=0.95)
        mon.run_check(rule.id, score=0.99)
        health = mon.get_dataset_health("ds1")
        assert health["overall_status"] == QualityStatus.HEALTHY
        assert QualityDimension.ACCURACY in health["dimensions"]
        assert health["total_checks"] == 1
        assert health["last_check_at"] is not None

    def test_multiple_dimensions(self):
        mon = _monitor()
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        r2 = mon.create_rule("r2", "ds1", QualityDimension.VALIDITY, threshold=1.0)
        mon.run_check(r1.id, score=0.99)  # WARNING
        mon.run_check(r2.id, score=0.5)  # CRITICAL
        health = mon.get_dataset_health("ds1")
        assert health["overall_status"] == QualityStatus.CRITICAL
        assert health["total_checks"] == 2
        assert len(health["dimensions"]) == 2

    def test_unknown_dataset(self):
        mon = _monitor()
        health = mon.get_dataset_health("nonexistent")
        assert health["overall_status"] == QualityStatus.HEALTHY
        assert health["total_checks"] == 0
        assert health["last_check_at"] is None


# ===========================================================================
# get_stats
# ===========================================================================


class TestGetStats:
    """Tests for DataQualityMonitor.get_stats."""

    def test_empty_stats(self):
        mon = _monitor()
        stats = mon.get_stats()
        assert stats["total_rules"] == 0
        assert stats["total_checks"] == 0
        assert stats["total_alerts"] == 0
        assert stats["datasets_monitored"] == 0
        assert stats["dimension_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated_stats(self):
        mon = _monitor(alert_cooldown_seconds=0)
        r1 = mon.create_rule("r1", "ds1", QualityDimension.ACCURACY, threshold=1.0)
        r2 = mon.create_rule("r2", "ds2", QualityDimension.VALIDITY, threshold=1.0)
        mon.run_check(r1.id, score=0.99)
        mon.run_check(r2.id, score=0.5)
        stats = mon.get_stats()
        assert stats["total_rules"] == 2
        assert stats["total_checks"] == 2
        assert stats["total_alerts"] == 2
        assert stats["datasets_monitored"] == 2
        assert "accuracy" in stats["dimension_distribution"]
        assert "validity" in stats["dimension_distribution"]
        assert "critical" in stats["status_distribution"]
