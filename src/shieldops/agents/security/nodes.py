"""Node implementations for the Security Agent LangGraph workflow.

Each node is an async function that:
1. Scans or queries security data via the SecurityToolkit
2. Uses the LLM to assess and prioritize findings
3. Updates the security scan state with results
4. Records its reasoning step in the audit trail
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from shieldops.agents.security.models import (
    CVEFinding,
    ComplianceControl,
    CredentialStatus,
    SecurityPosture,
    SecurityScanState,
    SecurityStep,
)
from shieldops.agents.security.prompts import (
    SYSTEM_COMPLIANCE_ASSESSMENT,
    SYSTEM_CREDENTIAL_ASSESSMENT,
    SYSTEM_POSTURE_SYNTHESIS,
    SYSTEM_VULNERABILITY_ASSESSMENT,
    ComplianceAssessmentResult,
    CredentialAssessmentResult,
    SecurityPostureResult,
    VulnerabilityAssessmentResult,
)
from shieldops.agents.security.tools import SecurityToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: SecurityToolkit | None = None


def set_toolkit(toolkit: SecurityToolkit | None) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> SecurityToolkit:
    if _toolkit is None:
        return SecurityToolkit()
    return _toolkit


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)


async def scan_vulnerabilities(state: SecurityScanState) -> dict:
    """Scan target resources for known CVEs."""
    start = datetime.now(timezone.utc)
    toolkit = _get_toolkit()

    logger.info(
        "security_scanning_cves",
        scan_id=state.scan_id,
        targets=len(state.target_resources),
    )

    resources = state.target_resources
    if not resources:
        resources = await toolkit.get_resource_list(state.target_environment)

    scan_data = await toolkit.scan_cves(resources)

    findings: list[CVEFinding] = []
    for raw in scan_data.get("findings", [])[:100]:
        findings.append(CVEFinding(
            cve_id=raw.get("cve_id", "UNKNOWN"),
            severity=raw.get("severity", "medium"),
            cvss_score=raw.get("cvss_score", 0.0),
            package_name=raw.get("package_name", "unknown"),
            installed_version=raw.get("installed_version", "unknown"),
            fixed_version=raw.get("fixed_version"),
            affected_resource=raw.get("affected_resource", "unknown"),
            description=raw.get("description", ""),
        ))

    step = SecurityStep(
        step_number=1,
        action="scan_vulnerabilities",
        input_summary=f"Scanning {len(resources)} resources for CVEs",
        output_summary=(
            f"Found {scan_data['total_findings']} CVEs: "
            f"{scan_data['critical_count']} critical, {scan_data['high_count']} high. "
            f"{scan_data['patches_available']} patches available"
        ),
        duration_ms=_elapsed_ms(start),
        tool_used="cve_scanner",
    )

    return {
        "scan_start": start,
        "cve_findings": findings,
        "critical_cve_count": scan_data["critical_count"],
        "patches_available": scan_data["patches_available"],
        "reasoning_chain": [step],
        "current_step": "scan_vulnerabilities",
    }


async def assess_findings(state: SecurityScanState) -> dict:
    """Use LLM to assess vulnerability findings and prioritize patches."""
    start = datetime.now(timezone.utc)

    logger.info(
        "security_assessing_findings",
        scan_id=state.scan_id,
        cve_count=len(state.cve_findings),
    )

    output_summary = f"{len(state.cve_findings)} CVEs found, {state.critical_cve_count} critical"

    if state.cve_findings:
        context_lines = [
            "## CVE Scan Results",
            f"Total findings: {len(state.cve_findings)}",
            f"Critical: {state.critical_cve_count}",
            f"Patches available: {state.patches_available}",
            "",
            "## CVE Details",
        ]
        for cve in state.cve_findings[:30]:
            fixed = f"→ {cve.fixed_version}" if cve.fixed_version else "NO FIX"
            context_lines.append(
                f"- {cve.cve_id} ({cve.severity}, CVSS {cve.cvss_score}): "
                f"{cve.package_name} {cve.installed_version} {fixed} "
                f"on {cve.affected_resource}"
            )

        try:
            assessment: VulnerabilityAssessmentResult = await llm_structured(
                system_prompt=SYSTEM_VULNERABILITY_ASSESSMENT,
                user_prompt="\n".join(context_lines),
                schema=VulnerabilityAssessmentResult,
            )
            output_summary = (
                f"{assessment.summary}. Risk: {assessment.risk_level}. "
                f"Priority patches: {len(assessment.patch_priority)}"
            )
        except Exception as e:
            logger.error("llm_vulnerability_assessment_failed", error=str(e))

    step = SecurityStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_findings",
        input_summary=f"Assessing {len(state.cve_findings)} CVE findings",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_findings",
    }


async def check_credentials(state: SecurityScanState) -> dict:
    """Check credential expiry status across managed services."""
    start = datetime.now(timezone.utc)
    toolkit = _get_toolkit()

    logger.info(
        "security_checking_credentials",
        scan_id=state.scan_id,
        environment=state.target_environment.value,
    )

    cred_data = await toolkit.check_credentials(environment=state.target_environment)

    statuses: list[CredentialStatus] = []
    now = datetime.now(timezone.utc)

    for raw in cred_data.get("expired", []) + cred_data.get("expiring_soon", []):
        expires_at = raw.get("expires_at")
        days_left = None
        if expires_at:
            days_left = max(0, (expires_at - now).days)

        statuses.append(CredentialStatus(
            credential_id=raw.get("credential_id", "unknown"),
            credential_type=raw.get("credential_type", "unknown"),
            service=raw.get("service", "unknown"),
            environment=state.target_environment,
            expires_at=expires_at,
            days_until_expiry=days_left,
            last_rotated=raw.get("last_rotated"),
            needs_rotation=True,
        ))

    # LLM assessment
    output_summary = (
        f"Credentials: {cred_data['total_credentials']} total, "
        f"{cred_data['expired_count']} expired, "
        f"{cred_data['expiring_soon_count']} expiring soon"
    )

    if statuses:
        context_lines = [
            "## Credential Status",
            f"Total tracked: {cred_data['total_credentials']}",
            f"Expired: {cred_data['expired_count']}",
            f"Expiring within 7 days: {cred_data['expiring_soon_count']}",
            "",
            "## Credentials Needing Rotation",
        ]
        for cred in statuses[:20]:
            context_lines.append(
                f"- {cred.credential_id} ({cred.credential_type}): "
                f"service={cred.service}, "
                f"days_left={cred.days_until_expiry}"
            )

        try:
            assessment: CredentialAssessmentResult = await llm_structured(
                system_prompt=SYSTEM_CREDENTIAL_ASSESSMENT,
                user_prompt="\n".join(context_lines),
                schema=CredentialAssessmentResult,
            )
            output_summary = (
                f"{assessment.summary}. "
                f"Urgent rotations: {len(assessment.urgent_rotations)}"
            )
        except Exception as e:
            logger.error("llm_credential_assessment_failed", error=str(e))

    step = SecurityStep(
        step_number=len(state.reasoning_chain) + 1,
        action="check_credentials",
        input_summary=f"Checking credentials in {state.target_environment.value}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="credential_store + llm",
    )

    return {
        "credential_statuses": statuses,
        "credentials_needing_rotation": len(statuses),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "check_credentials",
    }


async def evaluate_compliance(state: SecurityScanState) -> dict:
    """Evaluate compliance posture against configured frameworks."""
    start = datetime.now(timezone.utc)
    toolkit = _get_toolkit()

    frameworks = state.compliance_frameworks or ["soc2"]

    logger.info(
        "security_evaluating_compliance",
        scan_id=state.scan_id,
        frameworks=frameworks,
    )

    all_controls: list[ComplianceControl] = []
    total_passing = 0
    total_checked = 0

    for framework in frameworks:
        compliance_data = await toolkit.check_compliance(framework)

        for raw in compliance_data.get("controls", []):
            all_controls.append(ComplianceControl(
                control_id=raw.get("control_id", ""),
                framework=framework,
                title=raw.get("title", ""),
                status=raw.get("status", "not_applicable"),
                severity=raw.get("severity", "medium"),
                evidence=raw.get("evidence", []),
            ))

        total_passing += compliance_data.get("passing", 0)
        total_checked += compliance_data.get("controls_checked", 0)

    compliance_score = (total_passing / total_checked * 100) if total_checked else 0.0
    output_summary = (
        f"Compliance: {total_passing}/{total_checked} controls passing "
        f"({compliance_score:.1f}%) across {frameworks}"
    )

    # LLM assessment
    if all_controls:
        context_lines = [
            "## Compliance Evaluation",
            f"Frameworks: {', '.join(frameworks)}",
            f"Total controls: {total_checked}",
            f"Passing: {total_passing}",
            f"Score: {compliance_score:.1f}%",
            "",
            "## Control Results",
        ]
        failing = [c for c in all_controls if c.status == "failing"]
        for control in failing[:20]:
            context_lines.append(
                f"- FAIL {control.control_id}: {control.title} ({control.severity})"
            )

        if not failing:
            context_lines.append("All controls passing.")

        try:
            assessment: ComplianceAssessmentResult = await llm_structured(
                system_prompt=SYSTEM_COMPLIANCE_ASSESSMENT,
                user_prompt="\n".join(context_lines),
                schema=ComplianceAssessmentResult,
            )
            compliance_score = assessment.overall_score
            output_summary = (
                f"{assessment.summary}. Score: {compliance_score:.1f}%. "
                f"Failing: {len(assessment.failing_controls)}, "
                f"Auto-remediable: {len(assessment.auto_remediable)}"
            )
        except Exception as e:
            logger.error("llm_compliance_assessment_failed", error=str(e))

    step = SecurityStep(
        step_number=len(state.reasoning_chain) + 1,
        action="evaluate_compliance",
        input_summary=f"Evaluating compliance for {frameworks}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="compliance_checker + llm",
    )

    return {
        "compliance_controls": all_controls,
        "compliance_score": compliance_score,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "evaluate_compliance",
    }


async def synthesize_posture(state: SecurityScanState) -> dict:
    """Synthesize all findings into an overall security posture assessment."""
    start = datetime.now(timezone.utc)

    logger.info("security_synthesizing_posture", scan_id=state.scan_id)

    # Build context from all prior findings
    context_lines = [
        "## Vulnerability Summary",
        f"CVEs found: {len(state.cve_findings)}",
        f"Critical CVEs: {state.critical_cve_count}",
        f"Patches available: {state.patches_available}",
        "",
        "## Credential Health",
        f"Credentials needing rotation: {state.credentials_needing_rotation}",
        "",
        "## Compliance Status",
        f"Compliance score: {state.compliance_score:.1f}%",
        f"Controls evaluated: {len(state.compliance_controls)}",
        f"Failing controls: {sum(1 for c in state.compliance_controls if c.status == 'failing')}",
        "",
        "## Investigation Chain",
    ]
    for step in state.reasoning_chain:
        context_lines.append(f"Step {step.step_number} ({step.action}): {step.output_summary}")

    # Default posture from raw data
    raw_score = 100.0
    if state.critical_cve_count > 0:
        raw_score -= min(40, state.critical_cve_count * 10)
    if state.credentials_needing_rotation > 0:
        raw_score -= min(20, state.credentials_needing_rotation * 5)
    raw_score = max(0, min(100, raw_score * (state.compliance_score / 100) if state.compliance_score else raw_score))

    posture = SecurityPosture(
        overall_score=raw_score,
        critical_cves=state.critical_cve_count,
        high_cves=sum(1 for c in state.cve_findings if c.severity == "high"),
        pending_patches=state.patches_available,
        credentials_expiring_soon=state.credentials_needing_rotation,
        compliance_scores={
            fw: state.compliance_score
            for fw in (state.compliance_frameworks or ["soc2"])
        },
    )

    output_summary = f"Security posture score: {raw_score:.1f}/100"

    try:
        assessment: SecurityPostureResult = await llm_structured(
            system_prompt=SYSTEM_POSTURE_SYNTHESIS,
            user_prompt="\n".join(context_lines),
            schema=SecurityPostureResult,
        )
        posture.overall_score = assessment.overall_score
        posture.top_risks = assessment.top_risks[:5]
        output_summary = (
            f"Score: {assessment.overall_score:.1f}/100. "
            f"{assessment.summary[:200]}"
        )
    except Exception as e:
        logger.error("llm_posture_synthesis_failed", error=str(e))

    step = SecurityStep(
        step_number=len(state.reasoning_chain) + 1,
        action="synthesize_posture",
        input_summary="Synthesizing overall security posture",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "posture": posture,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "scan_duration_ms": int(
            (datetime.now(timezone.utc) - state.scan_start).total_seconds() * 1000
        ) if state.scan_start else 0,
    }
