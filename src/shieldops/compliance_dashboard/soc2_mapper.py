"""SOC2 Type II Trust Service Criteria mapper for ShieldOps controls."""

from __future__ import annotations

import time
from typing import Any

import structlog

from shieldops.compliance_dashboard.models import (
    ComplianceControl,
    ComplianceFramework,
    ControlStatus,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# SOC2 Trust Service Criteria definitions
# ---------------------------------------------------------------------------

_SOC2_CRITERIA: list[dict[str, str]] = [
    # CC1 — Control Environment
    {
        "control_id": "CC1.1",
        "category": "Control Environment",
        "title": "COSO Principle 1: Integrity and Ethical Values",
        "description": ("The entity demonstrates a commitment to integrity and ethical values."),
    },
    {
        "control_id": "CC1.2",
        "category": "Control Environment",
        "title": "COSO Principle 2: Board Independence",
        "description": (
            "The board of directors demonstrates independence from"
            " management and exercises oversight."
        ),
    },
    {
        "control_id": "CC1.3",
        "category": "Control Environment",
        "title": "COSO Principle 3: Management Structure",
        "description": (
            "Management establishes structures, reporting lines,"
            " and appropriate authorities and responsibilities."
        ),
    },
    {
        "control_id": "CC1.4",
        "category": "Control Environment",
        "title": "COSO Principle 4: Competence Commitment",
        "description": (
            "The entity demonstrates a commitment to attract,"
            " develop, and retain competent individuals."
        ),
    },
    {
        "control_id": "CC1.5",
        "category": "Control Environment",
        "title": "COSO Principle 5: Accountability",
        "description": (
            "The entity holds individuals accountable for their internal control responsibilities."
        ),
    },
    # CC2 — Communication and Information
    {
        "control_id": "CC2.1",
        "category": "Communication and Information",
        "title": "COSO Principle 13: Quality Information",
        "description": (
            "The entity obtains or generates and uses relevant,"
            " quality information to support internal control."
        ),
    },
    {
        "control_id": "CC2.2",
        "category": "Communication and Information",
        "title": "COSO Principle 14: Internal Communication",
        "description": (
            "The entity internally communicates information necessary to support internal control."
        ),
    },
    {
        "control_id": "CC2.3",
        "category": "Communication and Information",
        "title": "COSO Principle 15: External Communication",
        "description": (
            "The entity communicates with external parties"
            " regarding matters affecting internal control."
        ),
    },
    # CC3 — Risk Assessment
    {
        "control_id": "CC3.1",
        "category": "Risk Assessment",
        "title": "COSO Principle 6: Risk Objectives",
        "description": (
            "The entity specifies objectives with sufficient clarity"
            " to enable identification and assessment of risks."
        ),
    },
    {
        "control_id": "CC3.2",
        "category": "Risk Assessment",
        "title": "COSO Principle 7: Risk Identification",
        "description": (
            "The entity identifies risks to the achievement of its objectives and analyzes risks."
        ),
    },
    {
        "control_id": "CC3.3",
        "category": "Risk Assessment",
        "title": "COSO Principle 8: Fraud Risk",
        "description": ("The entity considers the potential for fraud in assessing risks."),
    },
    {
        "control_id": "CC3.4",
        "category": "Risk Assessment",
        "title": "COSO Principle 9: Change Assessment",
        "description": (
            "The entity identifies and assesses changes"
            " that could significantly impact internal control."
        ),
    },
    # CC4 — Monitoring Activities
    {
        "control_id": "CC4.1",
        "category": "Monitoring Activities",
        "title": "COSO Principle 16: Ongoing Evaluations",
        "description": (
            "The entity selects, develops, and performs ongoing and/or separate evaluations."
        ),
    },
    {
        "control_id": "CC4.2",
        "category": "Monitoring Activities",
        "title": "COSO Principle 17: Deficiency Communication",
        "description": (
            "The entity evaluates and communicates internal"
            " control deficiencies in a timely manner."
        ),
    },
    # CC5 — Control Activities
    {
        "control_id": "CC5.1",
        "category": "Control Activities",
        "title": "COSO Principle 10: Risk Mitigation",
        "description": (
            "The entity selects and develops control activities that contribute to risk mitigation."
        ),
    },
    {
        "control_id": "CC5.2",
        "category": "Control Activities",
        "title": "COSO Principle 11: Technology Controls",
        "description": (
            "The entity selects and develops general control activities over technology."
        ),
    },
    {
        "control_id": "CC5.3",
        "category": "Control Activities",
        "title": "COSO Principle 12: Control Policies",
        "description": ("The entity deploys control activities through policies and procedures."),
    },
    # CC6 — Logical and Physical Access Controls
    {
        "control_id": "CC6.1",
        "category": "Logical and Physical Access Controls",
        "title": "Access Security Software and Infrastructure",
        "description": (
            "The entity implements logical access security"
            " software, infrastructure, and architectures."
        ),
    },
    {
        "control_id": "CC6.2",
        "category": "Logical and Physical Access Controls",
        "title": "User Registration and Authorization",
        "description": (
            "Prior to issuing credentials, the entity registers and authorizes new users."
        ),
    },
    {
        "control_id": "CC6.3",
        "category": "Logical and Physical Access Controls",
        "title": "Role-Based Access",
        "description": (
            "The entity authorizes, modifies, or removes access based on role or need."
        ),
    },
    {
        "control_id": "CC6.6",
        "category": "Logical and Physical Access Controls",
        "title": "System Boundary Protection",
        "description": (
            "The entity implements logical access security measures to protect against threats."
        ),
    },
    {
        "control_id": "CC6.7",
        "category": "Logical and Physical Access Controls",
        "title": "Data Encryption",
        "description": (
            "The entity restricts transmission, movement,"
            " and removal of information using encryption."
        ),
    },
    {
        "control_id": "CC6.8",
        "category": "Logical and Physical Access Controls",
        "title": "Malicious Software Prevention",
        "description": (
            "The entity implements controls to prevent or detect and act upon malicious software."
        ),
    },
    # CC7 — System Operations
    {
        "control_id": "CC7.1",
        "category": "System Operations",
        "title": "Infrastructure Monitoring",
        "description": (
            "The entity uses detection and monitoring procedures"
            " to identify changes to configurations."
        ),
    },
    {
        "control_id": "CC7.2",
        "category": "System Operations",
        "title": "Security Event Monitoring",
        "description": (
            "The entity monitors system components for anomalies"
            " indicative of malicious acts or natural disasters."
        ),
    },
    {
        "control_id": "CC7.3",
        "category": "System Operations",
        "title": "Security Incident Evaluation",
        "description": (
            "The entity evaluates security events to determine"
            " whether they constitute security incidents."
        ),
    },
    {
        "control_id": "CC7.4",
        "category": "System Operations",
        "title": "Incident Response",
        "description": (
            "The entity responds to identified security incidents"
            " by executing a defined incident response program."
        ),
    },
    {
        "control_id": "CC7.5",
        "category": "System Operations",
        "title": "Incident Recovery",
        "description": (
            "The entity identifies, develops, and implements"
            " activities to recover from security incidents."
        ),
    },
    # CC8 — Change Management
    {
        "control_id": "CC8.1",
        "category": "Change Management",
        "title": "Infrastructure and Software Changes",
        "description": (
            "The entity authorizes, designs, develops, configures,"
            " documents, tests, approves, and implements changes."
        ),
    },
    # CC9 — Risk Mitigation
    {
        "control_id": "CC9.1",
        "category": "Risk Mitigation",
        "title": "Risk Mitigation Identification",
        "description": (
            "The entity identifies, selects, and develops risk mitigation activities for risks."
        ),
    },
    {
        "control_id": "CC9.2",
        "category": "Risk Mitigation",
        "title": "Vendor Risk Management",
        "description": (
            "The entity assesses and manages risks associated with vendors and business partners."
        ),
    },
    # A1 — Availability
    {
        "control_id": "A1.1",
        "category": "Availability",
        "title": "Availability Commitments",
        "description": (
            "The entity maintains, monitors, and evaluates current processing capacity and use."
        ),
    },
    {
        "control_id": "A1.2",
        "category": "Availability",
        "title": "Environmental Protections",
        "description": (
            "The entity authorizes, designs, develops, and implements environmental protections."
        ),
    },
    {
        "control_id": "A1.3",
        "category": "Availability",
        "title": "Recovery Operations",
        "description": ("The entity tests recovery plan procedures supporting system recovery."),
    },
    # PI1 — Processing Integrity
    {
        "control_id": "PI1.1",
        "category": "Processing Integrity",
        "title": "Processing Accuracy",
        "description": (
            "The entity implements policies to define and deliver processing accuracy."
        ),
    },
    {
        "control_id": "PI1.2",
        "category": "Processing Integrity",
        "title": "System Input Controls",
        "description": (
            "The entity implements policies for system inputs that result in accurate processing."
        ),
    },
    # C1 — Confidentiality
    {
        "control_id": "C1.1",
        "category": "Confidentiality",
        "title": "Confidential Information Identification",
        "description": (
            "The entity identifies and maintains confidential"
            " information to meet confidentiality objectives."
        ),
    },
    {
        "control_id": "C1.2",
        "category": "Confidentiality",
        "title": "Confidential Information Disposal",
        "description": (
            "The entity disposes of confidential information to meet confidentiality objectives."
        ),
    },
    # P1-P8 — Privacy
    {
        "control_id": "P1.1",
        "category": "Privacy",
        "title": "Privacy Notice",
        "description": ("The entity provides notice about its privacy practices to data subjects."),
    },
    {
        "control_id": "P2.1",
        "category": "Privacy",
        "title": "Choice and Consent",
        "description": ("The entity communicates choices available and obtains consent."),
    },
    {
        "control_id": "P3.1",
        "category": "Privacy",
        "title": "Collection Limitation",
        "description": ("The entity collects personal information only for identified purposes."),
    },
    {
        "control_id": "P4.1",
        "category": "Privacy",
        "title": "Use and Retention",
        "description": ("The entity limits the use and retention of personal information."),
    },
    {
        "control_id": "P5.1",
        "category": "Privacy",
        "title": "Access to Personal Information",
        "description": (
            "The entity grants identified and authenticated"
            " data subjects access to their personal information."
        ),
    },
    {
        "control_id": "P6.1",
        "category": "Privacy",
        "title": "Disclosure and Notification",
        "description": (
            "The entity discloses personal information to third parties with appropriate consent."
        ),
    },
    {
        "control_id": "P7.1",
        "category": "Privacy",
        "title": "Quality of Personal Information",
        "description": (
            "The entity collects and maintains accurate, up-to-date, complete personal information."
        ),
    },
    {
        "control_id": "P8.1",
        "category": "Privacy",
        "title": "Monitoring and Enforcement",
        "description": (
            "The entity monitors compliance with its privacy commitments and procedures."
        ),
    },
]

# ---------------------------------------------------------------------------
# ShieldOps feature -> SOC2 control mapping
# ---------------------------------------------------------------------------

_SHIELDOPS_TO_SOC2: dict[str, list[str]] = {
    "audit_logging": ["CC7.2", "CC7.3", "CC4.1"],
    "opa_policy_engine": ["CC6.1", "CC5.1", "CC5.3"],
    "encryption_at_rest": ["CC6.7", "C1.1"],
    "encryption_in_transit": ["CC6.7", "C1.1"],
    "rbac_access_control": ["CC6.2", "CC6.3"],
    "incident_response_agent": ["CC7.4", "CC7.5"],
    "vulnerability_scanning": ["CC7.1", "CC6.8"],
    "change_management": ["CC8.1"],
    "slo_monitoring": ["A1.1"],
    "disaster_recovery": ["A1.3"],
    "data_classification": ["C1.1", "P3.1"],
    "secrets_management": ["CC6.7", "CC6.1"],
    "mfa_enforcement": ["CC6.1", "CC6.2"],
    "network_segmentation": ["CC6.6"],
    "vendor_risk_management": ["CC9.2"],
    "security_awareness_training": ["CC1.4"],
    "backup_verification": ["A1.2", "A1.3"],
    "input_validation": ["PI1.2"],
    "privacy_controls": [
        "P1.1",
        "P2.1",
        "P3.1",
        "P4.1",
        "P5.1",
        "P6.1",
        "P7.1",
        "P8.1",
    ],
    "risk_assessment": ["CC3.1", "CC3.2", "CC9.1"],
    "monitoring_and_alerting": ["CC4.1", "CC4.2", "CC7.1"],
    "credential_rotation": ["CC6.1", "CC6.2"],
}

# Map each SOC2 control to feature(s) it depends on (reverse index).
_SOC2_TO_FEATURES: dict[str, list[str]] = {}
for _feat, _cids in _SHIELDOPS_TO_SOC2.items():
    for _cid in _cids:
        _SOC2_TO_FEATURES.setdefault(_cid, []).append(_feat)


class SOC2Mapper:
    """Maps ShieldOps platform features to SOC2 Type II controls."""

    def __init__(self) -> None:
        self._controls: dict[str, ComplianceControl] = {}
        self._active_features: set[str] = set()
        self._init_controls()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_controls(self) -> None:
        for defn in _SOC2_CRITERIA:
            ctrl = ComplianceControl(
                control_id=defn["control_id"],
                framework=ComplianceFramework.SOC2,
                category=defn["category"],
                title=defn["title"],
                description=defn["description"],
                status=ControlStatus.NOT_ASSESSED,
            )
            self._controls[ctrl.control_id] = ctrl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active_features(self, features: list[str]) -> None:
        """Register which ShieldOps features are currently active."""
        self._active_features = set(features)
        logger.info(
            "soc2_mapper.active_features_updated",
            count=len(features),
        )

    def list_controls(self) -> list[ComplianceControl]:
        """Return all SOC2 controls."""
        return list(self._controls.values())

    def get_control(self, control_id: str) -> ComplianceControl | None:
        """Return a single control by ID."""
        return self._controls.get(control_id)

    def map_shieldops_controls(
        self,
    ) -> dict[str, list[str]]:
        """Map ShieldOps features to SOC2 control IDs.

        Returns a dict of ``{feature: [control_ids]}``.
        """
        return dict(_SHIELDOPS_TO_SOC2)

    async def assess_control(self, control_id: str) -> ComplianceControl:
        """Auto-assess a control by checking active features.

        If every required feature for this control is active the
        status is set to ``compliant``; if some are active it is
        ``partial``; otherwise ``non_compliant``.
        """
        ctrl = self._controls.get(control_id)
        if ctrl is None:
            raise ValueError(f"Unknown SOC2 control: {control_id}")

        required_features = _SOC2_TO_FEATURES.get(control_id, [])
        if not required_features:
            ctrl.status = ControlStatus.NOT_APPLICABLE
            ctrl.notes = "No mapped ShieldOps feature."
            ctrl.last_assessed = time.time()
            logger.info(
                "soc2_mapper.assess_control",
                control_id=control_id,
                status=ctrl.status,
            )
            return ctrl

        active = [f for f in required_features if f in self._active_features]
        ratio = len(active) / len(required_features)

        if ratio == 1.0:
            ctrl.status = ControlStatus.COMPLIANT
            ctrl.notes = f"All features active: {', '.join(active)}"
            ctrl.remediation_steps = []
        elif ratio > 0:
            ctrl.status = ControlStatus.PARTIAL
            missing = set(required_features) - set(active)
            ctrl.notes = f"Active: {', '.join(active)}. Missing: {', '.join(missing)}"
            ctrl.remediation_steps = [f"Enable feature: {f}" for f in missing]
        else:
            ctrl.status = ControlStatus.NON_COMPLIANT
            ctrl.notes = "No required features are active."
            ctrl.remediation_steps = [f"Enable feature: {f}" for f in required_features]

        ctrl.last_assessed = time.time()
        ctrl.assessor = "shieldops-auto-assessor"
        logger.info(
            "soc2_mapper.assess_control",
            control_id=control_id,
            status=ctrl.status,
            ratio=ratio,
        )
        return ctrl

    async def assess_all(self) -> list[ComplianceControl]:
        """Assess every SOC2 control."""
        results: list[ComplianceControl] = []
        for cid in self._controls:
            results.append(await self.assess_control(cid))
        return results

    async def get_gap_analysis(
        self,
    ) -> list[dict[str, Any]]:
        """Return controls that are non_compliant or not_assessed.

        Each entry includes the control, its required features,
        and remediation suggestions.
        """
        gaps: list[dict[str, Any]] = []
        for ctrl in self._controls.values():
            if ctrl.status not in (
                ControlStatus.NON_COMPLIANT,
                ControlStatus.NOT_ASSESSED,
            ):
                continue
            required = _SOC2_TO_FEATURES.get(ctrl.control_id, [])
            missing = [f for f in required if f not in self._active_features]
            gaps.append(
                {
                    "control_id": ctrl.control_id,
                    "title": ctrl.title,
                    "category": ctrl.category,
                    "status": ctrl.status,
                    "required_features": required,
                    "missing_features": missing,
                    "remediation": [f"Enable feature: {f}" for f in missing]
                    if missing
                    else ["Perform manual assessment"],
                }
            )

        logger.info(
            "soc2_mapper.gap_analysis",
            total_gaps=len(gaps),
        )
        return gaps
