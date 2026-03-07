"""Maps investigation hypotheses to concrete K8s remediation actions."""

from __future__ import annotations

from typing import Any

import structlog
from shieldops_investigate.models import InvestigationResult  # type: ignore[import-not-found]

from shieldops.pipeline.models import RemediationRecommendation
from shieldops.remediation.models import K8sActionType

logger = structlog.get_logger()

# Confidence threshold above which recommendations are auto-approved.
AUTO_APPROVE_THRESHOLD: float = 0.8

# Mapping from hypothesis title keywords to (action_type, default_params).
_HYPOTHESIS_ACTION_MAP: dict[
    str,
    tuple[K8sActionType, dict[str, Any]],
] = {
    "deployment regression": (
        K8sActionType.ROLLBACK_DEPLOYMENT,
        {},
    ),
    "memory leak": (
        K8sActionType.UPDATE_RESOURCE_LIMITS,
        {"memory_limit": "2Gi"},
    ),
    "oom": (
        K8sActionType.UPDATE_RESOURCE_LIMITS,
        {"memory_limit": "2Gi"},
    ),
    "crashloopbackoff": (
        K8sActionType.RESTART_DEPLOYMENT,
        {},
    ),
    "cpu resource exhaustion": (
        K8sActionType.SCALE_DEPLOYMENT,
        {"replicas": 3},
    ),
    "node issue": (
        K8sActionType.CORDON_NODE,
        {},
    ),
    "dns resolution issue": (
        K8sActionType.RESTART_DEPLOYMENT,
        {"target_override": "coredns"},
    ),
}

# Titles that indicate no automated remediation is possible.
_MANUAL_ONLY_TITLES: frozenset[str] = frozenset(
    {"image pull failure"},
)


class RemediationRecommender:
    """Translates investigation hypotheses into remediation recommendations.

    For each hypothesis in an ``InvestigationResult``, the recommender
    checks whether a known mapping exists and, if so, produces a
    ``RemediationRecommendation`` with the appropriate action type and
    default parameters.
    """

    def recommend(
        self,
        investigation_result: InvestigationResult,
    ) -> list[RemediationRecommendation]:
        """Generate remediation recommendations from investigation results.

        Args:
            investigation_result: The completed investigation containing
                ranked hypotheses.

        Returns:
            A list of ``RemediationRecommendation`` objects ordered by
            hypothesis confidence (highest first).
        """
        recommendations: list[RemediationRecommendation] = []
        service = investigation_result.service or "unknown"

        sorted_hypotheses = sorted(
            investigation_result.hypotheses,
            key=lambda h: h.confidence,
            reverse=True,
        )

        for hypothesis in sorted_hypotheses:
            title_lower = hypothesis.title.lower()

            # Skip hypotheses that require manual intervention.
            if title_lower in _MANUAL_ONLY_TITLES:
                logger.info(
                    "hypothesis_manual_only",
                    title=hypothesis.title,
                    confidence=hypothesis.confidence,
                )
                continue

            # Find a matching action mapping.
            matched = False
            for keyword, (action_type, default_params) in _HYPOTHESIS_ACTION_MAP.items():
                if keyword in title_lower:
                    target = default_params.pop("target_override", service)
                    rec = RemediationRecommendation(
                        hypothesis_title=hypothesis.title,
                        confidence=hypothesis.confidence,
                        action_type=action_type,
                        target_resource=target,
                        parameters=dict(default_params),
                        auto_approve=(hypothesis.confidence > AUTO_APPROVE_THRESHOLD),
                    )
                    recommendations.append(rec)
                    logger.info(
                        "recommendation_generated",
                        title=hypothesis.title,
                        action=action_type,
                        confidence=hypothesis.confidence,
                        auto_approve=rec.auto_approve,
                    )
                    matched = True
                    break

            if not matched:
                logger.info(
                    "hypothesis_no_mapping",
                    title=hypothesis.title,
                    confidence=hypothesis.confidence,
                )

        return recommendations
