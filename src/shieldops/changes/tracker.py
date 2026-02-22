"""Deployment change tracker and incident correlation engine.

Records change/deployment events from multiple sources (Kubernetes, GitHub,
CI/CD pipelines, manual entries) and correlates them with incidents using
a time-window scoring algorithm.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Valid enumerations (kept as plain sets for validation)
# ---------------------------------------------------------------------------

VALID_SOURCES = {"kubernetes", "github", "cicd", "manual"}
VALID_CHANGE_TYPES = {"deployment", "config_change", "rollback", "scale"}
VALID_BLAST_RADII = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"in_progress", "completed", "failed", "rolled_back"}


def _generate_change_id() -> str:
    """Generate a unique change ID prefixed with ``chg-``."""
    return f"chg-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChangeRecord(BaseModel):
    """A single deployment or infrastructure change event."""

    id: str = Field(default_factory=_generate_change_id)
    source: str  # kubernetes | github | cicd | manual
    service: str
    environment: str
    change_type: str  # deployment | config_change | rollback | scale
    description: str
    deployed_by: str = ""
    commit_sha: str = ""
    version: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "in_progress"
    metadata: dict[str, Any] = Field(default_factory=dict)
    blast_radius: str = "low"


class CorrelationResult(BaseModel):
    """Correlation between an incident and a change event."""

    incident_id: str
    change_id: str
    correlation_score: float  # 0.0 - 1.0
    time_delta_minutes: float
    same_service: bool
    same_environment: bool
    factors: list[str]


class ChangeTimeline(BaseModel):
    """Timeline view of recent changes."""

    changes: list[ChangeRecord]
    total: int
    time_range: dict[str, str]


class RecordChangeRequest(BaseModel):
    """Request body for recording a new change."""

    source: str
    service: str
    environment: str
    change_type: str
    description: str
    deployed_by: str = ""
    commit_sha: str = ""
    version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    blast_radius: str = "low"


# ---------------------------------------------------------------------------
# ChangeTracker
# ---------------------------------------------------------------------------


class ChangeTracker:
    """In-memory change tracker with deployment correlation capabilities.

    Stores change records and provides a scoring algorithm to correlate
    changes with incidents based on time proximity, service overlap,
    environment match, recency, and blast radius.
    """

    def __init__(self) -> None:
        self._changes: dict[str, ChangeRecord] = {}

    # -- Recording ----------------------------------------------------------

    def record_change(self, request: RecordChangeRequest) -> ChangeRecord:
        """Create and store a new change record from a request payload."""
        record = ChangeRecord(
            source=request.source,
            service=request.service,
            environment=request.environment,
            change_type=request.change_type,
            description=request.description,
            deployed_by=request.deployed_by,
            commit_sha=request.commit_sha,
            version=request.version,
            metadata=request.metadata,
            blast_radius=request.blast_radius,
        )
        self._changes[record.id] = record
        logger.info(
            "change_recorded",
            change_id=record.id,
            source=record.source,
            service=record.service,
            environment=record.environment,
        )
        return record

    def complete_change(
        self,
        change_id: str,
        status: str = "completed",
    ) -> ChangeRecord | None:
        """Mark an existing change as completed (or failed/rolled_back)."""
        record = self._changes.get(change_id)
        if record is None:
            return None
        record.status = status
        record.completed_at = datetime.now(UTC)
        logger.info("change_completed", change_id=change_id, status=status)
        return record

    def get_change(self, change_id: str) -> ChangeRecord | None:
        """Return a single change record by ID, or ``None``."""
        return self._changes.get(change_id)

    def list_changes(
        self,
        service: str | None = None,
        environment: str | None = None,
        limit: int = 50,
    ) -> list[ChangeRecord]:
        """List changes with optional service/environment filters, newest first."""
        results = list(self._changes.values())
        if service is not None:
            results = [c for c in results if c.service == service]
        if environment is not None:
            results = [c for c in results if c.environment == environment]
        results.sort(key=lambda c: c.started_at, reverse=True)
        return results[:limit]

    # -- Timeline -----------------------------------------------------------

    def get_timeline(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> ChangeTimeline:
        """Build a timeline of changes within an optional time range."""
        changes = list(self._changes.values())
        if start is not None:
            changes = [c for c in changes if c.started_at >= start]
        if end is not None:
            changes = [c for c in changes if c.started_at <= end]
        changes.sort(key=lambda c: c.started_at, reverse=True)

        time_range: dict[str, str] = {}
        if changes:
            time_range["start"] = changes[-1].started_at.isoformat()
            time_range["end"] = changes[0].started_at.isoformat()
        return ChangeTimeline(
            changes=changes,
            total=len(changes),
            time_range=time_range,
        )

    # -- Correlation --------------------------------------------------------

    def correlate_with_incident(
        self,
        incident_id: str,
        incident_service: str,
        incident_env: str,
        incident_time: datetime,
        time_window_minutes: int = 60,
    ) -> list[CorrelationResult]:
        """Find changes within a time window and score their correlation.

        Scoring algorithm:
          - Base score: 0.3 (change falls within the time window)
          - +0.3 if the change targets the same service
          - +0.2 if the change targets the same environment
          - +0.1 if the change is recent (within 15 minutes of incident)
          - +0.1 if the change has high or critical blast_radius

        Results are sorted by score descending.
        """
        results: list[CorrelationResult] = []

        for change in self._changes.values():
            delta = abs((incident_time - change.started_at).total_seconds()) / 60.0

            # Skip changes outside the window
            if delta > time_window_minutes:
                continue

            score = 0.3
            factors: list[str] = ["within_time_window"]

            same_service = change.service == incident_service
            if same_service:
                score += 0.3
                factors.append("same_service")

            same_env = change.environment == incident_env
            if same_env:
                score += 0.2
                factors.append("same_environment")

            if delta <= 15.0:
                score += 0.1
                factors.append("recent_change")

            if change.blast_radius in {"high", "critical"}:
                score += 0.1
                factors.append("high_blast_radius")

            # Cap at 1.0
            score = min(score, 1.0)

            results.append(
                CorrelationResult(
                    incident_id=incident_id,
                    change_id=change.id,
                    correlation_score=round(score, 2),
                    time_delta_minutes=round(delta, 2),
                    same_service=same_service,
                    same_environment=same_env,
                    factors=factors,
                )
            )

        results.sort(key=lambda r: r.correlation_score, reverse=True)
        return results

    # -- Blast radius estimation --------------------------------------------

    def estimate_blast_radius(
        self,
        service: str,
        change_type: str,
        environment: str,
    ) -> str:
        """Heuristic blast-radius estimation based on change context.

        Rules (evaluated in order):
          - production + deployment  -> "high"
          - production + rollback    -> "medium"
          - production + config_change -> "medium"
          - production + scale       -> "low"
          - staging (any)            -> "low"
          - config_change (non-prod) -> "medium"
          - rollback (non-prod)      -> "medium"
          - default                  -> "low"
        """
        env_lower = environment.lower()
        ct_lower = change_type.lower()

        if env_lower == "production":
            if ct_lower == "deployment":
                return "high"
            if ct_lower in {"rollback", "config_change"}:
                return "medium"
            return "low"

        if env_lower == "staging":
            return "low"

        # Non-prod, non-staging
        if ct_lower in {"config_change", "rollback"}:
            return "medium"

        return "low"

    # -- Source-specific parsers ---------------------------------------------

    def record_from_k8s_event(self, event: dict[str, Any]) -> ChangeRecord:
        """Parse a Kubernetes rollout event into a ChangeRecord."""
        metadata = event.get("metadata", {})
        spec = event.get("spec", {})
        record = ChangeRecord(
            source="kubernetes",
            service=metadata.get("name", "unknown"),
            environment=metadata.get("namespace", "default"),
            change_type="deployment",
            description=f"K8s rollout: {metadata.get('name', 'unknown')}",
            version=spec.get("template", {})
            .get("spec", {})
            .get("containers", [{}])[0]
            .get("image", ""),
            metadata={"k8s_event": event},
        )
        record.blast_radius = self.estimate_blast_radius(
            record.service,
            record.change_type,
            record.environment,
        )
        self._changes[record.id] = record
        logger.info(
            "k8s_change_recorded",
            change_id=record.id,
            service=record.service,
        )
        return record

    def record_from_github_webhook(self, payload: dict[str, Any]) -> ChangeRecord:
        """Parse a GitHub push or deployment webhook into a ChangeRecord."""
        repo = payload.get("repository", {})
        repo_name = repo.get("name", "unknown")

        # Deployment event
        if "deployment" in payload:
            deployment = payload["deployment"]
            record = ChangeRecord(
                source="github",
                service=repo_name,
                environment=deployment.get("environment", "production"),
                change_type="deployment",
                description=deployment.get("description", f"GitHub deployment: {repo_name}"),
                deployed_by=payload.get("sender", {}).get("login", ""),
                commit_sha=deployment.get("sha", ""),
                version=deployment.get("ref", ""),
                metadata={"github_payload": payload},
            )
        else:
            # Push event
            head_commit = payload.get("head_commit", {})
            pusher = payload.get("pusher", {})
            ref = payload.get("ref", "")
            record = ChangeRecord(
                source="github",
                service=repo_name,
                environment="production" if ref.endswith("/main") else "staging",
                change_type="deployment",
                description=head_commit.get("message", f"Push to {repo_name}"),
                deployed_by=pusher.get("name", ""),
                commit_sha=head_commit.get("id", ""),
                version=ref,
                metadata={"github_payload": payload},
            )

        record.blast_radius = self.estimate_blast_radius(
            record.service,
            record.change_type,
            record.environment,
        )
        self._changes[record.id] = record
        logger.info(
            "github_change_recorded",
            change_id=record.id,
            service=record.service,
        )
        return record

    def record_from_cicd(self, pipeline: dict[str, Any]) -> ChangeRecord:
        """Parse a CI/CD pipeline event into a ChangeRecord."""
        record = ChangeRecord(
            source="cicd",
            service=pipeline.get("project", "unknown"),
            environment=pipeline.get("environment", "staging"),
            change_type=pipeline.get("action", "deployment"),
            description=pipeline.get("name", "CI/CD pipeline run"),
            deployed_by=pipeline.get("triggered_by", ""),
            commit_sha=pipeline.get("commit_sha", ""),
            version=pipeline.get("version", ""),
            metadata={"cicd_pipeline": pipeline},
        )
        record.blast_radius = self.estimate_blast_radius(
            record.service,
            record.change_type,
            record.environment,
        )
        self._changes[record.id] = record
        logger.info(
            "cicd_change_recorded",
            change_id=record.id,
            service=record.service,
        )
        return record
