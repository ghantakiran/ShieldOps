"""Repository layer — bridges Pydantic domain models and SQLAlchemy ORM."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.agents.investigation.models import InvestigationState
from shieldops.agents.remediation.models import RemediationState
from shieldops.db.models import (
    AgentSession,
    AuditLog,
    IncidentOutcomeRecord,
    InvestigationRecord,
    RemediationRecord,
    UserRecord,
)
from shieldops.models.base import AuditEntry

logger = structlog.get_logger()


class Repository:
    """Unified persistence repository for all ShieldOps domain objects."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # ── Users ─────────────────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> dict | None:
        async with self._sf() as session:
            stmt = select(UserRecord).where(UserRecord.email == email)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._user_to_dict(record)

    async def get_user_by_id(self, user_id: str) -> dict | None:
        async with self._sf() as session:
            record = await session.get(UserRecord, user_id)
            if record is None:
                return None
            return self._user_to_dict(record)

    async def create_user(
        self, email: str, name: str, password_hash: str, role: str = "viewer"
    ) -> dict:
        async with self._sf() as session:
            record = UserRecord(
                email=email,
                name=name,
                password_hash=password_hash,
                role=role,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return self._user_to_dict(record)

    @staticmethod
    def _user_to_dict(record: UserRecord) -> dict:
        return {
            "id": record.id,
            "email": record.email,
            "name": record.name,
            "password_hash": record.password_hash,
            "role": record.role,
            "is_active": record.is_active,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    # ── Investigations ──────────────────────────────────────────────

    async def save_investigation(
        self, investigation_id: str, state: InvestigationState
    ) -> None:
        """Upsert an investigation result to the database."""
        async with self._sf() as session:
            record = await session.get(InvestigationRecord, investigation_id)
            if record is None:
                record = InvestigationRecord(id=investigation_id)
                session.add(record)

            record.alert_id = state.alert_id
            record.alert_name = state.alert_context.alert_name
            record.severity = state.alert_context.severity
            record.status = state.current_step
            record.confidence = state.confidence_score
            record.hypotheses = [h.model_dump(mode="json") for h in state.hypotheses]
            record.reasoning_chain = [r.model_dump(mode="json") for r in state.reasoning_chain]
            record.alert_context = state.alert_context.model_dump(mode="json")
            record.log_findings = [f.model_dump(mode="json") for f in state.log_findings]
            record.metric_anomalies = [a.model_dump(mode="json") for a in state.metric_anomalies]
            record.recommended_action = (
                state.recommended_action.model_dump(mode="json")
                if state.recommended_action
                else None
            )
            record.error = state.error
            record.duration_ms = state.investigation_duration_ms

            await session.commit()
            logger.info("investigation_persisted", investigation_id=investigation_id)

    async def get_investigation(self, investigation_id: str) -> dict | None:
        """Load an investigation record as a dict (matching runner.list format)."""
        async with self._sf() as session:
            record = await session.get(InvestigationRecord, investigation_id)
            if record is None:
                return None
            return self._investigation_to_dict(record)

    async def list_investigations(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """List investigation summaries from the database."""
        async with self._sf() as session:
            stmt = select(InvestigationRecord).order_by(
                InvestigationRecord.created_at.desc()
            )
            if status:
                stmt = stmt.where(InvestigationRecord.status == status)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [self._investigation_to_dict(r) for r in result.scalars().all()]

    async def count_investigations(self, status: str | None = None) -> int:
        """Count investigation records."""
        from sqlalchemy import func as sa_func

        async with self._sf() as session:
            stmt = select(sa_func.count(InvestigationRecord.id))
            if status:
                stmt = stmt.where(InvestigationRecord.status == status)
            result = await session.execute(stmt)
            return result.scalar_one()

    @staticmethod
    def _investigation_to_dict(record: InvestigationRecord) -> dict:
        return {
            "investigation_id": record.id,
            "alert_id": record.alert_id,
            "alert_name": record.alert_name,
            "severity": record.severity,
            "status": record.status,
            "confidence": record.confidence,
            "hypotheses_count": len(record.hypotheses) if record.hypotheses else 0,
            "hypotheses": record.hypotheses,
            "reasoning_chain": record.reasoning_chain,
            "alert_context": record.alert_context,
            "log_findings": record.log_findings,
            "metric_anomalies": record.metric_anomalies,
            "recommended_action": record.recommended_action,
            "duration_ms": record.duration_ms,
            "error": record.error,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    # ── Remediations ────────────────────────────────────────────────

    async def save_remediation(
        self, remediation_id: str, state: RemediationState
    ) -> None:
        """Upsert a remediation result to the database."""
        async with self._sf() as session:
            record = await session.get(RemediationRecord, remediation_id)
            if record is None:
                record = RemediationRecord(id=remediation_id)
                session.add(record)

            record.action_type = state.action.action_type
            record.target_resource = state.action.target_resource
            record.environment = state.action.environment.value
            record.risk_level = (state.assessed_risk or state.action.risk_level).value
            record.status = state.current_step
            record.validation_passed = state.validation_passed
            record.reasoning_chain = [r.model_dump(mode="json") for r in state.reasoning_chain]
            record.action_data = state.action.model_dump(mode="json")
            record.execution_result = (
                state.execution_result.model_dump(mode="json")
                if state.execution_result
                else None
            )
            record.snapshot_data = (
                state.snapshot.model_dump(mode="json") if state.snapshot else None
            )
            record.investigation_id = state.investigation_id
            record.error = state.error
            record.duration_ms = state.remediation_duration_ms

            await session.commit()
            logger.info("remediation_persisted", remediation_id=remediation_id)

    async def get_remediation(self, remediation_id: str) -> dict | None:
        """Load a remediation record as a dict."""
        async with self._sf() as session:
            record = await session.get(RemediationRecord, remediation_id)
            if record is None:
                return None
            return self._remediation_to_dict(record)

    async def list_remediations(
        self,
        environment: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List remediation summaries from the database."""
        async with self._sf() as session:
            stmt = select(RemediationRecord).order_by(
                RemediationRecord.created_at.desc()
            )
            if environment:
                stmt = stmt.where(RemediationRecord.environment == environment)
            if status:
                stmt = stmt.where(RemediationRecord.status == status)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [self._remediation_to_dict(r) for r in result.scalars().all()]

    async def count_remediations(
        self, environment: str | None = None, status: str | None = None
    ) -> int:
        from sqlalchemy import func as sa_func

        async with self._sf() as session:
            stmt = select(sa_func.count(RemediationRecord.id))
            if environment:
                stmt = stmt.where(RemediationRecord.environment == environment)
            if status:
                stmt = stmt.where(RemediationRecord.status == status)
            result = await session.execute(stmt)
            return result.scalar_one()

    @staticmethod
    def _remediation_to_dict(record: RemediationRecord) -> dict:
        return {
            "remediation_id": record.id,
            "action_type": record.action_type,
            "target_resource": record.target_resource,
            "environment": record.environment,
            "risk_level": record.risk_level,
            "status": record.status,
            "validation_passed": record.validation_passed,
            "reasoning_chain": record.reasoning_chain,
            "action_data": record.action_data,
            "execution_result": record.execution_result,
            "snapshot_data": record.snapshot_data,
            "investigation_id": record.investigation_id,
            "duration_ms": record.duration_ms,
            "error": record.error,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    # ── Audit Log ───────────────────────────────────────────────────

    async def append_audit_log(self, entry: AuditEntry) -> None:
        """Append an audit entry — INSERT only, never UPDATE."""
        async with self._sf() as session:
            record = AuditLog(
                id=entry.id,
                timestamp=entry.timestamp,
                agent_type=entry.agent_type,
                action=entry.action,
                target_resource=entry.target_resource,
                environment=entry.environment.value,
                risk_level=entry.risk_level.value,
                policy_evaluation=entry.policy_evaluation,
                approval_status=entry.approval_status.value if entry.approval_status else None,
                outcome=entry.outcome.value,
                reasoning=entry.reasoning,
                actor=entry.actor,
            )
            session.add(record)
            await session.commit()
            logger.info("audit_log_appended", audit_id=entry.id, action=entry.action)

    async def list_audit_logs(
        self, environment: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        async with self._sf() as session:
            stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
            if environment:
                stmt = stmt.where(AuditLog.environment == environment)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "agent_type": r.agent_type,
                    "action": r.action,
                    "target_resource": r.target_resource,
                    "environment": r.environment,
                    "risk_level": r.risk_level,
                    "policy_evaluation": r.policy_evaluation,
                    "approval_status": r.approval_status,
                    "outcome": r.outcome,
                    "reasoning": r.reasoning,
                    "actor": r.actor,
                }
                for r in result.scalars().all()
            ]

    # ── Agent Sessions ──────────────────────────────────────────────

    async def save_agent_session(
        self,
        session_id: str,
        agent_type: str,
        event_type: str,
        status: str = "started",
        input_data: dict | None = None,
        result_data: dict | None = None,
        duration_ms: int = 0,
    ) -> None:
        async with self._sf() as session:
            record = await session.get(AgentSession, session_id)
            if record is None:
                record = AgentSession(id=session_id)
                session.add(record)
            record.agent_type = agent_type
            record.event_type = event_type
            record.status = status
            record.input_data = input_data
            record.result_data = result_data
            record.duration_ms = duration_ms
            await session.commit()

    # ── Incident Outcomes (Learning Agent) ────────────────────────

    async def save_incident_outcome(
        self,
        incident_id: str,
        alert_type: str,
        environment: str,
        root_cause: str,
        resolution_action: str,
        investigation_id: str | None = None,
        remediation_id: str | None = None,
        investigation_duration_ms: int = 0,
        remediation_duration_ms: int = 0,
        was_automated: bool = False,
        was_correct: bool = True,
        feedback: str = "",
    ) -> None:
        """Persist an incident outcome for learning analysis."""
        async with self._sf() as session:
            record = await session.get(IncidentOutcomeRecord, incident_id)
            if record is None:
                record = IncidentOutcomeRecord(id=incident_id)
                session.add(record)

            record.alert_type = alert_type
            record.environment = environment
            record.root_cause = root_cause
            record.resolution_action = resolution_action
            record.investigation_id = investigation_id
            record.remediation_id = remediation_id
            record.investigation_duration_ms = investigation_duration_ms
            record.remediation_duration_ms = remediation_duration_ms
            record.was_automated = was_automated
            record.was_correct = was_correct
            record.feedback = feedback

            await session.commit()
            logger.info("incident_outcome_saved", incident_id=incident_id)

    async def query_incident_outcomes(
        self, period: str = "30d", limit: int = 200
    ) -> dict:
        """Query incident outcomes for a given period.

        Returns format compatible with LearningToolkit.get_incident_outcomes().
        """
        from datetime import timedelta

        days = int(period.rstrip("d")) if period.endswith("d") else 30
        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with self._sf() as session:
            stmt = (
                select(IncidentOutcomeRecord)
                .where(IncidentOutcomeRecord.created_at >= cutoff)
                .order_by(IncidentOutcomeRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

        outcomes = [
            {
                "incident_id": r.id,
                "alert_type": r.alert_type,
                "environment": r.environment,
                "root_cause": r.root_cause,
                "resolution_action": r.resolution_action,
                "investigation_id": r.investigation_id,
                "remediation_id": r.remediation_id,
                "investigation_duration_ms": r.investigation_duration_ms,
                "remediation_duration_ms": r.remediation_duration_ms,
                "was_automated": r.was_automated,
                "was_correct": r.was_correct,
                "feedback": r.feedback,
            }
            for r in records
        ]
        return {
            "period": period,
            "total_incidents": len(outcomes),
            "outcomes": outcomes,
        }

    async def save_feedback(
        self, incident_id: str, feedback: str, was_correct: bool | None = None
    ) -> bool:
        """Update feedback on an existing incident outcome.

        Returns True if the record was found and updated.
        """
        async with self._sf() as session:
            record = await session.get(IncidentOutcomeRecord, incident_id)
            if record is None:
                return False
            record.feedback = feedback
            if was_correct is not None:
                record.was_correct = was_correct
            await session.commit()
            logger.info("incident_feedback_saved", incident_id=incident_id)
            return True
