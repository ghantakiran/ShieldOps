"""Predefined periodic jobs for ShieldOps agents.

Each function follows the same contract:
  - Accept its runner dependency as a keyword argument (may be ``None``).
  - Accept ``**kwargs`` so the scheduler can pass extra config.
  - Return silently when the runner is unavailable.
  - Log start/completion using structlog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from shieldops.agents.cost.runner import CostRunner
    from shieldops.agents.learning.runner import LearningRunner
    from shieldops.agents.security.drift import DriftDetector
    from shieldops.agents.security.runner import SecurityRunner

logger = structlog.get_logger()


async def nightly_learning_cycle(
    learning_runner: LearningRunner | None = None,
    **kwargs: Any,
) -> None:
    """Run a full learning cycle -- typically nightly (every 24 h).

    Analyses the last 7 days of incident outcomes to discover patterns,
    recommend playbook updates, and refine alert thresholds.
    """
    if learning_runner is None:
        logger.warning("nightly_learning_skipped", reason="no runner provided")
        return

    logger.info("nightly_learning_started")
    result = await learning_runner.learn(learning_type="full", period="7d")
    logger.info(
        "nightly_learning_completed",
        learning_id=result.learning_id,
        incidents=result.total_incidents_analyzed,
        patterns=len(result.pattern_insights),
    )


async def periodic_security_scan(
    security_runner: SecurityRunner | None = None,
    environment: str = "production",
    **kwargs: Any,
) -> None:
    """Run a security scan -- typically every 6 hours.

    Performs CVE scanning, credential rotation checks, and compliance
    evaluation for the specified environment.
    """
    if security_runner is None:
        logger.warning("security_scan_skipped", reason="no runner provided")
        return

    from shieldops.models.base import Environment

    try:
        env = Environment(environment)
    except ValueError:
        logger.warning(
            "security_scan_invalid_environment",
            environment=environment,
            fallback="production",
        )
        env = Environment.PRODUCTION

    logger.info("periodic_security_scan_started", environment=env.value)
    result = await security_runner.scan(
        scan_type="full",
        environment=env,
    )
    logger.info(
        "periodic_security_scan_completed",
        scan_id=result.scan_id,
        cve_count=len(result.cve_findings),
    )


async def daily_cost_analysis(
    cost_runner: CostRunner | None = None,
    environment: str = "production",
    **kwargs: Any,
) -> None:
    """Run cost analysis -- typically daily.

    Identifies cost anomalies, optimization opportunities, and potential
    savings across all services in the target environment.
    """
    if cost_runner is None:
        logger.warning("cost_analysis_skipped", reason="no runner provided")
        return

    from shieldops.models.base import Environment

    try:
        env = Environment(environment)
    except ValueError:
        logger.warning(
            "cost_analysis_invalid_environment",
            environment=environment,
            fallback="production",
        )
        env = Environment.PRODUCTION

    logger.info("daily_cost_analysis_started", environment=env.value)
    result = await cost_runner.analyze(environment=env)
    logger.info(
        "daily_cost_analysis_completed",
        analysis_id=result.analysis_id,
    )


async def sla_check_job(
    repository: Any | None = None,
    **kwargs: Any,
) -> None:
    """Check SLA compliance for all open vulnerabilities -- hourly."""
    if repository is None:
        logger.warning("sla_check_skipped", reason="no repository")
        return

    from shieldops.vulnerability.sla_engine import SLAEngine

    logger.info("sla_check_started")
    engine = SLAEngine(repository=repository)
    result = await engine.check_all_sla_compliance()
    logger.info(
        "sla_check_completed",
        checked=result.get("checked", 0),
        newly_breached=result.get("newly_breached", 0),
    )


async def vulnerability_dedup_job(
    repository: Any | None = None,
    **kwargs: Any,
) -> None:
    """Deduplicate vulnerability records -- daily."""
    if repository is None:
        logger.warning("vuln_dedup_skipped", reason="no repository")
        return

    from shieldops.vulnerability.lifecycle import VulnerabilityLifecycleManager

    logger.info("vuln_dedup_started")
    mgr = VulnerabilityLifecycleManager(repository=repository)
    result = await mgr.deduplicate_findings()
    logger.info("vuln_dedup_completed", deduplicated=result.get("deduplicated", 0))


async def daily_security_newsletter(
    repository: Any | None = None,
    notification_dispatcher: Any | None = None,
    **kwargs: Any,
) -> None:
    """Send daily security digest -- runs every 24 hours."""
    if repository is None:
        logger.warning("daily_newsletter_skipped", reason="no repository")
        return

    from shieldops.vulnerability.newsletter import SecurityNewsletterService

    logger.info("daily_newsletter_started")
    service = SecurityNewsletterService(
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    digest = await service.generate_daily_digest()
    result = await service.send_digest(digest)
    logger.info(
        "daily_newsletter_completed",
        sent=result.get("sent", False),
        recipients=result.get("recipients", 0),
    )


async def weekly_security_newsletter(
    repository: Any | None = None,
    notification_dispatcher: Any | None = None,
    **kwargs: Any,
) -> None:
    """Send weekly security summary -- runs every 7 days."""
    if repository is None:
        logger.warning("weekly_newsletter_skipped", reason="no repository")
        return

    from shieldops.vulnerability.newsletter import SecurityNewsletterService

    logger.info("weekly_newsletter_started")
    service = SecurityNewsletterService(
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    digest = await service.generate_weekly_digest()
    result = await service.send_digest(digest)
    logger.info(
        "weekly_newsletter_completed",
        sent=result.get("sent", False),
        recipients=result.get("recipients", 0),
    )


async def escalation_check_job(
    repository: Any | None = None,
    notification_dispatcher: Any | None = None,
    **kwargs: Any,
) -> None:
    """Check escalation conditions -- runs hourly with SLA check."""
    if repository is None:
        logger.warning("escalation_check_skipped", reason="no repository")
        return

    from shieldops.vulnerability.escalation import EscalationEngine

    logger.info("escalation_check_started")
    engine = EscalationEngine(
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    result = await engine.check_and_escalate()
    logger.info(
        "escalation_check_completed",
        escalations=result.get("escalations_triggered", 0),
    )


async def periodic_drift_scan(
    drift_detector: DriftDetector | None = None,
    environment: str = "production",
    tfstate_path: str | None = None,
    **kwargs: Any,
) -> None:
    """Run a Terraform drift scan -- typically every 4-6 hours.

    Compares Terraform state files against live infrastructure to detect
    configuration drift across all registered providers.
    """
    if drift_detector is None:
        logger.warning("drift_scan_skipped", reason="no detector provided")
        return

    from shieldops.agents.security.drift import DriftScanRequest

    logger.info(
        "periodic_drift_scan_started",
        environment=environment,
        tfstate_path=tfstate_path,
    )
    request = DriftScanRequest(
        tfstate_path=tfstate_path,
        environment=environment,
    )
    report = await drift_detector.scan(request)
    logger.info(
        "periodic_drift_scan_completed",
        scan_id=report.scan_id,
        total_resources=report.total_resources,
        drifted_resources=report.drifted_resources,
        drift_items=len(report.drift_items),
    )
