"""GDPR data subject request processing.

Handles right-to-access (data portability), right-to-erasure,
and data processing activity reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class DSRType(StrEnum):
    ACCESS = "access"
    ERASURE = "erasure"
    PORTABILITY = "portability"
    RECTIFICATION = "rectification"


class DSRStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class DataSubjectRequest(BaseModel):
    """A GDPR data subject request."""

    id: str = Field(default_factory=lambda: f"dsr-{uuid4().hex[:12]}")
    subject_id: str
    request_type: DSRType
    status: DSRStatus = DSRStatus.PENDING
    reason: str = ""
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class DataProcessingActivity(BaseModel):
    """Record of a data processing activity (for DPA reports)."""

    name: str
    purpose: str
    data_categories: list[str] = Field(default_factory=list)
    retention_days: int = 365
    legal_basis: str = "legitimate_interest"
    third_party_sharing: bool = False


class DPAReport(BaseModel):
    """Data Processing Activities report."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    organization: str = "ShieldOps"
    activities: list[DataProcessingActivity] = Field(default_factory=list)
    total_subjects: int = 0
    dsr_summary: dict[str, int] = Field(default_factory=dict)


class GDPRProcessor:
    """Handles GDPR data subject requests.

    Provides access, erasure, and portability processing with
    audit logging for compliance.
    """

    # Default data processing activities for ShieldOps
    DEFAULT_ACTIVITIES = [
        DataProcessingActivity(
            name="Incident Investigation",
            purpose="Automated incident analysis and root cause determination",
            data_categories=["logs", "metrics", "traces", "user_actions"],
            retention_days=365,
            legal_basis="legitimate_interest",
        ),
        DataProcessingActivity(
            name="Remediation Execution",
            purpose="Automated infrastructure remediation",
            data_categories=["infrastructure_state", "configuration", "credentials"],
            retention_days=730,
            legal_basis="contract",
        ),
        DataProcessingActivity(
            name="Security Scanning",
            purpose="Vulnerability detection and compliance monitoring",
            data_categories=["code", "dependencies", "network_config", "credentials"],
            retention_days=365,
            legal_basis="legitimate_interest",
        ),
        DataProcessingActivity(
            name="User Authentication",
            purpose="User identity verification and access control",
            data_categories=["email", "name", "role", "login_history"],
            retention_days=365,
            legal_basis="contract",
        ),
        DataProcessingActivity(
            name="Audit Logging",
            purpose="Compliance audit trail for all platform actions",
            data_categories=["user_actions", "api_calls", "agent_decisions"],
            retention_days=2555,  # 7 years
            legal_basis="legal_obligation",
        ),
    ]

    def __init__(self) -> None:
        self._requests: dict[str, DataSubjectRequest] = {}
        self._subject_data: dict[str, dict[str, Any]] = {}
        self._activities = list(self.DEFAULT_ACTIVITIES)

    def create_request(self, request: DataSubjectRequest) -> DataSubjectRequest:
        """Create a new data subject request."""
        self._requests[request.id] = request
        logger.info(
            "gdpr_dsr_created",
            dsr_id=request.id,
            subject_id=request.subject_id,
            type=request.request_type,
        )
        return request

    def get_request(self, request_id: str) -> DataSubjectRequest | None:
        return self._requests.get(request_id)

    def list_requests(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DataSubjectRequest]:
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r.status == status]
        return requests[:limit]

    async def process_access(self, subject_id: str) -> dict[str, Any]:
        """Process a data access request — export all data for a subject."""
        data = self._subject_data.get(subject_id, {})
        result = {
            "subject_id": subject_id,
            "data_export": data,
            "categories": list(data.keys()) if data else [],
            "exported_at": datetime.now(UTC).isoformat(),
        }
        logger.info("gdpr_access_processed", subject_id=subject_id)
        return result

    async def process_erasure(self, subject_id: str) -> dict[str, Any]:
        """Process an erasure request — anonymize PII across all stores."""
        erased_fields: list[str] = []

        if subject_id in self._subject_data:
            data = self._subject_data[subject_id]
            pii_fields = ["email", "name", "phone", "address", "ip_address"]
            for field in pii_fields:
                if field in data:
                    data[field] = "[REDACTED]"
                    erased_fields.append(field)
            # Mark as anonymized
            data["_anonymized"] = True
            data["_anonymized_at"] = datetime.now(UTC).isoformat()

        result = {
            "subject_id": subject_id,
            "erased_fields": erased_fields,
            "anonymized": True,
            "processed_at": datetime.now(UTC).isoformat(),
        }
        logger.info(
            "gdpr_erasure_processed",
            subject_id=subject_id,
            fields=erased_fields,
        )
        return result

    async def process_request(self, request_id: str) -> DataSubjectRequest | None:
        """Process a pending DSR based on its type."""
        req = self._requests.get(request_id)
        if req is None:
            return None

        req.status = DSRStatus.PROCESSING

        if req.request_type == DSRType.ACCESS or req.request_type == DSRType.PORTABILITY:
            req.result = await self.process_access(req.subject_id)
        elif req.request_type == DSRType.ERASURE:
            req.result = await self.process_erasure(req.subject_id)
        else:
            req.result = {"message": "Rectification requires manual review"}

        req.status = DSRStatus.COMPLETED
        req.completed_at = datetime.now(UTC)
        return req

    def generate_dpa_report(self) -> DPAReport:
        """Generate a Data Processing Activities summary report."""
        dsr_summary: dict[str, int] = {}
        for req in self._requests.values():
            dsr_summary[req.request_type] = dsr_summary.get(req.request_type, 0) + 1

        return DPAReport(
            activities=self._activities,
            total_subjects=len(self._subject_data),
            dsr_summary=dsr_summary,
        )

    def register_subject_data(self, subject_id: str, data: dict[str, Any]) -> None:
        """Register data for a subject (for testing/demo)."""
        self._subject_data[subject_id] = data
