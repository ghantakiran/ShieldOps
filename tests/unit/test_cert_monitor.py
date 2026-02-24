"""Tests for shieldops.security.cert_monitor — CertificateExpiryMonitor."""

from __future__ import annotations

import time

from shieldops.security.cert_monitor import (
    CertificateExpiryMonitor,
    CertificateRecord,
    CertificateType,
    CertInventorySummary,
    CertStatus,
    RenewalAlert,
    RenewalPriority,
)


def _engine(**kw) -> CertificateExpiryMonitor:
    return CertificateExpiryMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CertificateType (6)
    def test_type_tls(self):
        assert CertificateType.TLS == "tls"

    def test_type_code_signing(self):
        assert CertificateType.CODE_SIGNING == "code_signing"

    def test_type_client_auth(self):
        assert CertificateType.CLIENT_AUTH == "client_auth"

    def test_type_ca_root(self):
        assert CertificateType.CA_ROOT == "ca_root"

    def test_type_intermediate(self):
        assert CertificateType.INTERMEDIATE == "intermediate"

    def test_type_self_signed(self):
        assert CertificateType.SELF_SIGNED == "self_signed"

    # CertStatus (5)
    def test_status_valid(self):
        assert CertStatus.VALID == "valid"

    def test_status_expiring_soon(self):
        assert CertStatus.EXPIRING_SOON == "expiring_soon"

    def test_status_expired(self):
        assert CertStatus.EXPIRED == "expired"

    def test_status_revoked(self):
        assert CertStatus.REVOKED == "revoked"

    def test_status_unknown(self):
        assert CertStatus.UNKNOWN == "unknown"

    # RenewalPriority (4)
    def test_priority_low(self):
        assert RenewalPriority.LOW == "low"

    def test_priority_medium(self):
        assert RenewalPriority.MEDIUM == "medium"

    def test_priority_high(self):
        assert RenewalPriority.HIGH == "high"

    def test_priority_critical(self):
        assert RenewalPriority.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_certificate_record_defaults(self):
        c = CertificateRecord()
        assert c.id
        assert c.cert_type == CertificateType.TLS
        assert c.status == CertStatus.UNKNOWN
        assert c.auto_renew is False

    def test_renewal_alert_defaults(self):
        a = RenewalAlert()
        assert a.id
        assert a.priority == RenewalPriority.LOW
        assert a.acknowledged is False

    def test_cert_inventory_summary_defaults(self):
        s = CertInventorySummary()
        assert s.total_certificates == 0
        assert s.recommendations == []


# ---------------------------------------------------------------------------
# register_certificate
# ---------------------------------------------------------------------------


class TestRegisterCertificate:
    def test_valid_cert_far_future(self):
        eng = _engine()
        future = time.time() + 365 * 86400  # 1 year from now
        cert = eng.register_certificate("example.com", CertificateType.TLS, expires_at=future)
        assert cert.status == CertStatus.VALID
        assert cert.domain == "example.com"

    def test_expired_cert(self):
        eng = _engine()
        past = time.time() - 86400  # yesterday
        cert = eng.register_certificate("old.com", CertificateType.TLS, expires_at=past)
        assert cert.status == CertStatus.EXPIRED

    def test_expiring_soon_cert(self):
        eng = _engine(expiry_warning_days=30)
        soon = time.time() + 10 * 86400  # 10 days from now
        cert = eng.register_certificate("soon.com", CertificateType.TLS, expires_at=soon)
        assert cert.status == CertStatus.EXPIRING_SOON

    def test_eviction(self):
        eng = _engine(max_certificates=3)
        future = time.time() + 365 * 86400
        for i in range(5):
            eng.register_certificate(f"d{i}.com", CertificateType.TLS, expires_at=future)
        assert len(eng._certificates) == 3


# ---------------------------------------------------------------------------
# get_certificate
# ---------------------------------------------------------------------------


