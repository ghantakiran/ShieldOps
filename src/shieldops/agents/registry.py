"""Agent registry — manages agent registrations, status, and heartbeats."""

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.db.models import AgentRegistration

logger = structlog.get_logger()


class AgentRegistry:
    """Manages agent fleet registration and status."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def register(
        self,
        agent_type: str,
        environment: str = "production",
        config: dict | None = None,
    ) -> dict:
        """Register or update an agent."""
        async with self._sf() as session:
            # Check if already registered for this type+env
            stmt = (
                select(AgentRegistration)
                .where(AgentRegistration.agent_type == agent_type)
                .where(AgentRegistration.environment == environment)
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                record = AgentRegistration(
                    id=f"agt-{uuid4().hex[:12]}",
                    agent_type=agent_type,
                    environment=environment,
                    status="idle",
                    config=config or {},
                    last_heartbeat=datetime.now(timezone.utc),
                )
                session.add(record)
            else:
                record.config = config or record.config
                record.last_heartbeat = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(record)
            logger.info("agent_registered", agent_id=record.id, type=agent_type)
            return self._to_dict(record)

    async def list_agents(
        self,
        environment: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        async with self._sf() as session:
            stmt = select(AgentRegistration).order_by(AgentRegistration.agent_type)
            if environment:
                stmt = stmt.where(AgentRegistration.environment == environment)
            if status:
                stmt = stmt.where(AgentRegistration.status == status)
            result = await session.execute(stmt)
            return [self._to_dict(r) for r in result.scalars().all()]

    async def get_agent(self, agent_id: str) -> dict | None:
        async with self._sf() as session:
            record = await session.get(AgentRegistration, agent_id)
            if record is None:
                return None
            return self._to_dict(record)

    async def enable(self, agent_id: str) -> dict | None:
        async with self._sf() as session:
            record = await session.get(AgentRegistration, agent_id)
            if record is None:
                return None
            record.status = "idle"
            await session.commit()
            await session.refresh(record)
            return self._to_dict(record)

    async def disable(self, agent_id: str) -> dict | None:
        async with self._sf() as session:
            record = await session.get(AgentRegistration, agent_id)
            if record is None:
                return None
            record.status = "disabled"
            await session.commit()
            await session.refresh(record)
            return self._to_dict(record)

    async def heartbeat(self, agent_id: str) -> dict | None:
        async with self._sf() as session:
            record = await session.get(AgentRegistration, agent_id)
            if record is None:
                return None
            record.last_heartbeat = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(record)
            return self._to_dict(record)

    @staticmethod
    def _to_dict(record: AgentRegistration) -> dict:
        return {
            "agent_id": record.id,
            "agent_type": record.agent_type,
            "environment": record.environment,
            "status": record.status,
            "config": record.config,
            "last_heartbeat": (
                record.last_heartbeat.isoformat() if record.last_heartbeat else None
            ),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
