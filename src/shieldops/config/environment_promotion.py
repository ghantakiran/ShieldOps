"""Environment promotion workflow for configs, flags, and playbooks.

Provides diff preview, approval workflow, apply, and rollback for
promoting resources between development → staging → production.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class PromotionEnvironment(enum.StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class PromotableType(enum.StrEnum):
    CONFIG = "config"
    FEATURE_FLAG = "feature_flag"
    PLAYBOOK = "playbook"
    AGENT_QUOTA = "agent_quota"
    ESCALATION_POLICY = "escalation_policy"


class PromotionStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


# ── Models ───────────────────────────────────────────────────────────


class PromotionChange(BaseModel):
    """A single changed field within a resource."""

    field: str
    old_value: Any = None
    new_value: Any = None


class PromotionDiff(BaseModel):
    """Diff for a single resource being promoted."""

    resource_type: PromotableType
    resource_name: str
    source_value: dict[str, Any] = Field(default_factory=dict)
    target_value: dict[str, Any] = Field(default_factory=dict)
    changes: list[PromotionChange] = Field(default_factory=list)
    is_new: bool = False


class PromotionRequest(BaseModel):
    """A request to promote resources between environments."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_env: PromotionEnvironment
    target_env: PromotionEnvironment
    diffs: list[PromotionDiff] = Field(default_factory=list)
    status: PromotionStatus = PromotionStatus.PENDING_REVIEW
    requested_by: str = ""
    reviewed_by: str = ""
    review_comment: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    applied_at: float | None = None
    rolled_back_at: float | None = None


# ── Manager ──────────────────────────────────────────────────────────


