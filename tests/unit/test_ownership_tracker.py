"""Tests for shieldops.topology.ownership_tracker — ServiceOwnershipTracker."""

from __future__ import annotations

from shieldops.topology.ownership_tracker import (
    EscalationLevel,
    OwnershipRecord,
    OwnershipRole,
    OwnershipStatus,
    OwnershipTransfer,
    ServiceOwnershipReport,
    ServiceOwnershipTracker,
)


def _engine(**kw) -> ServiceOwnershipTracker:
    return ServiceOwnershipTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # OwnershipRole (5)
    def test_role_primary_owner(self):
        assert OwnershipRole.PRIMARY_OWNER == "primary_owner"

    def test_role_secondary_owner(self):
        assert OwnershipRole.SECONDARY_OWNER == "secondary_owner"

    def test_role_on_call(self):
        assert OwnershipRole.ON_CALL == "on_call"

    def test_role_contributor(self):
        assert OwnershipRole.CONTRIBUTOR == "contributor"

    def test_role_stakeholder(self):
        assert OwnershipRole.STAKEHOLDER == "stakeholder"

    # OwnershipStatus (5)
    def test_status_active(self):
        assert OwnershipStatus.ACTIVE == "active"

    def test_status_transitioning(self):
        assert OwnershipStatus.TRANSITIONING == "transitioning"

    def test_status_orphaned(self):
        assert OwnershipStatus.ORPHANED == "orphaned"

    def test_status_deprecated(self):
        assert OwnershipStatus.DEPRECATED == "deprecated"

    def test_status_archived(self):
        assert OwnershipStatus.ARCHIVED == "archived"

    # EscalationLevel (5)
    def test_escalation_team(self):
        assert EscalationLevel.TEAM == "team"

    def test_escalation_engineering_lead(self):
        assert EscalationLevel.ENGINEERING_LEAD == "engineering_lead"

    def test_escalation_director(self):
        assert EscalationLevel.DIRECTOR == "director"

    def test_escalation_vp(self):
        assert EscalationLevel.VP == "vp"

    def test_escalation_cto(self):
        assert EscalationLevel.CTO == "cto"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_ownership_record_defaults(self):
        r = OwnershipRecord()
        assert r.id
        assert r.service_name == ""
        assert r.role == OwnershipRole.PRIMARY_OWNER
        assert r.status == OwnershipStatus.ACTIVE
        assert r.escalation == EscalationLevel.TEAM
        assert r.tenure_days == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_ownership_transfer_defaults(self):
        r = OwnershipTransfer()
        assert r.id
        assert r.transfer_name == ""
        assert r.role == OwnershipRole.PRIMARY_OWNER
        assert r.status == OwnershipStatus.ACTIVE
        assert r.from_team == ""
        assert r.to_team == ""
        assert r.created_at > 0

    def test_service_ownership_report_defaults(self):
        r = ServiceOwnershipReport()
        assert r.total_ownerships == 0
        assert r.total_transfers == 0
        assert r.active_rate_pct == 0.0
        assert r.by_role == {}
        assert r.by_status == {}
        assert r.orphan_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_ownership
# -------------------------------------------------------------------


