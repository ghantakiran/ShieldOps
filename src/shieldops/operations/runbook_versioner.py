"""Runbook Version Manager — version-control runbooks with diffs."""

from __future__ import annotations

import hashlib
import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class ChangeType(StrEnum):
    STEP_ADDED = "step_added"
    STEP_REMOVED = "step_removed"
    STEP_MODIFIED = "step_modified"
    PARAMETER_CHANGED = "parameter_changed"
    REORDERED = "reordered"


class RunbookCategory(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    DEPLOYMENT = "deployment"
    MAINTENANCE = "maintenance"
    SECURITY = "security"
    RECOVERY = "recovery"


# --- Models ---


class RunbookVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    version_number: int = 1
    status: VersionStatus = VersionStatus.DRAFT
    category: RunbookCategory = RunbookCategory.INCIDENT_RESPONSE
    author: str = ""
    change_type: ChangeType = ChangeType.STEP_ADDED
    change_summary: str = ""
    content_hash: str = ""
    steps: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class RunbookDiff(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    from_version: int = 0
    to_version: int = 0
    changes: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    created_at: float = Field(default_factory=time.time)


class VersionReport(BaseModel):
    total_runbooks: int = 0
    total_versions: int = 0
    avg_versions_per_runbook: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    stale_runbooks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookVersionManager:
    """Version-control runbooks with diff tracking and rollback."""

    def __init__(
        self,
        max_versions: int = 100000,
        stale_age_days: int = 90,
    ) -> None:
        self._max_versions = max_versions
        self._stale_age_days = stale_age_days
        self._items: list[RunbookVersion] = []
        self._diffs: dict[str, RunbookDiff] = {}
        logger.info(
            "runbook_versioner.initialized",
            max_versions=max_versions,
            stale_age_days=stale_age_days,
        )

    # -- helpers ----------------------------------------------------

    def _compute_hash(self, steps: list[str]) -> str:
        content = "|".join(steps)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_latest_version_number(self, runbook_id: str) -> int:
        versions = [v for v in self._items if v.runbook_id == runbook_id]
        if not versions:
            return 0
        return max(v.version_number for v in versions)

    # -- CRUD -------------------------------------------------------

    def create_version(
        self,
        runbook_id: str,
        steps: list[str] | None = None,
        category: RunbookCategory = (RunbookCategory.INCIDENT_RESPONSE),
        author: str = "",
        change_type: ChangeType = ChangeType.STEP_ADDED,
        change_summary: str = "",
    ) -> RunbookVersion:
        step_list = steps or []
        ver_num = self._get_latest_version_number(runbook_id) + 1
        content_hash = self._compute_hash(step_list)

        version = RunbookVersion(
            runbook_id=runbook_id,
            version_number=ver_num,
            category=category,
            author=author,
            change_type=change_type,
            change_summary=change_summary,
            content_hash=content_hash,
            steps=step_list,
        )
        self._items.append(version)
        if len(self._items) > self._max_versions:
            self._items = self._items[-self._max_versions :]
        logger.info(
            "runbook_versioner.version_created",
            version_id=version.id,
            runbook_id=runbook_id,
            version_number=ver_num,
        )
        return version

    def get_version(self, version_id: str) -> RunbookVersion | None:
        for v in self._items:
            if v.id == version_id:
                return v
        return None

    def list_versions(
        self,
        runbook_id: str | None = None,
        status: VersionStatus | None = None,
        limit: int = 50,
    ) -> list[RunbookVersion]:
        results = list(self._items)
        if runbook_id is not None:
            results = [v for v in results if v.runbook_id == runbook_id]
        if status is not None:
            results = [v for v in results if v.status == status]
        return results[-limit:]

    # -- Diff -------------------------------------------------------

    def diff_versions(
        self,
        version_id_a: str,
        version_id_b: str,
    ) -> RunbookDiff | None:
        va = self.get_version(version_id_a)
        vb = self.get_version(version_id_b)
        if va is None or vb is None:
            return None
        if va.runbook_id != vb.runbook_id:
            return None

        set_a = set(va.steps)
        set_b = set(vb.steps)
        added = set_b - set_a
        removed = set_a - set_b

        changes: list[str] = []
        for s in sorted(added):
            changes.append(f"+ {s}")
        for s in sorted(removed):
            changes.append(f"- {s}")

        diff = RunbookDiff(
            runbook_id=va.runbook_id,
            from_version=va.version_number,
            to_version=vb.version_number,
            changes=changes,
            additions=len(added),
            deletions=len(removed),
        )
        self._diffs[diff.id] = diff
        logger.info(
            "runbook_versioner.diff_computed",
            diff_id=diff.id,
            runbook_id=va.runbook_id,
            additions=len(added),
            deletions=len(removed),
        )
        return diff

    # -- Workflow ---------------------------------------------------

    def approve_version(self, version_id: str) -> RunbookVersion | None:
        v = self.get_version(version_id)
        if v is None:
            return None
        v.status = VersionStatus.APPROVED
        logger.info(
            "runbook_versioner.version_approved",
            version_id=version_id,
            runbook_id=v.runbook_id,
        )
        return v

    def publish_version(self, version_id: str) -> RunbookVersion | None:
        v = self.get_version(version_id)
        if v is None:
            return None
        # Deprecate older published versions
        for other in self._items:
            if (
                other.runbook_id == v.runbook_id
                and other.status == VersionStatus.PUBLISHED
                and other.id != version_id
            ):
                other.status = VersionStatus.DEPRECATED
        v.status = VersionStatus.PUBLISHED
        logger.info(
            "runbook_versioner.version_published",
            version_id=version_id,
            runbook_id=v.runbook_id,
        )
        return v

    def rollback_to_version(
        self,
        runbook_id: str,
        version_id: str,
    ) -> RunbookVersion | None:
        target = self.get_version(version_id)
        if target is None:
            return None
        if target.runbook_id != runbook_id:
            return None

        # Create a new version from the target's steps
        new_ver = self.create_version(
            runbook_id=runbook_id,
            steps=list(target.steps),
            category=target.category,
            author="rollback",
            change_type=ChangeType.REORDERED,
            change_summary=(f"Rollback to v{target.version_number}"),
        )
        new_ver.status = VersionStatus.PUBLISHED

        # Deprecate current published
        for v in self._items:
            if (
                v.runbook_id == runbook_id
                and v.status == VersionStatus.PUBLISHED
                and v.id != new_ver.id
            ):
                v.status = VersionStatus.DEPRECATED

        logger.info(
            "runbook_versioner.rollback_performed",
            runbook_id=runbook_id,
            target_version=target.version_number,
            new_version_id=new_ver.id,
        )
        return new_ver

    # -- Analysis ---------------------------------------------------

    def detect_stale_runbooks(self, max_age_days: int = 90) -> list[dict[str, Any]]:
        cutoff = time.time() - (max_age_days * 86400)

        runbook_latest: dict[str, RunbookVersion] = {}
        for v in self._items:
            existing = runbook_latest.get(v.runbook_id)
            if existing is None or v.version_number > existing.version_number:
                runbook_latest[v.runbook_id] = v

        stale: list[dict[str, Any]] = []
        for rb_id, latest in runbook_latest.items():
            if latest.created_at < cutoff:
                age_days = int((time.time() - latest.created_at) / 86400)
                stale.append(
                    {
                        "runbook_id": rb_id,
                        "latest_version": (latest.version_number),
                        "age_days": age_days,
                        "category": latest.category.value,
                    }
                )

        stale.sort(key=lambda x: x["age_days"], reverse=True)
        logger.info(
            "runbook_versioner.stale_detected",
            stale_count=len(stale),
            max_age_days=max_age_days,
        )
        return stale

    # -- Report -----------------------------------------------------

    def generate_version_report(self) -> VersionReport:
        total = len(self._items)
        if total == 0:
            return VersionReport(
                recommendations=["No runbook versions registered"],
            )

        runbook_ids: set[str] = set()
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for v in self._items:
            runbook_ids.add(v.runbook_id)
            sk = v.status.value
            by_status[sk] = by_status.get(sk, 0) + 1
            ck = v.category.value
            by_category[ck] = by_category.get(ck, 0) + 1

        rb_count = len(runbook_ids)
        avg_ver = round(total / rb_count, 2) if rb_count else 0.0

        stale = self.detect_stale_runbooks(self._stale_age_days)
        stale_ids = [s["runbook_id"] for s in stale]

        recs: list[str] = []
        if stale:
            recs.append(f"{len(stale)} runbook(s) not updated in >{self._stale_age_days} days")
        draft_count = by_status.get("draft", 0)
        if draft_count > 5:
            recs.append(f"{draft_count} draft version(s) pending review")
        deprecated = by_status.get("deprecated", 0)
        if deprecated > 10:
            recs.append(f"{deprecated} deprecated version(s) — consider archiving")

        report = VersionReport(
            total_runbooks=rb_count,
            total_versions=total,
            avg_versions_per_runbook=avg_ver,
            by_status=by_status,
            by_category=by_category,
            stale_runbooks=stale_ids,
            recommendations=recs,
        )
        logger.info(
            "runbook_versioner.report_generated",
            total_runbooks=rb_count,
            total_versions=total,
        )
        return report

    # -- Housekeeping -----------------------------------------------

    def clear_data(self) -> None:
        self._items.clear()
        self._diffs.clear()
        logger.info("runbook_versioner.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        runbook_ids = {v.runbook_id for v in self._items}
        statuses = {v.status.value for v in self._items}
        categories = {v.category.value for v in self._items}
        return {
            "total_versions": len(self._items),
            "total_diffs": len(self._diffs),
            "unique_runbooks": len(runbook_ids),
            "statuses": sorted(statuses),
            "categories": sorted(categories),
        }
