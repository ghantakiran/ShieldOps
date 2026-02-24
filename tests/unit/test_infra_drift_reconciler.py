"""Tests for shieldops.operations.infra_drift_reconciler — InfraDriftReconciler.

Covers:
- DriftType, ReconcileAction, IaCProvider enums
- InfraDrift, ReconcileResult, InfraDriftReport model defaults
- record_drift (basic, unique IDs, extra fields, eviction at max)
- get_drift (found, not found)
- list_drifts (all, filter by provider, filter by type, limit)
- reconcile_drift (basic, not found)
- auto_reconcile_safe_drifts (with safe, disabled)
- calculate_drift_score (basic, clean)
- identify_persistent_drifts (persistent, none)
- estimate_reconcile_effort (basic, empty)
- generate_drift_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.operations.infra_drift_reconciler import (
    DriftType,
    IaCProvider,
    InfraDrift,
    InfraDriftReconciler,
    InfraDriftReport,
    ReconcileAction,
    ReconcileResult,
)


def _engine(**kw) -> InfraDriftReconciler:
    return InfraDriftReconciler(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DriftType (5 values)

    def test_drift_type_added(self):
        assert DriftType.ADDED == "added"

    def test_drift_type_removed(self):
        assert DriftType.REMOVED == "removed"

    def test_drift_type_modified(self):
        assert DriftType.MODIFIED == "modified"

    def test_drift_type_reordered(self):
        assert DriftType.REORDERED == "reordered"

    def test_drift_type_permission_changed(self):
        assert DriftType.PERMISSION_CHANGED == ("permission_changed")

    # ReconcileAction (5 values)

    def test_action_apply_iac(self):
        assert ReconcileAction.APPLY_IAC == "apply_iac"

    def test_action_import_actual(self):
        assert ReconcileAction.IMPORT_ACTUAL == ("import_actual")

    def test_action_ignore(self):
        assert ReconcileAction.IGNORE == "ignore"

    def test_action_manual_review(self):
        assert ReconcileAction.MANUAL_REVIEW == ("manual_review")

    def test_action_destroy_orphan(self):
        assert ReconcileAction.DESTROY_ORPHAN == ("destroy_orphan")

    # IaCProvider (5 values)

    def test_provider_terraform(self):
        assert IaCProvider.TERRAFORM == "terraform"

    def test_provider_cloudformation(self):
        assert IaCProvider.CLOUDFORMATION == ("cloudformation")

    def test_provider_pulumi(self):
        assert IaCProvider.PULUMI == "pulumi"

    def test_provider_ansible(self):
        assert IaCProvider.ANSIBLE == "ansible"

    def test_provider_helm(self):
        assert IaCProvider.HELM == "helm"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_infra_drift_defaults(self):
        d = InfraDrift(resource_id="vpc-001")
        assert d.id
        assert d.resource_type == ""
        assert d.resource_id == "vpc-001"
        assert d.provider == IaCProvider.TERRAFORM
        assert d.drift_type == DriftType.MODIFIED
        assert d.expected_value == ""
        assert d.actual_value == ""
        assert d.reconcile_action == (ReconcileAction.MANUAL_REVIEW)
        assert d.is_reconciled is False
        assert d.detected_at > 0
        assert d.created_at > 0

    def test_reconcile_result_defaults(self):
        r = ReconcileResult(drift_id="d-1")
        assert r.id
        assert r.drift_id == "d-1"
        assert r.action == ReconcileAction.MANUAL_REVIEW
        assert r.success is False
        assert r.message == ""
        assert r.reconciled_at > 0
        assert r.created_at > 0

    def test_infra_drift_report_defaults(self):
        r = InfraDriftReport()
        assert r.total_drifts == 0
        assert r.total_reconciled == 0
        assert r.reconcile_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_provider == {}
        assert r.by_action == {}
        assert r.unreconciled == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_drift
# -------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        e = _engine()
        d = e.record_drift(
            resource_type="aws_instance",
            resource_id="i-001",
            provider=IaCProvider.TERRAFORM,
            drift_type=DriftType.MODIFIED,
        )
        assert d.resource_type == "aws_instance"
        assert d.resource_id == "i-001"
        assert d.provider == IaCProvider.TERRAFORM
        assert d.drift_type == DriftType.MODIFIED

    def test_unique_ids(self):
        e = _engine()
        d1 = e.record_drift(resource_id="a")
        d2 = e.record_drift(resource_id="b")
        assert d1.id != d2.id

    def test_extra_fields(self):
        e = _engine()
        d = e.record_drift(
            resource_id="sg-001",
            provider=IaCProvider.CLOUDFORMATION,
            drift_type=DriftType.PERMISSION_CHANGED,
            expected_value="ingress: 443",
            actual_value="ingress: 443,80",
            reconcile_action=ReconcileAction.APPLY_IAC,
        )
        assert d.provider == IaCProvider.CLOUDFORMATION
        assert d.drift_type == DriftType.PERMISSION_CHANGED
        assert d.expected_value == "ingress: 443"
        assert d.actual_value == "ingress: 443,80"
        assert d.reconcile_action == (ReconcileAction.APPLY_IAC)

    def test_evicts_at_max(self):
        e = _engine(max_drifts=2)
        d1 = e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.record_drift(resource_id="c")
        drifts = e.list_drifts()
        ids = {d.id for d in drifts}
        assert d1.id not in ids
        assert len(drifts) == 2


# -------------------------------------------------------------------
# get_drift
# -------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        e = _engine()
        d = e.record_drift(resource_id="vpc-1")
        assert e.get_drift(d.id) is not None
        assert e.get_drift(d.id).resource_id == "vpc-1"

    def test_not_found(self):
        e = _engine()
        assert e.get_drift("nonexistent") is None


# -------------------------------------------------------------------
# list_drifts
# -------------------------------------------------------------------


class TestListDrifts:
    def test_list_all(self):
        e = _engine()
        e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.record_drift(resource_id="c")
        assert len(e.list_drifts()) == 3

    def test_filter_by_provider(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            provider=IaCProvider.TERRAFORM,
        )
        e.record_drift(
            resource_id="b",
            provider=IaCProvider.HELM,
        )
        filtered = e.list_drifts(provider=IaCProvider.TERRAFORM)
        assert len(filtered) == 1
        assert filtered[0].provider == (IaCProvider.TERRAFORM)

    def test_filter_by_type(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            drift_type=DriftType.ADDED,
        )
        e.record_drift(
            resource_id="b",
            drift_type=DriftType.REMOVED,
        )
        filtered = e.list_drifts(drift_type=DriftType.ADDED)
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.record_drift(resource_id=f"r-{i}")
        assert len(e.list_drifts(limit=3)) == 3


# -------------------------------------------------------------------
# reconcile_drift
# -------------------------------------------------------------------


class TestReconcileDrift:
    def test_basic(self):
        e = _engine()
        d = e.record_drift(resource_id="vpc-1")
        result = e.reconcile_drift(d.id, ReconcileAction.APPLY_IAC)
        assert result is not None
        assert result.drift_id == d.id
        assert result.action == ReconcileAction.APPLY_IAC
        assert result.success is True
        assert d.is_reconciled is True

    def test_not_found(self):
        e = _engine()
        assert e.reconcile_drift("nonexistent") is None


# -------------------------------------------------------------------
# auto_reconcile_safe_drifts
# -------------------------------------------------------------------


class TestAutoReconcileSafeDrifts:
    def test_with_safe(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            drift_type=DriftType.REORDERED,
        )
        e.record_drift(
            resource_id="b",
            drift_type=DriftType.MODIFIED,
            reconcile_action=ReconcileAction.APPLY_IAC,
        )
        e.record_drift(
            resource_id="c",
            drift_type=DriftType.PERMISSION_CHANGED,
            reconcile_action=ReconcileAction.MANUAL_REVIEW,
        )
        results = e.auto_reconcile_safe_drifts()
        assert len(results) == 2

    def test_disabled(self):
        e = _engine(auto_reconcile_enabled=False)
        e.record_drift(
            resource_id="a",
            drift_type=DriftType.REORDERED,
        )
        results = e.auto_reconcile_safe_drifts()
        assert len(results) == 0


# -------------------------------------------------------------------
# calculate_drift_score
# -------------------------------------------------------------------


class TestCalculateDriftScore:
    def test_basic(self):
        e = _engine()
        d1 = e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        e.reconcile_drift(d1.id)
        result = e.calculate_drift_score()
        assert result["total_drifts"] == 2
        assert result["unreconciled"] == 1
        assert result["reconciled"] == 1
        assert result["drift_score"] == 50.0
        assert result["health"] == "critical"

    def test_clean(self):
        e = _engine()
        result = e.calculate_drift_score()
        assert result["drift_score"] == 0.0
        assert result["health"] == "clean"


# -------------------------------------------------------------------
# identify_persistent_drifts
# -------------------------------------------------------------------


class TestIdentifyPersistentDrifts:
    def test_persistent(self):
        e = _engine()
        e.record_drift(resource_id="vpc-1")
        e.record_drift(resource_id="vpc-1")
        e.record_drift(resource_id="sg-1")
        persistent = e.identify_persistent_drifts()
        assert len(persistent) == 1
        assert persistent[0]["occurrences"] == 2

    def test_none_persistent(self):
        e = _engine()
        e.record_drift(resource_id="a")
        e.record_drift(resource_id="b")
        assert e.identify_persistent_drifts() == []


# -------------------------------------------------------------------
# estimate_reconcile_effort
# -------------------------------------------------------------------


class TestEstimateReconcileEffort:
    def test_basic(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            reconcile_action=ReconcileAction.APPLY_IAC,
        )
        e.record_drift(
            resource_id="b",
            reconcile_action=ReconcileAction.MANUAL_REVIEW,
        )
        result = e.estimate_reconcile_effort()
        assert result["unreconciled_count"] == 2
        assert result["estimated_minutes"] == 35
        assert result["estimated_hours"] == 0.6
        assert "apply_iac" in result["by_action"]
        assert "manual_review" in result["by_action"]

    def test_empty(self):
        e = _engine()
        result = e.estimate_reconcile_effort()
        assert result["unreconciled_count"] == 0
        assert result["estimated_minutes"] == 0


# -------------------------------------------------------------------
# generate_drift_report
# -------------------------------------------------------------------


class TestGenerateDriftReport:
    def test_populated(self):
        e = _engine()
        d = e.record_drift(
            resource_id="a",
            provider=IaCProvider.TERRAFORM,
            drift_type=DriftType.MODIFIED,
        )
        e.record_drift(
            resource_id="b",
            provider=IaCProvider.HELM,
            drift_type=DriftType.ADDED,
        )
        e.reconcile_drift(d.id)
        report = e.generate_drift_report()
        assert report.total_drifts == 2
        assert report.total_reconciled == 1
        assert report.reconcile_rate_pct == 50.0
        assert "modified" in report.by_type
        assert "terraform" in report.by_provider
        assert len(report.unreconciled) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_drift_report()
        assert report.total_drifts == 0
        assert report.total_reconciled == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        d = e.record_drift(resource_id="a")
        e.reconcile_drift(d.id)
        count = e.clear_data()
        assert count == 1
        assert e.list_drifts() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_drifts"] == 0
        assert stats["total_results"] == 0
        assert stats["max_drifts"] == 200000
        assert stats["auto_reconcile_enabled"] is True
        assert stats["type_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.record_drift(
            resource_id="a",
            drift_type=DriftType.MODIFIED,
        )
        e.record_drift(
            resource_id="b",
            drift_type=DriftType.ADDED,
        )
        stats = e.get_stats()
        assert stats["total_drifts"] == 2
        assert "modified" in stats["type_distribution"]
        assert "added" in stats["type_distribution"]
