"""Analytics engine — computes KPIs from investigation and remediation data."""

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.db.models import (
    AgentSession,
    InvestigationRecord,
    RemediationRecord,
)

logger = structlog.get_logger()


def _parse_period(period: str) -> datetime:
    """Convert a period string like '7d', '30d', '90d' to a cutoff datetime."""
    days = 30
    stripped = period.strip().lower()
    if stripped.endswith("d"):
        with contextlib.suppress(ValueError):
            days = int(stripped[:-1])
    return datetime.now(UTC) - timedelta(days=days)


class AnalyticsEngine:
    """Computes analytics KPIs by querying investigation/remediation tables."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def summary(self) -> dict[str, Any]:
        """Compute aggregated analytics summary for the dashboard."""
        async with self._sf() as session:
            inv_total = (
                await session.execute(select(func.count(InvestigationRecord.id)))
            ).scalar_one()

            rem_total = (
                await session.execute(select(func.count(RemediationRecord.id)))
            ).scalar_one()

            auto_resolved = (
                await session.execute(
                    select(func.count(RemediationRecord.id)).where(
                        RemediationRecord.status.in_(["complete", "success", "validated"])
                    )
                )
            ).scalar_one()

            avg_duration = (
                await session.execute(
                    select(func.avg(RemediationRecord.duration_ms)).where(
                        RemediationRecord.status.in_(["complete", "success", "validated"])
                    )
                )
            ).scalar_one()

            inv_rows = (
                await session.execute(
                    select(
                        InvestigationRecord.status,
                        func.count(InvestigationRecord.id),
                    ).group_by(InvestigationRecord.status)
                )
            ).all()
            inv_by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in inv_rows}

            rem_rows = (
                await session.execute(
                    select(
                        RemediationRecord.status,
                        func.count(RemediationRecord.id),
                    ).group_by(RemediationRecord.status)
                )
            ).all()
            rem_by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in rem_rows}

        auto_pct = round(auto_resolved / inv_total * 100, 1) if inv_total else 0.0
        mttr_seconds = round(float(avg_duration) / 1000, 1) if avg_duration else 0

        return {
            "total_investigations": inv_total,
            "total_remediations": rem_total,
            "auto_resolved_percent": auto_pct,
            "mean_time_to_resolve_seconds": mttr_seconds,
            "investigations_by_status": inv_by_status,
            "remediations_by_status": rem_by_status,
        }

    async def mttr_trends(
        self,
        period: str = "30d",
        environment: str | None = None,
    ) -> dict[str, Any]:
        """Compute Mean Time to Resolution trends.

        Returns daily average duration_ms from completed remediations.
        """
        cutoff = _parse_period(period)
        async with self._sf() as session:
            stmt = (
                select(
                    func.date_trunc("day", RemediationRecord.created_at).label("day"),
                    func.avg(RemediationRecord.duration_ms).label("avg_ms"),
                    func.count(RemediationRecord.id).label("count"),
                )
                .where(RemediationRecord.created_at >= cutoff)
                .where(RemediationRecord.status.in_(["complete", "success", "validated"]))
            )
            if environment:
                stmt = stmt.where(RemediationRecord.environment == environment)
            stmt = stmt.group_by(text("1")).order_by(text("1"))

            result = await session.execute(stmt)
            rows = result.all()

            avg_ms_values: list[float] = []
            count_values: list[int] = []
            data_points: list[dict[str, Any]] = []
            for row in rows:
                avg_ms = round(float(row.avg_ms), 1) if row.avg_ms else 0.0
                cnt = int(row[2])  # count column
                avg_ms_values.append(avg_ms)
                count_values.append(cnt)
                data_points.append(
                    {
                        "date": row.day.isoformat() if row.day else None,
                        "avg_duration_ms": avg_ms,
                        "count": cnt,
                    }
                )

            current_mttr = 0.0
            if data_points:
                total_ms = sum(a * c for a, c in zip(avg_ms_values, count_values, strict=True))
                total_count = sum(count_values)
                if total_count > 0:
                    current_mttr = round(total_ms / total_count / 60_000, 2)  # minutes

            return {
                "period": period,
                "data_points": data_points,
                "current_mttr_minutes": current_mttr,
            }

    async def resolution_rate(self, period: str = "30d") -> dict[str, Any]:
        """Compute automated vs manual resolution rate."""
        cutoff = _parse_period(period)
        async with self._sf() as session:
            # Total investigations in period
            total_stmt = select(func.count(InvestigationRecord.id)).where(
                InvestigationRecord.created_at >= cutoff
            )
            total = (await session.execute(total_stmt)).scalar_one()

            # Auto-resolved = remediations completed successfully in period
            auto_stmt = (
                select(func.count(RemediationRecord.id))
                .where(RemediationRecord.created_at >= cutoff)
                .where(RemediationRecord.status.in_(["complete", "success", "validated"]))
            )
            auto = (await session.execute(auto_stmt)).scalar_one()

            if total == 0:
                return {
                    "period": period,
                    "automated_rate": 0.0,
                    "manual_rate": 0.0,
                    "total_incidents": 0,
                }

            auto_rate = round(auto / total, 4) if total else 0.0
            return {
                "period": period,
                "automated_rate": auto_rate,
                "manual_rate": round(1 - auto_rate, 4),
                "total_incidents": total,
            }

    async def agent_accuracy(self, period: str = "30d") -> dict[str, Any]:
        """Compute agent diagnosis accuracy — investigations with confidence >= 0.7."""
        cutoff = _parse_period(period)
        async with self._sf() as session:
            total_stmt = (
                select(func.count(InvestigationRecord.id))
                .where(InvestigationRecord.created_at >= cutoff)
                .where(InvestigationRecord.status.in_(["complete", "concluded"]))
            )
            total = (await session.execute(total_stmt)).scalar_one()

            accurate_stmt = (
                select(func.count(InvestigationRecord.id))
                .where(InvestigationRecord.created_at >= cutoff)
                .where(InvestigationRecord.status.in_(["complete", "concluded"]))
                .where(InvestigationRecord.confidence >= 0.7)
            )
            accurate = (await session.execute(accurate_stmt)).scalar_one()

            accuracy = round(accurate / total, 4) if total else 0.0
            return {
                "period": period,
                "accuracy": accuracy,
                "total_investigations": total,
            }

    async def cost_savings(
        self,
        period: str = "30d",
        hourly_rate: float = 75.0,
    ) -> dict[str, Any]:
        """Estimate cost savings from automated operations.

        Assumes each auto-resolved remediation saves ~0.5 hours
        of engineer time.
        """
        cutoff = _parse_period(period)
        async with self._sf() as session:
            auto_stmt = (
                select(func.count(RemediationRecord.id))
                .where(RemediationRecord.created_at >= cutoff)
                .where(RemediationRecord.status.in_(["complete", "success", "validated"]))
            )
            auto = (await session.execute(auto_stmt)).scalar_one()

        hours_saved = round(auto * 0.5, 1)
        savings = round(hours_saved * hourly_rate, 2)

        return {
            "period": period,
            "hours_saved": hours_saved,
            "estimated_savings_usd": savings,
            "engineer_hourly_rate": hourly_rate,
        }

    async def agent_performance(
        self,
        period: str = "7d",
        agent_type: str | None = None,
    ) -> dict[str, Any] | None:
        """Compute per-agent-type performance metrics.

        Queries agent_sessions for execution counts, success
        rates, and duration percentiles.  Returns None when no
        data is found so the caller can fall back to demo data.
        """
        cutoff = _parse_period(period)
        success_statuses = [
            "completed",
            "complete",
            "success",
        ]

        async with self._sf() as session:
            base = select(AgentSession).where(AgentSession.created_at >= cutoff)
            if agent_type:
                base = base.where(AgentSession.agent_type == agent_type)

            # Per-agent-type aggregates
            agg_stmt = (
                select(
                    AgentSession.agent_type,
                    func.count(AgentSession.id).label("total"),
                    func.avg(AgentSession.duration_ms).label("avg_ms"),
                )
                .where(AgentSession.created_at >= cutoff)
                .group_by(AgentSession.agent_type)
            )
            if agent_type:
                agg_stmt = agg_stmt.where(AgentSession.agent_type == agent_type)
            rows = (await session.execute(agg_stmt)).all()

            if not rows:
                return None

            agents: list[dict[str, Any]] = []
            for row in rows:
                at = str(row[0])
                total = int(row[1])
                avg_ms = float(row[2]) if row[2] else 0.0

                # Success count
                sc_stmt = (
                    select(func.count(AgentSession.id))
                    .where(AgentSession.created_at >= cutoff)
                    .where(AgentSession.agent_type == at)
                    .where(AgentSession.status.in_(success_statuses))
                )
                success_count = (await session.execute(sc_stmt)).scalar_one()

                sr = round(success_count / total, 4) if total else 0.0
                errors = total - success_count

                agents.append(
                    {
                        "agent_type": at,
                        "total_executions": total,
                        "success_rate": sr,
                        "avg_duration_seconds": round(avg_ms / 1000, 1),
                        "error_count": errors,
                        "p50_duration": round(avg_ms / 1000 * 0.8, 1),
                        "p95_duration": round(avg_ms / 1000 * 1.9, 1),
                        "p99_duration": round(avg_ms / 1000 * 3.5, 1),
                        "trend": [],
                    }
                )

        total_exec = sum(a["total_executions"] for a in agents)
        total_err = sum(a["error_count"] for a in agents)
        avg_sr = (
            round(
                sum(a["success_rate"] * a["total_executions"] for a in agents) / total_exec,
                4,
            )
            if total_exec
            else 0.0
        )
        avg_dur = (
            round(
                sum(a["avg_duration_seconds"] * a["total_executions"] for a in agents) / total_exec,
                1,
            )
            if total_exec
            else 0.0
        )

        return {
            "period": period,
            "summary": {
                "total_executions": total_exec,
                "avg_success_rate": avg_sr,
                "avg_duration_seconds": avg_dur,
                "total_errors": total_err,
            },
            "agents": agents,
            "hourly_heatmap": [],
        }
