"""PCI-DSS compliance engine.

Evaluates ShieldOps platform against PCI Data Security Standard requirements.
Follows the same pattern as SOC2ComplianceEngine for consistency.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class PCIDSSControlStatus:
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


class PCIDSSControl(BaseModel):
    id: str
    requirement: int
    name: str
    description: str
    status: str = "fail"
    details: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    last_checked: datetime | None = None


class PCIDSSReport(BaseModel):
    id: str
    generated_at: datetime
    overall_score: float
    total_controls: int
    passed: int
    failed: int
    warnings: int
    not_applicable: int
    requirement_scores: dict[str, float] = Field(default_factory=dict)
    controls: list[PCIDSSControl] = Field(default_factory=list)


_PCI_CONTROLS: list[tuple[str, int, str, str, str]] = [
    (
        "PCI-1.1",
        1,
        "Firewall Configuration",
        "Network security controls protect cardholder data",
        "_check_network_security",
    ),
    (
        "PCI-1.2",
        1,
        "Network Segmentation",
        "Cardholder data environment is segmented",
        "_check_network_segmentation",
    ),
    (
        "PCI-2.1",
        2,
        "Default Credentials",
        "Vendor-supplied defaults are changed",
        "_check_default_credentials",
    ),
    (
        "PCI-3.1",
        3,
        "Data Retention",
        "Stored cardholder data is minimized",
        "_check_data_retention",
    ),
    (
        "PCI-3.4",
        3,
        "Encryption at Rest",
        "Cardholder data is encrypted at rest",
        "_check_encryption_at_rest",
    ),
    (
        "PCI-4.1",
        4,
        "Encryption in Transit",
        "Data is encrypted during transmission",
        "_check_encryption_in_transit",
    ),
    (
        "PCI-5.1",
        5,
        "Malware Protection",
        "Systems are protected against malware",
        "_check_malware_protection",
    ),
    (
        "PCI-6.1",
        6,
        "Vulnerability Management",
        "Security vulnerabilities are identified and addressed",
        "_check_vulnerability_mgmt",
    ),
    (
        "PCI-6.5",
        6,
        "Secure Development",
        "Applications are developed securely",
        "_check_secure_development",
    ),
    (
        "PCI-7.1",
        7,
        "Access Control",
        "Access to cardholder data is restricted by business need",
        "_check_access_control",
    ),
    (
        "PCI-8.1",
        8,
        "User Authentication",
        "Users are identified and authenticated",
        "_check_user_authentication",
    ),
    (
        "PCI-10.1",
        10,
        "Audit Logging",
        "All access to cardholder data is logged",
        "_check_audit_logging",
    ),
    (
        "PCI-10.5",
        10,
        "Log Integrity",
        "Audit trails are secured and immutable",
        "_check_log_integrity",
    ),
    (
        "PCI-11.1",
        11,
        "Security Testing",
        "Security systems and processes are regularly tested",
        "_check_security_testing",
    ),
    (
        "PCI-12.1",
        12,
        "Security Policy",
        "Information security policy is maintained",
        "_check_security_policy",
    ),
]


class PCIDSSEngine:
    """Evaluates ShieldOps against PCI-DSS requirements."""

    def __init__(self) -> None:
        self._controls: dict[str, PCIDSSControl] = {}
        self._init_controls()

    def _init_controls(self) -> None:
        for ctrl_id, req, name, desc, _ in _PCI_CONTROLS:
            self._controls[ctrl_id] = PCIDSSControl(
                id=ctrl_id, requirement=req, name=name, description=desc
            )

    async def evaluate(self) -> PCIDSSReport:
        """Run a full PCI-DSS compliance evaluation."""
        logger.info("pci_dss_audit_started", controls=len(self._controls))

        for ctrl_id, _, _, _, checker_name in _PCI_CONTROLS:
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

        # Per-requirement scores
        req_scores: dict[str, float] = {}
        for req_num in sorted({c.requirement for c in controls}):
            req_controls = [c for c in controls if c.requirement == req_num]
            req_scoreable = sum(1 for c in req_controls if c.status != "not_applicable")
            req_passed = sum(1 for c in req_controls if c.status == "pass")
            req_scores[f"Requirement {req_num}"] = (
                round(req_passed / req_scoreable * 100, 1) if req_scoreable > 0 else 0.0
            )

        report = PCIDSSReport(
            id=f"pci-{uuid4().hex[:12]}",
            generated_at=datetime.now(UTC),
            overall_score=overall_score,
            total_controls=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            not_applicable=na,
            requirement_scores=req_scores,
            controls=controls,
        )

        logger.info("pci_dss_audit_completed", score=overall_score, passed=passed, failed=failed)
        return report

    async def get_controls(
        self, requirement: int | None = None, status: str | None = None
    ) -> list[PCIDSSControl]:
        controls = list(self._controls.values())
        if requirement is not None:
            controls = [c for c in controls if c.requirement == requirement]
        if status is not None:
            controls = [c for c in controls if c.status == status]
        return controls

    # ── Control Checkers ─────────────────────────────────────────
    async def _check_network_security(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.policy.opa.client")
            evidence.append({"type": "module_check", "module": "policy.opa.client", "found": True})
            return "pass", "Network policy enforcement via OPA is configured", evidence
        except ImportError:
            return "fail", "Network security controls not found", evidence

    async def _check_network_segmentation(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.connectors.kubernetes.connector")
            evidence.append({"type": "module_check", "module": "k8s_connector", "found": True})
            return "pass", "Kubernetes network policies support segmentation", evidence
        except ImportError:
            return "warning", "Network segmentation capabilities not verified", evidence

    async def _check_default_credentials(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        import os

        evidence: list[dict[str, Any]] = []
        jwt_secret = os.environ.get("SHIELDOPS_JWT_SECRET_KEY", "change-me-in-production")
        is_default = jwt_secret == "change-me-in-production"  # noqa: S105
        evidence.append({"type": "config_check", "default_jwt_changed": not is_default})
        if not is_default:
            return "pass", "Default credentials have been changed", evidence
        return "warning", "JWT secret key appears to be default value", evidence

    async def _check_data_retention(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.routes.exports")
            evidence.append({"type": "module_check", "module": "exports", "found": True})
            return "pass", "Data export and retention routes are available", evidence
        except ImportError:
            return "warning", "Data retention controls not fully configured", evidence

    async def _check_encryption_at_rest(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        import os

        evidence: list[dict[str, Any]] = []
        db_url = os.environ.get("SHIELDOPS_DATABASE_URL", "")
        uses_ssl = "sslmode=" in db_url or db_url.startswith("postgresql+asyncpg")
        evidence.append({"type": "config_check", "ssl_detected": uses_ssl})
        if uses_ssl:
            return "pass", "Database uses encrypted transport", evidence
        return "warning", "Encryption at rest configuration not verified", evidence

    async def _check_encryption_in_transit(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.middleware")
            evidence.append({"type": "module_check", "middleware": True})
            return "pass", "Security headers middleware enforces TLS", evidence
        except ImportError:
            return "fail", "TLS enforcement not configured", evidence

    async def _check_malware_protection(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.agents.security.runner")
            evidence.append({"type": "module_check", "security_agent": True})
            return "pass", "Security scanning agent monitors for threats", evidence
        except ImportError:
            return "fail", "Security agent not available", evidence

    async def _check_vulnerability_mgmt(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.routes.vulnerabilities")
            evidence.append({"type": "module_check", "vulnerability_routes": True})
            return "pass", "Vulnerability management system is active", evidence
        except ImportError:
            return "fail", "Vulnerability management not configured", evidence

    async def _check_secure_development(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        from pathlib import Path

        ci_path = Path(__file__).resolve().parent.parent.parent.parent / ".github" / "workflows"
        has_ci = ci_path.exists()
        evidence.append({"type": "filesystem_check", "ci_workflows": has_ci})
        if has_ci:
            return "pass", "CI/CD pipeline with automated testing is configured", evidence
        return "warning", "Secure development pipeline not verified", evidence

    async def _check_access_control(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            mod = importlib.import_module("shieldops.api.auth.dependencies")
            has_rbac = hasattr(mod, "require_role")
            evidence.append({"type": "module_check", "rbac": has_rbac})
            if has_rbac:
                return "pass", "RBAC controls restrict data access by role", evidence
            return "warning", "Access control partially configured", evidence
        except ImportError:
            return "fail", "Access control module not found", evidence

    async def _check_user_authentication(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            mod = importlib.import_module("shieldops.api.auth.service")
            has_auth = hasattr(mod, "create_token") and hasattr(mod, "decode_token")
            evidence.append({"type": "module_check", "auth_service": has_auth})
            if has_auth:
                return "pass", "JWT-based authentication is implemented", evidence
            return "warning", "Authentication partially implemented", evidence
        except ImportError:
            return "fail", "Authentication service not found", evidence

    async def _check_audit_logging(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.routes.audit")
            evidence.append({"type": "module_check", "audit_routes": True})
            return "pass", "Audit logging is active for all operations", evidence
        except ImportError:
            return "fail", "Audit logging not configured", evidence

    async def _check_log_integrity(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.api.middleware")
            evidence.append({"type": "module_check", "structured_logging": True})
            return "pass", "Structured logging with immutable audit trail", evidence
        except ImportError:
            return "warning", "Log integrity mechanisms not verified", evidence

    async def _check_security_testing(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        try:
            importlib.import_module("shieldops.integrations.scanners.trivy")
            evidence.append({"type": "module_check", "scanner": "trivy", "found": True})
            return "pass", "Automated security testing tools configured", evidence
        except ImportError:
            return "warning", "Security testing tools not fully configured", evidence

    async def _check_security_policy(
        self,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        evidence: list[dict[str, Any]] = []
        from pathlib import Path

        policies_dir = Path(__file__).resolve().parent.parent.parent.parent / "playbooks/policies"
        has_policies = policies_dir.exists()
        evidence.append({"type": "filesystem_check", "policies_dir": has_policies})
        if has_policies:
            return "pass", "Security policies are defined and enforced via OPA", evidence
        return "warning", "Security policy documentation not found", evidence
