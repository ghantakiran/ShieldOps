"""Change Conflict Detector — detect scheduling conflicts between concurrent planned changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConflictType(StrEnum):
    DEPENDENCY_CONFLICT = "dependency_conflict"
    RESOURCE_CONTENTION = "resource_contention"
    MAINTENANCE_OVERLAP = "maintenance_overlap"
    MIGRATION_COLLISION = "migration_collision"
    FREEZE_VIOLATION = "freeze_violation"


class ConflictSeverity(StrEnum):
    ADVISORY = "advisory"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class ResolutionStrategy(StrEnum):
    RESCHEDULE_FIRST = "reschedule_first"
    RESCHEDULE_SECOND = "reschedule_second"
    MERGE_CHANGES = "merge_changes"
    SERIALIZE_CHANGES = "serialize_changes"
    MANUAL_COORDINATION = "manual_coordination"


# --- Models ---


class PlannedChange(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_name: str = ""
    service_name: str = ""
    owner: str = ""
    start_at: float = 0.0
    end_at: float = 0.0
    resources: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    status: str = "planned"
    created_at: float = Field(default_factory=time.time)


class ChangeConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_a_id: str = ""
    change_b_id: str = ""
    conflict_type: ConflictType = ConflictType.MAINTENANCE_OVERLAP
    severity: ConflictSeverity = ConflictSeverity.LOW
    resolution: ResolutionStrategy = ResolutionStrategy.MANUAL_COORDINATION
    resolved: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConflictReport(BaseModel):
    total_changes: int = 0
    total_conflicts: int = 0
    total_resolved: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_resolution: dict[str, int] = Field(default_factory=dict)
    blocking_conflicts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeConflictDetector:
    """Detect scheduling conflicts between concurrent planned changes."""

    def __init__(
        self,
        max_records: int = 100000,
        lookahead_hours: int = 168,
    ) -> None:
        self._max_records = max_records
        self._lookahead_hours = lookahead_hours
        self._changes: list[PlannedChange] = []
        self._conflicts: list[ChangeConflict] = []
        logger.info(
            "change_conflict_detector.initialized",
            max_records=max_records,
            lookahead_hours=lookahead_hours,
        )

    # -- changes -----------------------------------------------------

    def register_change(
        self,
        change_name: str,
        service_name: str = "",
        owner: str = "",
        start_at: float = 0.0,
        end_at: float = 0.0,
        resources: list[str] | None = None,
        dependencies: list[str] | None = None,
        **kw: Any,
    ) -> PlannedChange:
        change = PlannedChange(
            change_name=change_name,
            service_name=service_name,
            owner=owner,
            start_at=start_at,
            end_at=end_at,
            resources=resources or [],
            dependencies=dependencies or [],
            **kw,
        )
        self._changes.append(change)
        if len(self._changes) > self._max_records:
            self._changes = self._changes[-self._max_records :]
        logger.info(
            "change_conflict_detector.change_registered",
            change_id=change.id,
            change_name=change_name,
        )
        return change

    def get_change(self, change_id: str) -> PlannedChange | None:
        for c in self._changes:
            if c.id == change_id:
                return c
        return None

    def list_changes(
        self,
        service_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PlannedChange]:
        results = list(self._changes)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- conflict detection ------------------------------------------

    def detect_conflicts(
        self,
        change_id: str,
    ) -> list[ChangeConflict]:
        """Detect conflicts between a specific change and all others."""
        change = self.get_change(change_id)
        if change is None:
            return []
        conflicts: list[ChangeConflict] = []
        for other in self._changes:
            if other.id == change_id:
                continue
            conflict = self._check_conflict(change, other)
            if conflict is not None:
                conflicts.append(conflict)
                self._conflicts.append(conflict)
        if len(self._conflicts) > self._max_records:
            self._conflicts = self._conflicts[-self._max_records :]
        return conflicts

    def detect_all_conflicts(self) -> list[ChangeConflict]:
        """Detect all pairwise conflicts among planned changes."""
        seen: set[tuple[str, str]] = set()
        new_conflicts: list[ChangeConflict] = []
        for i, a in enumerate(self._changes):
            for b in self._changes[i + 1 :]:
                pair = (min(a.id, b.id), max(a.id, b.id))
                if pair in seen:
                    continue
                seen.add(pair)
                conflict = self._check_conflict(a, b)
                if conflict is not None:
                    new_conflicts.append(conflict)
                    self._conflicts.append(conflict)
        if len(self._conflicts) > self._max_records:
            self._conflicts = self._conflicts[-self._max_records :]
        return new_conflicts

    def get_conflict(self, conflict_id: str) -> ChangeConflict | None:
        for c in self._conflicts:
            if c.id == conflict_id:
                return c
        return None

    def list_conflicts(
        self,
        severity: ConflictSeverity | None = None,
        conflict_type: ConflictType | None = None,
        limit: int = 50,
    ) -> list[ChangeConflict]:
        results = list(self._conflicts)
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if conflict_type is not None:
            results = [r for r in results if r.conflict_type == conflict_type]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: ResolutionStrategy = ResolutionStrategy.MANUAL_COORDINATION,
    ) -> bool:
        conflict = self.get_conflict(conflict_id)
        if conflict is None:
            return False
        conflict.resolved = True
        conflict.resolution = resolution
        logger.info(
            "change_conflict_detector.conflict_resolved",
            conflict_id=conflict_id,
            resolution=resolution.value,
        )
        return True

    def suggest_reschedule(
        self,
        conflict_id: str,
    ) -> dict[str, Any]:
        """Suggest rescheduling for a conflict."""
        conflict = self.get_conflict(conflict_id)
        if conflict is None:
            return {"found": False, "suggestion": "No conflict found"}
        change_a = self.get_change(conflict.change_a_id)
        change_b = self.get_change(conflict.change_b_id)
        if change_a is None or change_b is None:
            return {"found": True, "suggestion": "One or more changes not found"}
        # Suggest moving the later change after the earlier one completes
        if change_a.start_at <= change_b.start_at:
            new_start = change_a.end_at + 3600  # 1 hour buffer
            suggestion = (
                f"Reschedule '{change_b.change_name}' to start after "
                f"'{change_a.change_name}' completes"
            )
        else:
            new_start = change_b.end_at + 3600
            suggestion = (
                f"Reschedule '{change_a.change_name}' to start after "
                f"'{change_b.change_name}' completes"
            )
        return {
            "found": True,
            "conflict_id": conflict_id,
            "suggestion": suggestion,
            "suggested_start_at": new_start,
            "strategy": ResolutionStrategy.SERIALIZE_CHANGES.value,
        }

    # -- report / stats ----------------------------------------------

    def generate_conflict_report(self) -> ConflictReport:
        by_type: dict[str, int] = {}
        for c in self._conflicts:
            key = c.conflict_type.value
            by_type[key] = by_type.get(key, 0) + 1
        by_severity: dict[str, int] = {}
        for c in self._conflicts:
            key = c.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        by_resolution: dict[str, int] = {}
        for c in self._conflicts:
            key = c.resolution.value
            by_resolution[key] = by_resolution.get(key, 0) + 1
        resolved_count = sum(1 for c in self._conflicts if c.resolved)
        blocking = [
            c.id
            for c in self._conflicts
            if c.severity == ConflictSeverity.BLOCKING and not c.resolved
        ]
        recs: list[str] = []
        if blocking:
            recs.append(f"{len(blocking)} blocking conflict(s) need resolution")
        unresolved = len(self._conflicts) - resolved_count
        if unresolved > 0 and not blocking:
            recs.append(f"{unresolved} unresolved conflict(s) to review")
        if not recs:
            recs.append("No change conflicts detected")
        return ConflictReport(
            total_changes=len(self._changes),
            total_conflicts=len(self._conflicts),
            total_resolved=resolved_count,
            by_type=by_type,
            by_severity=by_severity,
            by_resolution=by_resolution,
            blocking_conflicts=blocking[:10],
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._changes) + len(self._conflicts)
        self._changes.clear()
        self._conflicts.clear()
        logger.info("change_conflict_detector.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for c in self._conflicts:
            key = c.severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_changes": len(self._changes),
            "total_conflicts": len(self._conflicts),
            "lookahead_hours": self._lookahead_hours,
            "severity_distribution": sev_dist,
        }

    # -- internal helpers --------------------------------------------

    def _check_conflict(
        self,
        a: PlannedChange,
        b: PlannedChange,
    ) -> ChangeConflict | None:
        """Check for conflict between two changes."""
        # Time overlap check
        time_overlap = (
            a.start_at < b.end_at and b.start_at < a.end_at
            if a.start_at > 0 and a.end_at > 0 and b.start_at > 0 and b.end_at > 0
            else False
        )
        # Resource contention check
        shared_resources = set(a.resources) & set(b.resources)
        # Dependency conflict check
        dep_conflict = a.service_name in b.dependencies or b.service_name in a.dependencies
        if not time_overlap and not shared_resources and not dep_conflict:
            return None
        # Determine conflict type and severity
        if dep_conflict and time_overlap:
            ctype = ConflictType.DEPENDENCY_CONFLICT
            severity = ConflictSeverity.HIGH
        elif shared_resources:
            ctype = ConflictType.RESOURCE_CONTENTION
            severity = ConflictSeverity.BLOCKING if time_overlap else ConflictSeverity.MEDIUM
        elif time_overlap:
            ctype = ConflictType.MAINTENANCE_OVERLAP
            severity = ConflictSeverity.LOW
        else:
            ctype = ConflictType.DEPENDENCY_CONFLICT
            severity = ConflictSeverity.ADVISORY
        desc_parts = []
        if time_overlap:
            desc_parts.append("time overlap")
        if shared_resources:
            desc_parts.append(f"shared resources: {', '.join(shared_resources)}")
        if dep_conflict:
            desc_parts.append("dependency conflict")
        return ChangeConflict(
            change_a_id=a.id,
            change_b_id=b.id,
            conflict_type=ctype,
            severity=severity,
            description="; ".join(desc_parts),
        )
