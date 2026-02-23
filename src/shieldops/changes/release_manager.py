"""Release Management Tracker — release lifecycle, versioning, approval gates, release notes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReleaseStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"


class ReleaseType(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    HOTFIX = "hotfix"


class ApprovalOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


# --- Models ---


class Release(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str
    service: str
    release_type: ReleaseType = ReleaseType.MINOR
    status: ReleaseStatus = ReleaseStatus.DRAFT
    description: str = ""
    author: str = ""
    changes: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    released_at: float | None = None
    rolled_back_at: float | None = None


class ReleaseApproval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    release_id: str
    approver: str
    outcome: ApprovalOutcome = ApprovalOutcome.PENDING
    comment: str = ""
    decided_at: float = Field(default_factory=time.time)


class ReleaseStats(BaseModel):
    total_releases: int = 0
    status_distribution: dict[str, int] = Field(default_factory=dict)
    type_distribution: dict[str, int] = Field(default_factory=dict)
    avg_approval_count: float = 0.0


# --- Engine ---


class ReleaseManagementTracker:
    """Release lifecycle, versioning, approval gates, release notes generation."""

    def __init__(
        self,
        max_releases: int = 10000,
        require_approval: bool = True,
    ) -> None:
        self._max_releases = max_releases
        self._require_approval = require_approval
        self._releases: dict[str, Release] = {}
        self._approvals: list[ReleaseApproval] = []
        logger.info(
            "release_manager.initialized",
            max_releases=max_releases,
            require_approval=require_approval,
        )

    def create_release(
        self,
        version: str,
        service: str,
        release_type: ReleaseType = ReleaseType.MINOR,
        **kw: Any,
    ) -> Release:
        release = Release(
            version=version,
            service=service,
            release_type=release_type,
            **kw,
        )
        self._releases[release.id] = release
        if len(self._releases) > self._max_releases:
            oldest = next(iter(self._releases))
            del self._releases[oldest]
        logger.info(
            "release_manager.release_created",
            release_id=release.id,
            version=version,
            service=service,
        )
        return release

    def get_release(self, release_id: str) -> Release | None:
        return self._releases.get(release_id)

    def list_releases(
        self,
        service: str | None = None,
        status: ReleaseStatus | None = None,
    ) -> list[Release]:
        results = list(self._releases.values())
        if service is not None:
            results = [r for r in results if r.service == service]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results

    def submit_for_approval(self, release_id: str) -> Release | None:
        release = self._releases.get(release_id)
        if release is None:
            return None
        release.status = ReleaseStatus.PENDING_APPROVAL
        logger.info("release_manager.submitted_for_approval", release_id=release_id)
        return release

    def approve_release(
        self,
        release_id: str,
        approver: str,
        comment: str = "",
    ) -> ReleaseApproval | None:
        release = self._releases.get(release_id)
        if release is None:
            return None
        approval = ReleaseApproval(
            release_id=release_id,
            approver=approver,
            outcome=ApprovalOutcome.APPROVED,
            comment=comment,
        )
        self._approvals.append(approval)
        release.approvals.append(approver)
        release.status = ReleaseStatus.APPROVED
        logger.info(
            "release_manager.release_approved",
            release_id=release_id,
            approver=approver,
        )
        return approval

    def reject_release(
        self,
        release_id: str,
        approver: str,
        comment: str = "",
    ) -> ReleaseApproval | None:
        release = self._releases.get(release_id)
        if release is None:
            return None
        approval = ReleaseApproval(
            release_id=release_id,
            approver=approver,
            outcome=ApprovalOutcome.REJECTED,
            comment=comment,
        )
        self._approvals.append(approval)
        release.rejections.append(approver)
        release.status = ReleaseStatus.DRAFT
        logger.info(
            "release_manager.release_rejected",
            release_id=release_id,
            approver=approver,
        )
        return approval

    def mark_released(self, release_id: str) -> Release | None:
        release = self._releases.get(release_id)
        if release is None:
            return None
        if self._require_approval and release.status != ReleaseStatus.APPROVED:
            return None
        release.status = ReleaseStatus.RELEASED
        release.released_at = time.time()
        logger.info("release_manager.release_released", release_id=release_id)
        return release

    def rollback_release(self, release_id: str) -> Release | None:
        release = self._releases.get(release_id)
        if release is None:
            return None
        release.status = ReleaseStatus.ROLLED_BACK
        release.rolled_back_at = time.time()
        logger.info("release_manager.release_rolled_back", release_id=release_id)
        return release

    def generate_release_notes(self, release_id: str) -> dict[str, Any]:
        release = self._releases.get(release_id)
        if release is None:
            return {}
        return {
            "version": release.version,
            "service": release.service,
            "type": release.release_type,
            "description": release.description,
            "changes": release.changes,
            "author": release.author,
            "approvals": release.approvals,
            "status": release.status,
            "released_at": release.released_at,
        }

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for r in self._releases.values():
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            type_counts[r.release_type] = type_counts.get(r.release_type, 0) + 1
        approval_counts = [len(r.approvals) for r in self._releases.values()]
        avg_approvals = (
            round(sum(approval_counts) / len(approval_counts), 1) if approval_counts else 0.0
        )
        return {
            "total_releases": len(self._releases),
            "total_approvals": len(self._approvals),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "avg_approval_count": avg_approvals,
        }
