"""Tests for shieldops.security.credential_expiry_forecaster."""

from __future__ import annotations

import time

from shieldops.security.credential_expiry_forecaster import (
    CredentialExpiryForecaster,
    CredentialRecord,
    CredentialType,
    ExpiryReport,
    ExpiryStatus,
    RenewalForecast,
    RenewalUrgency,
)


def _engine(**kw) -> CredentialExpiryForecaster:
    return CredentialExpiryForecaster(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CredentialType (5 values)

    def test_type_api_key(self):
        assert CredentialType.API_KEY == "api_key"

    def test_type_service_account_token(self):
        assert CredentialType.SERVICE_ACCOUNT_TOKEN == "service_account_token"  # noqa: S105

    def test_type_oauth_secret(self):
        assert CredentialType.OAUTH_SECRET == "oauth_secret"  # noqa: S105

    def test_type_database_password(self):
        assert CredentialType.DATABASE_PASSWORD == "database_password"  # noqa: S105

    def test_type_tls_private_key(self):
        assert CredentialType.TLS_PRIVATE_KEY == "tls_private_key"

    # ExpiryStatus (5 values)

    def test_status_active(self):
        assert ExpiryStatus.ACTIVE == "active"

    def test_status_expiring_soon(self):
        assert ExpiryStatus.EXPIRING_SOON == "expiring_soon"

    def test_status_expired(self):
        assert ExpiryStatus.EXPIRED == "expired"

    def test_status_renewed(self):
        assert ExpiryStatus.RENEWED == "renewed"

    def test_status_revoked(self):
        assert ExpiryStatus.REVOKED == "revoked"

    # RenewalUrgency (5 values)

    def test_urgency_none(self):
        assert RenewalUrgency.NONE == "none"

    def test_urgency_low(self):
        assert RenewalUrgency.LOW == "low"

    def test_urgency_moderate(self):
        assert RenewalUrgency.MODERATE == "moderate"

    def test_urgency_high(self):
        assert RenewalUrgency.HIGH == "high"

    def test_urgency_emergency(self):
        assert RenewalUrgency.EMERGENCY == "emergency"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_credential_record_defaults(self):
        c = CredentialRecord()
        assert c.id
        assert c.credential_name == ""
        assert c.credential_type == CredentialType.API_KEY
        assert c.service_name == ""
        assert c.status == ExpiryStatus.ACTIVE
        assert c.issued_at > 0
        assert c.expires_at == 0.0
        assert c.owner == ""
        assert c.created_at > 0

    def test_renewal_forecast_defaults(self):
        f = RenewalForecast()
        assert f.id
        assert f.credential_id == ""
        assert f.days_until_expiry == 0.0
        assert f.urgency == RenewalUrgency.NONE
        assert f.recommended_renewal_date == 0.0
        assert f.created_at > 0

    def test_expiry_report_defaults(self):
        r = ExpiryReport()
        assert r.total_credentials == 0
        assert r.total_expired == 0
        assert r.total_expiring_soon == 0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_urgency == {}
        assert r.urgent_renewals == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# register_credential
# -------------------------------------------------------------------


class TestRegisterCredential:
    def test_basic_register(self):
        eng = _engine()
        c = eng.register_credential("my-api-key", service_name="svc-a")
        assert c.credential_name == "my-api-key"
        assert c.service_name == "svc-a"
        assert len(eng.list_credentials()) == 1

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        c1 = eng.register_credential("key-1")
        c2 = eng.register_credential("key-2")
        assert c1.id != c2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            c = eng.register_credential(f"key-{i}")
            ids.append(c.id)
        creds = eng.list_credentials(limit=100)
        assert len(creds) == 3
        found = {c.id for c in creds}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_credential
# -------------------------------------------------------------------


class TestGetCredential:
    def test_get_existing(self):
        eng = _engine()
        c = eng.register_credential("my-key")
        found = eng.get_credential(c.id)
        assert found is not None
        assert found.id == c.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_credential("nonexistent") is None


# -------------------------------------------------------------------
# list_credentials
# -------------------------------------------------------------------


class TestListCredentials:
    def test_list_all(self):
        eng = _engine()
        eng.register_credential("key-1")
        eng.register_credential("key-2")
        assert len(eng.list_credentials()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.register_credential("k1", credential_type=CredentialType.API_KEY)
        eng.register_credential("k2", credential_type=CredentialType.TLS_PRIVATE_KEY)
        results = eng.list_credentials(credential_type=CredentialType.API_KEY)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        c = eng.register_credential("k1")
        eng.update_status(c.id, ExpiryStatus.EXPIRED)
        eng.register_credential("k2")
        results = eng.list_credentials(status=ExpiryStatus.EXPIRED)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_credential(f"key-{i}")
        results = eng.list_credentials(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# forecast_renewal
# -------------------------------------------------------------------


class TestForecastRenewal:
    def test_forecast_no_expiry(self):
        eng = _engine()
        c = eng.register_credential("key-1", expires_at=0.0)
        f = eng.forecast_renewal(c.id)
        assert f is not None
        assert f.days_until_expiry == float("inf")
        assert f.urgency == RenewalUrgency.NONE

    def test_forecast_future_expiry(self):
        eng = _engine()
        future = time.time() + 86400 * 60
        c = eng.register_credential("key-1", expires_at=future)
        f = eng.forecast_renewal(c.id)
        assert f is not None
        assert f.days_until_expiry > 50
        assert f.urgency == RenewalUrgency.LOW

    def test_forecast_not_found(self):
        eng = _engine()
        assert eng.forecast_renewal("nope") is None


# -------------------------------------------------------------------
# list_forecasts
# -------------------------------------------------------------------


class TestListForecasts:
    def test_list_all(self):
        eng = _engine()
        c1 = eng.register_credential("k1")
        c2 = eng.register_credential("k2")
        eng.forecast_renewal(c1.id)
        eng.forecast_renewal(c2.id)
        assert len(eng.list_forecasts()) == 2

    def test_filter_by_credential_id(self):
        eng = _engine()
        c1 = eng.register_credential("k1")
        c2 = eng.register_credential("k2")
        eng.forecast_renewal(c1.id)
        eng.forecast_renewal(c2.id)
        results = eng.list_forecasts(credential_id=c1.id)
        assert len(results) == 1
        assert results[0].credential_id == c1.id


# -------------------------------------------------------------------
# update_status
# -------------------------------------------------------------------


class TestUpdateStatus:
    def test_update_existing(self):
        eng = _engine()
        c = eng.register_credential("k1")
        assert eng.update_status(c.id, ExpiryStatus.RENEWED) is True
        found = eng.get_credential(c.id)
        assert found is not None
        assert found.status == ExpiryStatus.RENEWED

    def test_update_not_found(self):
        eng = _engine()
        assert eng.update_status("nope", ExpiryStatus.EXPIRED) is False


# -------------------------------------------------------------------
# find_expired_unrotated
# -------------------------------------------------------------------


class TestFindExpiredUnrotated:
    def test_finds_expired_active(self):
        eng = _engine()
        past = time.time() - 86400
        eng.register_credential("k1", expires_at=past)
        results = eng.find_expired_unrotated()
        assert len(results) == 1

    def test_excludes_renewed(self):
        eng = _engine()
        past = time.time() - 86400
        c = eng.register_credential("k1", expires_at=past)
        eng.update_status(c.id, ExpiryStatus.RENEWED)
        results = eng.find_expired_unrotated()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.find_expired_unrotated() == []


# -------------------------------------------------------------------
# calculate_urgency
# -------------------------------------------------------------------


class TestCalculateUrgency:
    def test_not_found(self):
        eng = _engine()
        result = eng.calculate_urgency("nope")
        assert result["found"] is False

    def test_no_expiry(self):
        eng = _engine()
        c = eng.register_credential("k1", expires_at=0.0)
        result = eng.calculate_urgency(c.id)
        assert result["found"] is True
        assert result["urgency"] == "none"

    def test_emergency_urgency(self):
        eng = _engine()
        past = time.time() - 86400
        c = eng.register_credential("k1", expires_at=past)
        result = eng.calculate_urgency(c.id)
        assert result["urgency"] == "emergency"


# -------------------------------------------------------------------
# generate_expiry_report
# -------------------------------------------------------------------


class TestGenerateExpiryReport:
    def test_basic_report(self):
        eng = _engine()
        past = time.time() - 86400
        eng.register_credential("k1", expires_at=past)
        eng.register_credential("k2")
        report = eng.generate_expiry_report()
        assert report.total_credentials == 2
        assert report.total_expired >= 1
        assert isinstance(report.by_type, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_expiry_report()
        assert report.total_credentials == 0
        assert report.total_expired == 0
        assert "All credentials within acceptable lifecycle" in report.recommendations


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        c = eng.register_credential("k1")
        eng.forecast_renewal(c.id)
        count = eng.clear_data()
        assert count == 1
        assert len(eng.list_credentials()) == 0
        assert len(eng.list_forecasts()) == 0

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
        assert stats["total_credentials"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["warning_days"] == 30
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.register_credential("k1", credential_type=CredentialType.API_KEY)
        eng.register_credential("k2", credential_type=CredentialType.TLS_PRIVATE_KEY)
        stats = eng.get_stats()
        assert stats["total_credentials"] == 2
        assert len(stats["type_distribution"]) == 2
