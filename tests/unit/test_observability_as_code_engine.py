"""Tests for shieldops.observability.observability_as_code_engine — ObservabilityAsCodeEngine."""

from __future__ import annotations

from shieldops.observability.observability_as_code_engine import (
    ConfigDiff,
    ConfigStatus,
    ConfigType,
    DiffAction,
    OaCConfig,
    OaCReport,
    ObservabilityAsCodeEngine,
)


def _engine(**kw) -> ObservabilityAsCodeEngine:
    return ObservabilityAsCodeEngine(**kw)


class TestEnums:
    def test_config_type_dashboard(self):
        assert ConfigType.DASHBOARD == "dashboard"

    def test_config_type_alert_rule(self):
        assert ConfigType.ALERT_RULE == "alert_rule"

    def test_config_type_slo(self):
        assert ConfigType.SLO == "slo"

    def test_config_type_recording_rule(self):
        assert ConfigType.RECORDING_RULE == "recording_rule"

    def test_config_type_notification(self):
        assert ConfigType.NOTIFICATION == "notification"

    def test_config_status_applied(self):
        assert ConfigStatus.APPLIED == "applied"

    def test_config_status_pending(self):
        assert ConfigStatus.PENDING == "pending"

    def test_config_status_failed(self):
        assert ConfigStatus.FAILED == "failed"

    def test_diff_action_create(self):
        assert DiffAction.CREATE == "create"

    def test_diff_action_update(self):
        assert DiffAction.UPDATE == "update"

    def test_diff_action_delete(self):
        assert DiffAction.DELETE == "delete"

    def test_diff_action_no_change(self):
        assert DiffAction.NO_CHANGE == "no_change"


class TestModels:
    def test_config_defaults(self):
        c = OaCConfig()
        assert c.id
        assert c.name == ""
        assert c.config_type == ConfigType.DASHBOARD
        assert c.status == ConfigStatus.DRAFT
        assert c.version == 1
        assert c.content == {}

    def test_diff_defaults(self):
        d = ConfigDiff()
        assert d.id
        assert d.action == DiffAction.NO_CHANGE

    def test_report_defaults(self):
        r = OaCReport()
        assert r.total_configs == 0
        assert r.recommendations == []


class TestAddConfig:
    def test_basic(self):
        eng = _engine()
        c = eng.add_config("dash-1", config_type=ConfigType.DASHBOARD, owner="team-a")
        assert c.name == "dash-1"
        assert c.owner == "team-a"

    def test_with_content(self):
        eng = _engine()
        c = eng.add_config("alert-1", content={"threshold": 90})
        assert c.content == {"threshold": 90}

    def test_eviction(self):
        eng = _engine(max_configs=3)
        for i in range(5):
            eng.add_config(f"c-{i}")
        assert len(eng._configs) == 3


class TestValidateConfig:
    def test_not_found(self):
        eng = _engine()
        result = eng.validate_config("nonexistent")
        assert result["valid"] is False

    def test_valid(self):
        eng = _engine()
        eng.add_config("dash", content={"panels": []}, owner="team-a")
        result = eng.validate_config("dash")
        assert result["valid"] is True

    def test_empty_content(self):
        eng = _engine()
        eng.add_config("dash", owner="team-a")
        result = eng.validate_config("dash")
        assert result["valid"] is False
        assert "empty content" in result["errors"]

    def test_no_owner(self):
        eng = _engine()
        eng.add_config("dash", content={"x": 1})
        result = eng.validate_config("dash")
        assert "no owner specified" in result["errors"]


class TestApplyConfig:
    def test_not_found(self):
        eng = _engine()
        result = eng.apply_config("nonexistent")
        assert result["status"] == "not_found"

    def test_success(self):
        eng = _engine()
        eng.add_config("dash", content={"x": 1}, owner="t")
        result = eng.apply_config("dash")
        assert result["status"] == "applied"

    def test_failed_validation(self):
        eng = _engine()
        eng.add_config("dash")
        result = eng.apply_config("dash")
        assert result["status"] == "failed"


class TestDiffConfig:
    def test_new_config(self):
        eng = _engine()
        diff = eng.diff_config("new", {"x": 1})
        assert diff.action == DiffAction.CREATE

    def test_no_change(self):
        eng = _engine()
        eng.add_config("dash", content={"x": 1})
        diff = eng.diff_config("dash", {"x": 1})
        assert diff.action == DiffAction.NO_CHANGE

    def test_update(self):
        eng = _engine()
        eng.add_config("dash", content={"x": 1})
        diff = eng.diff_config("dash", {"x": 2})
        assert diff.action == DiffAction.UPDATE
        assert len(diff.changes) > 0


class TestRollbackConfig:
    def test_no_history(self):
        eng = _engine()
        result = eng.rollback_config("nonexistent")
        assert result["status"] == "no_history"

    def test_successful_rollback(self):
        eng = _engine()
        eng.add_config("dash", content={"x": 1}, owner="t")
        eng.apply_config("dash")
        result = eng.rollback_config("dash")
        assert result["status"] == "rolled_back"


class TestExportConfig:
    def test_empty(self):
        eng = _engine()
        assert eng.export_config() == []

    def test_all(self):
        eng = _engine()
        eng.add_config("a")
        eng.add_config("b")
        assert len(eng.export_config()) == 2

    def test_by_name(self):
        eng = _engine()
        eng.add_config("a")
        eng.add_config("b")
        assert len(eng.export_config(name="a")) == 1


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_configs == 0

    def test_with_drafts(self):
        eng = _engine()
        eng.add_config("a")
        report = eng.generate_report()
        assert any("draft" in r.lower() for r in report.recommendations)


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_config("a")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._configs) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_configs"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_config("a", owner="team-x")
        stats = eng.get_stats()
        assert stats["unique_owners"] == 1