class TestGetCertificate:
    def test_found(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        cert = eng.register_certificate("example.com", CertificateType.TLS, expires_at=future)
        assert eng.get_certificate(cert.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_certificate("nonexistent") is None


# ---------------------------------------------------------------------------
# list_certificates
# ---------------------------------------------------------------------------


class TestListCertificates:
    def test_list_all(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        eng.register_certificate("a.com", CertificateType.TLS, expires_at=future)
        eng.register_certificate("b.com", CertificateType.CODE_SIGNING, expires_at=future)
        assert len(eng.list_certificates()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        eng.register_certificate("a.com", CertificateType.TLS, expires_at=future)
        eng.register_certificate("b.com", CertificateType.CODE_SIGNING, expires_at=future)
        results = eng.list_certificates(cert_type=CertificateType.TLS)
        assert len(results) == 1
        assert results[0].cert_type == CertificateType.TLS

    def test_filter_by_status(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        past = time.time() - 86400
        eng.register_certificate("valid.com", CertificateType.TLS, expires_at=future)
        eng.register_certificate("expired.com", CertificateType.TLS, expires_at=past)
        results = eng.list_certificates(status=CertStatus.EXPIRED)
        assert len(results) == 1
        assert results[0].status == CertStatus.EXPIRED


# ---------------------------------------------------------------------------
# check_expiring
# ---------------------------------------------------------------------------


class TestCheckExpiring:
    def test_no_expiring(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        eng.register_certificate("safe.com", CertificateType.TLS, expires_at=future)
        alerts = eng.check_expiring()
        assert len(alerts) == 0

    def test_with_expiring_priorities(self):
        eng = _engine(expiry_warning_days=60)
        # Critical: <= 7 days
        critical_ts = time.time() + 3 * 86400
        eng.register_certificate("crit.com", CertificateType.TLS, expires_at=critical_ts)
        # High: <= 14 days
        high_ts = time.time() + 10 * 86400
        eng.register_certificate("high.com", CertificateType.TLS, expires_at=high_ts)
        # Medium: <= 30 days
        medium_ts = time.time() + 20 * 86400
        eng.register_certificate("med.com", CertificateType.TLS, expires_at=medium_ts)
        alerts = eng.check_expiring()
        assert len(alerts) == 3
        priorities = {a.priority for a in alerts}
        assert RenewalPriority.CRITICAL in priorities
        assert RenewalPriority.HIGH in priorities
        assert RenewalPriority.MEDIUM in priorities

    def test_custom_days_ahead(self):
        eng = _engine(expiry_warning_days=30)
        # 45 days away -- outside default window, but inside custom 60-day window
        expires = time.time() + 45 * 86400
        eng.register_certificate("custom.com", CertificateType.TLS, expires_at=expires)
        assert len(eng.check_expiring(days_ahead=60)) == 1


# ---------------------------------------------------------------------------
# acknowledge_alert
# ---------------------------------------------------------------------------


class TestAcknowledgeAlert:
    def test_success(self):
        eng = _engine(expiry_warning_days=60)
        soon = time.time() + 5 * 86400
        eng.register_certificate("soon.com", CertificateType.TLS, expires_at=soon)
        alerts = eng.check_expiring()
        assert len(alerts) >= 1
        assert eng.acknowledge_alert(alerts[0].id) is True
        assert alerts[0].acknowledged is True

    def test_not_found(self):
        eng = _engine()
        assert eng.acknowledge_alert("nonexistent") is False


# ---------------------------------------------------------------------------
# renew_certificate
# ---------------------------------------------------------------------------


class TestRenewCertificate:
    def test_success(self):
        eng = _engine()
        past = time.time() - 86400
        cert = eng.register_certificate("old.com", CertificateType.TLS, expires_at=past)
        assert cert.status == CertStatus.EXPIRED
        new_expiry = time.time() + 365 * 86400
        assert eng.renew_certificate(cert.id, new_expiry) is True
        assert cert.status == CertStatus.VALID
        assert cert.expires_at == new_expiry

    def test_not_found(self):
        eng = _engine()
        assert eng.renew_certificate("nonexistent", time.time() + 86400) is False


# ---------------------------------------------------------------------------
# revoke_certificate
# ---------------------------------------------------------------------------


class TestRevokeCertificate:
    def test_success(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        cert = eng.register_certificate("rev.com", CertificateType.TLS, expires_at=future)
        assert eng.revoke_certificate(cert.id) is True
        assert cert.status == CertStatus.REVOKED

    def test_not_found(self):
        eng = _engine()
        assert eng.revoke_certificate("nonexistent") is False


# ---------------------------------------------------------------------------
# generate_inventory_summary
# ---------------------------------------------------------------------------


class TestGenerateInventorySummary:
    def test_basic_summary(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        past = time.time() - 86400
        eng.register_certificate(
            "valid.com",
            CertificateType.TLS,
            expires_at=future,
            auto_renew=True,
        )
        eng.register_certificate("expired.com", CertificateType.TLS, expires_at=past)
        summary = eng.generate_inventory_summary()
        assert summary.total_certificates == 2
        assert summary.valid_count == 1
        assert summary.expired_count == 1
        assert summary.auto_renew_count == 1
        assert len(summary.recommendations) >= 1


# ---------------------------------------------------------------------------
# delete_certificate
# ---------------------------------------------------------------------------


class TestDeleteCertificate:
    def test_success(self):
        eng = _engine()
        future = time.time() + 365 * 86400
        cert = eng.register_certificate("del.com", CertificateType.TLS, expires_at=future)
        assert eng.delete_certificate(cert.id) is True
        assert eng.get_certificate(cert.id) is None

    def test_not_found(self):
        eng = _engine()
        assert eng.delete_certificate("nonexistent") is False


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine(expiry_warning_days=60)
        soon = time.time() + 5 * 86400
        eng.register_certificate("soon.com", CertificateType.TLS, expires_at=soon)
        eng.check_expiring()  # populate alerts
        eng.clear_data()
        assert len(eng._certificates) == 0
        assert len(eng._alerts) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_certificates"] == 0
        assert stats["total_alerts"] == 0

    def test_populated(self):
        eng = _engine(expiry_warning_days=60)
        future = time.time() + 365 * 86400
        soon = time.time() + 5 * 86400
        eng.register_certificate("valid.com", CertificateType.TLS, expires_at=future)
        eng.register_certificate("soon.com", CertificateType.TLS, expires_at=soon)
        eng.check_expiring()
        stats = eng.get_stats()
        assert stats["total_certificates"] == 2
        assert stats["total_alerts"] >= 1
        assert stats["unique_domains"] == 2
        assert stats["auto_renew_count"] == 0
