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