class TestRecordOwnership:
    def test_basic(self):
        eng = _engine()
        r = eng.record_ownership("api-gateway", role=OwnershipRole.PRIMARY_OWNER)
        assert r.service_name == "api-gateway"
        assert r.role == OwnershipRole.PRIMARY_OWNER

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_ownership(
            "payment-service",
            role=OwnershipRole.SECONDARY_OWNER,
            status=OwnershipStatus.TRANSITIONING,
            escalation=EscalationLevel.DIRECTOR,
            tenure_days=365.0,
            details="Transitioning to new team",
        )
        assert r.status == OwnershipStatus.TRANSITIONING
        assert r.escalation == EscalationLevel.DIRECTOR
        assert r.tenure_days == 365.0
        assert r.details == "Transitioning to new team"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_ownership(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_ownership
# -------------------------------------------------------------------


class TestGetOwnership:
    def test_found(self):
        eng = _engine()
        r = eng.record_ownership("api-gateway")
        assert eng.get_ownership(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_ownership("nonexistent") is None


# -------------------------------------------------------------------
# list_ownerships
# -------------------------------------------------------------------


class TestListOwnerships:
    def test_list_all(self):
        eng = _engine()
        eng.record_ownership("svc-a")
        eng.record_ownership("svc-b")
        assert len(eng.list_ownerships()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_ownership("svc-a")
        eng.record_ownership("svc-b")
        results = eng.list_ownerships(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_role(self):
        eng = _engine()
        eng.record_ownership("svc-a", role=OwnershipRole.PRIMARY_OWNER)
        eng.record_ownership("svc-b", role=OwnershipRole.ON_CALL)
        results = eng.list_ownerships(role=OwnershipRole.ON_CALL)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_transfer
# -------------------------------------------------------------------


class TestAddTransfer:
    def test_basic(self):
        eng = _engine()
        t = eng.add_transfer(
            "ownership-handoff",
            role=OwnershipRole.PRIMARY_OWNER,
            status=OwnershipStatus.TRANSITIONING,
            from_team="team-alpha",
            to_team="team-beta",
        )
        assert t.transfer_name == "ownership-handoff"
        assert t.role == OwnershipRole.PRIMARY_OWNER
        assert t.from_team == "team-alpha"
        assert t.to_team == "team-beta"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_transfer(f"transfer-{i}")
        assert len(eng._transfers) == 2


# -------------------------------------------------------------------
# analyze_ownership_health
# -------------------------------------------------------------------


class TestAnalyzeOwnershipHealth:
    def test_with_data(self):
        eng = _engine(max_orphan_days=30.0)
        eng.record_ownership(
            "svc-a",
            status=OwnershipStatus.ACTIVE,
            tenure_days=100.0,
        )
        eng.record_ownership(
            "svc-a",
            status=OwnershipStatus.ACTIVE,
            tenure_days=200.0,
        )
        eng.record_ownership(
            "svc-a",
            status=OwnershipStatus.ORPHANED,
            tenure_days=50.0,
        )
        result = eng.analyze_ownership_health("svc-a")
        assert result["active_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_ownership_health("unknown-svc")
        assert result["status"] == "no_data"

    def test_avg_tenure(self):
        eng = _engine(max_orphan_days=30.0)
        eng.record_ownership("svc-a", tenure_days=100.0)
        eng.record_ownership("svc-a", tenure_days=200.0)
        result = eng.analyze_ownership_health("svc-a")
        assert result["avg_tenure"] == 150.0


# -------------------------------------------------------------------
# identify_orphaned_services
# -------------------------------------------------------------------


class TestIdentifyOrphanedServices:
    def test_with_orphans(self):
        eng = _engine()
        eng.record_ownership("svc-a", status=OwnershipStatus.ORPHANED)
        eng.record_ownership("svc-a", status=OwnershipStatus.DEPRECATED)
        eng.record_ownership("svc-b", status=OwnershipStatus.ACTIVE)
        results = eng.identify_orphaned_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["orphan_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_orphaned_services() == []

    def test_single_orphan_not_returned(self):
        eng = _engine()
        eng.record_ownership("svc-a", status=OwnershipStatus.ORPHANED)
        assert eng.identify_orphaned_services() == []


# -------------------------------------------------------------------
# rank_by_ownership_stability
# -------------------------------------------------------------------


class TestRankByOwnershipStability:
    def test_with_data(self):
        eng = _engine()
        eng.record_ownership("svc-a", tenure_days=30.0)
        eng.record_ownership("svc-b", tenure_days=365.0)
        results = eng.rank_by_ownership_stability()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_tenure_days"] == 365.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_ownership_stability() == []


# -------------------------------------------------------------------
# detect_ownership_gaps
# -------------------------------------------------------------------


class TestDetectOwnershipGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_ownership("svc-a", status=OwnershipStatus.ORPHANED)
        eng.record_ownership("svc-b", status=OwnershipStatus.ACTIVE)
        results = eng.detect_ownership_gaps()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["non_active_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_ownership_gaps() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_ownership("svc-a", status=OwnershipStatus.ORPHANED)
        assert eng.detect_ownership_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_ownership("svc-a", status=OwnershipStatus.ORPHANED)
        eng.record_ownership("svc-b", status=OwnershipStatus.ACTIVE)
        eng.add_transfer("transfer-1")
        report = eng.generate_report()
        assert report.total_ownerships == 2
        assert report.total_transfers == 1
        assert report.by_role != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_ownerships == 0
        assert report.active_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_ownership("svc-a")
        eng.add_transfer("transfer-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._transfers) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_ownerships"] == 0
        assert stats["total_transfers"] == 0
        assert stats["role_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_orphan_days=30.0)
        eng.record_ownership("svc-a", role=OwnershipRole.PRIMARY_OWNER)
        eng.record_ownership("svc-b", role=OwnershipRole.ON_CALL)
        eng.add_transfer("transfer-1")
        stats = eng.get_stats()
        assert stats["total_ownerships"] == 2
        assert stats["total_transfers"] == 1
        assert stats["unique_services"] == 2
        assert stats["max_orphan_days"] == 30.0
