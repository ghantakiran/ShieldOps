"""Investigation-to-remediation pipeline.

Connects the OSS investigation toolkit to the K8s remediation engine,
mapping ranked hypotheses to concrete remediation actions with policy
gates and rollback safety.
"""

from __future__ import annotations

from shieldops.pipeline.models import (
    PipelineRun,
    PipelineStatus,
    RemediationRecommendation,
)
from shieldops.pipeline.orchestrator import PipelineOrchestrator
from shieldops.pipeline.recommender import RemediationRecommender

__all__ = [
    "PipelineOrchestrator",
    "PipelineRun",
    "PipelineStatus",
    "RemediationRecommender",
    "RemediationRecommendation",
]
