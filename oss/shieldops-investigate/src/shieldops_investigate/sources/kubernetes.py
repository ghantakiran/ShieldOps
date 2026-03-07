"""Kubernetes data source for pod status, events, and deployment history.

Uses ``kubernetes-asyncio`` to query the cluster for investigation signals.
Falls back gracefully when no kubeconfig is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

# Lazy-import kubernetes_asyncio so the library can be loaded without a
# cluster present (useful for testing, docs, and Prometheus-only mode).
_k8s_available = True
try:
    from kubernetes_asyncio import client as k8s_client  # type: ignore[import-untyped]
    from kubernetes_asyncio import config as k8s_config  # type: ignore[import-untyped]
except ImportError:
    _k8s_available = False


# ---------------------------------------------------------------------------
# Lightweight result types
# ---------------------------------------------------------------------------


@dataclass
class PodStatus:
    """Snapshot of a single pod's state."""

    name: str
    namespace: str
    phase: str  # Running, Pending, Succeeded, Failed, Unknown
    ready: bool
    restart_count: int
    conditions: list[dict[str, Any]] = field(default_factory=list)
    container_statuses: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class K8sEvent:
    """A Kubernetes event relevant to the investigation."""

    reason: str
    message: str
    involved_object: str
    timestamp: datetime | None
    event_type: str  # Normal, Warning
    count: int = 1


@dataclass
class Deployment:
    """Summary of a Kubernetes Deployment or ReplicaSet rollout."""

    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    updated_at: datetime | None
    image: str = ""


@dataclass
class NodeCondition:
    """A node-level condition (Ready, MemoryPressure, DiskPressure, etc.)."""

    node_name: str
    condition_type: str
    status: str
    reason: str
    message: str


# ---------------------------------------------------------------------------
# Source implementation
# ---------------------------------------------------------------------------


class KubernetesSource:
    """Async interface to the Kubernetes API for investigation data.

    Args:
        kubeconfig_path: Path to a kubeconfig file. When *None*, the
            in-cluster config is attempted.
    """

    def __init__(self, kubeconfig_path: str | None = None) -> None:
        self._kubeconfig_path = kubeconfig_path
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Load the kubeconfig lazily on first use."""
        if self._loaded or not _k8s_available:
            return
        if self._kubeconfig_path:
            await k8s_config.load_kube_config(config_file=self._kubeconfig_path)
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                await k8s_config.load_kube_config()
        self._loaded = True

    # ------------------------------------------------------------------
    # Pod status
    # ------------------------------------------------------------------

    async def get_pod_status(
        self,
        namespace: str,
        label_selector: str = "",
    ) -> list[PodStatus]:
        """List pods and their status in the given namespace."""
        if not _k8s_available:
            logger.warning("kubernetes_asyncio_not_installed")
            return []

        await self._ensure_loaded()
        v1 = k8s_client.CoreV1Api()

        try:
            pods = await v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector,
            )
        finally:
            await v1.api_client.close()

        results: list[PodStatus] = []
        for pod in pods.items:
            cs = pod.status.container_statuses or []
            results.append(
                PodStatus(
                    name=pod.metadata.name,
                    namespace=namespace,
                    phase=pod.status.phase or "Unknown",
                    ready=all(getattr(c, "ready", False) for c in cs),
                    restart_count=sum(getattr(c, "restart_count", 0) for c in cs),
                    conditions=[
                        {
                            "type": cond.type,
                            "status": cond.status,
                            "reason": cond.reason or "",
                        }
                        for cond in (pod.status.conditions or [])
                    ],
                    container_statuses=[
                        {
                            "name": c.name,
                            "ready": c.ready,
                            "restart_count": c.restart_count,
                            "state": _extract_state(c.state),
                        }
                        for c in cs
                    ],
                )
            )

        return results

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def get_events(
        self,
        namespace: str,
        involved_object: str | None = None,
    ) -> list[K8sEvent]:
        """Fetch recent events, optionally filtered by involved object name."""
        if not _k8s_available:
            return []

        await self._ensure_loaded()
        v1 = k8s_client.CoreV1Api()

        try:
            events = await v1.list_namespaced_event(namespace=namespace)
        finally:
            await v1.api_client.close()

        results: list[K8sEvent] = []
        for ev in events.items:
            obj_name = getattr(ev.involved_object, "name", "")
            if involved_object and involved_object not in obj_name:
                continue
            results.append(
                K8sEvent(
                    reason=ev.reason or "",
                    message=ev.message or "",
                    involved_object=obj_name,
                    timestamp=_to_utc(ev.last_timestamp or ev.event_time),
                    event_type=ev.type or "Normal",
                    count=ev.count or 1,
                )
            )

        # Most recent first
        results.sort(key=lambda e: e.timestamp or datetime.min.replace(tzinfo=UTC), reverse=True)
        return results

    # ------------------------------------------------------------------
    # Deployments
    # ------------------------------------------------------------------

    async def get_recent_deployments(
        self,
        namespace: str,
        since_minutes: int = 60,
    ) -> list[Deployment]:
        """Return deployments that were updated within *since_minutes*."""
        if not _k8s_available:
            return []

        await self._ensure_loaded()
        apps = k8s_client.AppsV1Api()

        try:
            deploys = await apps.list_namespaced_deployment(namespace=namespace)
        finally:
            await apps.api_client.close()

        now = datetime.now(tz=UTC)
        results: list[Deployment] = []

        for d in deploys.items:
            conditions = d.status.conditions or []
            last_update: datetime | None = None
            for cond in conditions:
                ts = _to_utc(cond.last_update_time or cond.last_transition_time)
                if ts and (last_update is None or ts > last_update):
                    last_update = ts

            if last_update and (now - last_update).total_seconds() <= since_minutes * 60:
                image = ""
                if d.spec.template.spec.containers:
                    image = d.spec.template.spec.containers[0].image or ""
                results.append(
                    Deployment(
                        name=d.metadata.name,
                        namespace=namespace,
                        replicas=d.spec.replicas or 0,
                        ready_replicas=d.status.ready_replicas or 0,
                        updated_at=last_update,
                        image=image,
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Node conditions
    # ------------------------------------------------------------------

    async def get_node_conditions(self) -> list[NodeCondition]:
        """Return conditions for every node in the cluster."""
        if not _k8s_available:
            return []

        await self._ensure_loaded()
        v1 = k8s_client.CoreV1Api()

        try:
            nodes = await v1.list_node()
        finally:
            await v1.api_client.close()

        results: list[NodeCondition] = []
        for node in nodes.items:
            for cond in node.status.conditions or []:
                results.append(
                    NodeCondition(
                        node_name=node.metadata.name,
                        condition_type=cond.type,
                        status=cond.status,
                        reason=cond.reason or "",
                        message=cond.message or "",
                    )
                )

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_utc(ts: Any) -> datetime | None:  # noqa: ANN401
    """Normalize a K8s timestamp to a timezone-aware UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts
    return None


def _extract_state(state: Any) -> str:  # noqa: ANN401
    """Return a short human-readable container state string."""
    if state is None:
        return "unknown"
    if state.running:
        return "running"
    if state.waiting:
        return f"waiting: {state.waiting.reason or 'unknown'}"
    if state.terminated:
        return f"terminated: {state.terminated.reason or 'unknown'}"
    return "unknown"
