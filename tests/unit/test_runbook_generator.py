"""Tests for shieldops.operations.runbook_generator — OperationalRunbookGenerator."""

from __future__ import annotations

from shieldops.operations.runbook_generator import (
    GeneratedRunbook,
    GenerationRule,
    OperationalRunbookGenerator,
    RunbookGeneratorReport,
    RunbookQuality,
    RunbookScope,
    RunbookSource,
)


def _engine(**kw) -> OperationalRunbookGenerator:
    return OperationalRunbookGenerator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RunbookSource (5)
    def test_source_incident_pattern(self):
        assert RunbookSource.INCIDENT_PATTERN == "incident_pattern"

    def test_source_historical_resolution(self):
        assert RunbookSource.HISTORICAL_RESOLUTION == "historical_resolution"

    def test_source_best_practice(self):
        assert RunbookSource.BEST_PRACTICE == "best_practice"

    def test_source_template(self):
        assert RunbookSource.TEMPLATE == "template"

    def test_source_manual_input(self):
        assert RunbookSource.MANUAL_INPUT == "manual_input"

    # RunbookQuality (5)
    def test_quality_production_ready(self):
        assert RunbookQuality.PRODUCTION_READY == "production_ready"

    def test_quality_reviewed(self):
        assert RunbookQuality.REVIEWED == "reviewed"

    def test_quality_draft(self):
        assert RunbookQuality.DRAFT == "draft"

    def test_quality_needs_revision(self):
        assert RunbookQuality.NEEDS_REVISION == "needs_revision"

    def test_quality_obsolete(self):
        assert RunbookQuality.OBSOLETE == "obsolete"

    # RunbookScope (5)
    def test_scope_service_specific(self):
        assert RunbookScope.SERVICE_SPECIFIC == "service_specific"

    def test_scope_team_wide(self):
        assert RunbookScope.TEAM_WIDE == "team_wide"

    def test_scope_platform_wide(self):
        assert RunbookScope.PLATFORM_WIDE == "platform_wide"

    def test_scope_cross_team(self):
        assert RunbookScope.CROSS_TEAM == "cross_team"

    def test_scope_emergency(self):
        assert RunbookScope.EMERGENCY == "emergency"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_generated_runbook_defaults(self):
        r = GeneratedRunbook()
        assert r.id
        assert r.runbook_name == ""
        assert r.source == RunbookSource.INCIDENT_PATTERN
        assert r.quality == RunbookQuality.DRAFT
        assert r.scope == RunbookScope.SERVICE_SPECIFIC
        assert r.accuracy_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_generation_rule_defaults(self):
        r = GenerationRule()
        assert r.id
        assert r.rule_name == ""
        assert r.source == RunbookSource.INCIDENT_PATTERN
        assert r.scope == RunbookScope.SERVICE_SPECIFIC
        assert r.min_incidents == 3
        assert r.auto_generate is True
        assert r.created_at > 0

    def test_runbook_generator_report_defaults(self):
        r = RunbookGeneratorReport()
        assert r.total_runbooks == 0
        assert r.total_rules == 0
        assert r.production_ready_rate_pct == 0.0
        assert r.by_source == {}
        assert r.by_quality == {}
        assert r.obsolete_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_runbook
# -------------------------------------------------------------------


