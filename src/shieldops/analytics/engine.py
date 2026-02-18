"""Analytics engine — computes KPIs from investigation and remediation data."""

import contextlib
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.db.models import InvestigationRecord, RemediationRecord

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

    async def mttr_trends(self, period: str = "30d", environment: str | None = None) -> dict:
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

            data_points = [
                {
                    "date": row.day.isoformat() if row.day else None,
                    "avg_duration_ms": round(float(row.avg_ms), 1) if row.avg_ms else 0,
                    "count": row.count,
                }
                for row in rows
            ]

            current_mttr = 0.0
            if data_points:
                total_ms = sum(d["avg_duration_ms"] * d["count"] for d in data_points)
                total_count = sum(d["count"] for d in data_points)
                if total_count > 0:
                    current_mttr = round(total_ms / total_count / 60_000, 2)  # minutes

            return {
                "period": period,
                "data_points": data_points,
                "current_mttr_minutes": current_mttr,
            }

    async def resolution_rate(self, period: str = "30d") -> dict:
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

    async def agent_accuracy(self, period: str = "30d") -> dict:
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

    async def cost_savings(self, period: str = "30d", hourly_rate: float = 75.0) -> dict:
        """Estimate cost savings from automated operations.

        Assumes each auto-resolved remediation saves ~0.5 hours of engineer time.
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
