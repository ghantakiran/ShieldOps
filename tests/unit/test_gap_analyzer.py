"""Tests for shieldops.compliance.gap_analyzer — ComplianceGapAnalyzer."""

from __future__ import annotations

import pytest

from shieldops.compliance.gap_analyzer import (
    ComplianceControl,
    ComplianceGap,
    ComplianceGapAnalyzer,
    GapSeverity,
    GapStatus,
)


def _analyzer(**kw) -> ComplianceGapAnalyzer:
    return ComplianceGapAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # GapSeverity (4 values)

    def test_gap_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_gap_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_gap_severity_medium(self):
        assert GapSeverity.MEDIUM == "medium"

    def test_gap_severity_low(self):
        assert GapSeverity.LOW == "low"

    # GapStatus (4 values)

    def test_gap_status_open(self):
        assert GapStatus.OPEN == "open"

    def test_gap_status_in_progress(self):
        assert GapStatus.IN_PROGRESS == "in_progress"

    def test_gap_status_resolved(self):
        assert GapStatus.RESOLVED == "resolved"

    def test_gap_status_accepted(self):
        assert GapStatus.ACCEPTED == "accepted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_control_defaults(self):
        c = ComplianceControl(
            framework="SOC2",
            control_id="CC6.1",
            title="Logical Access",
        )
        assert c.id
        assert c.framework == "SOC2"
        assert c.control_id == "CC6.1"
        assert c.implemented is False
        assert c.evidence_count == 0
        assert c.last_assessed_at is None

    def test_compliance_gap_defaults(self):
        g = ComplianceGap(
            control_id="ctrl-1",
            framework="SOC2",
        )
        assert g.id
        assert g.status == GapStatus.OPEN
        assert g.assigned_to == ""
        assert g.severity == GapSeverity.HIGH
        assert g.remediation_plan == ""
        assert g.resolved_at is None
        assert g.detected_at > 0


# ---------------------------------------------------------------------------
# register_control
# ---------------------------------------------------------------------------


