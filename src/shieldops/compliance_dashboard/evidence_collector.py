"""Evidence collection and management for compliance controls."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from shieldops.compliance_dashboard.models import (
    ComplianceFramework,
    EvidenceRecord,
    EvidenceType,
)

logger = structlog.get_logger()


class EvidenceCollector:
    """Collects, stores, and reports on compliance evidence."""

    def __init__(self) -> None:
        self._evidence: dict[str, EvidenceRecord] = {}
        self._schedules: dict[ComplianceFramework, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Evidence storage helpers
    # ------------------------------------------------------------------

    def _store(self, record: EvidenceRecord) -> EvidenceRecord:
        self._evidence[record.evidence_id] = record
        logger.info(
            "evidence_collector.stored",
            evidence_id=record.evidence_id,
            control_id=record.control_id,
            evidence_type=record.evidence_type,
        )
        return record

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        """Retrieve a single evidence record by ID."""
        return self._evidence.get(evidence_id)

    def list_evidence_for_control(self, control_id: str) -> list[EvidenceRecord]:
        """Return all evidence linked to a control."""
        return [e for e in self._evidence.values() if e.control_id == control_id]

    # ------------------------------------------------------------------
    # Collection methods
    # ------------------------------------------------------------------

    async def collect_audit_logs(
        self,
        start_date: float,
        end_date: float,
        control_id: str = "",
    ) -> EvidenceRecord:
        """Query the audit trail and store as log evidence.

        In a production deployment this would query PostgreSQL
        or an external SIEM.  Here we create a placeholder
        evidence record representing the collection.
        """
        record = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            control_id=control_id,
            evidence_type=EvidenceType.LOG,
            title="Audit Log Extract",
            description=(f"Audit logs from {start_date} to {end_date}"),
            file_path=(f"/evidence/audit_logs/{int(start_date)}_{int(end_date)}.json"),
            collected_at=time.time(),
            collector="shieldops-evidence-collector",
            verified=False,
            metadata={
                "start_date": start_date,
                "end_date": end_date,
                "source": "audit_trail",
            },
        )
        logger.info(
            "evidence_collector.audit_logs_collected",
            control_id=control_id,
            start=start_date,
            end=end_date,
        )
        return self._store(record)

    async def collect_config_evidence(
        self,
        config_type: str,
        control_id: str = "",
    ) -> EvidenceRecord:
        """Snapshot the current configuration as evidence.

        ``config_type`` might be ``"opa_policies"``,
        ``"rbac_config"``, ``"network_rules"`` etc.
        """
        record = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            control_id=control_id,
            evidence_type=EvidenceType.CONFIG,
            title=f"Config Snapshot: {config_type}",
            description=(f"Point-in-time snapshot of {config_type} configuration."),
            file_path=(f"/evidence/configs/{config_type}_{int(time.time())}.json"),
            collected_at=time.time(),
            collector="shieldops-evidence-collector",
            verified=False,
            metadata={
                "config_type": config_type,
                "snapshot_time": time.time(),
            },
        )
        logger.info(
            "evidence_collector.config_evidence_collected",
            config_type=config_type,
            control_id=control_id,
        )
        return self._store(record)

    async def collect_agent_policy_evidence(
        self,
        control_id: str = "",
    ) -> EvidenceRecord:
        """Export OPA policies as compliance evidence.

        In production this fetches policies from the OPA
        endpoint; here we record the collection event.
        """
        record = EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            control_id=control_id,
            evidence_type=EvidenceType.CONFIG,
            title="OPA Agent Policy Export",
            description=("Export of all OPA policies governing agent actions."),
            file_path=(f"/evidence/policies/opa_export_{int(time.time())}.rego"),
            collected_at=time.time(),
            collector="shieldops-evidence-collector",
            verified=False,
            metadata={
                "source": "opa_policy_engine",
                "policy_count": 0,
            },
        )
        logger.info(
            "evidence_collector.agent_policy_evidence_collected",
            control_id=control_id,
        )
        return self._store(record)

    async def generate_evidence_report(self, control_id: str) -> dict[str, Any]:
        """Compile all evidence for a control into a report.

        Returns a structured dict suitable for serialisation
        or rendering.
        """
        records = self.list_evidence_for_control(control_id)
        report: dict[str, Any] = {
            "control_id": control_id,
            "generated_at": time.time(),
            "total_evidence": len(records),
            "verified_count": sum(1 for r in records if r.verified),
            "unverified_count": sum(1 for r in records if not r.verified),
            "evidence": [r.model_dump() for r in records],
        }
        logger.info(
            "evidence_collector.report_generated",
            control_id=control_id,
            total=len(records),
        )
        return report

    async def schedule_evidence_collection(
        self,
        framework: ComplianceFramework,
        interval_hours: int = 24,
    ) -> dict[str, Any]:
        """Register periodic evidence collection for a framework.

        The actual scheduling would be handled by an external
        task runner (e.g. Celery / APScheduler).  This method
        records the intent and returns the schedule metadata.
        """
        schedule: dict[str, Any] = {
            "framework": framework,
            "interval_hours": interval_hours,
            "next_run": time.time() + interval_hours * 3600,
            "created_at": time.time(),
            "schedule_id": str(uuid.uuid4()),
            "status": "active",
        }
        self._schedules[framework] = schedule
        logger.info(
            "evidence_collector.schedule_created",
            framework=framework,
            interval_hours=interval_hours,
        )
        return schedule

    def get_schedule(self, framework: ComplianceFramework) -> dict[str, Any] | None:
        """Return the collection schedule for a framework."""
        return self._schedules.get(framework)
