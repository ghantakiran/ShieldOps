"""Repository layer — bridges Pydantic domain models and SQLAlchemy ORM."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from shieldops.agents.security.models import SecurityScanState

from shieldops.agents.investigation.models import InvestigationState
from shieldops.agents.remediation.models import RemediationState
from shieldops.db.models import (
    AgentContextRecord,
    AgentSession,
    APIKeyRecord,
    AuditLog,
    IncidentOutcomeRecord,
    InvestigationRecord,
    LearningCycleRecord,
    NotificationPreferenceRecord,
    OnboardingProgressRecord,
    OrganizationRecord,
    PlaybookRecord,
    RemediationRecord,
    RiskAcceptanceRecord,
    SecurityScanRecord,
    TeamMemberRecord,
    TeamRecord,
    UserRecord,
    VulnerabilityCommentRecord,
    VulnerabilityRecord,
)
from shieldops.models.base import AuditEntry

logger = structlog.get_logger()


class Repository:
    """Unified persistence repository for all ShieldOps domain objects."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # ── Users ─────────────────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        async with self._sf() as session:
            stmt = select(UserRecord).where(UserRecord.email == email)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._user_to_dict(record)

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        async with self._sf() as session:
            record = await session.get(UserRecord, user_id)
            if record is None:
                return None
            return self._user_to_dict(record)

    async def create_user(
        self, email: str, name: str, password_hash: str, role: str = "viewer"
    ) -> dict[str, Any]:
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

    async def list_users(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List users ordered by creation date."""
        async with self._sf() as session:
            stmt = (
                select(UserRecord)
                .order_by(UserRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._user_to_dict(r) for r in result.scalars().all()]

    async def update_user_role(self, user_id: str, role: str) -> dict[str, Any] | None:
        """Update a user's role. Returns updated user or None."""
        async with self._sf() as session:
            record = await session.get(UserRecord, user_id)
            if record is None:
                return None
            record.role = role
            await session.commit()
            await session.refresh(record)
            return self._user_to_dict(record)

    async def update_user_active(self, user_id: str, is_active: bool) -> dict[str, Any] | None:
        """Toggle a user's active status. Returns updated user or None."""
        async with self._sf() as session:
            record = await session.get(UserRecord, user_id)
            if record is None:
                return None
            record.is_active = is_active
            await session.commit()
            await session.refresh(record)
            return self._user_to_dict(record)

    @staticmethod
    def _user_to_dict(record: UserRecord) -> dict[str, Any]:
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

    async def save_investigation(self, investigation_id: str, state: InvestigationState) -> None:
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

    async def get_investigation(self, investigation_id: str) -> dict[str, Any] | None:
        """Load an investigation record as a dict (matching runner.list format)."""
        async with self._sf() as session:
            record = await session.get(InvestigationRecord, investigation_id)
            if record is None:
                return None
            return self._investigation_to_dict(record)

    async def list_investigations(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List investigation summaries from the database."""
        async with self._sf() as session:
            stmt = select(InvestigationRecord).order_by(InvestigationRecord.created_at.desc())
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
    def _investigation_to_dict(record: InvestigationRecord) -> dict[str, Any]:
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

    async def save_remediation(self, remediation_id: str, state: RemediationState) -> None:
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
                state.execution_result.model_dump(mode="json") if state.execution_result else None
            )
            record.snapshot_data = (
                state.snapshot.model_dump(mode="json") if state.snapshot else None
            )
            record.investigation_id = state.investigation_id
            record.error = state.error
            record.duration_ms = state.remediation_duration_ms

            await session.commit()
            logger.info("remediation_persisted", remediation_id=remediation_id)

    async def get_remediation(self, remediation_id: str) -> dict[str, Any] | None:
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
    ) -> list[dict[str, Any]]:
        """List remediation summaries from the database."""
        async with self._sf() as session:
            stmt = select(RemediationRecord).order_by(RemediationRecord.created_at.desc())
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
    def _remediation_to_dict(record: RemediationRecord) -> dict[str, Any]:
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

    # ── Security Scans ─────────────────────────────────────────────

    async def save_security_scan(self, scan_id: str, state: SecurityScanState) -> None:
        """Upsert a security scan result to the database."""
        async with self._sf() as session:
            record = await session.get(SecurityScanRecord, scan_id)
            if record is None:
                record = SecurityScanRecord(id=scan_id)
                session.add(record)

            record.scan_type = state.scan_type
            record.environment = state.target_environment.value
            record.status = state.current_step
            record.cve_findings = [f.model_dump(mode="json") for f in state.cve_findings]
            record.critical_cve_count = state.critical_cve_count
            record.credential_statuses = [
                c.model_dump(mode="json") for c in state.credential_statuses
            ]
            record.compliance_controls = [
                c.model_dump(mode="json") for c in state.compliance_controls
            ]
            record.compliance_score = state.compliance_score
            record.patch_results = [p.model_dump(mode="json") for p in state.patch_results]
            record.rotation_results = [r.model_dump(mode="json") for r in state.rotation_results]
            record.patches_applied = state.patches_applied
            record.credentials_rotated = state.credentials_rotated
            record.posture_data = state.posture.model_dump(mode="json") if state.posture else None
            record.reasoning_chain = [r.model_dump(mode="json") for r in state.reasoning_chain]
            record.error = state.error
            record.duration_ms = state.scan_duration_ms

            await session.commit()
            logger.info("security_scan_persisted", scan_id=scan_id)

    async def get_security_scan(self, scan_id: str) -> dict[str, Any] | None:
        """Load a security scan record as a dict."""
        async with self._sf() as session:
            record = await session.get(SecurityScanRecord, scan_id)
            if record is None:
                return None
            return self._security_scan_to_dict(record)

    async def list_security_scans(
        self,
        environment: str | None = None,
        scan_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List security scan summaries from the database."""
        async with self._sf() as session:
            stmt = select(SecurityScanRecord).order_by(SecurityScanRecord.created_at.desc())
            if environment:
                stmt = stmt.where(SecurityScanRecord.environment == environment)
            if scan_type:
                stmt = stmt.where(SecurityScanRecord.scan_type == scan_type)
            if status:
                stmt = stmt.where(SecurityScanRecord.status == status)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [self._security_scan_to_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _security_scan_to_dict(record: SecurityScanRecord) -> dict[str, Any]:
        return {
            "scan_id": record.id,
            "scan_type": record.scan_type,
            "environment": record.environment,
            "status": record.status,
            "cve_findings": record.cve_findings,
            "critical_cve_count": record.critical_cve_count,
            "credential_statuses": record.credential_statuses,
            "compliance_controls": record.compliance_controls,
            "compliance_score": record.compliance_score,
            "patch_results": record.patch_results,
            "rotation_results": record.rotation_results,
            "patches_applied": record.patches_applied,
            "credentials_rotated": record.credentials_rotated,
            "posture_data": record.posture_data,
            "reasoning_chain": record.reasoning_chain,
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
    ) -> list[dict[str, Any]]:
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

    # ── Investigation Timeline ──────────────────────────────────

    async def get_investigation_timeline(
        self,
        investigation_id: str,
    ) -> list[dict[str, Any]]:
        """Get merged timeline events for an investigation.

        Queries investigations, remediations, and audit_log
        tables, merges results sorted by timestamp (ascending).
        """
        events: list[dict[str, Any]] = []

        async with self._sf() as session:
            # 1. Investigation record itself
            inv = await session.get(
                InvestigationRecord,
                investigation_id,
            )
            if inv is not None:
                events.append(
                    {
                        "id": f"inv-{inv.id}",
                        "timestamp": (inv.created_at.isoformat() if inv.created_at else None),
                        "type": "investigation",
                        "action": f"investigation_{inv.status or 'started'}",
                        "actor": "agent:investigation",
                        "severity": inv.severity,
                        "details": {
                            "alert_id": inv.alert_id,
                            "alert_name": inv.alert_name,
                            "confidence": inv.confidence,
                            "duration_ms": inv.duration_ms,
                            "error": inv.error,
                        },
                    }
                )
                if inv.updated_at and inv.created_at and inv.updated_at != inv.created_at:
                    events.append(
                        {
                            "id": f"inv-{inv.id}-updated",
                            "timestamp": (inv.updated_at.isoformat()),
                            "type": "investigation",
                            "action": f"investigation_{inv.status or 'updated'}",
                            "actor": "agent:investigation",
                            "severity": inv.severity,
                            "details": {
                                "alert_id": inv.alert_id,
                                "confidence": inv.confidence,
                            },
                        }
                    )

            # 2. Related remediations
            rem_stmt = (
                select(RemediationRecord)
                .where(
                    RemediationRecord.investigation_id == investigation_id,
                )
                .order_by(
                    RemediationRecord.created_at.asc(),
                )
            )
            rem_result = await session.execute(rem_stmt)
            for rem in rem_result.scalars().all():
                events.append(
                    {
                        "id": f"rem-{rem.id}",
                        "timestamp": (rem.created_at.isoformat() if rem.created_at else None),
                        "type": "remediation",
                        "action": (f"{rem.action_type}_{rem.status}"),
                        "actor": "agent:remediation",
                        "severity": rem.risk_level,
                        "details": {
                            "remediation_id": rem.id,
                            "action_type": rem.action_type,
                            "target_resource": (rem.target_resource),
                            "environment": rem.environment,
                            "validation_passed": (rem.validation_passed),
                            "duration_ms": rem.duration_ms,
                            "error": rem.error,
                        },
                    }
                )

            # 3. Audit log entries referencing this ID
            audit_stmt = (
                select(AuditLog)
                .where(
                    AuditLog.reasoning.ilike(
                        f"%{investigation_id}%",
                    ),
                )
                .order_by(AuditLog.timestamp.asc())
            )
            audit_result = await session.execute(
                audit_stmt,
            )
            for aud in audit_result.scalars().all():
                events.append(
                    {
                        "id": f"aud-{aud.id}",
                        "timestamp": (aud.timestamp.isoformat() if aud.timestamp else None),
                        "type": "audit",
                        "action": aud.action,
                        "actor": aud.actor,
                        "severity": aud.risk_level,
                        "details": {
                            "audit_id": aud.id,
                            "agent_type": aud.agent_type,
                            "target_resource": (aud.target_resource),
                            "environment": aud.environment,
                            "policy_evaluation": (aud.policy_evaluation),
                            "approval_status": (aud.approval_status),
                            "outcome": aud.outcome,
                            "reasoning": aud.reasoning,
                        },
                    }
                )

        # Sort all events chronologically
        events.sort(
            key=lambda e: e.get("timestamp") or "",
        )
        return events

    # ── Snapshot Retrieval (for durable connector rollback) ──────

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """Retrieve snapshot data from RemediationRecord by snapshot_id.

        Connectors store snapshots in-memory, but on restart they can
        fall back to this DB lookup via the ``snapshot_data`` JSONB column.
        """
        async with self._sf() as session:
            stmt = select(RemediationRecord).where(
                RemediationRecord.snapshot_data["id"].as_string() == snapshot_id
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record and record.snapshot_data:
                return record.snapshot_data
            return None

    # ── Agent Sessions ──────────────────────────────────────────────

    async def save_agent_session(
        self,
        session_id: str,
        agent_type: str,
        event_type: str,
        status: str = "started",
        input_data: dict[str, Any] | None = None,
        result_data: dict[str, Any] | None = None,
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

    async def get_similar_incidents(
        self,
        alert_type: str,
        resource_id: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find past incidents with matching alert_type for pattern matching.

        Returns incidents ordered by most recent, with a simple text-based
        similarity score (exact alert_type match = 0.8, same resource = 0.9).
        """
        async with self._sf() as session:
            stmt = (
                select(IncidentOutcomeRecord)
                .where(IncidentOutcomeRecord.alert_type == alert_type)
                .order_by(IncidentOutcomeRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

        patterns: list[dict[str, Any]] = []
        for r in records:
            score = 0.8
            if resource_id and resource_id in (r.root_cause or ""):
                score = 0.9
            patterns.append(
                {
                    "incident_id": r.id,
                    "alert_type": r.alert_type,
                    "root_cause": r.root_cause,
                    "resolution_action": r.resolution_action,
                    "similarity_score": score,
                    "was_correct": r.was_correct,
                    "environment": r.environment,
                }
            )
        return patterns

    async def query_incident_outcomes(
        self,
        period: str = "30d",
        limit: int = 200,
    ) -> dict[str, Any]:
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

    # ── Alert Thresholds (Learning Agent) ─────────────────────────

    async def query_alert_thresholds(self) -> dict[str, Any]:
        """Query alert threshold config for learning agent analysis.

        If a team_notification_configs table exists, reads from it;
        otherwise returns an empty list so the learning agent falls
        back to its built-in stub data.
        """
        try:
            from shieldops.db.models import TeamNotificationConfigRecord

            async with self._sf() as session:
                stmt = select(TeamNotificationConfigRecord)
                result = await session.execute(stmt)
                records = result.scalars().all()
                thresholds = [
                    {
                        "metric_name": r.metric_name,
                        "threshold": r.threshold,
                        "duration": r.duration,
                        "severity": r.severity,
                    }
                    for r in records
                    if hasattr(r, "metric_name")
                ]
                return {"thresholds": thresholds, "total": len(thresholds)}
        except Exception:
            # Table may not exist yet — graceful fallback
            return {"thresholds": [], "total": 0}

    # ── Learning Cycles ────────────────────────────────────────────

    async def save_learning_cycle(self, state: Any) -> str:
        """Persist a completed learning cycle from LearningState."""
        record = LearningCycleRecord(
            id=state.learning_id,
            learning_type=state.learning_type,
            target_period=state.target_period,
            status=state.current_step or "completed",
            total_incidents_analyzed=state.total_incidents_analyzed,
            recurring_pattern_count=state.recurring_pattern_count,
            improvement_score=state.improvement_score,
            automation_accuracy=state.automation_accuracy,
            pattern_insights=[
                p.model_dump() if hasattr(p, "model_dump") else p for p in state.pattern_insights
            ],
            playbook_updates=[
                u.model_dump() if hasattr(u, "model_dump") else u for u in state.playbook_updates
            ],
            threshold_adjustments=[
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in state.threshold_adjustments
            ],
            reasoning_chain=[
                r.model_dump() if hasattr(r, "model_dump") else r for r in state.reasoning_chain
            ],
            error=state.error,
            duration_ms=state.learning_duration_ms or 0,
        )
        async with self._sf() as session:
            session.add(record)
            await session.commit()
        learning_id: str = state.learning_id
        logger.info("learning_cycle_saved", learning_id=learning_id)
        return learning_id

    async def query_learning_cycles(
        self, limit: int = 20, learning_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Query recent learning cycles."""
        async with self._sf() as session:
            stmt = select(LearningCycleRecord).order_by(LearningCycleRecord.created_at.desc())
            if learning_type:
                stmt = stmt.where(LearningCycleRecord.learning_type == learning_type)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "learning_type": r.learning_type,
                    "target_period": r.target_period,
                    "status": r.status,
                    "total_incidents_analyzed": r.total_incidents_analyzed,
                    "improvement_score": r.improvement_score,
                    "duration_ms": r.duration_ms,
                    "created_at": (r.created_at.isoformat() if r.created_at else None),
                }
                for r in records
            ]

    # ── Vulnerabilities ───────────────────────────────────────────

    async def save_vulnerability(self, vuln_data: dict[str, Any]) -> str:
        """Save or deduplicate a vulnerability.

        Dedup key: (cve_id + affected_resource + package_name).
        If a matching record exists, update last_seen_at instead of creating a new one.
        """
        async with self._sf() as session:
            # Check for existing vulnerability (deduplication)
            dedup_key_cve = vuln_data.get("cve_id")
            dedup_key_resource = vuln_data.get("affected_resource", "")
            dedup_key_pkg = vuln_data.get("package_name", "")

            if dedup_key_cve and dedup_key_resource:
                stmt = select(VulnerabilityRecord).where(
                    VulnerabilityRecord.cve_id == dedup_key_cve,
                    VulnerabilityRecord.affected_resource == dedup_key_resource,
                    VulnerabilityRecord.package_name == dedup_key_pkg,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.last_seen_at = datetime.now(UTC)
                    existing.scan_id = vuln_data.get("scan_id", existing.scan_id)
                    if vuln_data.get("severity"):
                        existing.severity = vuln_data["severity"]
                    if vuln_data.get("cvss_score"):
                        existing.cvss_score = vuln_data["cvss_score"]
                    await session.commit()
                    logger.info("vulnerability_deduped", vuln_id=existing.id)
                    return existing.id

            from uuid import uuid4

            vuln_id = vuln_data.get("id", f"vuln-{uuid4().hex[:12]}")
            record = VulnerabilityRecord(
                id=vuln_id,
                cve_id=vuln_data.get("cve_id"),
                scan_id=vuln_data.get("scan_id"),
                source=vuln_data.get("source", "unknown"),
                scanner_type=vuln_data.get("scanner_type", "cve"),
                severity=vuln_data.get("severity", "medium"),
                cvss_score=vuln_data.get("cvss_score", 0.0),
                title=vuln_data.get("title", ""),
                description=vuln_data.get("description", ""),
                package_name=vuln_data.get("package_name", ""),
                affected_resource=vuln_data.get("affected_resource", "unknown"),
                status="new",
                sla_due_at=vuln_data.get("sla_due_at"),
                remediation_steps=vuln_data.get("remediation_steps", []),
                scan_metadata=vuln_data.get("scan_metadata", {}),
            )
            session.add(record)
            await session.commit()
            logger.info("vulnerability_saved", vuln_id=vuln_id)
            return vuln_id

    async def get_vulnerability(self, vuln_id: str) -> dict[str, Any] | None:
        async with self._sf() as session:
            record = await session.get(VulnerabilityRecord, vuln_id)
            if record is None:
                return None
            return self._vulnerability_to_dict(record)

    async def list_vulnerabilities(
        self,
        status: str | None = None,
        severity: str | None = None,
        scanner_type: str | None = None,
        team_id: str | None = None,
        sla_breached: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with self._sf() as session:
            stmt = select(VulnerabilityRecord).order_by(VulnerabilityRecord.created_at.desc())
            if status:
                stmt = stmt.where(VulnerabilityRecord.status == status)
            if severity:
                stmt = stmt.where(VulnerabilityRecord.severity == severity)
            if scanner_type:
                stmt = stmt.where(VulnerabilityRecord.scanner_type == scanner_type)
            if team_id:
                stmt = stmt.where(VulnerabilityRecord.assigned_team_id == team_id)
            if sla_breached is not None:
                stmt = stmt.where(VulnerabilityRecord.sla_breached == sla_breached)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [self._vulnerability_to_dict(r) for r in result.scalars().all()]

    async def count_vulnerabilities(
        self,
        status: str | None = None,
        severity: str | None = None,
        sla_breached: bool | None = None,
    ) -> int:
        from sqlalchemy import func as sa_func

        async with self._sf() as session:
            stmt = select(sa_func.count(VulnerabilityRecord.id))
            if status:
                stmt = stmt.where(VulnerabilityRecord.status == status)
            if severity:
                stmt = stmt.where(VulnerabilityRecord.severity == severity)
            if sla_breached is not None:
                stmt = stmt.where(VulnerabilityRecord.sla_breached == sla_breached)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def update_vulnerability_status(self, vuln_id: str, status: str, **fields: Any) -> bool:
        async with self._sf() as session:
            record = await session.get(VulnerabilityRecord, vuln_id)
            if record is None:
                return False
            record.status = status
            if status == "remediated":
                record.remediated_at = datetime.now(UTC)
            if status == "closed":
                record.closed_at = datetime.now(UTC)
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            await session.commit()
            return True

    async def assign_vulnerability(
        self, vuln_id: str, team_id: str | None = None, user_id: str | None = None
    ) -> bool:
        async with self._sf() as session:
            record = await session.get(VulnerabilityRecord, vuln_id)
            if record is None:
                return False
            if team_id is not None:
                record.assigned_team_id = team_id
            if user_id is not None:
                record.assigned_user_id = user_id
            await session.commit()
            return True

    async def get_vulnerability_stats(self) -> dict[str, Any]:
        from sqlalchemy import func as sa_func

        async with self._sf() as session:
            # By severity
            sev_stmt = select(
                VulnerabilityRecord.severity,
                sa_func.count(VulnerabilityRecord.id),
            ).group_by(VulnerabilityRecord.severity)
            sev_result = await session.execute(sev_stmt)
            by_severity = {row[0]: row[1] for row in sev_result.all()}

            # By status
            status_stmt = select(
                VulnerabilityRecord.status,
                sa_func.count(VulnerabilityRecord.id),
            ).group_by(VulnerabilityRecord.status)
            status_result = await session.execute(status_stmt)
            by_status = {row[0]: row[1] for row in status_result.all()}

            # SLA breaches
            sla_stmt = select(sa_func.count(VulnerabilityRecord.id)).where(
                VulnerabilityRecord.sla_breached == True  # noqa: E712
            )
            sla_result = await session.execute(sla_stmt)
            sla_breaches = sla_result.scalar_one()

            # Total
            total_stmt = select(sa_func.count(VulnerabilityRecord.id))
            total_result = await session.execute(total_stmt)
            total = total_result.scalar_one()

            return {
                "total": total,
                "by_severity": by_severity,
                "by_status": by_status,
                "sla_breaches": sla_breaches,
            }

    @staticmethod
    def _vulnerability_to_dict(record: VulnerabilityRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "cve_id": record.cve_id,
            "scan_id": record.scan_id,
            "source": record.source,
            "scanner_type": record.scanner_type,
            "severity": record.severity,
            "cvss_score": record.cvss_score,
            "title": record.title,
            "description": record.description,
            "package_name": record.package_name,
            "affected_resource": record.affected_resource,
            "status": record.status,
            "assigned_team_id": record.assigned_team_id,
            "assigned_user_id": record.assigned_user_id,
            "sla_due_at": record.sla_due_at.isoformat() if record.sla_due_at else None,
            "sla_breached": record.sla_breached,
            "first_seen_at": record.first_seen_at.isoformat() if record.first_seen_at else None,
            "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
            "remediated_at": record.remediated_at.isoformat() if record.remediated_at else None,
            "closed_at": record.closed_at.isoformat() if record.closed_at else None,
            "remediation_steps": record.remediation_steps,
            "scan_metadata": record.scan_metadata,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    # ── Teams ──────────────────────────────────────────────────────

    async def create_team(self, name: str, **fields: Any) -> dict[str, Any]:
        async with self._sf() as session:
            record = TeamRecord(name=name)
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return self._team_to_dict(record)

    async def get_team(self, team_id: str) -> dict[str, Any] | None:
        async with self._sf() as session:
            record = await session.get(TeamRecord, team_id)
            if record is None:
                return None
            return self._team_to_dict(record)

    async def list_teams(self) -> list[dict[str, Any]]:
        async with self._sf() as session:
            stmt = select(TeamRecord).order_by(TeamRecord.name)
            result = await session.execute(stmt)
            return [self._team_to_dict(r) for r in result.scalars().all()]

    async def add_team_member(self, team_id: str, user_id: str, role: str = "member") -> str:
        async with self._sf() as session:
            record = TeamMemberRecord(team_id=team_id, user_id=user_id, role=role)
            session.add(record)
            await session.commit()
            return record.id

    async def remove_team_member(self, team_id: str, user_id: str) -> bool:
        async with self._sf() as session:
            stmt = select(TeamMemberRecord).where(
                TeamMemberRecord.team_id == team_id,
                TeamMemberRecord.user_id == user_id,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    async def list_team_members(self, team_id: str) -> list[dict[str, Any]]:
        async with self._sf() as session:
            stmt = select(TeamMemberRecord).where(TeamMemberRecord.team_id == team_id)
            result = await session.execute(stmt)
            return [
                {
                    "id": r.id,
                    "team_id": r.team_id,
                    "user_id": r.user_id,
                    "role": r.role,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in result.scalars().all()
            ]

    @staticmethod
    def _team_to_dict(record: TeamRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "slack_channel": record.slack_channel,
            "pagerduty_service_id": record.pagerduty_service_id,
            "email": record.email,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    # ── Vulnerability Comments ─────────────────────────────────────

    async def add_vulnerability_comment(
        self,
        vulnerability_id: str,
        content: str,
        user_id: str | None = None,
        comment_type: str = "comment",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        async with self._sf() as session:
            record = VulnerabilityCommentRecord(
                vulnerability_id=vulnerability_id,
                user_id=user_id,
                content=content,
                comment_type=comment_type,
                comment_metadata=metadata or {},
            )
            session.add(record)
            await session.commit()
            return record.id

    async def list_vulnerability_comments(self, vulnerability_id: str) -> list[dict[str, Any]]:
        async with self._sf() as session:
            stmt = (
                select(VulnerabilityCommentRecord)
                .where(VulnerabilityCommentRecord.vulnerability_id == vulnerability_id)
                .order_by(VulnerabilityCommentRecord.created_at.asc())
            )
            result = await session.execute(stmt)
            return [
                {
                    "id": r.id,
                    "vulnerability_id": r.vulnerability_id,
                    "user_id": r.user_id,
                    "content": r.content,
                    "comment_type": r.comment_type,
                    "metadata": r.comment_metadata,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in result.scalars().all()
            ]

    # ── Organizations ─────────────────────────────────────────────

    async def list_organizations(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List organizations ordered by creation date."""
        async with self._sf() as session:
            stmt = (
                select(OrganizationRecord)
                .order_by(OrganizationRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._organization_to_dict(r) for r in result.scalars().all()]

    async def create_organization(self, name: str, slug: str, plan: str = "free") -> dict[str, Any]:
        """Create a new organization."""
        async with self._sf() as session:
            record = OrganizationRecord(name=name, slug=slug, plan=plan)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return self._organization_to_dict(record)

    async def get_organization(self, org_id: str) -> dict[str, Any] | None:
        """Get an organization by ID."""
        async with self._sf() as session:
            record = await session.get(OrganizationRecord, org_id)
            if record is None:
                return None
            return self._organization_to_dict(record)

    async def update_organization(self, org_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Update mutable fields on an organization."""
        async with self._sf() as session:
            record = await session.get(OrganizationRecord, org_id)
            if record is None:
                return None
            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return self._organization_to_dict(record)

    @staticmethod
    def _organization_to_dict(
        record: OrganizationRecord,
    ) -> dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "slug": record.slug,
            "plan": record.plan,
            "is_active": record.is_active,
            "settings": record.settings,
            "rate_limit": record.rate_limit,
            "created_at": (record.created_at.isoformat() if record.created_at else None),
            "updated_at": (record.updated_at.isoformat() if record.updated_at else None),
        }

    # ── Risk Acceptance ────────────────────────────────────────────

    async def create_risk_acceptance(
        self,
        vulnerability_id: str,
        accepted_by: str,
        reason: str,
        expires_at: datetime | None = None,
    ) -> str:
        async with self._sf() as session:
            record = RiskAcceptanceRecord(
                vulnerability_id=vulnerability_id,
                accepted_by=accepted_by,
                reason=reason,
                expires_at=expires_at,
            )
            session.add(record)
            # Also update the vulnerability status
            vuln = await session.get(VulnerabilityRecord, vulnerability_id)
            if vuln:
                vuln.status = "accepted_risk"
            await session.commit()
            return record.id

    # ── Agent Context ─────────────────────────────────────────────

    async def get_agent_context(self, agent_type: str, key: str) -> dict[str, Any] | None:
        """Fetch a single agent context entry by type + key."""
        async with self._sf() as session:
            stmt = select(AgentContextRecord).where(
                AgentContextRecord.agent_type == agent_type,
                AgentContextRecord.context_key == key,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._agent_context_to_dict(record)

    async def upsert_agent_context(
        self,
        agent_type: str,
        key: str,
        value: dict[str, Any],
        ttl_hours: int | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Insert or update an agent context entry."""
        async with self._sf() as session:
            stmt = select(AgentContextRecord).where(
                AgentContextRecord.agent_type == agent_type,
                AgentContextRecord.context_key == key,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                record = AgentContextRecord(
                    agent_type=agent_type,
                    context_key=key,
                )
                session.add(record)

            record.context_value = value
            record.ttl_hours = ttl_hours
            record.expires_at = expires_at
            await session.commit()
            await session.refresh(record)
            return self._agent_context_to_dict(record)

    async def delete_agent_context(self, agent_type: str, key: str) -> bool:
        """Delete an agent context entry. Returns True if deleted."""
        async with self._sf() as session:
            stmt = select(AgentContextRecord).where(
                AgentContextRecord.agent_type == agent_type,
                AgentContextRecord.context_key == key,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    async def search_agent_context(
        self,
        agent_type: str,
        key_pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search context entries by agent type with optional key LIKE filter."""
        async with self._sf() as session:
            stmt = select(AgentContextRecord).where(
                AgentContextRecord.agent_type == agent_type,
            )
            if key_pattern:
                stmt = stmt.where(AgentContextRecord.context_key.ilike(f"%{key_pattern}%"))
            stmt = stmt.order_by(AgentContextRecord.updated_at.desc())
            result = await session.execute(stmt)
            return [self._agent_context_to_dict(r) for r in result.scalars().all()]

    async def cleanup_expired_context(self) -> int:
        """Delete all expired context entries. Returns count deleted."""
        from sqlalchemy import delete

        async with self._sf() as session:
            stmt = (
                delete(AgentContextRecord)
                .where(AgentContextRecord.expires_at.isnot(None))
                .where(AgentContextRecord.expires_at < datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount  # type: ignore[attr-defined,return-value]

    @staticmethod
    def _agent_context_to_dict(
        record: AgentContextRecord,
    ) -> dict[str, Any]:
        return {
            "id": record.id,
            "agent_type": record.agent_type,
            "context_key": record.context_key,
            "context_value": record.context_value,
            "ttl_hours": record.ttl_hours,
            "expires_at": (record.expires_at.isoformat() if record.expires_at else None),
            "created_at": (record.created_at.isoformat() if record.created_at else None),
            "updated_at": (record.updated_at.isoformat() if record.updated_at else None),
        }

    # ── API Keys ─────────────────────────────────────────────────

    async def create_api_key(
        self,
        user_id: str,
        key_prefix: str,
        key_hash: str,
        name: str,
        scopes: list[str] | None = None,
        organization_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a new API key record."""
        async with self._sf() as session:
            record = APIKeyRecord(
                user_id=user_id,
                key_prefix=key_prefix,
                key_hash=key_hash,
                name=name,
                scopes=scopes or [],
                organization_id=organization_id,
                expires_at=expires_at,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            logger.info(
                "api_key_created",
                key_id=record.id,
                user_id=user_id,
            )
            return self._api_key_to_dict(record)

    async def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        """Look up an API key by its SHA-256 hash."""
        async with self._sf() as session:
            stmt = select(APIKeyRecord).where(APIKeyRecord.key_hash == key_hash)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._api_key_to_dict(record)

    async def list_api_keys_for_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List API keys owned by a user (never returns key_hash)."""
        async with self._sf() as session:
            stmt = (
                select(APIKeyRecord)
                .where(APIKeyRecord.user_id == user_id)
                .order_by(APIKeyRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._api_key_to_dict(r) for r in result.scalars().all()]

    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke an API key. Returns True if found and revoked."""
        async with self._sf() as session:
            record = await session.get(APIKeyRecord, key_id)
            if record is None or record.user_id != user_id:
                return False
            record.is_active = False
            await session.commit()
            logger.info(
                "api_key_revoked",
                key_id=key_id,
                user_id=user_id,
            )
            return True

    async def update_api_key_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for an API key."""
        async with self._sf() as session:
            record = await session.get(APIKeyRecord, key_id)
            if record is not None:
                record.last_used_at = datetime.now(UTC)
                await session.commit()

    @staticmethod
    def _api_key_to_dict(
        record: APIKeyRecord,
    ) -> dict[str, Any]:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "organization_id": record.organization_id,
            "key_prefix": record.key_prefix,
            "key_hash": record.key_hash,
            "name": record.name,
            "scopes": record.scopes,
            "expires_at": (record.expires_at.isoformat() if record.expires_at else None),
            "last_used_at": (record.last_used_at.isoformat() if record.last_used_at else None),
            "is_active": record.is_active,
            "created_at": (record.created_at.isoformat() if record.created_at else None),
        }

    # ── Playbooks ─────────────────────────────────────────────────

    async def create_playbook(
        self,
        name: str,
        content: str,
        description: str = "",
        tags: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new custom playbook."""
        async with self._sf() as session:
            record = PlaybookRecord(
                name=name,
                description=description,
                content=content,
                tags=tags or [],
                created_by=created_by,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            logger.info(
                "playbook_created",
                playbook_id=record.id,
                name=name,
            )
            return self._playbook_to_dict(record)

    async def get_playbook(self, playbook_id: str) -> dict[str, Any] | None:
        """Get a playbook by ID."""
        async with self._sf() as session:
            record = await session.get(PlaybookRecord, playbook_id)
            if record is None:
                return None
            return self._playbook_to_dict(record)

    async def list_playbooks(
        self,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List custom playbooks from the database."""
        async with self._sf() as session:
            stmt = select(PlaybookRecord).order_by(PlaybookRecord.created_at.desc())
            if active_only:
                stmt = stmt.where(
                    PlaybookRecord.is_active == True  # noqa: E712
                )
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return [self._playbook_to_dict(r) for r in result.scalars().all()]

    async def update_playbook(self, playbook_id: str, **fields: Any) -> dict[str, Any] | None:
        """Update a custom playbook. Returns updated dict or None."""
        async with self._sf() as session:
            record = await session.get(PlaybookRecord, playbook_id)
            if record is None:
                return None
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            logger.info(
                "playbook_updated",
                playbook_id=playbook_id,
            )
            return self._playbook_to_dict(record)

    async def delete_playbook(self, playbook_id: str) -> bool:
        """Soft-delete a playbook. Returns True if found."""
        async with self._sf() as session:
            record = await session.get(PlaybookRecord, playbook_id)
            if record is None:
                return False
            record.is_active = False
            await session.commit()
            logger.info(
                "playbook_deleted",
                playbook_id=playbook_id,
            )
            return True

    @staticmethod
    def _playbook_to_dict(
        record: PlaybookRecord,
    ) -> dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "content": record.content,
            "tags": record.tags or [],
            "is_active": record.is_active,
            "created_by": record.created_by,
            "created_at": (record.created_at.isoformat() if record.created_at else None),
            "updated_at": (record.updated_at.isoformat() if record.updated_at else None),
        }

    # ── Notification Preferences ────────────────────────────────

    async def get_notification_preferences(self, user_id: str) -> list[dict[str, Any]]:
        """List all notification preferences for a user."""
        async with self._sf() as session:
            stmt = (
                select(NotificationPreferenceRecord)
                .where(NotificationPreferenceRecord.user_id == user_id)
                .order_by(NotificationPreferenceRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            return [self._notif_pref_to_dict(r) for r in result.scalars().all()]

    async def upsert_notification_preference(
        self,
        user_id: str,
        channel: str,
        event_type: str,
        enabled: bool = True,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert or update a notification preference.

        Uses the (user_id, channel, event_type) unique constraint
        to determine whether to insert or update.
        """
        async with self._sf() as session:
            stmt = select(NotificationPreferenceRecord).where(
                NotificationPreferenceRecord.user_id == user_id,
                NotificationPreferenceRecord.channel == channel,
                NotificationPreferenceRecord.event_type == event_type,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                record = NotificationPreferenceRecord(
                    user_id=user_id,
                    channel=channel,
                    event_type=event_type,
                )
                session.add(record)

            record.enabled = enabled
            record.config = config
            await session.commit()
            await session.refresh(record)
            logger.info(
                "notification_preference_upserted",
                user_id=user_id,
                channel=channel,
                event_type=event_type,
            )
            return self._notif_pref_to_dict(record)

    async def delete_notification_preference(self, preference_id: str, user_id: str) -> bool:
        """Delete a preference. Returns False if not found or not owned."""
        async with self._sf() as session:
            record = await session.get(NotificationPreferenceRecord, preference_id)
            if record is None or record.user_id != user_id:
                return False
            await session.delete(record)
            await session.commit()
            logger.info(
                "notification_preference_deleted",
                preference_id=preference_id,
                user_id=user_id,
            )
            return True

    async def get_subscribers_for_event(self, event_type: str) -> list[str]:
        """Return user_ids that have an enabled pref for this event."""
        async with self._sf() as session:
            stmt = (
                select(NotificationPreferenceRecord.user_id)
                .where(
                    NotificationPreferenceRecord.event_type == event_type,
                    NotificationPreferenceRecord.enabled.is_(True),
                )
                .distinct()
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    @staticmethod
    def _notif_pref_to_dict(
        record: NotificationPreferenceRecord,
    ) -> dict[str, Any]:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "channel": record.channel,
            "event_type": record.event_type,
            "enabled": record.enabled,
            "config": record.config,
            "created_at": (record.created_at.isoformat() if record.created_at else None),
            "updated_at": (record.updated_at.isoformat() if record.updated_at else None),
        }

    # ── Onboarding Progress ─────────────────────────────────────

    async def get_onboarding_progress(self, org_id: str) -> list[dict[str, Any]]:
        """Return all onboarding step records for an organization."""
        async with self._sf() as session:
            stmt = (
                select(OnboardingProgressRecord)
                .where(OnboardingProgressRecord.org_id == org_id)
                .order_by(OnboardingProgressRecord.created_at.asc())
            )
            result = await session.execute(stmt)
            return [
                {
                    "id": r.id,
                    "org_id": r.org_id,
                    "step_name": r.step_name,
                    "status": r.status,
                    "metadata": r.step_metadata,
                    "completed_at": (r.completed_at.isoformat() if r.completed_at else None),
                    "created_at": (r.created_at.isoformat() if r.created_at else None),
                }
                for r in result.scalars().all()
            ]

    async def update_onboarding_step(
        self,
        org_id: str,
        step: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update an onboarding step for an organization."""
        async with self._sf() as session:
            stmt = select(OnboardingProgressRecord).where(
                OnboardingProgressRecord.org_id == org_id,
                OnboardingProgressRecord.step_name == step,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                record = OnboardingProgressRecord(
                    org_id=org_id,
                    step_name=step,
                )
                session.add(record)

            record.status = status
            if metadata is not None:
                record.step_metadata = metadata
            if status in ("completed", "skipped"):
                record.completed_at = datetime.now(UTC)
            await session.commit()
            logger.info(
                "onboarding_step_updated",
                org_id=org_id,
                step=step,
                status=status,
            )

    # ── Global Search ────────────────────────────────────────────

    async def search_investigations(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search investigations by alert_name/alert_id using ILIKE.

        Uses parameterized queries to prevent SQL injection.
        """
        pattern = f"%{query}%"
        async with self._sf() as session:
            from sqlalchemy import or_

            stmt = (
                select(InvestigationRecord)
                .where(
                    or_(
                        InvestigationRecord.alert_name.ilike(pattern),
                        InvestigationRecord.alert_id.ilike(pattern),
                    )
                )
                .order_by(InvestigationRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._investigation_to_dict(r) for r in result.scalars().all()]

    async def search_remediations(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search remediations by action_type/target_resource using ILIKE.

        Uses parameterized queries to prevent SQL injection.
        """
        pattern = f"%{query}%"
        async with self._sf() as session:
            from sqlalchemy import or_

            stmt = (
                select(RemediationRecord)
                .where(
                    or_(
                        RemediationRecord.action_type.ilike(pattern),
                        RemediationRecord.target_resource.ilike(pattern),
                    )
                )
                .order_by(RemediationRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._remediation_to_dict(r) for r in result.scalars().all()]

    async def search_vulnerabilities(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search vulnerabilities by cve_id/title/package_name using ILIKE.

        Uses parameterized queries to prevent SQL injection.
        """
        pattern = f"%{query}%"
        async with self._sf() as session:
            from sqlalchemy import or_

            stmt = (
                select(VulnerabilityRecord)
                .where(
                    or_(
                        VulnerabilityRecord.cve_id.ilike(pattern),
                        VulnerabilityRecord.title.ilike(pattern),
                        VulnerabilityRecord.package_name.ilike(pattern),
                    )
                )
                .order_by(VulnerabilityRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._vulnerability_to_dict(r) for r in result.scalars().all()]

    # ── Data Export ───────────────────────────────────────────────

    async def export_investigations(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Export investigation records with optional filters.

        Returns flat dicts suitable for CSV/JSON export.
        """
        async with self._sf() as session:
            stmt = select(InvestigationRecord).order_by(InvestigationRecord.created_at.desc())
            if start_date:
                stmt = stmt.where(InvestigationRecord.created_at >= start_date)
            if end_date:
                stmt = stmt.where(InvestigationRecord.created_at <= end_date)
            if status:
                stmt = stmt.where(InvestigationRecord.status == status)
            if severity:
                stmt = stmt.where(InvestigationRecord.severity == severity)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._investigation_to_dict(r) for r in result.scalars().all()]

    async def export_remediations(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Export remediation records with optional filters.

        The *severity* filter maps to the ``risk_level`` column.
        Returns flat dicts suitable for CSV/JSON export.
        """
        async with self._sf() as session:
            stmt = select(RemediationRecord).order_by(RemediationRecord.created_at.desc())
            if start_date:
                stmt = stmt.where(RemediationRecord.created_at >= start_date)
            if end_date:
                stmt = stmt.where(RemediationRecord.created_at <= end_date)
            if status:
                stmt = stmt.where(RemediationRecord.status == status)
            if severity:
                stmt = stmt.where(RemediationRecord.risk_level == severity)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._remediation_to_dict(r) for r in result.scalars().all()]

    async def export_compliance_data(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Export security scan records for compliance reporting.

        Returns flat dicts with compliance scores and posture data.
        """
        async with self._sf() as session:
            stmt = select(SecurityScanRecord).order_by(SecurityScanRecord.created_at.desc())
            if start_date:
                stmt = stmt.where(SecurityScanRecord.created_at >= start_date)
            if end_date:
                stmt = stmt.where(SecurityScanRecord.created_at <= end_date)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._security_scan_to_dict(r) for r in result.scalars().all()]