class TestRegisterControl:
    def test_basic_register(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Logical Access")
        assert ctrl.framework == "SOC2"
        assert ctrl.control_id == "CC6.1"
        assert ctrl.title == "Logical Access"
        assert ctrl.implemented is False

    def test_register_stores_control(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Logical Access")
        assert az.get_control(ctrl.id) is not None

    def test_evicts_at_max_controls(self):
        az = _analyzer(max_controls=2)
        c1 = az.register_control("SOC2", "CC6.1", "First")
        az.register_control("SOC2", "CC6.2", "Second")
        az.register_control("SOC2", "CC6.3", "Third")
        controls = az.list_controls()
        assert len(controls) == 2
        ids = {c.id for c in controls}
        assert c1.id not in ids

    def test_register_with_description(self):
        az = _analyzer()
        ctrl = az.register_control(
            "ISO27001",
            "A.9.1",
            "Access Control",
            description="Limit access to information",
        )
        assert ctrl.description == "Limit access to information"


# ---------------------------------------------------------------------------
# assess_control
# ---------------------------------------------------------------------------


class TestAssessControl:
    def test_marks_implemented_with_evidence(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        assessed = az.assess_control(
            ctrl.id,
            implemented=True,
            evidence_count=5,
        )
        assert assessed is not None
        assert assessed.implemented is True
        assert assessed.evidence_count == 5
        assert assessed.last_assessed_at is not None

    def test_creates_gap_when_not_implemented(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        az.assess_control(ctrl.id, implemented=False)
        gaps = az.list_gaps(framework="SOC2")
        assert len(gaps) == 1
        assert gaps[0].control_id == ctrl.id
        assert gaps[0].severity == GapSeverity.HIGH

    def test_returns_none_for_unknown(self):
        az = _analyzer()
        assert az.assess_control("nonexistent", True) is None

    def test_no_gap_created_when_implemented(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        az.assess_control(ctrl.id, implemented=True)
        gaps = az.list_gaps()
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# create_gap
# ---------------------------------------------------------------------------


class TestCreateGap:
    def test_creates_with_severity(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.CRITICAL)
        assert gap.severity == GapSeverity.CRITICAL
        assert gap.framework == "SOC2"
        assert gap.control_id == ctrl.id
        assert gap.status == GapStatus.OPEN

    def test_evicts_at_max_gaps(self):
        az = _analyzer(max_gaps=2)
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        g1 = az.create_gap(ctrl.id, GapSeverity.HIGH)
        az.create_gap(ctrl.id, GapSeverity.MEDIUM)
        az.create_gap(ctrl.id, GapSeverity.LOW)
        gaps = az.list_gaps()
        assert len(gaps) == 2
        ids = {g.id for g in gaps}
        assert g1.id not in ids

    def test_accepts_string_severity(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, "medium")
        assert gap.severity == GapSeverity.MEDIUM

    def test_framework_empty_for_unknown_control(self):
        az = _analyzer()
        gap = az.create_gap("nonexistent", GapSeverity.LOW)
        assert gap.framework == ""


# ---------------------------------------------------------------------------
# update_gap_status
# ---------------------------------------------------------------------------


class TestUpdateGapStatus:
    def test_changes_status(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.HIGH)
        updated = az.update_gap_status(gap.id, GapStatus.IN_PROGRESS)
        assert updated is not None
        assert updated.status == GapStatus.IN_PROGRESS

    def test_resolved_sets_resolved_at(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.HIGH)
        updated = az.update_gap_status(gap.id, GapStatus.RESOLVED)
        assert updated.resolved_at is not None
        assert updated.resolved_at > 0

    def test_returns_none_for_unknown(self):
        az = _analyzer()
        assert az.update_gap_status("nope", GapStatus.OPEN) is None

    def test_accepts_string_status(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.HIGH)
        updated = az.update_gap_status(gap.id, "accepted")
        assert updated.status == GapStatus.ACCEPTED


# ---------------------------------------------------------------------------
# assign_gap
# ---------------------------------------------------------------------------


class TestAssignGap:
    def test_assigns_to_person(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.HIGH)
        updated = az.assign_gap(gap.id, "alice")
        assert updated is not None
        assert updated.assigned_to == "alice"

    def test_returns_none_for_unknown(self):
        az = _analyzer()
        assert az.assign_gap("nope", "alice") is None


# ---------------------------------------------------------------------------
# resolve_gap
# ---------------------------------------------------------------------------


class TestResolveGap:
    def test_shortcut_sets_resolved(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "Test")
        gap = az.create_gap(ctrl.id, GapSeverity.HIGH)
        resolved = az.resolve_gap(gap.id)
        assert resolved is not None
        assert resolved.status == GapStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_returns_none_for_unknown(self):
        az = _analyzer()
        assert az.resolve_gap("nope") is None


# ---------------------------------------------------------------------------
# list_controls
# ---------------------------------------------------------------------------


class TestListControls:
    def test_filter_by_framework(self):
        az = _analyzer()
        az.register_control("SOC2", "CC6.1", "A")
        az.register_control("ISO27001", "A.9.1", "B")
        results = az.list_controls(framework="SOC2")
        assert len(results) == 1
        assert results[0].framework == "SOC2"

    def test_filter_by_implemented(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        az.register_control("SOC2", "CC6.2", "B")
        az.assess_control(c1.id, implemented=True)
        results = az.list_controls(implemented=True)
        assert len(results) == 1
        assert results[0].implemented is True

    def test_list_all(self):
        az = _analyzer()
        az.register_control("SOC2", "CC6.1", "A")
        az.register_control("ISO27001", "A.9.1", "B")
        assert len(az.list_controls()) == 2


# ---------------------------------------------------------------------------
# list_gaps
# ---------------------------------------------------------------------------


class TestListGaps:
    def test_filter_by_framework(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        c2 = az.register_control("ISO27001", "A.9.1", "B")
        az.create_gap(c1.id, GapSeverity.HIGH)
        az.create_gap(c2.id, GapSeverity.MEDIUM)
        results = az.list_gaps(framework="SOC2")
        assert len(results) == 1
        assert results[0].framework == "SOC2"

    def test_filter_by_severity(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "A")
        az.create_gap(ctrl.id, GapSeverity.CRITICAL)
        az.create_gap(ctrl.id, GapSeverity.LOW)
        results = az.list_gaps(severity=GapSeverity.CRITICAL)
        assert len(results) == 1
        assert results[0].severity == GapSeverity.CRITICAL

    def test_filter_by_status(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "A")
        g1 = az.create_gap(ctrl.id, GapSeverity.HIGH)
        az.create_gap(ctrl.id, GapSeverity.MEDIUM)
        az.update_gap_status(g1.id, GapStatus.RESOLVED)
        results = az.list_gaps(status=GapStatus.OPEN)
        assert len(results) == 1
        assert results[0].status == GapStatus.OPEN

    def test_filter_by_string_severity(self):
        az = _analyzer()
        ctrl = az.register_control("SOC2", "CC6.1", "A")
        az.create_gap(ctrl.id, GapSeverity.LOW)
        results = az.list_gaps(severity="low")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# get_framework_coverage
# ---------------------------------------------------------------------------


class TestGetFrameworkCoverage:
    def test_computes_coverage_pct(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        az.register_control("SOC2", "CC6.2", "B")
        az.assess_control(c1.id, implemented=True, evidence_count=3)
        cov = az.get_framework_coverage("SOC2")
        assert cov["total"] == 2
        assert cov["implemented"] == 1
        assert cov["coverage_pct"] == pytest.approx(50.0)

    def test_gaps_by_severity(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        az.create_gap(c1.id, GapSeverity.CRITICAL)
        az.create_gap(c1.id, GapSeverity.CRITICAL)
        az.create_gap(c1.id, GapSeverity.LOW)
        cov = az.get_framework_coverage("SOC2")
        assert cov["gaps_by_severity"][GapSeverity.CRITICAL] == 2
        assert cov["gaps_by_severity"][GapSeverity.LOW] == 1

    def test_empty_framework_returns_zero(self):
        az = _analyzer()
        cov = az.get_framework_coverage("NIST")
        assert cov["total"] == 0
        assert cov["implemented"] == 0
        assert cov["coverage_pct"] == pytest.approx(0.0)
        assert cov["gaps_by_severity"] == {}

    def test_full_coverage(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        c2 = az.register_control("SOC2", "CC6.2", "B")
        az.assess_control(c1.id, implemented=True)
        az.assess_control(c2.id, implemented=True)
        cov = az.get_framework_coverage("SOC2")
        assert cov["coverage_pct"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        az = _analyzer()
        stats = az.get_stats()
        assert stats["total_controls"] == 0
        assert stats["total_gaps"] == 0
        assert stats["frameworks_tracked"] == 0
        assert stats["overall_coverage_pct"] == pytest.approx(0.0)
        assert stats["severity_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated_stats(self):
        az = _analyzer()
        c1 = az.register_control("SOC2", "CC6.1", "A")
        c2 = az.register_control("ISO27001", "A.9.1", "B")
        az.assess_control(c1.id, implemented=True)
        az.create_gap(c2.id, GapSeverity.CRITICAL)
        az.create_gap(c2.id, GapSeverity.LOW)
        stats = az.get_stats()
        assert stats["total_controls"] == 2
        assert stats["total_gaps"] == 2
        assert stats["frameworks_tracked"] == 2
        # 1 implemented out of 2 controls = 50%
        assert stats["overall_coverage_pct"] == pytest.approx(50.0)
        sev_dist = stats["severity_distribution"]
        assert sev_dist[GapSeverity.CRITICAL] == 1
        assert sev_dist[GapSeverity.LOW] == 1
        status_dist = stats["status_distribution"]
        assert status_dist[GapStatus.OPEN] == 2
