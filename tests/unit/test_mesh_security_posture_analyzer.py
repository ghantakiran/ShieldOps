"""Tests for MeshSecurityPostureAnalyzer."""

from __future__ import annotations

from shieldops.observability.mesh_security_posture_analyzer import (
    AuthzGapSeverity,
    CertHealth,
    MeshSecurityPostureAnalyzer,
    MtlsStatus,
)


def _engine(**kw) -> MeshSecurityPostureAnalyzer:
    return MeshSecurityPostureAnalyzer(**kw)


class TestEnums:
    def test_mtls_status_values(self):
        for v in MtlsStatus:
            assert isinstance(v.value, str)

    def test_authz_gap_severity_values(self):
        for v in AuthzGapSeverity:
            assert isinstance(v.value, str)

    def test_cert_health_values(self):
        for v in CertHealth:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service="svc-a")
        assert r.service == "svc-a"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service=f"svc-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            service="svc-a",
            mesh_name="istio",
            mtls_status=MtlsStatus.PERMISSIVE,
            days_to_expiry=30,
        )
        assert r.days_to_expiry == 30


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(service="svc-a")
        a = eng.process(r.id)
        assert a.service == "svc-a"

    def test_insecure(self):
        eng = _engine()
        r = eng.add_record(
            mtls_status=MtlsStatus.DISABLED,
        )
        a = eng.process(r.id)
        assert a.is_secure is False

    def test_authz_gap(self):
        eng = _engine()
        r = eng.add_record(
            authz_gap_severity=(AuthzGapSeverity.CRITICAL),
        )
        a = eng.process(r.id)
        assert a.has_authz_gap is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_insecure_services(self):
        eng = _engine()
        eng.add_record(
            service="svc-a",
            mtls_status=MtlsStatus.DISABLED,
        )
        rpt = eng.generate_report()
        assert len(rpt.insecure_services) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAssessMtlsCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            mesh_name="istio",
            mtls_status=MtlsStatus.ENFORCED,
        )
        result = eng.assess_mtls_coverage()
        assert len(result) == 1
        assert result[0]["coverage_pct"] == 100.0

    def test_empty(self):
        assert _engine().assess_mtls_coverage() == []


class TestDetectAuthorizationGaps:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service="svc-a",
            authz_gap_severity=(AuthzGapSeverity.CRITICAL),
        )
        result = eng.detect_authorization_gaps()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_authorization_gaps() == []


class TestMonitorCertificateHealth:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service="svc-a",
            cert_health=CertHealth.EXPIRING_SOON,
            days_to_expiry=7,
        )
        result = eng.monitor_certificate_health()
        assert len(result) == 1
        assert result[0]["days_to_expiry"] == 7

    def test_empty(self):
        assert _engine().monitor_certificate_health() == []
