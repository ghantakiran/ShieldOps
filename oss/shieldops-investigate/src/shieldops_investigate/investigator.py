"""Main investigation orchestrator.

The :class:`Investigator` ties together Prometheus metrics, Kubernetes
cluster data, rule-based correlation, and (optionally) Claude-powered
root-cause summarisation into a single ``async investigate()`` call.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog

from shieldops_investigate.correlator import correlate
from shieldops_investigate.models import (
    Evidence,
    EvidenceSource,
    Hypothesis,
    InvestigationResult,
)
from shieldops_investigate.sources.kubernetes import KubernetesSource
from shieldops_investigate.sources.prometheus import BUILTIN_QUERIES, PrometheusSource

logger = structlog.get_logger()


class Investigator:
    """End-to-end Kubernetes incident investigator.

    Args:
        prometheus_url: Base URL for a Prometheus server
            (e.g. ``http://prometheus:9090``).
        kubeconfig_path: Optional path to a kubeconfig file.
            Defaults to the in-cluster config or ``~/.kube/config``.
        anthropic_api_key: Optional Anthropic API key. When provided, the
            investigator generates an AI-powered root-cause summary using
            Claude. When omitted, a rule-based summary is used instead.
    """

    def __init__(
        self,
        prometheus_url: str,
        kubeconfig_path: str | None = None,
        anthropic_api_key: str | None = None,
    ) -> None:
        self._prom = PrometheusSource(prometheus_url)
        self._k8s = KubernetesSource(kubeconfig_path)
        self._anthropic_key = anthropic_api_key

    async def investigate(
        self,
        alert_name: str,
        namespace: str,
        service: str | None = None,
    ) -> InvestigationResult:
        """Run a full investigation and return ranked hypotheses.

        Steps:

        1. Query Prometheus for anomalous metrics (CPU, memory, error rate,
           latency, restarts).
        2. Query Kubernetes for pod status, events, and recent deployments.
        3. Correlate signals using deterministic rules to produce hypotheses.
        4. (Optional) Call Claude for an AI-powered root-cause summary.
        5. Return :class:`InvestigationResult` with ranked hypotheses,
           evidence, and a plain-language summary.
        """
        t0 = time.monotonic()
        log = logger.bind(alert=alert_name, namespace=namespace, service=service)
        log.info("investigation_started")

        all_evidence: list[Evidence] = []

        # ---- Step 1: Prometheus signals ------------------------------------
        metrics = await self._prom.collect_signals(namespace, service)
        log.info("prometheus_signals_collected", signal_count=len(metrics))

        # Anomaly detection on each built-in query
        for name, template in BUILTIN_QUERIES.items():
            current, score = await self._prom.detect_anomalies(template, namespace, service)
            if current is not None:
                all_evidence.append(
                    Evidence(
                        source=EvidenceSource.PROMETHEUS,
                        query=name,
                        value=f"{current:.4g}",
                        anomaly_score=score,
                    )
                )

        # ---- Step 2: Kubernetes signals ------------------------------------
        label_selector = f"app={service}" if service else ""

        pods = await self._k8s.get_pod_status(namespace, label_selector)
        events = await self._k8s.get_events(namespace, involved_object=service)
        deployments = await self._k8s.get_recent_deployments(namespace, since_minutes=60)

        log.info(
            "kubernetes_signals_collected",
            pods=len(pods),
            events=len(events),
            deployments=len(deployments),
        )

        for ev in events[:10]:
            all_evidence.append(
                Evidence(
                    source=EvidenceSource.KUBERNETES,
                    query=f"event/{ev.reason}",
                    value=f"{ev.involved_object}: {ev.message[:200]}",
                    timestamp=ev.timestamp or datetime.now(tz=UTC),
                    anomaly_score=0.7 if ev.event_type == "Warning" else 0.2,
                )
            )

        # ---- Step 3: Correlate signals -------------------------------------
        hypotheses = correlate(metrics, pods, events, deployments)

        # ---- Step 4: AI summary (optional) ---------------------------------
        if self._anthropic_key and hypotheses:
            summary = await self._generate_ai_summary(
                alert_name, namespace, service, hypotheses, all_evidence
            )
        else:
            summary = self._generate_rule_summary(alert_name, hypotheses)

        duration = time.monotonic() - t0
        log.info(
            "investigation_complete",
            duration_s=round(duration, 2),
            hypothesis_count=len(hypotheses),
        )

        return InvestigationResult(
            alert_name=alert_name,
            namespace=namespace,
            service=service,
            hypotheses=hypotheses,
            evidence=all_evidence,
            summary=summary,
            duration_seconds=round(duration, 3),
        )

    async def close(self) -> None:
        """Release resources held by the investigator."""
        await self._prom.close()

    # ------------------------------------------------------------------
    # Summary generators
    # ------------------------------------------------------------------

    async def _generate_ai_summary(
        self,
        alert_name: str,
        namespace: str,
        service: str | None,
        hypotheses: list[Hypothesis],
        evidence: list[Evidence],
    ) -> str:
        """Use Claude to produce a concise root-cause summary."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.warning("anthropic_not_installed_falling_back_to_rules")
            return self._generate_rule_summary(alert_name, hypotheses)

        client = AsyncAnthropic(api_key=self._anthropic_key)

        hypothesis_text = "\n".join(
            f"- [{h.confidence:.0%}] {h.title}: {h.description}" for h in hypotheses[:5]
        )

        evidence_text = "\n".join(
            f"- [{e.source.value}] {e.query}: {e.value} (anomaly={e.anomaly_score:.2f})"
            for e in sorted(evidence, key=lambda x: x.anomaly_score, reverse=True)[:15]
        )

        prompt = (
            f"You are an expert SRE investigating a Kubernetes incident.\n\n"
            f"Alert: {alert_name}\n"
            f"Namespace: {namespace}\n"
            f"Service: {service or 'all'}\n\n"
            f"Hypotheses (ranked by confidence):\n{hypothesis_text}\n\n"
            f"Evidence (ranked by anomaly score):\n{evidence_text}\n\n"
            f"Write a concise (3-5 sentence) root-cause analysis summary. "
            f"State the most likely cause, the supporting evidence, and the "
            f"recommended immediate action. Be specific and actionable."
        )

        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception:
            logger.exception("ai_summary_failed")
            return self._generate_rule_summary(alert_name, hypotheses)

    @staticmethod
    def _generate_rule_summary(alert_name: str, hypotheses: list[Hypothesis]) -> str:
        """Produce a summary from hypotheses without an LLM."""
        if not hypotheses:
            return (
                f"Investigation of alert '{alert_name}' did not identify a clear root cause. "
                f"Manual investigation is recommended."
            )

        top = hypotheses[0]
        others = hypotheses[1:3]

        summary = (
            f"Investigation of alert '{alert_name}' identified "
            f"'{top.title}' as the most likely root cause "
            f"(confidence: {top.confidence:.0%}). {top.description}"
        )

        if others:
            alt_names = ", ".join(f"'{h.title}' ({h.confidence:.0%})" for h in others)
            summary += f" Alternative hypotheses: {alt_names}."

        if top.suggested_action:
            summary += f" Recommended action: {top.suggested_action}"

        return summary
