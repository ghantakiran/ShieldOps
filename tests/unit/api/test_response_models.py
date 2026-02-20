"""Tests for Pydantic response models in shieldops.api.schemas.responses.

Validates default values, required fields, serialization, and edge cases
for every response model.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shieldops.api.schemas.responses import (
    AgentResponse,
    AuditLogEntry,
    ErrorResponse,
    HealthResponse,
    InvestigationResponse,
    PaginatedResponse,
    RemediationResponse,
    SecurityScanResponse,
    UserResponse,
    VulnerabilityResponse,
)


class TestInvestigationResponse:
    """InvestigationResponse model validation."""

    def test_investigation_response_defaults(self) -> None:
        """Minimal construction uses sensible defaults."""
        model = InvestigationResponse(id="inv-1", alert_id="alt-1")
        assert model.alert_name == ""
        assert model.severity == "warning"
        assert model.status == "init"
        assert model.confidence == 0.0
        assert model.environment is None
        assert model.created_at is None
        assert model.updated_at is None

    def test_investigation_response_all_fields(self) -> None:
        """All fields populated and serialised correctly."""
        now = datetime.now(UTC)
        model = InvestigationResponse(
            id="inv-2",
            alert_id="alt-2",
            alert_name="MemoryLeak",
            severity="critical",
            status="complete",
            confidence=0.95,
            environment="staging",
            created_at=now,
            updated_at=now,
        )
        data = model.model_dump()
        assert data["id"] == "inv-2"
        assert data["severity"] == "critical"
        assert data["confidence"] == 0.95

    def test_investigation_response_missing_required(self) -> None:
        """Omitting required 'id' or 'alert_id' raises ValidationError."""
        with pytest.raises(ValidationError):
            InvestigationResponse(alert_id="a")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            InvestigationResponse(id="i")  # type: ignore[call-arg]


class TestRemediationResponse:
    """RemediationResponse model validation."""

    def test_remediation_response_all_fields(self) -> None:
        """Full construction round-trips through model_dump."""
        now = datetime.now(UTC)
        model = RemediationResponse(
            id="rem-1",
            action_type="restart_service",
            target_resource="web-pod-7f8b",
            environment="production",
            risk_level="high",
            status="complete",
            validation_passed=True,
            investigation_id="inv-99",
            created_at=now,
        )
        data = model.model_dump()
        assert data["action_type"] == "restart_service"
        assert data["validation_passed"] is True
        assert data["investigation_id"] == "inv-99"

    def test_remediation_response_defaults(self) -> None:
        """Defaults are applied for optional fields."""
        model = RemediationResponse(
            id="rem-2",
            action_type="scale_up",
            target_resource="api-deploy",
            environment="staging",
            risk_level="low",
        )
        assert model.status == "init"
        assert model.validation_passed is None
        assert model.investigation_id is None
        assert model.created_at is None


class TestSecurityScanResponse:
    """SecurityScanResponse model validation."""

    def test_security_scan_response(self) -> None:
        """Numeric defaults are zero."""
        model = SecurityScanResponse(
            id="scan-1",
            scan_type="full",
            environment="production",
        )
        assert model.compliance_score == 0.0
        assert model.critical_cve_count == 0
        assert model.patches_applied == 0
        assert model.credentials_rotated == 0
        assert model.status == "init"

    def test_security_scan_response_populated(self) -> None:
        """All fields can be set and retrieved."""
        model = SecurityScanResponse(
            id="scan-2",
            scan_type="cve_only",
            environment="staging",
            status="complete",
            compliance_score=87.5,
            critical_cve_count=3,
            patches_applied=2,
            credentials_rotated=1,
            created_at=datetime.now(UTC),
        )
        assert model.compliance_score == 87.5
        assert model.critical_cve_count == 3


class TestVulnerabilityResponse:
    """VulnerabilityResponse model validation."""

    def test_vulnerability_response(self) -> None:
        """Basic construction with required + default fields."""
        model = VulnerabilityResponse(
            id="vuln-1",
            severity="critical",
            affected_resource="nginx:1.21",
        )
        assert model.cve_id is None
        assert model.status == "new"
        assert model.cvss_score == 0.0
        assert model.sla_breached is False

    def test_vulnerability_response_full(self) -> None:
        """Full construction with CVE and SLA breach."""
        model = VulnerabilityResponse(
            id="vuln-2",
            cve_id="CVE-2025-12345",
            severity="high",
            status="in_progress",
            title="Buffer overflow in libxml2",
            affected_resource="libxml2:2.9.12",
            cvss_score=8.1,
            sla_breached=True,
            created_at=datetime.now(UTC),
        )
        assert model.cve_id == "CVE-2025-12345"
        assert model.sla_breached is True
        assert model.cvss_score == 8.1


class TestAgentResponse:
    """AgentResponse model validation."""

    def test_agent_response(self) -> None:
        """Defaults match expected fleet values."""
        model = AgentResponse(id="agt-1", agent_type="investigation")
        assert model.environment == "production"
        assert model.status == "idle"
        assert model.last_heartbeat is None

    def test_agent_response_active(self) -> None:
        """Active agent with heartbeat."""
        now = datetime.now(UTC)
        model = AgentResponse(
            id="agt-2",
            agent_type="remediation",
            environment="staging",
            status="active",
            last_heartbeat=now,
        )
        assert model.status == "active"
        assert model.last_heartbeat == now


class TestAuditLogEntry:
    """AuditLogEntry model validation."""

    def test_audit_log_entry(self) -> None:
        """All required fields must be provided."""
        now = datetime.now(UTC)
        model = AuditLogEntry(
            id="aud-1",
            timestamp=now,
            agent_type="remediation",
            action="restart_service",
            target_resource="web-pod",
            environment="production",
            risk_level="medium",
            outcome="success",
            actor="agent:rem-01",
        )
        assert model.id == "aud-1"
        assert model.outcome == "success"
        assert model.actor == "agent:rem-01"

    def test_audit_log_entry_missing_required(self) -> None:
        """Omitting any required field raises ValidationError."""
        with pytest.raises(ValidationError):
            AuditLogEntry(
                id="aud-2",
                # timestamp missing
                agent_type="security",
                action="patch",
                target_resource="host",
                environment="staging",
                risk_level="low",
                outcome="failure",
                actor="agent:sec-01",
            )  # type: ignore[call-arg]


class TestUserResponse:
    """UserResponse model validation."""

    def test_user_response(self) -> None:
        """Basic user with defaults."""
        model = UserResponse(
            id="usr-1",
            email="alice@shieldops.io",
            name="Alice",
            role="admin",
        )
        assert model.is_active is True
        assert model.created_at is None

    def test_user_response_inactive(self) -> None:
        """Inactive user serialization."""
        model = UserResponse(
            id="usr-2",
            email="bob@shieldops.io",
            name="Bob",
            role="viewer",
            is_active=False,
            created_at=datetime.now(UTC),
        )
        data = model.model_dump()
        assert data["is_active"] is False
        assert data["role"] == "viewer"


class TestPaginatedResponse:
    """PaginatedResponse generic model validation."""

    def test_paginated_response_generic(self) -> None:
        """Works with arbitrary item types."""
        model = PaginatedResponse[int](
            items=[1, 2, 3],
            total=100,
            limit=3,
            offset=0,
        )
        assert model.items == [1, 2, 3]
        assert model.total == 100

    def test_paginated_response_empty(self) -> None:
        """Empty page is valid."""
        model = PaginatedResponse[str](
            items=[],
            total=0,
            limit=50,
            offset=0,
        )
        assert model.items == []
        assert model.total == 0

    def test_paginated_response_with_models(self) -> None:
        """Nested Pydantic models inside PaginatedResponse."""
        user = UserResponse(
            id="u1",
            email="a@b.com",
            name="A",
            role="viewer",
        )
        model = PaginatedResponse[UserResponse](
            items=[user],
            total=1,
            limit=10,
            offset=0,
        )
        assert len(model.items) == 1
        assert model.items[0].email == "a@b.com"


class TestErrorResponse:
    """ErrorResponse model validation."""

    def test_error_response(self) -> None:
        """Simple detail string."""
        model = ErrorResponse(detail="Resource not found")
        assert model.detail == "Resource not found"

    def test_error_response_serialization(self) -> None:
        """Round-trip serialization matches expected shape."""
        model = ErrorResponse(detail="Unauthorized")
        data = model.model_dump()
        assert data == {"detail": "Unauthorized"}


class TestHealthResponse:
    """HealthResponse model validation."""

    def test_health_response(self) -> None:
        """Services dict defaults to empty."""
        model = HealthResponse(status="healthy", version="1.0.0")
        assert model.services == {}

    def test_health_response_with_services(self) -> None:
        """Services dict can be populated."""
        model = HealthResponse(
            status="degraded",
            version="1.0.0",
            services={"database": "ok", "redis": "error"},
        )
        assert model.services["redis"] == "error"
        assert model.status == "degraded"
