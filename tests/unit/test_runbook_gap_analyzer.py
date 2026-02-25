"""Tests for shieldops.operations.runbook_gap_analyzer."""

from __future__ import annotations

from shieldops.operations.runbook_gap_analyzer import (
    DiscoverySource,
    GapAnalysisReport,
    GapCategory,
    GapRemediation,
    GapSeverity,
    RunbookGap,
    RunbookGapAnalyzer,
)


def _engine(**kw) -> RunbookGapAnalyzer:
    return RunbookGapAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GapSeverity (5 values)

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_moderate(self):
        assert GapSeverity.MODERATE == "moderate"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_urgent(self):
        assert GapSeverity.URGENT == "urgent"

    # GapCategory (5 values)

    def test_category_no_runbook(self):
        assert GapCategory.NO_RUNBOOK == "no_runbook"

    def test_category_outdated_runbook(self):
        assert GapCategory.OUTDATED_RUNBOOK == "outdated_runbook"

    def test_category_partial_coverage(self):
        assert GapCategory.PARTIAL_COVERAGE == "partial_coverage"

    def test_category_wrong_service(self):
        assert GapCategory.WRONG_SERVICE == "wrong_service"

    def test_category_untested_runbook(self):
        assert GapCategory.UNTESTED_RUNBOOK == "untested_runbook"

    # DiscoverySource (5 values)

    def test_source_incident_history(self):
        assert DiscoverySource.INCIDENT_HISTORY == "incident_history"

    def test_source_alert_analysis(self):
        assert DiscoverySource.ALERT_ANALYSIS == "alert_analysis"

    def test_source_failure_mode_catalog(self):
        assert DiscoverySource.FAILURE_MODE_CATALOG == "failure_mode_catalog"

    def test_source_team_feedback(self):
        assert DiscoverySource.TEAM_FEEDBACK == "team_feedback"

    def test_source_automated_scan(self):
        assert DiscoverySource.AUTOMATED_SCAN == "automated_scan"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_runbook_gap_defaults(self):
        g = RunbookGap()
        assert g.id
        assert g.service_name == ""
        assert g.scenario == ""
        assert g.severity == GapSeverity.LOW
        assert g.category == GapCategory.NO_RUNBOOK
        assert g.source == DiscoverySource.AUTOMATED_SCAN
        assert g.incident_count == 0
        assert g.resolved is False
        assert g.created_at > 0

    def test_gap_remediation_defaults(self):
        r = GapRemediation()
        assert r.id
        assert r.gap_id == ""
        assert r.action == ""
        assert r.assignee == ""
        assert r.status == "pending"
        assert r.created_at > 0

    def test_gap_analysis_report_defaults(self):
        r = GapAnalysisReport()
        assert r.total_gaps == 0
        assert r.total_resolved == 0
        assert r.total_remediations == 0
        assert r.by_severity == {}
        assert r.by_category == {}
        assert r.by_source == {}
        assert r.critical_services == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# register_gap
# -------------------------------------------------------------------


class TestRegisterGap:
    def test_basic_register(self):
        eng = _engine()
        g = eng.register_gap("svc-a", scenario="disk full")
        assert g.service_name == "svc-a"
        assert g.scenario == "disk full"
        assert len(eng.list_gaps()) == 1

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        g1 = eng.register_gap("svc-a")
        g2 = eng.register_gap("svc-b")
        assert g1.id != g2.id

    def test_eviction_at_max(self):
        eng = _engine(max_gaps=3)
        ids = []
        for i in range(4):
            g = eng.register_gap(f"svc-{i}")
            ids.append(g.id)
        gaps = eng.list_gaps(limit=100)
        assert len(gaps) == 3
        found = {g.id for g in gaps}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_gap
# -------------------------------------------------------------------


class TestGetGap:
    def test_get_existing(self):
        eng = _engine()
        g = eng.register_gap("svc-a")
        found = eng.get_gap(g.id)
        assert found is not None
        assert found.id == g.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


