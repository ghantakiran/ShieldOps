"""Tests for Third-Party Risk Tracker (Phase 17 — F10)."""

from __future__ import annotations

import time

import pytest

from shieldops.vulnerability.third_party_risk import (
    RiskAssessment,
    ThirdPartyRiskTracker,
    VendorCategory,
    VendorIncident,
    VendorRecord,
    VendorRiskLevel,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _tracker(**kw) -> ThirdPartyRiskTracker:
    return ThirdPartyRiskTracker(**kw)


def _register(
    t: ThirdPartyRiskTracker,
    name: str = "Acme SaaS",
    category: VendorCategory = VendorCategory.SAAS,
    **kw,
) -> VendorRecord:
    return t.register_vendor(name=name, category=category, **kw)


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_risk_level_low(self):
        assert VendorRiskLevel.LOW == "low"

    def test_risk_level_medium(self):
        assert VendorRiskLevel.MEDIUM == "medium"

    def test_risk_level_high(self):
        assert VendorRiskLevel.HIGH == "high"

    def test_risk_level_critical(self):
        assert VendorRiskLevel.CRITICAL == "critical"

    def test_risk_level_unassessed(self):
        assert VendorRiskLevel.UNASSESSED == "unassessed"

    def test_category_saas(self):
        assert VendorCategory.SAAS == "saas"

    def test_category_open_source(self):
        assert VendorCategory.OPEN_SOURCE == "open_source"

    def test_category_infrastructure(self):
        assert VendorCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_data_processor(self):
        assert VendorCategory.DATA_PROCESSOR == "data_processor"

    def test_category_security_tool(self):
        assert VendorCategory.SECURITY_TOOL == "security_tool"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_vendor_record_defaults(self):
        v = VendorRecord(
            name="Vendor A",
            category=VendorCategory.SAAS,
        )
        assert v.id
        assert v.name == "Vendor A"
        assert v.risk_level == VendorRiskLevel.UNASSESSED
        assert v.compliance_certifications == []
        assert v.last_assessment_at is None
        assert v.next_assessment_due is None
        assert v.contact_email == ""
        assert v.notes == ""
        assert v.metadata == {}
        assert v.created_at > 0

    def test_vendor_record_full(self):
        v = VendorRecord(
            name="CloudDB",
            category=VendorCategory.DATA_PROCESSOR,
            risk_level=VendorRiskLevel.HIGH,
            compliance_certifications=["SOC2", "ISO27001"],
            contact_email="sec@cloud.db",
            notes="Critical vendor",
            metadata={"region": "us-east"},
        )
        assert v.risk_level == VendorRiskLevel.HIGH
        assert len(v.compliance_certifications) == 2
        assert v.metadata["region"] == "us-east"

    def test_risk_assessment_defaults(self):
        a = RiskAssessment(
            vendor_id="v1",
            risk_level=VendorRiskLevel.LOW,
        )
        assert a.id
        assert a.findings == []
        assert a.recommendations == []
        assert a.assessed_by == ""
        assert a.assessed_at > 0

    def test_vendor_incident_defaults(self):
        inc = VendorIncident(
            vendor_id="v1",
            title="Data breach",
        )
        assert inc.id
        assert inc.description == ""
        assert inc.severity == "medium"
        assert inc.impact == ""
        assert inc.reported_at > 0
        assert inc.resolved_at is None


# -------------------------------------------------------------------
# register_vendor
# -------------------------------------------------------------------


class TestRegisterVendor:
    def test_basic_registration(self):
        t = _tracker()
        v = _register(t)
        assert v.name == "Acme SaaS"
        assert v.category == VendorCategory.SAAS

    def test_registration_all_fields(self):
        t = _tracker()
        v = t.register_vendor(
            name="SecTool",
            category=VendorCategory.SECURITY_TOOL,
            compliance_certifications=["ISO27001"],
            contact_email="sec@tool.com",
            notes="Primary scanner",
            metadata={"tier": "enterprise"},
        )
        assert v.contact_email == "sec@tool.com"
        assert v.metadata["tier"] == "enterprise"

    def test_unique_ids(self):
        t = _tracker()
        v1 = _register(t, name="V1")
        v2 = _register(t, name="V2")
        assert v1.id != v2.id

    def test_max_vendors_limit(self):
        t = _tracker(max_vendors=2)
        _register(t, name="V1")
        _register(t, name="V2")
        with pytest.raises(ValueError, match="Maximum vendors limit"):
            _register(t, name="V3")


# -------------------------------------------------------------------
# assess_vendor
# -------------------------------------------------------------------


class TestAssessVendor:
    def test_basic_assessment(self):
        t = _tracker()
        v = _register(t)
        a = t.assess_vendor(v.id, VendorRiskLevel.LOW)
        assert a.vendor_id == v.id
        assert a.risk_level == VendorRiskLevel.LOW

    def test_assessment_updates_vendor(self):
        t = _tracker()
        v = _register(t)
        t.assess_vendor(v.id, VendorRiskLevel.HIGH)
        updated = t.get_vendor(v.id)
        assert updated is not None
        assert updated.risk_level == VendorRiskLevel.HIGH
        assert updated.last_assessment_at is not None
        assert updated.next_assessment_due is not None

    def test_assessment_sets_next_due(self):
        t = _tracker(assessment_interval_days=30)
        v = _register(t)
        before = time.time()
        t.assess_vendor(v.id, VendorRiskLevel.MEDIUM)
        updated = t.get_vendor(v.id)
        assert updated is not None
        expected_due = before + (30 * 86400)
        assert updated.next_assessment_due is not None
        assert updated.next_assessment_due >= expected_due - 1

    def test_assessment_with_findings(self):
        t = _tracker()
        v = _register(t)
        a = t.assess_vendor(
            v.id,
            VendorRiskLevel.HIGH,
            findings=["No encryption at rest"],
            recommendations=["Enable AES-256"],
            assessed_by="auditor@co.com",
        )
        assert a.findings == ["No encryption at rest"]
        assert a.recommendations == ["Enable AES-256"]
        assert a.assessed_by == "auditor@co.com"

    def test_assess_unknown_vendor_raises(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Vendor not found"):
            t.assess_vendor("ghost", VendorRiskLevel.LOW)


# -------------------------------------------------------------------
# report_incident / resolve_incident
# -------------------------------------------------------------------


class TestIncidents:
    def test_report_basic(self):
        t = _tracker()
        v = _register(t)
        inc = t.report_incident(v.id, "Outage")
        assert inc.vendor_id == v.id
        assert inc.title == "Outage"
        assert inc.resolved_at is None

    def test_report_full(self):
        t = _tracker()
        v = _register(t)
        inc = t.report_incident(
            v.id,
            "Data leak",
            description="Customer PII exposed",
            severity="critical",
            impact="10k records",
        )
        assert inc.severity == "critical"
        assert inc.impact == "10k records"

    def test_report_unknown_vendor_raises(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Vendor not found"):
            t.report_incident("ghost", "Outage")

    def test_resolve_incident(self):
        t = _tracker()
        v = _register(t)
        inc = t.report_incident(v.id, "Outage")
        resolved = t.resolve_incident(inc.id)
        assert resolved is not None
        assert resolved.resolved_at is not None

    def test_resolve_unknown_returns_none(self):
        t = _tracker()
        assert t.resolve_incident("nope") is None


# -------------------------------------------------------------------
# get_vendor / list_vendors / delete_vendor
# -------------------------------------------------------------------


class TestVendorAccess:
    def test_get_existing(self):
        t = _tracker()
        v = _register(t)
        found = t.get_vendor(v.id)
        assert found is not None
        assert found.name == "Acme SaaS"

    def test_get_nonexistent(self):
        t = _tracker()
        assert t.get_vendor("ghost") is None

    def test_list_all(self):
        t = _tracker()
        _register(t, name="V1")
        _register(t, name="V2")
        assert len(t.list_vendors()) == 2

    def test_list_by_risk_level(self):
        t = _tracker()
        v1 = _register(t, name="V1")
        v2 = _register(t, name="V2")
        t.assess_vendor(v1.id, VendorRiskLevel.HIGH)
        t.assess_vendor(v2.id, VendorRiskLevel.LOW)
        highs = t.list_vendors(risk_level=VendorRiskLevel.HIGH)
        assert len(highs) == 1
        assert highs[0].id == v1.id

    def test_list_by_category(self):
        t = _tracker()
        _register(t, name="S1", category=VendorCategory.SAAS)
        _register(t, name="I1", category=VendorCategory.INFRASTRUCTURE)
        saas = t.list_vendors(category=VendorCategory.SAAS)
        assert len(saas) == 1

    def test_list_empty(self):
        t = _tracker()
        assert t.list_vendors() == []

    def test_delete_existing(self):
        t = _tracker()
        v = _register(t)
        assert t.delete_vendor(v.id) is True
        assert t.get_vendor(v.id) is None

    def test_delete_nonexistent(self):
        t = _tracker()
        assert t.delete_vendor("nope") is False


# -------------------------------------------------------------------
# list_incidents
# -------------------------------------------------------------------


class TestListIncidents:
    def test_list_all(self):
        t = _tracker()
        v = _register(t)
        t.report_incident(v.id, "Inc 1")
        t.report_incident(v.id, "Inc 2")
        assert len(t.list_incidents()) == 2

    def test_filter_by_vendor(self):
        t = _tracker()
        v1 = _register(t, name="V1")
        v2 = _register(t, name="V2")
        t.report_incident(v1.id, "V1 outage")
        t.report_incident(v2.id, "V2 outage")
        incs = t.list_incidents(vendor_id=v1.id)
        assert len(incs) == 1

    def test_filter_active_only(self):
        t = _tracker()
        v = _register(t)
        inc1 = t.report_incident(v.id, "Active")
        inc2 = t.report_incident(v.id, "Resolved")
        t.resolve_incident(inc2.id)
        active = t.list_incidents(active_only=True)
        assert len(active) == 1
        assert active[0].id == inc1.id

    def test_list_empty(self):
        t = _tracker()
        assert t.list_incidents() == []


# -------------------------------------------------------------------
# get_overdue_assessments
# -------------------------------------------------------------------


class TestOverdueAssessments:
    def test_never_assessed_is_overdue(self):
        t = _tracker()
        _register(t)
        overdue = t.get_overdue_assessments()
        assert len(overdue) == 1

    def test_recently_assessed_not_overdue(self):
        t = _tracker(assessment_interval_days=90)
        v = _register(t)
        t.assess_vendor(v.id, VendorRiskLevel.LOW)
        overdue = t.get_overdue_assessments()
        assert len(overdue) == 0

    def test_past_due_is_overdue(self):
        t = _tracker(assessment_interval_days=90)
        v = _register(t)
        # Simulate an old assessment
        v.last_assessment_at = time.time() - (91 * 86400)
        v.next_assessment_due = v.last_assessment_at + (90 * 86400)
        overdue = t.get_overdue_assessments()
        assert len(overdue) == 1


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        t = _tracker()
        s = t.get_stats()
        assert s["total_vendors"] == 0
        assert s["total_assessments"] == 0
        assert s["total_incidents"] == 0
        assert s["active_incidents"] == 0
        assert s["overdue_assessments"] == 0
        assert s["risk_distribution"] == {}

    def test_populated_stats(self):
        t = _tracker()
        v1 = _register(t, name="V1")
        v2 = _register(t, name="V2")
        t.assess_vendor(v1.id, VendorRiskLevel.HIGH)
        t.assess_vendor(v2.id, VendorRiskLevel.LOW)
        t.report_incident(v1.id, "Outage")
        s = t.get_stats()
        assert s["total_vendors"] == 2
        assert s["total_assessments"] == 2
        assert s["total_incidents"] == 1
        assert s["active_incidents"] == 1
        assert s["risk_distribution"]["high"] == 1
        assert s["risk_distribution"]["low"] == 1

    def test_resolved_incident_not_active(self):
        t = _tracker()
        v = _register(t)
        inc = t.report_incident(v.id, "Outage")
        t.resolve_incident(inc.id)
        s = t.get_stats()
        assert s["active_incidents"] == 0
