"""Structured log source for Kubernetes pod logs and generic log querying.

Provides log access for investigation agents by querying Kubernetes pod logs
directly via the K8s API. Serves as the MVP log source before Splunk/ELK
integration.
"""

import re
from datetime import datetime, timezone
from typing import Any

import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import LogSource

logger = structlog.get_logger()


class KubernetesLogSource(LogSource):
    """Query pod logs via the Kubernetes API.

    MVP log source that reads directly from K8s pod logs.
    Production deployments should use Splunk/ELK for richer querying.
    """

    source_name = "kubernetes"

    def __init__(self) -> None:
        self._core_api = None

    async def _ensure_client(self) -> None:
        if self._core_api is not None:
            return
        from kubernetes_asyncio import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            await config.load_kube_config()
        self._core_api = client.CoreV1Api()

    async def query_logs(
        self,
        query: str,
        time_range: TimeRange,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query pod logs. `query` format: 'namespace/pod_name' or just 'pod_name'."""
        await self._ensure_client()
        assert self._core_api is not None

        parts = query.split("/", 1)
        namespace = parts[0] if len(parts) == 2 else "default"
        pod_name = parts[1] if len(parts) == 2 else parts[0]

        since_seconds = int(
            (time_range.end - time_range.start).total_seconds()
        )

        try:
            log_text = await self._core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=limit,
                since_seconds=max(since_seconds, 60),
            )
        except Exception as e:
            logger.error(
                "k8s_log_query_failed",
                pod=pod_name,
                namespace=namespace,
                error=str(e),
            )
            return []

        entries = []
        for line in (log_text or "").strip().split("\n"):
            if not line:
                continue
            level = _detect_log_level(line)
            entries.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": line,
                "level": level,
                "source": f"{namespace}/{pod_name}",
            })

        return entries

    async def search_patterns(
        self,
        resource_id: str,
        patterns: list[str],
        time_range: TimeRange,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search pod logs for specific error patterns."""
        logs = await self.query_logs(resource_id, time_range, limit=500)

        results: dict[str, list[dict[str, Any]]] = {p: [] for p in patterns}

        for entry in logs:
            message_lower = entry["message"].lower()
            for pattern in patterns:
                if pattern.lower() in message_lower:
                    results[pattern].append(entry)

        logger.info(
            "k8s_log_pattern_search",
            resource_id=resource_id,
            patterns=patterns,
            matches={p: len(v) for p, v in results.items()},
        )
        return results


def _detect_log_level(line: str) -> str:
    """Heuristic log level detection from log line content."""
    line_upper = line.upper()
    if re.search(r'\b(FATAL|PANIC)\b', line_upper):
        return "fatal"
    if re.search(r'\b(ERROR|ERR)\b', line_upper):
        return "error"
    if re.search(r'\b(WARN|WARNING)\b', line_upper):
        return "warning"
    if re.search(r'\b(INFO)\b', line_upper):
        return "info"
    if re.search(r'\b(DEBUG|TRACE)\b', line_upper):
        return "debug"
    return "info"
