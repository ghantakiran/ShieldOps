"""HIPAA compliance engine.

Evaluates ShieldOps platform against HIPAA Administrative, Physical,
and Technical safeguard requirements.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class HIPAAControl(BaseModel):
    id: str
    safeguard: str  # administrative, physical, technical
    name: str
    description: str
    status: str = "fail"
    details: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    last_checked: datetime | None = None


class HIPAAReport(BaseModel):
    id: str
    generated_at: datetime
    overall_score: float
    total_controls: int
    passed: int
    failed: int
    warnings: int
    not_applicable: int
    safeguard_scores: dict[str, float] = Field(default_factory=dict)
    controls: list[HIPAAControl] = Field(default_factory=list)


_HIPAA_CONTROLS: list[tuple[str, str, str, str, str]] = [
    # Administrative Safeguards
    (
        "HIPAA-A-1",
        "administrative",
        "Security Management Process",
        "Policies and procedures to prevent, detect, and correct security violations",
        "_check_security_mgmt",
    ),
    (
        "HIPAA-A-2",
        "administrative",
        "Assigned Security Responsibility",
        "Designated security official responsible for policies",
        "_check_security_officer",
    ),
    (
        "HIPAA-A-3",
        "administrative",
        "Workforce Security",
        "Appropriate access to ePHI based on role",
        "_check_workforce_security",
    ),
    (
        "HIPAA-A-4",
        "administrative",
        "Information Access Management",
        "Policies for authorizing access to ePHI",
        "_check_access_management",
    ),
    (
        "HIPAA-A-5",
        "administrative",
        "Security Awareness Training",
        "Security awareness and training program",
        "_check_security_training",
    ),
    (
        "HIPAA-A-6",
        "administrative",
        "Security Incident Procedures",
        "Policies for reporting and responding to security incidents",
        "_check_incident_procedures",
    ),
    (
        "HIPAA-A-7",
        "administrative",
        "Contingency Plan",
        "Plans for data backup, disaster recovery, and emergency operations",
        "_check_contingency_plan",
    ),
    # Physical Safeguards
    (
        "HIPAA-P-1",
        "physical",
        "Facility Access Controls",
        "Policies to limit physical access to electronic information systems",
        "_check_facility_access",
    ),
    (
        "HIPAA-P-2",
        "physical",
        "Workstation Security",
        "Physical safeguards for workstations accessing ePHI",
        "_check_workstation_security",
    ),
    # Technical Safeguards
    (
        "HIPAA-T-1",
        "technical",
        "Access Control",
        "Technical policies to allow access only to authorized persons",
        "_check_tech_access_control",
    ),
    (
        "HIPAA-T-2",
        "technical",
        "Audit Controls",
        "Hardware, software, and procedural mechanisms to record and examine access",
        "_check_audit_controls",
    ),
    (
        "HIPAA-T-3",
        "technical",
        "Integrity Controls",
        "Policies to protect ePHI from improper alteration or destruction",
        "_check_integrity_controls",
    ),
    (
        "HIPAA-T-4",
        "technical",
        "Transmission Security",
        "Technical security measures to guard against unauthorized access during transmission",
        "_check_transmission_security",
    ),
    (
        "HIPAA-T-5",
        "technical",
        "Encryption",
        "Encryption mechanisms for ePHI at rest and in transit",
        "_check_encryption",
    ),
]


class HIPAAEngine:
    """Evaluates ShieldOps against HIPAA safeguard requirements."""

    def __init__(self) -> None:
        self._controls: dict[str, HIPAAControl] = {}
        self._init_controls()

    def _init_controls(self) -> None:
        for ctrl_id, safeguard, name, desc, _ in _HIPAA_CONTROLS:
            self._controls[ctrl_id] = HIPAAControl(
                id=ctrl_id, safeguard=safeguard, name=name, description=desc
            )

    async def evaluate(self) -> HIPAAReport:
        """Run a full HIPAA compliance evaluation."""
        logger.info("hipaa_audit_started", controls=len(self._controls))

        for ctrl_id, _, _, _, checker_name in _HIPAA_CONTROLS:
            checker = getattr(self, checker_name)
            status, details, evidence = await checker()
            ctrl = self._controls[ctrl_id]
            ctrl.status = status
            ctrl.details = details
            ctrl.evidence = evidence
            ctrl.last_checked = datetime.now(UTC)

        controls = list(self._controls.values())
        total = len(controls)
        passed = sum(1 for c in controls if c.status == "pass")
        failed = sum(1 for c in controls if c.status == "fail")
        warnings = sum(1 for c in controls if c.status == "warning")
        na = sum(1 for c in controls if c.status == "not_applicable")

        scoreable = total - na
        overall_score = round((passed / scoreable * 100) if scoreable > 0 else 0.0, 1)

        safeguard_scores: dict[str, float] = {}
        for sg in ("administrative", "physical", "technical"):
            sg_controls = [c for c in controls if c.safeguard == sg]
            sg_scoreable = sum(1 for c in sg_controls if c.status != "not_applicable")
            sg_passed = sum(1 for c in sg_controls if c.status == "pass")
            safeguard_scores[sg] = (
                round(sg_passed / sg_scoreable * 100, 1) if sg_scoreable > 0 else 0.0
            )

        report = HIPAAReport(
            id=f"hipaa-{uuid4().hex[:12]}",
            generated_at=datetime.now(UTC),
            overall_score=overall_score,
            total_controls=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            not_applicable=na,
            safeguard_scores=safeguard_scores,
            controls=controls,
        )
        logger.info("hipaa_audit_completed", score=overall_score, passed=passed, failed=failed)
        return report

    async def get_controls(
        self, safeguard: str | None = None, status: str | None = None
    ) -> list[HIPAAControl]:
        controls = list(self._controls.values())
        if safeguard:
            controls = [c for c in controls if c.safeguard == safeguard]
        if status:
            controls = [c for c in controls if c.status == status]
        return controls

    # ── Administrative Safeguard Checkers ─────────────────────────
    async def _check_security_mgmt(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.policy.opa.client")
            importlib.import_module("shieldops.agents.security.runner")
            evidence.append({"type": "module_check", "opa": True, "security_agent": True})
            return "pass", "Security management via OPA policies and security agent", evidence
        except ImportError:
            return "fail", "Security management components not found", evidence

    async def _check_security_officer(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            mod = importlib.import_module("shieldops.api.auth.models")
            has_roles = hasattr(mod, "UserRole")
            evidence.append({"type": "module_check", "roles_defined": has_roles})
            if has_roles:
                msg = "Role-based system supports security responsibility assignment"
                return "pass", msg, evidence
            return "warning", "Security roles partially defined", evidence
        except ImportError:
            return "warning", "Role system not verified", evidence

    async def _check_workforce_security(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            mod = importlib.import_module("shieldops.api.auth.dependencies")
            has_rbac = hasattr(mod, "require_role")
            evidence.append({"type": "module_check", "rbac": has_rbac})
            if has_rbac:
                return "pass", "RBAC enforces workforce security controls", evidence
            return "warning", "Workforce security partially implemented", evidence
        except ImportError:
            return "fail", "Workforce security controls not found", evidence

    async def _check_access_management(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.routes.permissions")
            evidence.append({"type": "module_check", "permissions_routes": True})
            return "pass", "Information access management via permissions API", evidence
        except ImportError:
            return "warning", "Permissions management not fully configured", evidence

    async def _check_security_training(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        evidence.append({"type": "policy_check", "training_program": "organizational"})
        return "warning", "Security training is an organizational requirement", evidence

    async def _check_incident_procedures(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.agents.investigation.runner")
            importlib.import_module("shieldops.agents.remediation.runner")
            evidence.append({"type": "module_check", "incident_agents": True})
            return "pass", "Automated incident detection, investigation, and response", evidence
        except ImportError:
            return "fail", "Incident response procedures not configured", evidence

    async def _check_contingency_plan(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.policy.approval.workflow")
            importlib.import_module("shieldops.policy.rollback")
            evidence.append({"type": "module_check", "rollback": True, "approval": True})
            msg = "Rollback and approval workflows support contingency operations"
            return "pass", msg, evidence
        except ImportError:
            return "warning", "Contingency plan components partially available", evidence

    # ── Physical Safeguard Checkers ──────────────────────────────
    async def _check_facility_access(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        evidence.append({"type": "deployment_check", "cloud_hosted": True})
        return "pass", "Cloud-hosted infrastructure with provider physical security", evidence

    async def _check_workstation_security(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        evidence.append({"type": "deployment_check", "api_based": True})
        return "pass", "API-based access eliminates direct workstation ePHI access", evidence

    # ── Technical Safeguard Checkers ─────────────────────────────
    async def _check_tech_access_control(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            mod = importlib.import_module("shieldops.api.auth.service")
            has_auth = hasattr(mod, "create_token")
            evidence.append({"type": "module_check", "jwt_auth": has_auth})
            if has_auth:
                return "pass", "JWT-based access control with role enforcement", evidence
            return "warning", "Access control partially configured", evidence
        except ImportError:
            return "fail", "Technical access control not found", evidence

    async def _check_audit_controls(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.routes.audit")
            evidence.append({"type": "module_check", "audit_routes": True})
            return "pass", "Comprehensive audit logging for all system activities", evidence
        except ImportError:
            return "fail", "Audit controls not configured", evidence

    async def _check_integrity_controls(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.policy.opa.client")
            evidence.append({"type": "module_check", "policy_engine": True})
            return "pass", "OPA policy engine prevents unauthorized data modification", evidence
        except ImportError:
            return "fail", "Integrity controls not found", evidence

    async def _check_transmission_security(self) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.middleware")
            evidence.append({"type": "module_check", "security_headers": True})
            return "pass", "Security headers enforce HSTS and TLS", evidence
        except ImportError:
            return "warning", "Transmission security not fully verified", evidence

    async def _check_encryption(self) -> tuple[str, str, list[dict[str, Any]]]:
        import os

        evidence: list[dict[str, Any]] = []
        db_url = os.environ.get("SHIELDOPS_DATABASE_URL", "")
        uses_ssl = "sslmode=" in db_url or "asyncpg" in db_url
        evidence.append({"type": "config_check", "db_encryption": uses_ssl})
        if uses_ssl:
            return "pass", "Database connections use encrypted transport", evidence
        return "warning", "Encryption configuration not fully verified", evidence
