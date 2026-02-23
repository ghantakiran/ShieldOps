"""Tests for the change risk scorer module.

Covers:
- RiskLevel enum values
- ChangeType enum values
- ChangeRecord model defaults and full creation
- RiskScore model defaults
- RiskFactor model defaults
- _CHANGE_TYPE_WEIGHTS and _ENVIRONMENT_WEIGHTS constants
- ChangeRiskScorer creation and defaults
- record_change() with all params, minimal, max limit
- score_change() type weight, environment weight, files, lines,
  rollback, historical failure rate, clamping, risk levels
- get_score() found and not found
- get_service_risk_history() found and empty
- list_changes() all, filter by service, filter by change_type
- get_high_risk_changes() threshold filtering
- mark_outcome() success, failure, not found
- get_stats() empty and populated
"""

from __future__ import annotations

import pytest

from shieldops.analytics.change_risk_scorer import (
    _CHANGE_TYPE_WEIGHTS,
    _ENVIRONMENT_WEIGHTS,
    ChangeRecord,
    ChangeRiskScorer,
    ChangeType,
    RiskFactor,
    RiskLevel,
    RiskScore,
)

# -- Helpers ----------------------------------------------------------


def _make_scorer(**kwargs) -> ChangeRiskScorer:
    """Return a fresh ChangeRiskScorer with optional overrides."""
    return ChangeRiskScorer(**kwargs)


def _record(
    scorer: ChangeRiskScorer,
    service: str = "api-gw",
    change_type: ChangeType = ChangeType.DEPLOYMENT,
    **kwargs,
) -> ChangeRecord:
    """Record a change and return the record."""
    return scorer.record_change(
        service=service,
        change_type=change_type,
        **kwargs,
    )


# -- Fixtures ---------------------------------------------------------


@pytest.fixture()
def scorer() -> ChangeRiskScorer:
    """Return a fresh ChangeRiskScorer."""
    return ChangeRiskScorer()


@pytest.fixture()
def populated_scorer() -> ChangeRiskScorer:
    """Scorer with several changes, some scored."""
    s = ChangeRiskScorer()
    r1 = s.record_change(
        service="api-gw",
        change_type=ChangeType.DEPLOYMENT,
        description="Deploy v2.1",
        author="alice",
        environment="production",
    )
    s.score_change(r1.id)

    r2 = s.record_change(
        service="api-gw",
        change_type=ChangeType.DATABASE_MIGRATION,
        environment="production",
        files_changed=60,
        lines_changed=800,
        rollback_available=False,
    )
    s.score_change(r2.id)

    r3 = s.record_change(
        service="web-app",
        change_type=ChangeType.FEATURE_FLAG,
        environment="staging",
    )
    s.score_change(r3.id)
    return s


# -- Enum Tests -------------------------------------------------------


class TestRiskLevelEnum:
    def test_low_value(self) -> None:
        assert RiskLevel.LOW == "low"

    def test_medium_value(self) -> None:
        assert RiskLevel.MEDIUM == "medium"

    def test_high_value(self) -> None:
        assert RiskLevel.HIGH == "high"

    def test_critical_value(self) -> None:
        assert RiskLevel.CRITICAL == "critical"

    def test_all_members(self) -> None:
        members = {m.value for m in RiskLevel}
        assert members == {"low", "medium", "high", "critical"}


class TestChangeTypeEnum:
    def test_deployment_value(self) -> None:
        assert ChangeType.DEPLOYMENT == "deployment"

    def test_config_change_value(self) -> None:
        assert ChangeType.CONFIG_CHANGE == "config_change"

    def test_infrastructure_value(self) -> None:
        assert ChangeType.INFRASTRUCTURE == "infrastructure"

    def test_database_migration_value(self) -> None:
        assert ChangeType.DATABASE_MIGRATION == "database_migration"

    def test_feature_flag_value(self) -> None:
        assert ChangeType.FEATURE_FLAG == "feature_flag"

    def test_all_members(self) -> None:
        members = {m.value for m in ChangeType}
        expected = {
            "deployment",
            "config_change",
            "infrastructure",
            "database_migration",
            "feature_flag",
        }
        assert members == expected


