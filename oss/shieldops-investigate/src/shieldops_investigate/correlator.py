"""Signal correlator that turns raw metrics and K8s data into ranked hypotheses.

The correlator applies a set of deterministic rules to identify common
Kubernetes failure patterns. Each rule evaluates available evidence and
produces a :class:`~shieldops_investigate.models.Hypothesis` when its
conditions are met.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from shieldops_investigate.models import Evidence, EvidenceSource, Hypothesis

if TYPE_CHECKING:
    from shieldops_investigate.sources.kubernetes import Deployment, K8sEvent, PodStatus
    from shieldops_investigate.sources.prometheus import TimeSeries

logger = structlog.get_logger()


def correlate(
    metrics: dict[str, list[TimeSeries]],
    pods: list[PodStatus],
    events: list[K8sEvent],
    deployments: list[Deployment],
) -> list[Hypothesis]:
    """Correlate signals from Prometheus and Kubernetes into ranked hypotheses.

    Args:
        metrics: Keyed by signal name (``cpu``, ``memory``, ``error_rate``, etc.).
        pods: Pod status snapshots from the target namespace.
        events: Recent K8s events from the target namespace.
        deployments: Recent deployments (rollouts) in the namespace.

    Returns:
        A list of hypotheses sorted by descending confidence.
    """
    hypotheses: list[Hypothesis] = []

    hypotheses.extend(_check_deployment_regression(metrics, deployments))
    hypotheses.extend(_check_memory_leak(metrics, pods, events))
    hypotheses.extend(_check_node_issues(pods, events))
    hypotheses.extend(_check_crashloop(pods, events))
    hypotheses.extend(_check_dns_issues(events))
    hypotheses.extend(_check_resource_exhaustion(metrics, pods))
    hypotheses.extend(_check_image_pull_errors(events))

    # Sort by confidence descending
    hypotheses.sort(key=lambda h: h.confidence, reverse=True)

    if hypotheses:
        top = hypotheses[0]
        logger.info(
            "correlation_complete",
            hypothesis_count=len(hypotheses),
            top_hypothesis=top.title,
            top_confidence=top.confidence,
        )
    else:
        logger.info("correlation_complete", hypothesis_count=0)

    return hypotheses


# ---------------------------------------------------------------------------
# Individual correlation rules
# ---------------------------------------------------------------------------


def _check_deployment_regression(
    metrics: dict[str, list[TimeSeries]],
    deployments: list[Deployment],
) -> list[Hypothesis]:
    """Deployment within 10 min of an error-rate spike -> deployment regression."""
    if not deployments:
        return []

    error_series = metrics.get("error_rate", [])
    has_error_spike = any(ts.latest is not None and ts.latest > 0.05 for ts in error_series)

    latency_series = metrics.get("latency_p99", [])
    has_latency_spike = any(ts.latest is not None and ts.latest > 1.0 for ts in latency_series)

    if not (has_error_spike or has_latency_spike):
        return []

    now = datetime.now(tz=UTC)
    recent = [
        d for d in deployments if d.updated_at and (now - d.updated_at) < timedelta(minutes=10)
    ]

    if not recent:
        # Widen to 30 min with lower confidence
        recent = [
            d for d in deployments if d.updated_at and (now - d.updated_at) < timedelta(minutes=30)
        ]
        if not recent:
            return []
        confidence = 0.55
    else:
        confidence = 0.9

    deploy = recent[0]
    evidence_items: list[Evidence] = []

    evidence_items.append(
        Evidence(
            source=EvidenceSource.KUBERNETES,
            query=f"deployment/{deploy.name}",
            value=f"Deployed {deploy.image} at {deploy.updated_at}",
            anomaly_score=0.8,
        )
    )

    if has_error_spike:
        latest_err = next((ts.latest for ts in error_series if ts.latest is not None), None)
        evidence_items.append(
            Evidence(
                source=EvidenceSource.PROMETHEUS,
                query="error_rate",
                value=f"Error rate: {latest_err:.2%}" if latest_err else "Elevated error rate",
                anomaly_score=0.85,
            )
        )

    if has_latency_spike:
        latest_lat = next((ts.latest for ts in latency_series if ts.latest is not None), None)
        evidence_items.append(
            Evidence(
                source=EvidenceSource.PROMETHEUS,
                query="latency_p99",
                value=f"p99 latency: {latest_lat:.3f}s" if latest_lat else "Elevated latency",
                anomaly_score=0.75,
            )
        )

    return [
        Hypothesis(
            title="Deployment Regression",
            description=(
                f"Deployment '{deploy.name}' (image: {deploy.image}) was rolled out "
                f"shortly before the anomaly was detected. The timing strongly correlates "
                f"with the observed error-rate and/or latency increase."
            ),
            confidence=confidence,
            evidence=evidence_items,
            suggested_action=(
                f"Roll back deployment '{deploy.name}' with: "
                f"kubectl rollout undo deployment/{deploy.name}"
            ),
        )
    ]


def _check_memory_leak(
    metrics: dict[str, list[TimeSeries]],
    pods: list[PodStatus],
    events: list[K8sEvent],
) -> list[Hypothesis]:
    """OOMKilled events + rising memory usage -> memory leak."""
    oom_events = [e for e in events if "OOMKill" in e.reason or "OOMKill" in e.message]
    oom_pods = [p for p in pods if _has_oom(p)]

    if not oom_events and not oom_pods:
        return []

    evidence_items: list[Evidence] = []

    for ev in oom_events[:3]:
        evidence_items.append(
            Evidence(
                source=EvidenceSource.KUBERNETES,
                query="events(reason=OOMKilled)",
                value=f"{ev.involved_object}: {ev.message}",
                anomaly_score=0.9,
            )
        )

    mem_series = metrics.get("memory", [])
    rising = any(_is_rising(ts) for ts in mem_series)

    if rising:
        evidence_items.append(
            Evidence(
                source=EvidenceSource.PROMETHEUS,
                query="container_memory_working_set_bytes",
                value="Memory usage shows a consistent upward trend",
                anomaly_score=0.8,
            )
        )

    confidence = 0.85 if (oom_events and rising) else 0.65

    return [
        Hypothesis(
            title="Memory Leak / OOM",
            description=(
                "One or more containers have been OOM-killed. "
                + (
                    "Memory usage shows a rising trend consistent with a memory leak."
                    if rising
                    else "Review container memory limits and application heap settings."
                )
            ),
            confidence=confidence,
            evidence=evidence_items,
            suggested_action=(
                "Increase memory limits as a short-term fix, then profile the application "
                "for memory leaks. Check: kubectl describe pod <name> for OOMKilled details."
            ),
        )
    ]


def _check_node_issues(
    pods: list[PodStatus],
    events: list[K8sEvent],
) -> list[Hypothesis]:
    """Node NotReady + pod scheduling failures -> node issue."""
    node_events = [
        e
        for e in events
        if any(kw in e.message.lower() for kw in ("notready", "not ready", "node"))
        and e.event_type == "Warning"
    ]
    scheduling_failures = [e for e in events if e.reason in ("FailedScheduling", "NodeNotReady")]

    if not node_events and not scheduling_failures:
        return []

    evidence_items = [
        Evidence(
            source=EvidenceSource.KUBERNETES,
            query="events(type=Warning,node-related)",
            value=f"{ev.reason}: {ev.message[:120]}",
            anomaly_score=0.85,
        )
        for ev in (node_events + scheduling_failures)[:5]
    ]

    failed_pods = [p for p in pods if p.phase in ("Pending", "Failed")]
    if failed_pods:
        evidence_items.append(
            Evidence(
                source=EvidenceSource.KUBERNETES,
                query="pods(phase=Pending|Failed)",
                value=f"{len(failed_pods)} pod(s) in non-running state",
                anomaly_score=0.7,
            )
        )

    return [
        Hypothesis(
            title="Node Issue",
            description=(
                "One or more cluster nodes appear unhealthy (NotReady). "
                "Pods may be unable to schedule or are being evicted."
            ),
            confidence=0.75,
            evidence=evidence_items,
            suggested_action=(
                "Check node status with: kubectl get nodes. "
                "Investigate kubelet logs on affected nodes."
            ),
        )
    ]


def _check_crashloop(
    pods: list[PodStatus],
    events: list[K8sEvent],
) -> list[Hypothesis]:
    """Pods in CrashLoopBackOff."""
    crashloop_pods = [
        p
        for p in pods
        if any(
            cs.get("state", "").startswith("waiting: CrashLoopBackOff")
            for cs in p.container_statuses
        )
    ]
    high_restart_pods = [p for p in pods if p.restart_count >= 5]

    affected = {p.name for p in crashloop_pods} | {p.name for p in high_restart_pods}
    if not affected:
        return []

    evidence_items = [
        Evidence(
            source=EvidenceSource.KUBERNETES,
            query="pods(CrashLoopBackOff)",
            value=f"Pod {name} in crash loop or high restart count",
            anomaly_score=0.9,
        )
        for name in list(affected)[:5]
    ]

    backoff_events = [e for e in events if "BackOff" in e.reason or "BackOff" in e.message]
    for ev in backoff_events[:3]:
        evidence_items.append(
            Evidence(
                source=EvidenceSource.KUBERNETES,
                query="events(reason=BackOff)",
                value=f"{ev.involved_object}: {ev.message[:120]}",
                anomaly_score=0.85,
            )
        )

    return [
        Hypothesis(
            title="CrashLoopBackOff",
            description=(
                f"{len(affected)} pod(s) are crash-looping. The application is repeatedly "
                f"crashing on startup, which may indicate a configuration error, missing "
                f"dependency, or a bug introduced in a recent deployment."
            ),
            confidence=0.80,
            evidence=evidence_items,
            suggested_action=(
                "Check container logs: kubectl logs <pod-name> --previous. "
                "Look for startup errors, missing env vars, or failed health checks."
            ),
        )
    ]


def _check_dns_issues(events: list[K8sEvent]) -> list[Hypothesis]:
    """DNS errors + coredns restarts -> DNS issue."""
    dns_events = [
        e for e in events if any(kw in e.message.lower() for kw in ("dns", "coredns", "resolve"))
    ]

    if not dns_events:
        return []

    evidence_items = [
        Evidence(
            source=EvidenceSource.KUBERNETES,
            query="events(dns-related)",
            value=f"{ev.reason}: {ev.message[:120]}",
            anomaly_score=0.7,
        )
        for ev in dns_events[:5]
    ]

    return [
        Hypothesis(
            title="DNS Resolution Issue",
            description=(
                "DNS-related events detected in the cluster. Services may be unable "
                "to resolve internal or external hostnames, causing connection failures."
            ),
            confidence=0.55,
            evidence=evidence_items,
            suggested_action=(
                "Check CoreDNS pods: kubectl get pods -n kube-system -l k8s-app=kube-dns. "
                "Verify DNS resolution: kubectl run -it --rm debug "
                "--image=busybox -- nslookup kubernetes."
            ),
        )
    ]


def _check_resource_exhaustion(
    metrics: dict[str, list[TimeSeries]],
    pods: list[PodStatus],
) -> list[Hypothesis]:
    """High CPU or memory across multiple pods -> resource exhaustion."""
    cpu_series = metrics.get("cpu", [])
    high_cpu = [ts for ts in cpu_series if ts.latest is not None and ts.latest > 0.9]

    if not high_cpu:
        return []

    evidence_items = [
        Evidence(
            source=EvidenceSource.PROMETHEUS,
            query="container_cpu_usage_seconds_total",
            value=f"Pod {ts.metric.get('pod', 'unknown')}: {ts.latest:.1%} CPU",
            anomaly_score=0.75,
        )
        for ts in high_cpu[:5]
    ]

    return [
        Hypothesis(
            title="CPU Resource Exhaustion",
            description=(
                f"{len(high_cpu)} pod(s) are using >90% of their CPU allocation. "
                f"This can cause request throttling, increased latency, and health-check failures."
            ),
            confidence=0.60,
            evidence=evidence_items,
            suggested_action=(
                "Consider scaling the deployment horizontally (increase replicas) or "
                "vertically (increase CPU limits). Check for hot-loop bugs in application code."
            ),
        )
    ]


def _check_image_pull_errors(events: list[K8sEvent]) -> list[Hypothesis]:
    """ImagePullBackOff or ErrImagePull events."""
    pull_events = [
        e
        for e in events
        if e.reason in ("ErrImagePull", "ImagePullBackOff", "Failed")
        and "image" in e.message.lower()
    ]

    if not pull_events:
        return []

    evidence_items = [
        Evidence(
            source=EvidenceSource.KUBERNETES,
            query="events(reason=ErrImagePull|ImagePullBackOff)",
            value=f"{ev.involved_object}: {ev.message[:120]}",
            anomaly_score=0.9,
        )
        for ev in pull_events[:5]
    ]

    return [
        Hypothesis(
            title="Image Pull Failure",
            description=(
                "One or more pods cannot pull their container image. This is usually "
                "caused by a typo in the image tag, a private registry authentication "
                "issue, or the image not existing."
            ),
            confidence=0.85,
            evidence=evidence_items,
            suggested_action=(
                "Verify the image name and tag exist in the registry. "
                "Check imagePullSecrets on the pod spec."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_oom(pod: PodStatus) -> bool:
    """Return True if any container in the pod was OOM-killed."""
    for cs in pod.container_statuses:
        state = cs.get("state", "")
        if "OOMKilled" in state:
            return True
    return False


def _is_rising(ts: TimeSeries, *, window: int = 10) -> bool:
    """Heuristic: is the time series trending upward over its last *window* points?"""
    if len(ts.values) < window:
        return False
    recent = [v for _, v in ts.values[-window:]]
    increases = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
    return increases >= window * 0.7
