"""Pre-built async task functions for common heavy operations.

Each function is a thin wrapper around an existing runner/service that
logs start/end and returns a summary dict suitable for storing as a
``TaskDefinition.result``.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def run_compliance_audit(engine: Any) -> dict[str, Any]:
    """Execute a full SOC2 compliance audit.

    Args:
        engine: A ``SOC2ComplianceEngine`` instance.

    Returns:
        Summary dict with audit results.
    """
    logger.info("task_compliance_audit_started")
    report = await engine.run_audit()
    summary = {
        "audit_id": getattr(report, "audit_id", None),
        "total_controls": getattr(report, "total_controls", 0),
        "passed": getattr(report, "passed", 0),
        "failed": getattr(report, "failed", 0),
        "warnings": getattr(report, "warnings", 0),
    }
    logger.info("task_compliance_audit_completed", **summary)
    return summary


async def run_bulk_export(
    repository: Any,
    entity_type: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Export entities in bulk (investigations, remediations, etc.).

    Args:
        repository: A ``Repository`` instance with export capabilities.
        entity_type: The entity type to export (e.g. ``"investigations"``).
        filters: Optional filter criteria.

    Returns:
        Summary dict with export metadata.
    """
    logger.info(
        "task_bulk_export_started",
        entity_type=entity_type,
        filters=filters,
    )
    rows = await repository.export_entities(entity_type, filters or {})
    count = len(rows) if isinstance(rows, list) else 0
    summary = {
        "entity_type": entity_type,
        "exported_count": count,
    }
    logger.info("task_bulk_export_completed", **summary)
    return summary


async def run_git_sync(git_sync: Any) -> dict[str, Any]:
    """Synchronize playbooks from the configured git repository.

    Args:
        git_sync: A ``GitPlaybookSync`` instance.

    Returns:
        Summary dict with sync results.
    """
    logger.info("task_git_sync_started")
    result = await git_sync.sync()
    summary = {
        "commit": getattr(result, "commit", None),
        "added": getattr(result, "added", 0),
        "updated": getattr(result, "updated", 0),
        "removed": getattr(result, "removed", 0),
    }
    logger.info("task_git_sync_completed", **summary)
    return summary


async def run_cost_analysis(
    cost_runner: Any,
    environment: str = "production",
) -> dict[str, Any]:
    """Execute a cost analysis scan for the given environment.

    Args:
        cost_runner: A ``CostRunner`` instance.
        environment: Target environment name.

    Returns:
        Summary dict with analysis metadata.
    """
    from shieldops.models.base import Environment

    logger.info("task_cost_analysis_started", environment=environment)
    try:
        env = Environment(environment)
    except ValueError:
        env = Environment.PRODUCTION

    result = await cost_runner.analyze(environment=env)
    summary = {
        "analysis_id": getattr(result, "analysis_id", None),
        "environment": environment,
    }
    logger.info("task_cost_analysis_completed", **summary)
    return summary


async def run_learning_cycle(learning_runner: Any) -> dict[str, Any]:
    """Execute a full learning cycle.

    Args:
        learning_runner: A ``LearningRunner`` instance.

    Returns:
        Summary dict with learning outcomes.
    """
    logger.info("task_learning_cycle_started")
    result = await learning_runner.learn(learning_type="full", period="7d")
    summary = {
        "learning_id": getattr(result, "learning_id", None),
        "incidents_analyzed": getattr(result, "total_incidents_analyzed", 0),
        "patterns_found": len(getattr(result, "pattern_insights", [])),
    }
    logger.info("task_learning_cycle_completed", **summary)
    return summary
