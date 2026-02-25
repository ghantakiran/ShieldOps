"""Tests for shieldops.security.permission_drift — PermissionDriftDetector."""

from __future__ import annotations

from shieldops.security.permission_drift import (
    DriftSeverity,
    DriftType,
    PermissionBaseline,
    PermissionDriftDetector,
    PermissionDriftRecord,
    PermissionDriftReport,
    PermissionScope,
)


def _engine(**kw) -> PermissionDriftDetector:
    return PermissionDriftDetector(**kw)


class TestEnums:
    def test_drift_unused(self):
        assert DriftType.UNUSED_PERMISSION == "unused_permission"

    def test_drift_over(self):
        assert DriftType.OVER_PRIVILEGED == "over_privileged"

    def test_drift_orphaned(self):
        assert DriftType.ORPHANED_ROLE == "orphaned_role"

    def test_drift_policy(self):
        assert DriftType.POLICY_VIOLATION == "policy_violation"

    def test_drift_escalation(self):
        assert DriftType.ESCALATION_RISK == "escalation_risk"

    def test_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert DriftSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_severity_info(self):
        assert DriftSeverity.INFORMATIONAL == "informational"

    def test_scope_iam(self):
        assert PermissionScope.IAM == "iam"

    def test_scope_rbac(self):
        assert PermissionScope.RBAC == "rbac"

    def test_scope_sa(self):
        assert PermissionScope.SERVICE_ACCOUNT == "service_account"

    def test_scope_api(self):
        assert PermissionScope.API_KEY == "api_key"

    def test_scope_db(self):
        assert PermissionScope.DATABASE == "database"


class TestModels:
    def test_drift_record_defaults(self):
        r = PermissionDriftRecord()
        assert r.id
        assert r.principal == ""
        assert r.scope == PermissionScope.IAM
        assert r.drift_type == DriftType.UNUSED_PERMISSION
        assert r.severity == DriftSeverity.MEDIUM
        assert r.unused_days == 0
        assert r.created_at > 0

    def test_baseline_defaults(self):
        b = PermissionBaseline()
        assert b.id
        assert b.permissions == []

    def test_report_defaults(self):
        r = PermissionDriftReport()
        assert r.total_drifts == 0
        assert r.recommendations == []


class TestRecordDrift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift(
            principal="admin-user",
            drift_type=DriftType.OVER_PRIVILEGED,
            severity=DriftSeverity.HIGH,
            permission="s3:*",
        )
        assert r.principal == "admin-user"
        assert r.drift_type == DriftType.OVER_PRIVILEGED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(principal=f"user-{i}")
        assert len(eng._records) == 3


class TestGetDrift:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift(principal="u1")
        assert eng.get_drift(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None


class TestListDrifts:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift(principal="u1")
        eng.record_drift(principal="u2")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_principal(self):
        eng = _engine()
        eng.record_drift(principal="u1")
        eng.record_drift(principal="u2")
        assert len(eng.list_drifts(principal="u1")) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_drift(principal="u1", drift_type=DriftType.UNUSED_PERMISSION)
        eng.record_drift(principal="u2", drift_type=DriftType.OVER_PRIVILEGED)
        assert len(eng.list_drifts(drift_type=DriftType.UNUSED_PERMISSION)) == 1


class TestSetBaseline:
    def test_basic(self):
        eng = _engine()
        b = eng.set_baseline(principal="user-a", permissions=["read", "write"])
        assert b.principal == "user-a"
        assert len(b.permissions) == 2


class TestDetectUnused:
    def test_finds_unused(self):
        eng = _engine(unused_days_threshold=90)
        eng.record_drift(
            principal="u1",
            drift_type=DriftType.UNUSED_PERMISSION,
            unused_days=120,
            permission="s3:PutObject",
        )
        results = eng.detect_unused_permissions()
        assert len(results) == 1

    def test_below_threshold(self):
        eng = _engine(unused_days_threshold=90)
        eng.record_drift(
            principal="u1",
            drift_type=DriftType.UNUSED_PERMISSION,
            unused_days=30,
        )
        assert eng.detect_unused_permissions() == []


class TestDetectOverPrivileged:
    def test_finds(self):
        eng = _engine()
        eng.record_drift(principal="u1", drift_type=DriftType.OVER_PRIVILEGED, permission="admin:*")
        results = eng.detect_over_privileged_principals()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_over_privileged_principals() == []


class TestCompareToBaseline:
    def test_with_baseline(self):
        eng = _engine()
        eng.set_baseline(principal="u1", permissions=["read"])
        eng.record_drift(principal="u1", permission="write")
        result = eng.compare_to_baseline("u1")
        assert result["baseline_found"] is True
        assert "write" in result["extra_permissions"]

    def test_no_baseline(self):
        eng = _engine()
        result = eng.compare_to_baseline("unknown")
        assert result["baseline_found"] is False


class TestRankPrincipalsByDrift:
    def test_ranked(self):
        eng = _engine()
        eng.record_drift(principal="u1", severity=DriftSeverity.CRITICAL)
        eng.record_drift(principal="u1", severity=DriftSeverity.HIGH)
        eng.record_drift(principal="u2", severity=DriftSeverity.LOW)
        results = eng.rank_principals_by_drift()
        assert results[0]["principal"] == "u1"
        assert results[0]["total_drifts"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_principals_by_drift() == []


class TestGenerateReportPD:
    def test_populated(self):
        eng = _engine(unused_days_threshold=90)
        eng.record_drift(
            principal="u1",
            drift_type=DriftType.UNUSED_PERMISSION,
            severity=DriftSeverity.CRITICAL,
            unused_days=120,
        )
        report = eng.generate_report()
        assert isinstance(report, PermissionDriftReport)
        assert report.total_drifts == 1
        assert report.critical_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "Permission configuration within acceptable drift limits" in report.recommendations


class TestClearDataPD:
    def test_clears(self):
        eng = _engine()
        eng.record_drift(principal="u1")
        eng.set_baseline(principal="u1", permissions=["read"])
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


class TestGetStatsPD:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_drifts"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_drift(principal="u1")
        stats = eng.get_stats()
        assert stats["total_drifts"] == 1
        assert stats["unique_principals"] == 1
