"""Tests for shieldops.topology.dep_change_tracker — DependencyChangeTracker."""

from __future__ import annotations

from shieldops.topology.dep_change_tracker import (
    ChangeImpact,
    ChangeStatus,
    ChangeType,
    DepChangeRecord,
    DepChangeReport,
    DepChangeRule,
    DependencyChangeTracker,
)


def _engine(**kw) -> DependencyChangeTracker:
    return DependencyChangeTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_added(self):
        assert ChangeType.ADDED == "added"

    def test_type_removed(self):
        assert ChangeType.REMOVED == "removed"

    def test_type_version_bump(self):
        assert ChangeType.VERSION_BUMP == "version_bump"

    def test_type_config_change(self):
        assert ChangeType.CONFIG_CHANGE == "config_change"

    def test_type_deprecated(self):
        assert ChangeType.DEPRECATED == "deprecated"

    def test_impact_none(self):
        assert ChangeImpact.NONE == "none"

    def test_impact_low(self):
        assert ChangeImpact.LOW == "low"

    def test_impact_medium(self):
        assert ChangeImpact.MEDIUM == "medium"

    def test_impact_high(self):
        assert ChangeImpact.HIGH == "high"

    def test_impact_breaking(self):
        assert ChangeImpact.BREAKING == "breaking"

    def test_status_pending(self):
        assert ChangeStatus.PENDING == "pending"

    def test_status_approved(self):
        assert ChangeStatus.APPROVED == "approved"

    def test_status_applied(self):
        assert ChangeStatus.APPLIED == "applied"

    def test_status_rolled_back(self):
        assert ChangeStatus.ROLLED_BACK == "rolled_back"

    def test_status_failed(self):
        assert ChangeStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dep_change_record_defaults(self):
        r = DepChangeRecord()
        assert r.id
        assert r.dependency_name == ""
        assert r.change_type == ChangeType.ADDED
        assert r.change_impact == ChangeImpact.NONE
        assert r.change_status == ChangeStatus.PENDING
        assert r.risk_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_dep_change_rule_defaults(self):
        ru = DepChangeRule()
        assert ru.id
        assert ru.dependency_pattern == ""
        assert ru.change_type == ChangeType.ADDED
        assert ru.max_risk_score == 0.0
        assert ru.auto_approve is False
        assert ru.description == ""
        assert ru.created_at > 0

    def test_dep_change_report_defaults(self):
        r = DepChangeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.breaking_changes == 0
        assert r.avg_risk_score == 0.0
        assert r.by_type == {}
        assert r.by_impact == {}
        assert r.by_status == {}
        assert r.high_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic(self):
        eng = _engine()
        r = eng.record_change(
            dependency_name="requests",
            change_type=ChangeType.VERSION_BUMP,
            change_impact=ChangeImpact.LOW,
            change_status=ChangeStatus.APPROVED,
            risk_score=2.5,
            team="backend",
        )
        assert r.dependency_name == "requests"
        assert r.change_type == ChangeType.VERSION_BUMP
        assert r.change_impact == ChangeImpact.LOW
        assert r.change_status == ChangeStatus.APPROVED
        assert r.risk_score == 2.5
        assert r.team == "backend"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_change(dependency_name=f"dep-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        r = eng.record_change(
            dependency_name="flask",
            change_impact=ChangeImpact.HIGH,
        )
        result = eng.get_change(r.id)
        assert result is not None
        assert result.change_impact == ChangeImpact.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(dependency_name="dep-a")
        eng.record_change(dependency_name="dep-b")
        assert len(eng.list_changes()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_change(
            dependency_name="dep-a",
            change_type=ChangeType.REMOVED,
        )
        eng.record_change(
            dependency_name="dep-b",
            change_type=ChangeType.ADDED,
        )
        results = eng.list_changes(change_type=ChangeType.REMOVED)
        assert len(results) == 1

    def test_filter_by_impact(self):
        eng = _engine()
        eng.record_change(
            dependency_name="dep-a",
            change_impact=ChangeImpact.BREAKING,
        )
        eng.record_change(
            dependency_name="dep-b",
            change_impact=ChangeImpact.LOW,
        )
        results = eng.list_changes(impact=ChangeImpact.BREAKING)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_change(dependency_name="dep-a", team="backend")
        eng.record_change(dependency_name="dep-b", team="frontend")
        results = eng.list_changes(team="backend")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(dependency_name=f"dep-{i}")
        assert len(eng.list_changes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            dependency_pattern="requests*",
            change_type=ChangeType.VERSION_BUMP,
            max_risk_score=3.0,
            auto_approve=True,
            description="Auto-approve minor bumps",
        )
        assert ru.dependency_pattern == "requests*"
        assert ru.change_type == ChangeType.VERSION_BUMP
        assert ru.max_risk_score == 3.0
        assert ru.auto_approve is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(dependency_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_change_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeChangePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_change(
            dependency_name="dep-a",
            change_type=ChangeType.VERSION_BUMP,
            risk_score=3.0,
        )
        eng.record_change(
            dependency_name="dep-b",
            change_type=ChangeType.VERSION_BUMP,
            risk_score=5.0,
        )
        result = eng.analyze_change_patterns()
        assert "version_bump" in result
        assert result["version_bump"]["count"] == 2
        assert result["version_bump"]["avg_risk_score"] == 4.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_change_patterns() == {}


# ---------------------------------------------------------------------------
# identify_breaking_changes
# ---------------------------------------------------------------------------


class TestIdentifyBreakingChanges:
    def test_detects_breaking(self):
        eng = _engine()
        eng.record_change(
            dependency_name="dep-a",
            change_impact=ChangeImpact.BREAKING,
        )
        eng.record_change(
            dependency_name="dep-b",
            change_impact=ChangeImpact.LOW,
        )
        results = eng.identify_breaking_changes()
        assert len(results) == 1
        assert results[0]["dependency_name"] == "dep-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_breaking_changes() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_change(dependency_name="dep-a", team="backend", risk_score=8.0)
        eng.record_change(dependency_name="dep-b", team="backend", risk_score=6.0)
        eng.record_change(dependency_name="dep-c", team="frontend", risk_score=2.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["team"] == "backend"
        assert results[0]["avg_risk_score"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_change_trends
# ---------------------------------------------------------------------------


class TestDetectChangeTrends:
    def test_stable(self):
        eng = _engine()
        for s in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(dependency_pattern="p", max_risk_score=s)
        result = eng.detect_change_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(dependency_pattern="p", max_risk_score=s)
        result = eng.detect_change_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_change_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_change(
            dependency_name="dep-a",
            change_type=ChangeType.REMOVED,
            change_impact=ChangeImpact.BREAKING,
            risk_score=9.0,
            team="backend",
        )
        report = eng.generate_report()
        assert isinstance(report, DepChangeReport)
        assert report.total_records == 1
        assert report.breaking_changes == 1
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
        eng.record_change(dependency_name="dep-a")
        eng.add_rule(dependency_pattern="p1")
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
        eng.record_change(
            dependency_name="requests",
            change_type=ChangeType.VERSION_BUMP,
            team="backend",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_dependencies"] == 1
        assert "version_bump" in stats["type_distribution"]
