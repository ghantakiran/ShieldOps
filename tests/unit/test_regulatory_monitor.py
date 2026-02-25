"""Tests for shieldops.compliance.regulatory_monitor — RegulatoryChangeMonitor.

Covers:
- RegulatoryBody, ChangeUrgency, ComplianceImpact enums
- RegulatoryChange, ImpactAssessment, RegulatoryReport model defaults
- record_change (basic, unique IDs, extra fields, eviction at max)
- get_change (found, not found)
- list_changes (all, filter by body, filter by urgency, limit)
- assess_impact (basic, not found)
- mark_addressed (success, not found)
- identify_overdue_changes (overdue, none)
- calculate_compliance_gap (basic, empty)
- estimate_total_effort (basic, empty)
- generate_regulatory_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

import time

from shieldops.compliance.regulatory_monitor import (
    ChangeUrgency,
    ComplianceImpact,
    ImpactAssessment,
    RegulatoryBody,
    RegulatoryChange,
    RegulatoryChangeMonitor,
    RegulatoryReport,
)


def _engine(**kw) -> RegulatoryChangeMonitor:
    return RegulatoryChangeMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RegulatoryBody (5 values)

    def test_body_nist(self):
        assert RegulatoryBody.NIST == "nist"

    def test_body_iso(self):
        assert RegulatoryBody.ISO == "iso"

    def test_body_pci_ssc(self):
        assert RegulatoryBody.PCI_SSC == "pci_ssc"

    def test_body_hipaa_hhs(self):
        assert RegulatoryBody.HIPAA_HHS == "hipaa_hhs"

    def test_body_gdpr_eu(self):
        assert RegulatoryBody.GDPR_EU == "gdpr_eu"

    # ChangeUrgency (5 values)

    def test_urgency_immediate(self):
        assert ChangeUrgency.IMMEDIATE == "immediate"

    def test_urgency_within_30_days(self):
        assert ChangeUrgency.WITHIN_30_DAYS == "within_30_days"

    def test_urgency_within_90_days(self):
        assert ChangeUrgency.WITHIN_90_DAYS == "within_90_days"

    def test_urgency_next_audit_cycle(self):
        assert ChangeUrgency.NEXT_AUDIT_CYCLE == "next_audit_cycle"

    def test_urgency_informational(self):
        assert ChangeUrgency.INFORMATIONAL == "informational"

    # ComplianceImpact (5 values)

    def test_impact_no_impact(self):
        assert ComplianceImpact.NO_IMPACT == "no_impact"

    def test_impact_minor_update(self):
        assert ComplianceImpact.MINOR_UPDATE == "minor_update"

    def test_impact_major_update(self):
        assert ComplianceImpact.MAJOR_UPDATE == "major_update"

    def test_impact_new_control(self):
        assert ComplianceImpact.NEW_CONTROL == "new_control"

    def test_impact_control_removed(self):
        assert ComplianceImpact.CONTROL_REMOVED == "control_removed"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_regulatory_change_defaults(self):
        c = RegulatoryChange(regulation="NIST 800-53")
        assert c.id
        assert c.body == RegulatoryBody.NIST
        assert c.regulation == "NIST 800-53"
        assert c.change_summary == ""
        assert c.urgency == ChangeUrgency.INFORMATIONAL
        assert c.impact == ComplianceImpact.NO_IMPACT
        assert c.affected_controls == []
        assert c.effective_date == ""
        assert c.is_addressed is False
        assert c.created_at > 0

    def test_impact_assessment_defaults(self):
        a = ImpactAssessment(change_id="c-1")
        assert a.id
        assert a.change_id == "c-1"
        assert a.service_name == ""
        assert a.current_compliant is True
        assert a.effort_hours == 0.0
        assert a.priority == 0
        assert a.assessor == ""
        assert a.created_at > 0

    def test_regulatory_report_defaults(self):
        r = RegulatoryReport()
        assert r.total_changes == 0
        assert r.addressed_count == 0
        assert r.pending_count == 0
        assert r.by_body == {}
        assert r.by_urgency == {}
        assert r.by_impact == {}
        assert r.overdue_changes == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_change
# -------------------------------------------------------------------


class TestRecordChange:
    def test_basic(self):
        e = _engine()
        c = e.record_change(
            body=RegulatoryBody.PCI_SSC,
            regulation="PCI DSS 4.0",
            change_summary="New MFA requirements",
        )
        assert c.body == RegulatoryBody.PCI_SSC
        assert c.regulation == "PCI DSS 4.0"
        assert c.change_summary == "New MFA requirements"

    def test_unique_ids(self):
        e = _engine()
        c1 = e.record_change(regulation="A")
        c2 = e.record_change(regulation="B")
        assert c1.id != c2.id

    def test_extra_fields(self):
        e = _engine()
        c = e.record_change(
            body=RegulatoryBody.GDPR_EU,
            urgency=ChangeUrgency.IMMEDIATE,
            impact=ComplianceImpact.MAJOR_UPDATE,
            affected_controls=["CTRL-1", "CTRL-2"],
            effective_date="2026-06-01",
        )
        assert c.urgency == ChangeUrgency.IMMEDIATE
        assert c.impact == ComplianceImpact.MAJOR_UPDATE
        assert len(c.affected_controls) == 2
        assert c.effective_date == "2026-06-01"

    def test_evicts_at_max(self):
        e = _engine(max_changes=2)
        c1 = e.record_change(regulation="A")
        e.record_change(regulation="B")
        e.record_change(regulation="C")
        changes = e.list_changes()
        ids = {c.id for c in changes}
        assert c1.id not in ids
        assert len(changes) == 2


# -------------------------------------------------------------------
# get_change
# -------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        e = _engine()
        c = e.record_change(regulation="SOX")
        assert e.get_change(c.id) is not None
        assert e.get_change(c.id).regulation == "SOX"

    def test_not_found(self):
        e = _engine()
        assert e.get_change("nonexistent") is None


# -------------------------------------------------------------------
# list_changes
# -------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        e = _engine()
        e.record_change(regulation="A")
        e.record_change(regulation="B")
        e.record_change(regulation="C")
        assert len(e.list_changes()) == 3

    def test_filter_by_body(self):
        e = _engine()
        e.record_change(body=RegulatoryBody.NIST)
        e.record_change(body=RegulatoryBody.ISO)
        filtered = e.list_changes(
            body=RegulatoryBody.NIST,
        )
        assert len(filtered) == 1
        assert filtered[0].body == RegulatoryBody.NIST

    def test_filter_by_urgency(self):
        e = _engine()
        e.record_change(
            urgency=ChangeUrgency.IMMEDIATE,
        )
        e.record_change(
            urgency=ChangeUrgency.INFORMATIONAL,
        )
        filtered = e.list_changes(
            urgency=ChangeUrgency.IMMEDIATE,
        )
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.record_change(regulation=f"R-{i}")
        assert len(e.list_changes(limit=3)) == 3


# -------------------------------------------------------------------
# assess_impact
# -------------------------------------------------------------------


class TestAssessImpact:
    def test_basic(self):
        e = _engine()
        c = e.record_change(
            urgency=ChangeUrgency.WITHIN_30_DAYS,
        )
        a = e.assess_impact(
            change_id=c.id,
            service_name="auth-svc",
            effort_hours=16.0,
            assessor="alice",
        )
        assert a is not None
        assert a.change_id == c.id
        assert a.service_name == "auth-svc"
        assert a.effort_hours == 16.0
        assert a.assessor == "alice"
        assert a.current_compliant is False
        assert a.priority == 2

    def test_not_found(self):
        e = _engine()
        assert e.assess_impact("bad-id") is None


# -------------------------------------------------------------------
# mark_addressed
# -------------------------------------------------------------------


class TestMarkAddressed:
    def test_success(self):
        e = _engine()
        c = e.record_change(regulation="X")
        result = e.mark_addressed(c.id)
        assert result is not None
        assert result.is_addressed is True

    def test_not_found(self):
        e = _engine()
        assert e.mark_addressed("nonexistent") is None


# -------------------------------------------------------------------
# identify_overdue_changes
# -------------------------------------------------------------------


class TestIdentifyOverdueChanges:
    def test_overdue(self):
        e = _engine(overdue_grace_days=0)
        c = e.record_change(regulation="OLD")
        # Force old timestamp
        c.created_at = time.time() - 100
        overdue = e.identify_overdue_changes()
        assert len(overdue) >= 1
        assert overdue[0].id == c.id

    def test_none_overdue(self):
        e = _engine(overdue_grace_days=365)
        e.record_change(regulation="NEW")
        assert e.identify_overdue_changes() == []


# -------------------------------------------------------------------
# calculate_compliance_gap
# -------------------------------------------------------------------


class TestCalculateComplianceGap:
    def test_basic(self):
        e = _engine()
        c = e.record_change(regulation="A")
        e.record_change(regulation="B")
        e.mark_addressed(c.id)
        result = e.calculate_compliance_gap()
        assert result["total_changes"] == 2
        assert result["addressed"] == 1
        assert result["pending"] == 1
        assert result["gap_pct"] == 50.0

    def test_empty(self):
        e = _engine()
        result = e.calculate_compliance_gap()
        assert result["total_changes"] == 0
        assert result["gap_pct"] == 0.0


# -------------------------------------------------------------------
# estimate_total_effort
# -------------------------------------------------------------------


class TestEstimateTotalEffort:
    def test_basic(self):
        e = _engine()
        c = e.record_change(regulation="A")
        e.assess_impact(
            c.id,
            effort_hours=10.0,
            assessor="bob",
        )
        result = e.estimate_total_effort()
        assert result["total_effort_hours"] == 10.0
        assert result["total_assessments"] == 1

    def test_empty(self):
        e = _engine()
        result = e.estimate_total_effort()
        assert result["total_effort_hours"] == 0.0
        assert result["total_assessments"] == 0


# -------------------------------------------------------------------
# generate_regulatory_report
# -------------------------------------------------------------------


class TestGenerateRegulatoryReport:
    def test_populated(self):
        e = _engine(overdue_grace_days=365)
        e.record_change(
            body=RegulatoryBody.NIST,
            urgency=ChangeUrgency.IMMEDIATE,
            impact=ComplianceImpact.MAJOR_UPDATE,
        )
        e.record_change(
            body=RegulatoryBody.ISO,
            urgency=ChangeUrgency.INFORMATIONAL,
            impact=ComplianceImpact.NO_IMPACT,
        )
        report = e.generate_regulatory_report()
        assert report.total_changes == 2
        assert report.pending_count == 2
        assert "nist" in report.by_body
        assert "immediate" in report.by_urgency
        assert "major_update" in report.by_impact
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_regulatory_report()
        assert report.total_changes == 0
        assert report.addressed_count == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.record_change(regulation="A")
        e.record_change(regulation="B")
        c = e.record_change(regulation="C")
        e.assess_impact(c.id, effort_hours=5.0)
        count = e.clear_data()
        assert count == 3
        assert e.list_changes() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_changes"] == 0
        assert stats["total_assessments"] == 0
        assert stats["max_changes"] == 50000
        assert stats["overdue_grace_days"] == 30
        assert stats["body_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.record_change(body=RegulatoryBody.NIST)
        e.record_change(body=RegulatoryBody.ISO)
        c = e.record_change(body=RegulatoryBody.NIST)
        e.assess_impact(c.id, effort_hours=4.0)
        stats = e.get_stats()
        assert stats["total_changes"] == 3
        assert stats["total_assessments"] == 1
        assert stats["body_distribution"]["nist"] == 2
        assert stats["body_distribution"]["iso"] == 1
