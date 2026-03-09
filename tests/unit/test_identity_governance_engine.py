"""Tests for IdentityGovernanceEngine."""

from __future__ import annotations

from shieldops.security.identity_governance_engine import (
    AccessLevel,
    AccessRecord,
    GovernanceMetric,
    GovernanceReport,
    IdentityGovernanceEngine,
    PrivilegeStatus,
    ReviewDecision,
)


def _engine(**kw) -> IdentityGovernanceEngine:
    return IdentityGovernanceEngine(**kw)


# --- Enum tests ---


class TestEnums:
    def test_access_read(self):
        assert AccessLevel.READ == "read"

    def test_access_write(self):
        assert AccessLevel.WRITE == "write"

    def test_access_admin(self):
        assert AccessLevel.ADMIN == "admin"

    def test_access_super(self):
        assert AccessLevel.SUPER_ADMIN == "super_admin"

    def test_access_svc(self):
        assert AccessLevel.SERVICE_ACCOUNT == "service_account"

    def test_decision_approved(self):
        assert ReviewDecision.APPROVED == "approved"

    def test_decision_revoked(self):
        assert ReviewDecision.REVOKED == "revoked"

    def test_decision_flagged(self):
        assert ReviewDecision.FLAGGED == "flagged"

    def test_privilege_active(self):
        assert PrivilegeStatus.ACTIVE == "active"

    def test_privilege_excessive(self):
        assert PrivilegeStatus.EXCESSIVE == "excessive"

    def test_privilege_dormant(self):
        assert PrivilegeStatus.DORMANT == "dormant"

    def test_privilege_compliant(self):
        assert PrivilegeStatus.COMPLIANT == "compliant"


# --- Model tests ---


class TestModels:
    def test_record_defaults(self):
        r = AccessRecord()
        assert r.id
        assert r.access_level == AccessLevel.READ
        assert r.decision == ReviewDecision.PENDING

    def test_metric_defaults(self):
        m = GovernanceMetric()
        assert m.id
        assert m.value == 0.0

    def test_report_defaults(self):
        r = GovernanceReport()
        assert r.total_records == 0
        assert r.excessive_count == 0


# --- review_access ---


class TestReviewAccess:
    def test_normal_approved(self):
        eng = _engine()
        r = eng.review_access("u1", "db", access_level=AccessLevel.READ)
        assert r.decision == ReviewDecision.APPROVED
        assert r.privilege_status == PrivilegeStatus.ACTIVE

    def test_admin_flagged(self):
        eng = _engine()
        r = eng.review_access("u1", "db", access_level=AccessLevel.ADMIN)
        assert r.decision == ReviewDecision.FLAGGED
        assert r.privilege_status == PrivilegeStatus.EXCESSIVE

    def test_dormant_flagged(self):
        eng = _engine(dormant_threshold_days=90)
        r = eng.review_access("u1", "db", last_used_days=120)
        assert r.decision == ReviewDecision.FLAGGED
        assert r.privilege_status == PrivilegeStatus.DORMANT

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.review_access(f"u{i}", "db")
        assert len(eng._records) == 3


# --- detect_privilege_creep ---


class TestPrivilegeCreep:
    def test_detected(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.ADMIN)
        eng.review_access("u1", "api", access_level=AccessLevel.SUPER_ADMIN)
        results = eng.detect_privilege_creep()
        assert len(results) == 1
        assert results[0]["excessive"] == 2

    def test_none(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.READ)
        assert eng.detect_privilege_creep() == []

    def test_dormant(self):
        eng = _engine(dormant_threshold_days=30)
        eng.review_access("u1", "db", last_used_days=60)
        results = eng.detect_privilege_creep()
        assert results[0]["dormant"] == 1


# --- enforce_least_privilege ---


class TestLeastPrivilege:
    def test_revokes_excessive(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.ADMIN)
        revoked = eng.enforce_least_privilege()
        assert len(revoked) == 1
        assert eng._records[0].privilege_status == PrivilegeStatus.REVOKED

    def test_no_action_on_normal(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.READ)
        revoked = eng.enforce_least_privilege()
        assert len(revoked) == 0


# --- certify_access ---


class TestCertifyAccess:
    def test_approve(self):
        eng = _engine()
        r = eng.review_access("u1", "db")
        result = eng.certify_access(r.id, approve=True)
        assert result["decision"] == "approved"
        assert result["status"] == "compliant"

    def test_revoke(self):
        eng = _engine()
        r = eng.review_access("u1", "db")
        result = eng.certify_access(r.id, approve=False)
        assert result["decision"] == "revoked"

    def test_not_found(self):
        eng = _engine()
        result = eng.certify_access("unknown")
        assert result["error"] == "not_found"


# --- get_governance_metrics ---


class TestGovernanceMetrics:
    def test_with_data(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.ADMIN)
        eng.review_access("u2", "api", access_level=AccessLevel.READ)
        result = eng.get_governance_metrics()
        assert result["total"] == 2
        assert result["excessive_rate"] == 50.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_governance_metrics()
        assert result["total"] == 0


# --- list_records ---


class TestListRecords:
    def test_all(self):
        eng = _engine()
        eng.review_access("u1", "db")
        eng.review_access("u2", "api")
        assert len(eng.list_records()) == 2

    def test_filter_level(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.READ)
        eng.review_access("u2", "api", access_level=AccessLevel.ADMIN)
        assert len(eng.list_records(access_level=AccessLevel.READ)) == 1

    def test_filter_team(self):
        eng = _engine()
        eng.review_access("u1", "db", team="sec")
        eng.review_access("u2", "api", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.review_access(f"u{i}", "db")
        assert len(eng.list_records(limit=5)) == 5


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine()
        eng.review_access("u1", "db", access_level=AccessLevel.ADMIN)
        report = eng.generate_report()
        assert isinstance(report, GovernanceReport)
        assert report.total_records == 1
        assert report.excessive_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "healthy range" in report.recommendations[0]


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.review_access("u1", "db")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_users"] == 1

    def test_clear(self):
        eng = _engine()
        eng.review_access("u1", "db")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
