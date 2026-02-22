"""Change Tracking & Deployment Correlation module.

Correlates deployments (K8s rollouts, GitHub webhooks, CI/CD pipeline events)
with incidents to identify which changes most likely caused an outage.
"""

from shieldops.changes.tracker import (
    ChangeRecord,
    ChangeTimeline,
    ChangeTracker,
    CorrelationResult,
    RecordChangeRequest,
)

__all__ = [
    "ChangeRecord",
    "ChangeTimeline",
    "ChangeTracker",
    "CorrelationResult",
    "RecordChangeRequest",
]
