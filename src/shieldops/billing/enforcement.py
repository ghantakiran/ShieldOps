"""Plan enforcement service -- checks agent and API quota limits per org.

Reads plan definitions from ``stripe_billing.PLANS`` and org plan
from the database (with a short TTL cache to avoid per-request DB hits).
"""

from __future__ import annotations

import threading
import time
from typing import Any

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.api.middleware.usage_tracker import UsageTracker
from shieldops.db.models import AgentRegistration, OrganizationRecord
from shieldops.integrations.billing.stripe_billing import PLANS

logger = structlog.get_logger()

# Default plan for orgs not found in the DB
_DEFAULT_PLAN = "free"

# Cache TTL in seconds -- avoids DB lookups on every request
_PLAN_CACHE_TTL_SECONDS = 60


class PlanEnforcementService:
    """Checks whether an organisation is within its plan limits.

    The service is designed to be instantiated once at startup and
    shared across middleware and route handlers.  Plan lookups are
    cached in-memory with a short TTL so enforcement adds negligible
    latency to the request path.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._sf = session_factory
        # {org_id: (plan_key, fetched_at_monotonic)}
        self._plan_cache: dict[str, tuple[str, float]] = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Plan resolution
    # ------------------------------------------------------------------

    async def get_org_plan(self, org_id: str) -> str:
        """Return the plan key for *org_id*, using a short TTL cache.

        Falls back to ``"free"`` when the org is not found or the
        database is unavailable.
        """
        cached = self._read_cache(org_id)
        if cached is not None:
            return cached

        plan = await self._fetch_plan_from_db(org_id)
        self._write_cache(org_id, plan)
        return plan

    # ------------------------------------------------------------------
    # Limit checks
    # ------------------------------------------------------------------

    async def check_agent_limit(
        self,
        org_id: str,
        plan: str | None = None,
    ) -> tuple[bool, int, int]:
        """Check whether *org_id* can create another agent.

        Returns:
            ``(allowed, current_count, limit)`` where *limit* is
            ``-1`` for unlimited (enterprise).
        """
        if plan is None:
            plan = await self.get_org_plan(org_id)

        plan_def = PLANS.get(plan, PLANS[_DEFAULT_PLAN])
        limit: int = plan_def["agent_limit"]

        current = await self._count_agents(org_id)

        if limit == -1:
            return (True, current, limit)

        allowed = current < limit
        return (allowed, current, limit)

    async def check_api_quota(
        self,
        org_id: str,
        plan: str | None = None,
    ) -> tuple[bool, int, int]:
        """Check whether *org_id* is within its monthly API call quota.

        Uses the in-memory :class:`UsageTracker` to count calls
        within the current billing period (approximated as 30 days /
        720 hours).

        Returns:
            ``(allowed, used, limit)`` where *limit* is ``-1`` for
            unlimited.
        """
        if plan is None:
            plan = await self.get_org_plan(org_id)

        plan_def = PLANS.get(plan, PLANS[_DEFAULT_PLAN])
        limit: int = plan_def["api_calls_limit"]

        tracker = UsageTracker.get_instance()
        usage = tracker.get_usage(org_id=org_id, hours=720)  # ~30 days
        used: int = usage["total_calls"]

        if limit == -1:
            return (True, used, limit)

        allowed = used < limit
        return (allowed, used, limit)

    async def get_usage_summary(
        self,
        org_id: str,
    ) -> dict[str, Any]:
        """Return a full usage-vs-limits summary for the org.

        This powers the ``GET /api/v1/billing/usage`` endpoint.
        """
        plan = await self.get_org_plan(org_id)
        plan_def = PLANS.get(plan, PLANS[_DEFAULT_PLAN])

        agent_allowed, agent_count, agent_limit = await self.check_agent_limit(org_id, plan=plan)
        api_allowed, api_used, api_limit = await self.check_api_quota(org_id, plan=plan)

        # Determine next plan upgrade, if any
        plan_order = ["free", "pro", "enterprise"]
        try:
            idx = plan_order.index(plan)
            upgrade_available = plan_order[idx + 1] if idx + 1 < len(plan_order) else None
        except ValueError:
            upgrade_available = None

        return {
            "plan": plan,
            "plan_name": plan_def.get("name", plan),
            "agent_count": agent_count,
            "agent_limit": agent_limit,
            "agent_limit_reached": not agent_allowed,
            "api_calls_used": api_used,
            "api_calls_limit": api_limit,
            "api_quota_exceeded": not api_allowed,
            "upgrade_available": upgrade_available,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_cache(self, org_id: str) -> str | None:
        with self._cache_lock:
            entry = self._plan_cache.get(org_id)
            if entry is None:
                return None
            plan, fetched_at = entry
            if (time.monotonic() - fetched_at) > _PLAN_CACHE_TTL_SECONDS:
                del self._plan_cache[org_id]
                return None
            return plan

    def _write_cache(self, org_id: str, plan: str) -> None:
        with self._cache_lock:
            self._plan_cache[org_id] = (plan, time.monotonic())

    def invalidate_cache(self, org_id: str | None = None) -> None:
        """Evict cached plan data.  Pass *org_id* to evict a single
        entry, or ``None`` to flush the entire cache.
        """
        with self._cache_lock:
            if org_id is None:
                self._plan_cache.clear()
            else:
                self._plan_cache.pop(org_id, None)

    async def _fetch_plan_from_db(self, org_id: str) -> str:
        """Look up the org's plan in the database."""
        if self._sf is None:
            return _DEFAULT_PLAN
        try:
            async with self._sf() as session:
                record = await session.get(OrganizationRecord, org_id)
                if record is None:
                    logger.debug(
                        "org_not_found_for_billing",
                        org_id=org_id,
                    )
                    return _DEFAULT_PLAN
                return record.plan or _DEFAULT_PLAN
        except Exception:
            logger.warning(
                "billing_plan_db_lookup_failed",
                org_id=org_id,
                exc_info=True,
            )
            return _DEFAULT_PLAN

    async def _count_agents(self, org_id: str) -> int:
        """Count active agent registrations for *org_id*.

        Note: The current ``AgentRegistration`` model does not have an
        ``organization_id`` column.  Until multi-tenant agent isolation
        is added, we count *all* non-disabled registrations as a
        platform-wide proxy.  This is a known simplification that
        should be revisited when per-org agent scoping ships.
        """
        if self._sf is None:
            return 0
        try:
            async with self._sf() as session:
                stmt = select(sa_func.count(AgentRegistration.id)).where(
                    AgentRegistration.status != "disabled",
                )
                result = await session.execute(stmt)
                return result.scalar_one()
        except Exception:
            logger.warning(
                "billing_agent_count_failed",
                org_id=org_id,
                exc_info=True,
            )
            return 0