# -- Model Tests ------------------------------------------------------


class TestChangeRecordModel:
    def test_defaults(self) -> None:
        rec = ChangeRecord(
            service="api",
            change_type=ChangeType.DEPLOYMENT,
        )
        assert rec.service == "api"
        assert rec.change_type == ChangeType.DEPLOYMENT
        assert rec.description == ""
        assert rec.author == ""
        assert rec.environment == "production"
        assert rec.files_changed == 0
        assert rec.lines_changed == 0
        assert rec.rollback_available is True
        assert rec.metadata == {}
        assert rec.created_at > 0
        assert len(rec.id) == 12

    def test_unique_ids(self) -> None:
        r1 = ChangeRecord(service="a", change_type=ChangeType.DEPLOYMENT)
        r2 = ChangeRecord(service="b", change_type=ChangeType.DEPLOYMENT)
        assert r1.id != r2.id

    def test_full_creation(self) -> None:
        rec = ChangeRecord(
            service="db",
            change_type=ChangeType.DATABASE_MIGRATION,
            description="Add index",
            author="alice",
            environment="staging",
            files_changed=5,
            lines_changed=120,
            rollback_available=False,
            metadata={"ticket": "JIRA-123"},
        )
        assert rec.environment == "staging"
        assert rec.rollback_available is False
        assert rec.metadata == {"ticket": "JIRA-123"}


class TestRiskScoreModel:
    def test_defaults(self) -> None:
        rs = RiskScore(change_id="c1", service="api")
        assert rs.change_id == "c1"
        assert rs.service == "api"
        assert rs.score == 0.0
        assert rs.risk_level == RiskLevel.LOW
        assert rs.factors == []
        assert rs.recommendation == ""
        assert rs.scored_at > 0
        assert len(rs.id) == 12


class TestRiskFactorModel:
    def test_defaults(self) -> None:
        rf = RiskFactor(name="type")
        assert rf.name == "type"
        assert rf.weight == 1.0
        assert rf.description == ""


# -- Constants --------------------------------------------------------


class TestChangeTypeWeights:
    def test_database_migration_highest(self) -> None:
        assert _CHANGE_TYPE_WEIGHTS[ChangeType.DATABASE_MIGRATION] == 0.8

    def test_infrastructure(self) -> None:
        assert _CHANGE_TYPE_WEIGHTS[ChangeType.INFRASTRUCTURE] == 0.6

    def test_deployment(self) -> None:
        assert _CHANGE_TYPE_WEIGHTS[ChangeType.DEPLOYMENT] == 0.4

    def test_config_change(self) -> None:
        assert _CHANGE_TYPE_WEIGHTS[ChangeType.CONFIG_CHANGE] == 0.3

    def test_feature_flag_lowest(self) -> None:
        assert _CHANGE_TYPE_WEIGHTS[ChangeType.FEATURE_FLAG] == 0.2

    def test_all_types_present(self) -> None:
        for ct in ChangeType:
            assert ct in _CHANGE_TYPE_WEIGHTS


class TestEnvironmentWeights:
    def test_production(self) -> None:
        assert _ENVIRONMENT_WEIGHTS["production"] == 0.3

    def test_staging(self) -> None:
        assert _ENVIRONMENT_WEIGHTS["staging"] == 0.1


# -- Scorer Creation --------------------------------------------------


class TestScorerCreation:
    def test_default_params(self) -> None:
        s = ChangeRiskScorer()
        assert s._max_records == 10000
        assert s._high_risk_threshold == 0.7
        assert s._critical_risk_threshold == 0.9

    def test_custom_params(self) -> None:
        s = ChangeRiskScorer(
            max_records=50,
            high_risk_threshold=0.5,
            critical_risk_threshold=0.8,
        )
        assert s._max_records == 50
        assert s._high_risk_threshold == 0.5
        assert s._critical_risk_threshold == 0.8

    def test_starts_empty(self) -> None:
        s = ChangeRiskScorer()
        assert len(s._records) == 0
        assert len(s._scores) == 0
        assert len(s._history) == 0
        assert len(s._outcomes) == 0


