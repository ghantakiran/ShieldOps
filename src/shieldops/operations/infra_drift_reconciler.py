"""Infrastructure Drift Reconciler — reconcile IaC vs actual state."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    REORDERED = "reordered"
    PERMISSION_CHANGED = "permission_changed"


class ReconcileAction(StrEnum):
    APPLY_IAC = "apply_iac"
    IMPORT_ACTUAL = "import_actual"
    IGNORE = "ignore"
    MANUAL_REVIEW = "manual_review"
    DESTROY_ORPHAN = "destroy_orphan"


class IaCProvider(StrEnum):
    TERRAFORM = "terraform"
    CLOUDFORMATION = "cloudformation"
    PULUMI = "pulumi"
    ANSIBLE = "ansible"
    HELM = "helm"


# --- Models ---


class InfraDrift(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    resource_type: str = ""
    resource_id: str = ""
    provider: IaCProvider = IaCProvider.TERRAFORM
    drift_type: DriftType = DriftType.MODIFIED
    expected_value: str = ""
    actual_value: str = ""
    reconcile_action: ReconcileAction = ReconcileAction.MANUAL_REVIEW
    is_reconciled: bool = False
    detected_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class ReconcileResult(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    drift_id: str = ""
    action: ReconcileAction = ReconcileAction.MANUAL_REVIEW
    success: bool = False
    message: str = ""
    reconciled_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class InfraDriftReport(BaseModel):
    total_drifts: int = 0
    total_reconciled: int = 0
    reconcile_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_provider: dict[str, int] = Field(
        default_factory=dict,
    )
    by_action: dict[str, int] = Field(
        default_factory=dict,
    )
    unreconciled: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Reconciler ---


class InfraDriftReconciler:
    """Detect and reconcile infra state drift from IaC."""

    def __init__(
        self,
        max_drifts: int = 200000,
        auto_reconcile_enabled: bool = True,
    ) -> None:
        self._max_drifts = max_drifts
        self._auto_reconcile_enabled = auto_reconcile_enabled
        self._items: list[InfraDrift] = []
        self._results: list[ReconcileResult] = []
        logger.info(
            "infra_drift_reconciler.initialized",
            max_drifts=max_drifts,
            auto_reconcile=auto_reconcile_enabled,
        )

    # -- record / get / list --

    def record_drift(
        self,
        resource_type: str = "",
        resource_id: str = "",
        provider: IaCProvider = IaCProvider.TERRAFORM,
        drift_type: DriftType = DriftType.MODIFIED,
        expected_value: str = "",
        actual_value: str = "",
        reconcile_action: ReconcileAction = (ReconcileAction.MANUAL_REVIEW),
        **kw: Any,
    ) -> InfraDrift:
        """Record an infrastructure drift."""
        drift = InfraDrift(
            resource_type=resource_type,
            resource_id=resource_id,
            provider=provider,
            drift_type=drift_type,
            expected_value=expected_value,
            actual_value=actual_value,
            reconcile_action=reconcile_action,
            **kw,
        )
        self._items.append(drift)
        if len(self._items) > self._max_drifts:
            self._items.pop(0)
        logger.info(
            "infra_drift_reconciler.recorded",
            drift_id=drift.id,
            resource_id=resource_id,
            provider=provider,
        )
        return drift

    def get_drift(
        self,
        drift_id: str,
    ) -> InfraDrift | None:
        """Get a single drift by ID."""
        for item in self._items:
            if item.id == drift_id:
                return item
        return None

    def list_drifts(
        self,
        provider: IaCProvider | None = None,
        drift_type: DriftType | None = None,
        limit: int = 50,
    ) -> list[InfraDrift]:
        """List drifts with optional filters."""
        results = list(self._items)
        if provider is not None:
            results = [d for d in results if d.provider == provider]
        if drift_type is not None:
            results = [d for d in results if d.drift_type == drift_type]
        return results[-limit:]

    # -- reconciliation operations --

    def reconcile_drift(
        self,
        drift_id: str,
        action: ReconcileAction = (ReconcileAction.APPLY_IAC),
    ) -> ReconcileResult | None:
        """Reconcile a drift with specified action."""
        drift = self.get_drift(drift_id)
        if drift is None:
            return None
        result = ReconcileResult(
            drift_id=drift_id,
            action=action,
            success=True,
            message=f"Applied {action.value} to {drift_id}",
        )
        self._results.append(result)
        drift.is_reconciled = True
        drift.reconcile_action = action
        logger.info(
            "infra_drift_reconciler.reconciled",
            drift_id=drift_id,
            action=action,
        )
        return result

    def auto_reconcile_safe_drifts(
        self,
    ) -> list[ReconcileResult]:
        """Auto-reconcile drifts deemed safe."""
        if not self._auto_reconcile_enabled:
            return []
        safe_types = {DriftType.REORDERED}
        safe_actions = {
            ReconcileAction.IGNORE,
            ReconcileAction.APPLY_IAC,
        }
        reconciled: list[ReconcileResult] = []
        for drift in self._items:
            if drift.is_reconciled:
                continue
            if drift.drift_type in safe_types or drift.reconcile_action in safe_actions:
                result = ReconcileResult(
                    drift_id=drift.id,
                    action=drift.reconcile_action,
                    success=True,
                    message="Auto-reconciled safe drift",
                )
                self._results.append(result)
                drift.is_reconciled = True
                reconciled.append(result)
        logger.info(
            "infra_drift_reconciler.auto_reconciled",
            count=len(reconciled),
        )
        return reconciled

    def calculate_drift_score(self) -> dict[str, Any]:
        """Calculate overall drift score (0=clean)."""
        total = len(self._items)
        unreconciled = sum(1 for d in self._items if not d.is_reconciled)
        score = 0.0
        if total > 0:
            score = round(unreconciled / total * 100, 2)
        return {
            "total_drifts": total,
            "unreconciled": unreconciled,
            "reconciled": total - unreconciled,
            "drift_score": score,
            "health": (
                "clean"
                if score == 0
                else "acceptable"
                if score < 20
                else "concerning"
                if score < 50
                else "critical"
            ),
        }

    def identify_persistent_drifts(
        self,
    ) -> list[dict[str, Any]]:
        """Identify resources that drift repeatedly."""
        resource_counts: dict[str, int] = {}
        for d in self._items:
            key = f"{d.provider.value}:{d.resource_id}"
            resource_counts[key] = resource_counts.get(key, 0) + 1
        persistent: list[dict[str, Any]] = [
            {"resource_key": k, "occurrences": v} for k, v in resource_counts.items() if v > 1
        ]
        persistent.sort(
            key=lambda x: x.get("occurrences", 0),  # type: ignore[return-value]
            reverse=True,
        )
        return persistent

    def estimate_reconcile_effort(
        self,
    ) -> dict[str, Any]:
        """Estimate effort to reconcile all drifts."""
        effort_map = {
            ReconcileAction.IGNORE: 1,
            ReconcileAction.APPLY_IAC: 5,
            ReconcileAction.IMPORT_ACTUAL: 10,
            ReconcileAction.DESTROY_ORPHAN: 15,
            ReconcileAction.MANUAL_REVIEW: 30,
        }
        unreconciled = [d for d in self._items if not d.is_reconciled]
        total_minutes = sum(effort_map.get(d.reconcile_action, 30) for d in unreconciled)
        by_action: dict[str, int] = {}
        for d in unreconciled:
            key = d.reconcile_action.value
            by_action[key] = by_action.get(key, 0) + 1
        return {
            "unreconciled_count": len(unreconciled),
            "estimated_minutes": total_minutes,
            "estimated_hours": round(total_minutes / 60, 1),
            "by_action": by_action,
        }

    # -- report --

    def generate_drift_report(self) -> InfraDriftReport:
        """Generate a comprehensive drift report."""
        total = len(self._items)
        reconciled = sum(1 for d in self._items if d.is_reconciled)
        rate = 0.0
        if total > 0:
            rate = round(reconciled / total * 100, 2)
        by_type: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        by_action: dict[str, int] = {}
        unreconciled: list[str] = []
        for d in self._items:
            t = d.drift_type.value
            by_type[t] = by_type.get(t, 0) + 1
            p = d.provider.value
            by_provider[p] = by_provider.get(p, 0) + 1
            a = d.reconcile_action.value
            by_action[a] = by_action.get(a, 0) + 1
            if not d.is_reconciled:
                unreconciled.append(d.id)
        recs = self._build_recommendations(
            total,
            len(unreconciled),
            rate,
        )
        return InfraDriftReport(
            total_drifts=total,
            total_reconciled=reconciled,
            reconcile_rate_pct=rate,
            by_type=by_type,
            by_provider=by_provider,
            by_action=by_action,
            unreconciled=unreconciled,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns drifts cleared."""
        count = len(self._items)
        self._items.clear()
        self._results.clear()
        logger.info(
            "infra_drift_reconciler.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        type_dist: dict[str, int] = {}
        for d in self._items:
            key = d.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_drifts": len(self._items),
            "total_results": len(self._results),
            "max_drifts": self._max_drifts,
            "auto_reconcile_enabled": (self._auto_reconcile_enabled),
            "type_distribution": type_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total: int,
        unreconciled: int,
        rate: float,
    ) -> list[str]:
        recs: list[str] = []
        if unreconciled > 0:
            recs.append(f"{unreconciled} unreconciled drift(s) require attention")
        if total == 0:
            recs.append("No drifts detected - IaC state is clean")
        if rate > 0 and rate < 80:
            recs.append(f"Reconcile rate at {rate}% - target 80%+")
        if not recs:
            recs.append("Infrastructure drift under control")
        return recs