# -------------------------------------------------------------------
# list_gaps
# -------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.register_gap("svc-a")
        eng.register_gap("svc-b")
        eng.register_gap("svc-c")
        assert len(eng.list_gaps()) == 3

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.register_gap("svc-a")
        eng.register_gap("svc-b")
        eng.register_gap("svc-a")
        results = eng.list_gaps(service_name="svc-a")
        assert len(results) == 2
        assert all(g.service_name == "svc-a" for g in results)

    def test_filter_by_severity(self):
        eng = _engine()
        eng.register_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.register_gap("svc-b", severity=GapSeverity.LOW)
        results = eng.list_gaps(severity=GapSeverity.CRITICAL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_gap(f"svc-{i}")
        results = eng.list_gaps(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# create_remediation
# -------------------------------------------------------------------


class TestCreateRemediation:
    def test_create_success(self):
        eng = _engine()
        g = eng.register_gap("svc-a")
        rem = eng.create_remediation(g.id, action="write runbook", assignee="alice")
        assert rem is not None
        assert rem.gap_id == g.id
        assert rem.action == "write runbook"
        assert rem.assignee == "alice"

    def test_create_gap_not_found(self):
        eng = _engine()
        assert eng.create_remediation("nope") is None


# -------------------------------------------------------------------
# list_remediations
# -------------------------------------------------------------------


class TestListRemediations:
    def test_list_all(self):
        eng = _engine()
        g = eng.register_gap("svc-a")
        eng.create_remediation(g.id, action="fix-1")
        eng.create_remediation(g.id, action="fix-2")
        assert len(eng.list_remediations()) == 2

    def test_filter_by_gap_id(self):
        eng = _engine()
        g1 = eng.register_gap("svc-a")
        g2 = eng.register_gap("svc-b")
        eng.create_remediation(g1.id, action="fix-a")
        eng.create_remediation(g2.id, action="fix-b")
        results = eng.list_remediations(gap_id=g1.id)
        assert len(results) == 1
        assert results[0].gap_id == g1.id


# -------------------------------------------------------------------
# mark_gap_resolved
# -------------------------------------------------------------------


class TestMarkGapResolved:
    def test_resolve_existing(self):
        eng = _engine()
        g = eng.register_gap("svc-a")
        assert eng.mark_gap_resolved(g.id) is True
        found = eng.get_gap(g.id)
        assert found is not None
        assert found.resolved is True

    def test_resolve_not_found(self):
        eng = _engine()
        assert eng.mark_gap_resolved("nope") is False


# -------------------------------------------------------------------
# correlate_incidents_to_gaps
# -------------------------------------------------------------------


class TestCorrelateIncidentsToGaps:
    def test_high_incident_correlation(self):
        eng = _engine(critical_incident_threshold=3)
        eng.register_gap("svc-a", scenario="oom", incident_count=5)
        eng.register_gap("svc-b", scenario="timeout", incident_count=1)
        results = eng.correlate_incidents_to_gaps()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["incident_count"] == 5

    def test_resolved_gaps_excluded(self):
        eng = _engine(critical_incident_threshold=2)
        g = eng.register_gap("svc-a", incident_count=10)
        eng.mark_gap_resolved(g.id)
        results = eng.correlate_incidents_to_gaps()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.correlate_incidents_to_gaps() == []


# -------------------------------------------------------------------
# prioritize_gaps
# -------------------------------------------------------------------


class TestPrioritizeGaps:
    def test_priority_order(self):
        eng = _engine()
        eng.register_gap("svc-low", severity=GapSeverity.LOW, incident_count=1)
        eng.register_gap("svc-urgent", severity=GapSeverity.URGENT, incident_count=10)
        prioritized = eng.prioritize_gaps()
        assert len(prioritized) == 2
        assert prioritized[0].service_name == "svc-urgent"

    def test_resolved_excluded(self):
        eng = _engine()
        g = eng.register_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.mark_gap_resolved(g.id)
        eng.register_gap("svc-b", severity=GapSeverity.LOW)
        prioritized = eng.prioritize_gaps()
        assert len(prioritized) == 1
        assert prioritized[0].service_name == "svc-b"


# -------------------------------------------------------------------
# generate_gap_report
# -------------------------------------------------------------------


class TestGenerateGapReport:
    def test_basic_report(self):
        eng = _engine()
        g = eng.register_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.register_gap("svc-b", severity=GapSeverity.LOW)
        eng.create_remediation(g.id, action="fix")
        report = eng.generate_gap_report()
        assert report.total_gaps == 2
        assert report.total_remediations == 1
        assert isinstance(report.by_severity, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_gap_report()
        assert report.total_gaps == 0
        assert report.total_resolved == 0
        assert "All runbook gaps have been addressed" in report.recommendations


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        g = eng.register_gap("svc-a")
        eng.create_remediation(g.id, action="fix")
        count = eng.clear_data()
        assert count == 1
        assert len(eng.list_gaps()) == 0
        assert len(eng.list_remediations()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_gaps"] == 0
        assert stats["total_remediations"] == 0
        assert stats["critical_incident_threshold"] == 3
        assert stats["severity_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.register_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.register_gap("svc-b", severity=GapSeverity.LOW)
        stats = eng.get_stats()
        assert stats["total_gaps"] == 2
        assert len(stats["severity_distribution"]) == 2