# -- record_change ----------------------------------------------------


class TestRecordChange:
    def test_minimal(self, scorer: ChangeRiskScorer) -> None:
        rec = scorer.record_change(service="api", change_type=ChangeType.DEPLOYMENT)
        assert rec.service == "api"
        assert rec.change_type == ChangeType.DEPLOYMENT

    def test_all_params(self, scorer: ChangeRiskScorer) -> None:
        rec = scorer.record_change(
            service="db",
            change_type=ChangeType.DATABASE_MIGRATION,
            description="Add index",
            author="alice",
            environment="staging",
            files_changed=10,
            lines_changed=200,
            rollback_available=False,
            metadata={"ticket": "T-1"},
        )
        assert rec.author == "alice"
        assert rec.environment == "staging"
        assert rec.files_changed == 10
        assert rec.lines_changed == 200
        assert rec.rollback_available is False
        assert rec.metadata == {"ticket": "T-1"}

    def test_stored_in_scorer(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        assert rec.id in scorer._records
        assert rec in scorer._history

    def test_max_limit_raises(self) -> None:
        s = ChangeRiskScorer(max_records=2)
        _record(s, service="a")
        _record(s, service="b")
        with pytest.raises(ValueError, match="Maximum records limit reached"):
            _record(s, service="c")

    def test_none_metadata_becomes_empty_dict(self, scorer: ChangeRiskScorer) -> None:
        rec = scorer.record_change(
            service="api",
            change_type=ChangeType.DEPLOYMENT,
            metadata=None,
        )
        assert rec.metadata == {}

    def test_returns_change_record_instance(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        assert isinstance(rec, ChangeRecord)


# -- score_change -----------------------------------------------------


class TestScoreChange:
    def test_deployment_production_baseline(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer, environment="production")
        rs = scorer.score_change(rec.id)
        # type=0.4 + env=0.3 = 0.7
        assert rs.score == pytest.approx(0.7, abs=0.01)
        assert rs.risk_level == RiskLevel.HIGH

    def test_feature_flag_staging_low_risk(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.FEATURE_FLAG,
            environment="staging",
        )
        rs = scorer.score_change(rec.id)
        # type=0.2 + env=0.1 = 0.3
        assert rs.score == pytest.approx(0.3, abs=0.01)
        assert rs.risk_level == RiskLevel.LOW

    def test_db_migration_production_high(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.DATABASE_MIGRATION,
            environment="production",
        )
        rs = scorer.score_change(rec.id)
        # type=0.8 + env=0.3 = 1.1 -> clamped to 1.0
        assert rs.score == pytest.approx(1.0, abs=0.01)
        assert rs.risk_level == RiskLevel.CRITICAL

    def test_files_changed_factor(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer, files_changed=51, environment="staging")
        rs = scorer.score_change(rec.id)
        # type=0.4 + env=0.1 + files=0.2 = 0.7
        assert rs.score == pytest.approx(0.7, abs=0.01)

    def test_lines_changed_factor(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer, lines_changed=501, environment="staging")
        rs = scorer.score_change(rec.id)
        # type=0.4 + env=0.1 + lines=0.2 = 0.7
        assert rs.score == pytest.approx(0.7, abs=0.01)

    def test_no_rollback_factor(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            rollback_available=False,
            environment="staging",
        )
        rs = scorer.score_change(rec.id)
        # type=0.4 + env=0.1 + no_rollback=0.2 = 0.7
        assert rs.score == pytest.approx(0.7, abs=0.01)

    def test_historical_failure_rate_factor(self, scorer: ChangeRiskScorer) -> None:
        # Record a past change with failure outcome
        r1 = _record(scorer, service="api", environment="staging")
        scorer.mark_outcome(r1.id, success=False)
        # New change for same service
        r2 = _record(scorer, service="api", environment="staging")
        rs = scorer.score_change(r2.id)
        # type=0.4 + env=0.1 + failure_rate=1.0*0.3 = 0.8
        assert rs.score == pytest.approx(0.8, abs=0.01)

    def test_score_clamped_to_1(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.DATABASE_MIGRATION,
            environment="production",
            files_changed=100,
            lines_changed=1000,
            rollback_available=False,
        )
        rs = scorer.score_change(rec.id)
        assert rs.score <= 1.0

    def test_score_clamped_to_0(self, scorer: ChangeRiskScorer) -> None:
        # Minimum possible: feature_flag + unknown env
        rec = scorer.record_change(
            service="api",
            change_type=ChangeType.FEATURE_FLAG,
            environment="dev",
        )
        rs = scorer.score_change(rec.id)
        assert rs.score >= 0.0

    def test_not_found_raises(self, scorer: ChangeRiskScorer) -> None:
        with pytest.raises(ValueError, match="Change record not found"):
            scorer.score_change("nonexistent")

    def test_risk_level_medium(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.CONFIG_CHANGE,
            environment="production",
        )
        rs = scorer.score_change(rec.id)
        # type=0.3 + env=0.3 = 0.6
        assert rs.risk_level == RiskLevel.MEDIUM

    def test_low_risk_recommendation(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.FEATURE_FLAG,
            environment="staging",
        )
        rs = scorer.score_change(rec.id)
        assert "Low risk" in rs.recommendation

    def test_critical_recommendation(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(
            scorer,
            change_type=ChangeType.DATABASE_MIGRATION,
            environment="production",
        )
        rs = scorer.score_change(rec.id)
        assert "Block deployment" in rs.recommendation

    def test_factors_populated(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        rs = scorer.score_change(rec.id)
        assert len(rs.factors) >= 2
        assert any("change_type" in f for f in rs.factors)
        assert any("environment" in f for f in rs.factors)

    def test_score_stored(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        scorer.score_change(rec.id)
        assert scorer.get_score(rec.id) is not None

    def test_returns_risk_score_instance(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        rs = scorer.score_change(rec.id)
        assert isinstance(rs, RiskScore)

    def test_unknown_environment_gets_default_weight(self, scorer: ChangeRiskScorer) -> None:
        rec = scorer.record_change(
            service="api",
            change_type=ChangeType.FEATURE_FLAG,
            environment="dev",
        )
        rs = scorer.score_change(rec.id)
        # type=0.2 + env=0.05(default) = 0.25
        assert rs.score == pytest.approx(0.25, abs=0.01)


# -- get_score --------------------------------------------------------


class TestGetScore:
    def test_found(self, populated_scorer: ChangeRiskScorer) -> None:
        scores = list(populated_scorer._scores.values())
        result = populated_scorer.get_score(scores[0].change_id)
        assert result is not None

    def test_not_found(self, scorer: ChangeRiskScorer) -> None:
        assert scorer.get_score("nonexistent") is None


# -- get_service_risk_history -----------------------------------------


class TestGetServiceRiskHistory:
    def test_found(self, populated_scorer: ChangeRiskScorer) -> None:
        history = populated_scorer.get_service_risk_history("api-gw")
        assert len(history) == 2

    def test_empty(self, populated_scorer: ChangeRiskScorer) -> None:
        history = populated_scorer.get_service_risk_history("unknown")
        assert history == []

    def test_correct_service(self, populated_scorer: ChangeRiskScorer) -> None:
        history = populated_scorer.get_service_risk_history("web-app")
        assert len(history) == 1
        assert history[0].service == "web-app"


# -- list_changes -----------------------------------------------------


class TestListChanges:
    def test_all(self, populated_scorer: ChangeRiskScorer) -> None:
        changes = populated_scorer.list_changes()
        assert len(changes) == 3

    def test_filter_by_service(self, populated_scorer: ChangeRiskScorer) -> None:
        changes = populated_scorer.list_changes(service="api-gw")
        assert len(changes) == 2

    def test_filter_by_change_type(self, populated_scorer: ChangeRiskScorer) -> None:
        changes = populated_scorer.list_changes(change_type=ChangeType.FEATURE_FLAG)
        assert len(changes) == 1

    def test_no_match(self, populated_scorer: ChangeRiskScorer) -> None:
        changes = populated_scorer.list_changes(service="unknown")
        assert changes == []

    def test_empty_scorer(self, scorer: ChangeRiskScorer) -> None:
        assert scorer.list_changes() == []


# -- get_high_risk_changes --------------------------------------------


class TestGetHighRiskChanges:
    def test_returns_high_and_critical(self, populated_scorer: ChangeRiskScorer) -> None:
        high = populated_scorer.get_high_risk_changes()
        for s in high:
            assert s.score >= 0.7

    def test_excludes_low_risk(self, populated_scorer: ChangeRiskScorer) -> None:
        high = populated_scorer.get_high_risk_changes()
        ids = {s.change_id for s in high}
        # web-app feature_flag on staging = 0.3 -> not included
        web_scores = [s for s in populated_scorer._scores.values() if s.service == "web-app"]
        for ws in web_scores:
            assert ws.change_id not in ids

    def test_empty_scorer(self, scorer: ChangeRiskScorer) -> None:
        assert scorer.get_high_risk_changes() == []


# -- mark_outcome -----------------------------------------------------


class TestMarkOutcome:
    def test_success(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        scorer.mark_outcome(rec.id, success=True)
        assert scorer._outcomes[rec.id] is True

    def test_failure(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        scorer.mark_outcome(rec.id, success=False)
        assert scorer._outcomes[rec.id] is False

    def test_not_found_raises(self, scorer: ChangeRiskScorer) -> None:
        with pytest.raises(ValueError, match="Change record not found"):
            scorer.mark_outcome("nonexistent", success=True)

    def test_overwrite_outcome(self, scorer: ChangeRiskScorer) -> None:
        rec = _record(scorer)
        scorer.mark_outcome(rec.id, success=True)
        scorer.mark_outcome(rec.id, success=False)
        assert scorer._outcomes[rec.id] is False


# -- get_stats --------------------------------------------------------


class TestGetStats:
    def test_empty_scorer(self, scorer: ChangeRiskScorer) -> None:
        stats = scorer.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_scored"] == 0
        assert stats["high_risk_changes"] == 0
        assert stats["critical_risk_changes"] == 0
        assert stats["total_outcomes"] == 0
        assert stats["total_failures"] == 0
        assert stats["overall_failure_rate"] == pytest.approx(0.0)

    def test_populated(self, populated_scorer: ChangeRiskScorer) -> None:
        stats = populated_scorer.get_stats()
        assert stats["total_records"] == 3
        assert stats["total_scored"] == 3

    def test_failure_rate_calculation(self, scorer: ChangeRiskScorer) -> None:
        r1 = _record(scorer, service="a")
        r2 = _record(scorer, service="b")
        r3 = _record(scorer, service="c")
        scorer.mark_outcome(r1.id, success=True)
        scorer.mark_outcome(r2.id, success=False)
        scorer.mark_outcome(r3.id, success=False)
        stats = scorer.get_stats()
        assert stats["total_outcomes"] == 3
        assert stats["total_failures"] == 2
        expected_rate = 2 / 3
        assert stats["overall_failure_rate"] == pytest.approx(expected_rate, abs=0.001)

    def test_stats_keys(self, scorer: ChangeRiskScorer) -> None:
        stats = scorer.get_stats()
        expected_keys = {
            "total_records",
            "total_scored",
            "high_risk_changes",
            "critical_risk_changes",
            "total_outcomes",
            "total_failures",
            "overall_failure_rate",
        }
        assert set(stats.keys()) == expected_keys