class TestRecordRunbook:
    def test_basic(self):
        eng = _engine()
        r = eng.record_runbook(
            "restart-svc",
            source=RunbookSource.INCIDENT_PATTERN,
            quality=RunbookQuality.DRAFT,
        )
        assert r.runbook_name == "restart-svc"
        assert r.source == RunbookSource.INCIDENT_PATTERN

    def test_with_quality(self):
        eng = _engine()
        r = eng.record_runbook(
            "scale-out",
            quality=RunbookQuality.PRODUCTION_READY,
        )
        assert r.quality == RunbookQuality.PRODUCTION_READY

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_runbook(f"rb-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_runbook
# -------------------------------------------------------------------


class TestGetRunbook:
    def test_found(self):
        eng = _engine()
        r = eng.record_runbook("rb-a")
        assert eng.get_runbook(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_runbook("nonexistent") is None


# -------------------------------------------------------------------
# list_runbooks
# -------------------------------------------------------------------


class TestListRunbooks:
    def test_list_all(self):
        eng = _engine()
        eng.record_runbook("rb-a")
        eng.record_runbook("rb-b")
        assert len(eng.list_runbooks()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.record_runbook("rb-a")
        eng.record_runbook("rb-b")
        results = eng.list_runbooks(
            runbook_name="rb-a",
        )
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            source=RunbookSource.BEST_PRACTICE,
        )
        eng.record_runbook(
            "rb-b",
            source=RunbookSource.TEMPLATE,
        )
        results = eng.list_runbooks(
            source=RunbookSource.BEST_PRACTICE,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "auto-gen-incidents",
            source=RunbookSource.INCIDENT_PATTERN,
            scope=RunbookScope.TEAM_WIDE,
            min_incidents=5,
            auto_generate=True,
        )
        assert p.rule_name == "auto-gen-incidents"
        assert p.min_incidents == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_runbook_quality
# -------------------------------------------------------------------


class TestAnalyzeRunbookQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.PRODUCTION_READY,
            accuracy_score=90.0,
        )
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.DRAFT,
            accuracy_score=60.0,
        )
        result = eng.analyze_runbook_quality("rb-a")
        assert result["runbook_name"] == "rb-a"
        assert result["runbook_count"] == 2
        assert result["ready_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_runbook_quality("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_obsolete_runbooks
# -------------------------------------------------------------------


class TestIdentifyObsoleteRunbooks:
    def test_with_obsolete(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.OBSOLETE,
        )
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.OBSOLETE,
        )
        eng.record_runbook(
            "rb-b",
            quality=RunbookQuality.PRODUCTION_READY,
        )
        results = eng.identify_obsolete_runbooks()
        assert len(results) == 1
        assert results[0]["runbook_name"] == "rb-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_obsolete_runbooks() == []


# -------------------------------------------------------------------
# rank_by_accuracy
# -------------------------------------------------------------------


class TestRankByAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            accuracy_score=90.0,
        )
        eng.record_runbook(
            "rb-a",
            accuracy_score=80.0,
        )
        eng.record_runbook(
            "rb-b",
            accuracy_score=50.0,
        )
        results = eng.rank_by_accuracy()
        assert results[0]["runbook_name"] == "rb-a"
        assert results[0]["avg_accuracy"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy() == []


# -------------------------------------------------------------------
# detect_quality_gaps
# -------------------------------------------------------------------


class TestDetectQualityGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_runbook(
                "rb-a",
                quality=RunbookQuality.DRAFT,
            )
        eng.record_runbook(
            "rb-b",
            quality=RunbookQuality.PRODUCTION_READY,
        )
        results = eng.detect_quality_gaps()
        assert len(results) == 1
        assert results[0]["runbook_name"] == "rb-a"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.DRAFT,
        )
        assert eng.detect_quality_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            quality=RunbookQuality.PRODUCTION_READY,
        )
        eng.record_runbook(
            "rb-b",
            quality=RunbookQuality.OBSOLETE,
        )
        eng.record_runbook(
            "rb-b",
            quality=RunbookQuality.OBSOLETE,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_runbooks == 3
        assert report.total_rules == 1
        assert report.by_source != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_runbooks == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_runbook("rb-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_runbooks"] == 0
        assert stats["total_rules"] == 0
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_runbook(
            "rb-a",
            source=RunbookSource.INCIDENT_PATTERN,
        )
        eng.record_runbook(
            "rb-b",
            source=RunbookSource.BEST_PRACTICE,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_runbooks"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_runbooks"] == 2
