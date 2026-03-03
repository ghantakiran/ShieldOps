"""Tests for shieldops.observability.observability_as_code_validator

ObservabilityAsCodeValidator.
"""

from __future__ import annotations

from shieldops.observability.observability_as_code_validator import (
    ConfigType,
    ObservabilityAsCodeReport,
    ObservabilityAsCodeValidator,
    ValidationAnalysis,
    ValidationRecord,
    ValidationSource,
    ValidationStatus,
)


def _engine(**kw) -> ObservabilityAsCodeValidator:
    return ObservabilityAsCodeValidator(**kw)


class TestEnums:
    def test_config_type_dashboard(self):
        assert ConfigType.DASHBOARD == "dashboard"

    def test_config_type_alert_rule(self):
        assert ConfigType.ALERT_RULE == "alert_rule"

    def test_config_type_slo_definition(self):
        assert ConfigType.SLO_DEFINITION == "slo_definition"

    def test_config_type_recording_rule(self):
        assert ConfigType.RECORDING_RULE == "recording_rule"

    def test_config_type_pipeline(self):
        assert ConfigType.PIPELINE == "pipeline"

    def test_validation_source_git_repo(self):
        assert ValidationSource.GIT_REPO == "git_repo"

    def test_validation_source_terraform(self):
        assert ValidationSource.TERRAFORM == "terraform"

    def test_validation_source_helm(self):
        assert ValidationSource.HELM == "helm"

    def test_validation_source_jsonnet(self):
        assert ValidationSource.JSONNET == "jsonnet"

    def test_validation_source_custom(self):
        assert ValidationSource.CUSTOM == "custom"

    def test_validation_status_valid(self):
        assert ValidationStatus.VALID == "valid"

    def test_validation_status_warning(self):
        assert ValidationStatus.WARNING == "warning"

    def test_validation_status_error(self):
        assert ValidationStatus.ERROR == "error"

    def test_validation_status_deprecated(self):
        assert ValidationStatus.DEPRECATED == "deprecated"

    def test_validation_status_unknown(self):
        assert ValidationStatus.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.name == ""
        assert r.config_type == ConfigType.DASHBOARD
        assert r.validation_source == ValidationSource.GIT_REPO
        assert r.validation_status == ValidationStatus.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ValidationAnalysis()
        assert a.id
        assert a.name == ""
        assert a.config_type == ConfigType.DASHBOARD
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ObservabilityAsCodeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_config_type == {}
        assert r.by_validation_source == {}
        assert r.by_validation_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            config_type=ConfigType.DASHBOARD,
            validation_source=ValidationSource.TERRAFORM,
            validation_status=ValidationStatus.VALID,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.config_type == ConfigType.DASHBOARD
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_config_type(self):
        eng = _engine()
        eng.record_entry(name="a", config_type=ConfigType.DASHBOARD)
        eng.record_entry(name="b", config_type=ConfigType.ALERT_RULE)
        assert len(eng.list_records(config_type=ConfigType.DASHBOARD)) == 1

    def test_filter_by_validation_source(self):
        eng = _engine()
        eng.record_entry(name="a", validation_source=ValidationSource.GIT_REPO)
        eng.record_entry(name="b", validation_source=ValidationSource.TERRAFORM)
        assert len(eng.list_records(validation_source=ValidationSource.GIT_REPO)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", config_type=ConfigType.ALERT_RULE, score=90.0)
        eng.record_entry(name="b", config_type=ConfigType.ALERT_RULE, score=70.0)
        result = eng.analyze_distribution()
        assert "alert_rule" in result
        assert result["alert_rule"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