class PromotionManager:
    """Manage environment promotions with diff/approve/apply/rollback.

    Parameters
    ----------
    require_approval_for_prod:
        When True, promotions targeting production require explicit approval.
    allowed_source_envs:
        List of environments allowed as promotion sources.
    """

    def __init__(
        self,
        require_approval_for_prod: bool = True,
        allowed_source_envs: list[str] | None = None,
    ) -> None:
        self._require_approval_for_prod = require_approval_for_prod
        self._allowed_source_envs = allowed_source_envs or ["development", "staging"]
        self._requests: dict[str, PromotionRequest] = {}
        # Environment snapshots: env → resource_type → resource_name → data
        self._snapshots: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
            env.value: {} for env in PromotionEnvironment
        }

    # ── Snapshot management ──────────────────────────────────────

    def set_resource(
        self,
        env: str,
        resource_type: str,
        resource_name: str,
        data: dict[str, Any],
    ) -> None:
        """Set a resource value in an environment snapshot."""
        if env not in self._snapshots:
            self._snapshots[env] = {}
        if resource_type not in self._snapshots[env]:
            self._snapshots[env][resource_type] = {}
        self._snapshots[env][resource_type][resource_name] = data

    def get_resource(
        self, env: str, resource_type: str, resource_name: str
    ) -> dict[str, Any] | None:
        return self._snapshots.get(env, {}).get(resource_type, {}).get(resource_name)

    def get_snapshot(self, env: str) -> dict[str, dict[str, dict[str, Any]]]:
        return self._snapshots.get(env, {})

    # ── Diff computation ─────────────────────────────────────────

    def compute_diffs(self, source_env: str, target_env: str) -> list[PromotionDiff]:
        """Compute differences between source and target environments."""
        diffs: list[PromotionDiff] = []
        source = self._snapshots.get(source_env, {})
        target = self._snapshots.get(target_env, {})

        for rtype, resources in source.items():
            target_resources = target.get(rtype, {})
            for rname, sdata in resources.items():
                tdata = target_resources.get(rname, {})
                changes: list[PromotionChange] = []
                is_new = not tdata

                all_keys = set(sdata.keys()) | set(tdata.keys())
                for key in sorted(all_keys):
                    sv = sdata.get(key)
                    tv = tdata.get(key)
                    if sv != tv:
                        changes.append(PromotionChange(field=key, old_value=tv, new_value=sv))

                if changes or is_new:
                    try:
                        pt = PromotableType(rtype)
                    except ValueError:
                        pt = PromotableType.CONFIG
                    diffs.append(
                        PromotionDiff(
                            resource_type=pt,
                            resource_name=rname,
                            source_value=sdata,
                            target_value=tdata,
                            changes=changes,
                            is_new=is_new,
                        )
                    )
        return diffs

    # ── Preview ──────────────────────────────────────────────────

    def preview(self, source_env: str, target_env: str) -> list[PromotionDiff]:
        """Show diffs without creating a promotion request."""
        return self.compute_diffs(source_env, target_env)

    # ── Promotion lifecycle ──────────────────────────────────────

    def create_request(
        self,
        source_env: str,
        target_env: str,
        requested_by: str = "",
        resource_types: list[str] | None = None,
    ) -> PromotionRequest:
        """Create a promotion request with computed diffs."""
        if source_env not in self._allowed_source_envs:
            allowed = self._allowed_source_envs
            raise ValueError(f"Source env '{source_env}' not in allowed: {allowed}")

        diffs = self.compute_diffs(source_env, target_env)
        if resource_types:
            diffs = [d for d in diffs if d.resource_type.value in resource_types]

        request = PromotionRequest(
            source_env=PromotionEnvironment(source_env),
            target_env=PromotionEnvironment(target_env),
            diffs=diffs,
            requested_by=requested_by,
        )

        # Auto-approve if not targeting production
        is_prod = target_env == PromotionEnvironment.PRODUCTION.value
        if not is_prod or not self._require_approval_for_prod:
            request.status = PromotionStatus.APPROVED

        self._requests[request.id] = request
        logger.info(
            "promotion_request_created",
            id=request.id,
            source=source_env,
            target=target_env,
        )
        return request

    def get_request(self, request_id: str) -> PromotionRequest | None:
        return self._requests.get(request_id)

    def list_requests(
        self, status: PromotionStatus | None = None, limit: int = 50
    ) -> list[PromotionRequest]:
        reqs = sorted(self._requests.values(), key=lambda r: r.created_at, reverse=True)
        if status:
            reqs = [r for r in reqs if r.status == status]
        return reqs[:limit]

    def approve(
        self, request_id: str, reviewed_by: str = "", comment: str = ""
    ) -> PromotionRequest | None:
        req = self._requests.get(request_id)
        if req is None or req.status != PromotionStatus.PENDING_REVIEW:
            return None
        req.status = PromotionStatus.APPROVED
        req.reviewed_by = reviewed_by
        req.review_comment = comment
        req.updated_at = time.time()
        return req

    def reject(
        self, request_id: str, reviewed_by: str = "", comment: str = ""
    ) -> PromotionRequest | None:
        req = self._requests.get(request_id)
        if req is None or req.status != PromotionStatus.PENDING_REVIEW:
            return None
        req.status = PromotionStatus.REJECTED
        req.reviewed_by = reviewed_by
        req.review_comment = comment
        req.updated_at = time.time()
        return req

    def apply(self, request_id: str) -> PromotionRequest | None:
        """Apply an approved promotion request to the target environment."""
        req = self._requests.get(request_id)
        if req is None or req.status != PromotionStatus.APPROVED:
            return None

        target = req.target_env.value
        for diff in req.diffs:
            self.set_resource(
                target, diff.resource_type.value, diff.resource_name, diff.source_value
            )

        req.status = PromotionStatus.APPLIED
        req.applied_at = time.time()
        req.updated_at = time.time()
        logger.info("promotion_applied", id=request_id, target=target)
        return req

    def rollback(self, request_id: str) -> PromotionRequest | None:
        """Rollback an applied promotion (restore target_value)."""
        req = self._requests.get(request_id)
        if req is None or req.status != PromotionStatus.APPLIED:
            return None

        target = req.target_env.value
        for diff in req.diffs:
            if diff.is_new:
                # Remove newly added resource
                env_snapshot = self._snapshots.get(target, {})
                rtype_snapshot = env_snapshot.get(diff.resource_type.value, {})
                rtype_snapshot.pop(diff.resource_name, None)
            else:
                self.set_resource(
                    target, diff.resource_type.value, diff.resource_name, diff.target_value
                )

        req.status = PromotionStatus.ROLLED_BACK
        req.rolled_back_at = time.time()
        req.updated_at = time.time()
        logger.info("promotion_rolled_back", id=request_id, target=target)
        return req

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for r in self._requests.values():
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        return {
            "total_requests": len(self._requests),
            "by_status": by_status,
            "environments": list(self._snapshots.keys()),
        }
