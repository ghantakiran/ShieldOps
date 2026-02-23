"""Tests for shieldops.sla.dependency_sla — DependencySLATracker.

Covers SLAType and ComplianceStatus enums, DependencySLA / SLAEvaluation /
CascadeRisk models, and all DependencySLATracker operations including SLA
management, evaluation, cascade risk detection, service reports, and statistics.
"""

from __future__ import annotations

import pytest

from shieldops.sla.dependency_sla import (
    CascadeRisk,
    ComplianceStatus,
    DependencySLA,
    DependencySLATracker,
    SLAEvaluation,
    SLAType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracker(**kw) -> DependencySLATracker:
    return DependencySLATracker(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of SLAType and ComplianceStatus."""

    # -- SLAType (4 members) -------------------------------------------------

    def test_sla_type_availability(self):
        assert SLAType.AVAILABILITY == "availability"

    def test_sla_type_latency(self):
        assert SLAType.LATENCY == "latency"

    def test_sla_type_throughput(self):
        assert SLAType.THROUGHPUT == "throughput"

    def test_sla_type_error_rate(self):
        assert SLAType.ERROR_RATE == "error_rate"

    # -- ComplianceStatus (4 members) ----------------------------------------

    def test_status_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_status_at_risk(self):
        assert ComplianceStatus.AT_RISK == "at_risk"

    def test_status_breached(self):
        assert ComplianceStatus.BREACHED == "breached"

    def test_status_not_measured(self):
        assert ComplianceStatus.NOT_MEASURED == "not_measured"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_dependency_sla_defaults(self):
        sla = DependencySLA(
            upstream_service="auth",
            downstream_service="api",
            sla_type=SLAType.AVAILABILITY,
            target_value=99.9,
        )
        assert sla.id
        assert sla.warning_threshold == 0.0
        assert sla.current_value is None
        assert sla.status == ComplianceStatus.NOT_MEASURED
        assert sla.last_evaluated_at is None
        assert sla.metadata == {}
        assert sla.created_at > 0

    def test_sla_evaluation_defaults(self):
        ev = SLAEvaluation(
            sla_id="sla-1",
            measured_value=99.5,
            status=ComplianceStatus.COMPLIANT,
        )
        assert ev.id
        assert ev.evaluated_at > 0
        assert ev.details == ""

    def test_cascade_risk_defaults(self):
        risk = CascadeRisk(source_service="auth")
        assert risk.id
        assert risk.affected_services == []
        assert risk.risk_level == "low"
        assert risk.sla_breaches == 0
        assert risk.description == ""
        assert risk.detected_at > 0


# ===========================================================================
# create_sla
# ===========================================================================


class TestCreateSLA:
    """Tests for DependencySLATracker.create_sla."""

    def test_basic_create(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        assert sla.upstream_service == "auth"
        assert sla.downstream_service == "api"
        assert sla.sla_type == SLAType.AVAILABILITY
        assert sla.target_value == 99.9
        assert t.get_sla(sla.id) is sla

    def test_default_warning_threshold(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 100.0)
        # Default warning_threshold = target_value * 0.9
        assert sla.warning_threshold == pytest.approx(90.0)

    def test_create_with_all_fields(self):
        t = _tracker()
        sla = t.create_sla(
            "auth",
            "api",
            SLAType.LATENCY,
            200.0,
            warning_threshold=180.0,
            metadata={"env": "prod"},
        )
        assert sla.warning_threshold == 180.0
        assert sla.metadata == {"env": "prod"}

    def test_create_max_limit(self):
        t = _tracker(max_slas=2)
        t.create_sla("a", "b", SLAType.AVAILABILITY, 99.9)
        t.create_sla("c", "d", SLAType.LATENCY, 200.0)
        with pytest.raises(ValueError, match="Maximum SLAs limit reached"):
            t.create_sla("e", "f", SLAType.THROUGHPUT, 1000.0)


# ===========================================================================
# evaluate_sla
# ===========================================================================


class TestEvaluateSLA:
    """Tests for DependencySLATracker.evaluate_sla."""

    def test_availability_compliant(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        ev = t.evaluate_sla(sla.id, 99.95)
        assert ev.status == ComplianceStatus.COMPLIANT

    def test_availability_at_risk(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        # warning_threshold = 99.9 * 0.9 = 89.91
        # 95.0 >= 89.91 but < 99.9 => AT_RISK
        ev = t.evaluate_sla(sla.id, 95.0)
        assert ev.status == ComplianceStatus.AT_RISK

    def test_availability_breached(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        # warning_threshold defaults to 99.9 * 0.9 = 89.91
        # 80.0 < 89.91 => BREACHED
        ev = t.evaluate_sla(sla.id, 80.0)
        assert ev.status == ComplianceStatus.BREACHED

    def test_latency_compliant(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.LATENCY, 200.0)
        # For latency, lower is better; 150 <= 200 => COMPLIANT
        ev = t.evaluate_sla(sla.id, 150.0)
        assert ev.status == ComplianceStatus.COMPLIANT

    def test_latency_breached(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.LATENCY, 200.0)
        # For latency: warning = 200 * 1.1 = 220; 300 > 220 => BREACHED
        ev = t.evaluate_sla(sla.id, 300.0)
        assert ev.status == ComplianceStatus.BREACHED

    def test_error_rate_compliant(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.ERROR_RATE, 0.05)
        # Error rate: lower is better, 0.02 <= 0.05 => COMPLIANT
        ev = t.evaluate_sla(sla.id, 0.02)
        assert ev.status == ComplianceStatus.COMPLIANT

    def test_error_rate_breached(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.ERROR_RATE, 0.05)
        # warning = 0.05 * 1.1 = 0.055; 0.10 > 0.055 => BREACHED
        ev = t.evaluate_sla(sla.id, 0.10)
        assert ev.status == ComplianceStatus.BREACHED

    def test_not_found(self):
        t = _tracker()
        with pytest.raises(ValueError, match="SLA not found"):
            t.evaluate_sla("nonexistent", 99.9)

    def test_trims_evaluations(self):
        t = _tracker(max_evaluations=3)
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        for _ in range(5):
            t.evaluate_sla(sla.id, 99.95)
        evals = t.get_evaluations()
        assert len(evals) == 3

    def test_updates_sla_fields(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla.id, 99.95)
        updated = t.get_sla(sla.id)
        assert updated.current_value == 99.95
        assert updated.status == ComplianceStatus.COMPLIANT
        assert updated.last_evaluated_at is not None


# ===========================================================================
# get_sla
# ===========================================================================


class TestGetSLA:
    """Tests for DependencySLATracker.get_sla."""

    def test_found(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        assert t.get_sla(sla.id) is sla

    def test_not_found(self):
        t = _tracker()
        assert t.get_sla("nonexistent") is None


# ===========================================================================
# list_slas
# ===========================================================================


class TestListSLAs:
    """Tests for DependencySLATracker.list_slas."""

    def test_list_all(self):
        t = _tracker()
        t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        assert len(t.list_slas()) == 2

    def test_by_upstream(self):
        t = _tracker()
        t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        result = t.list_slas(upstream="auth")
        assert len(result) == 1
        assert result[0].upstream_service == "auth"

    def test_by_downstream(self):
        t = _tracker()
        t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("auth", "web", SLAType.LATENCY, 200.0)
        result = t.list_slas(downstream="web")
        assert len(result) == 1
        assert result[0].downstream_service == "web"

    def test_by_status(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        t.evaluate_sla(sla1.id, 99.95)  # COMPLIANT
        result = t.list_slas(status=ComplianceStatus.COMPLIANT)
        assert len(result) == 1
        assert result[0].status == ComplianceStatus.COMPLIANT

    def test_empty(self):
        t = _tracker()
        assert t.list_slas() == []


# ===========================================================================
# delete_sla
# ===========================================================================


class TestDeleteSLA:
    """Tests for DependencySLATracker.delete_sla."""

    def test_delete_existing(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        assert t.delete_sla(sla.id) is True
        assert t.get_sla(sla.id) is None

    def test_delete_nonexistent(self):
        t = _tracker()
        assert t.delete_sla("nonexistent") is False


# ===========================================================================
# get_evaluations
# ===========================================================================


class TestGetEvaluations:
    """Tests for DependencySLATracker.get_evaluations."""

    def test_all_evaluations(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla.id, 99.95)
        t.evaluate_sla(sla.id, 99.80)
        assert len(t.get_evaluations()) == 2

    def test_by_sla_id(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        t.evaluate_sla(sla1.id, 99.95)
        t.evaluate_sla(sla2.id, 150.0)
        result = t.get_evaluations(sla_id=sla1.id)
        assert len(result) == 1
        assert result[0].sla_id == sla1.id

    def test_limit(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        for _ in range(10):
            t.evaluate_sla(sla.id, 99.95)
        result = t.get_evaluations(limit=3)
        assert len(result) == 3


# ===========================================================================
# detect_cascade_risks
# ===========================================================================


class TestCascadeRisks:
    """Tests for DependencySLATracker.detect_cascade_risks."""

    def test_no_breaches_no_risks(self):
        t = _tracker()
        sla = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla.id, 99.95)  # COMPLIANT
        risks = t.detect_cascade_risks()
        assert len(risks) == 0

    def test_two_breaches_medium_risk(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("auth", "web", SLAType.AVAILABILITY, 99.9)
        # Breach both SLAs from the same upstream "auth"
        t.evaluate_sla(sla1.id, 80.0)
        t.evaluate_sla(sla2.id, 80.0)
        risks = t.detect_cascade_risks()
        assert len(risks) == 1
        assert risks[0].risk_level == "medium"
        assert risks[0].source_service == "auth"
        assert risks[0].sla_breaches == 2

    def test_three_breaches_high_risk(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("auth", "web", SLAType.AVAILABILITY, 99.9)
        sla3 = t.create_sla("auth", "mobile", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla1.id, 80.0)
        t.evaluate_sla(sla2.id, 80.0)
        t.evaluate_sla(sla3.id, 80.0)
        risks = t.detect_cascade_risks()
        assert len(risks) == 1
        assert risks[0].risk_level == "high"
        assert risks[0].sla_breaches == 3
        assert len(risks[0].affected_services) == 3

    def test_affected_services(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("auth", "web", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla1.id, 80.0)
        t.evaluate_sla(sla2.id, 80.0)
        risks = t.detect_cascade_risks()
        affected = sorted(risks[0].affected_services)
        assert affected == ["api", "web"]


# ===========================================================================
# get_service_report
# ===========================================================================


class TestServiceReport:
    """Tests for DependencySLATracker.get_service_report."""

    def test_as_upstream(self):
        t = _tracker()
        t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("auth", "web", SLAType.AVAILABILITY, 99.5)
        report = t.get_service_report("auth")
        assert len(report["as_upstream"]) == 2
        assert len(report["as_downstream"]) == 0

    def test_as_downstream(self):
        t = _tracker()
        t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        report = t.get_service_report("api")
        assert len(report["as_upstream"]) == 0
        assert len(report["as_downstream"]) == 2

    def test_compliance_rate(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("auth", "web", SLAType.AVAILABILITY, 99.9)
        t.evaluate_sla(sla1.id, 99.95)  # COMPLIANT
        t.evaluate_sla(sla2.id, 80.0)  # BREACHED
        report = t.get_service_report("auth")
        # 1 compliant out of 2 measured = 50%
        assert report["compliance_rate"] == pytest.approx(50.0)
        assert report["breaches"] == 1


# ===========================================================================
# get_stats
# ===========================================================================


class TestGetStats:
    """Tests for DependencySLATracker.get_stats."""

    def test_empty_stats(self):
        t = _tracker()
        stats = t.get_stats()
        assert stats["total_slas"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["compliant"] == 0
        assert stats["at_risk"] == 0
        assert stats["breached"] == 0
        assert stats["cascade_risks"] == 0

    def test_populated_stats(self):
        t = _tracker()
        sla1 = t.create_sla("auth", "api", SLAType.AVAILABILITY, 99.9)
        sla2 = t.create_sla("db", "api", SLAType.LATENCY, 200.0)
        t.evaluate_sla(sla1.id, 99.95)  # COMPLIANT
        t.evaluate_sla(sla2.id, 300.0)  # BREACHED
        stats = t.get_stats()
        assert stats["total_slas"] == 2
        assert stats["total_evaluations"] == 2
        assert stats["compliant"] == 1
        assert stats["breached"] == 1
