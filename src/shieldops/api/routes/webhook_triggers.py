"""Custom webhook triggers — ingest alerts from external monitoring tools."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter()

# Module-level singletons
_investigation_runner: Any | None = None
_webhook_secret: str = ""
_dedup_cache: dict[str, float] = {}  # fingerprint -> timestamp
_dedup_window_seconds: int = 300  # 5 minutes


def set_investigation_runner(runner: Any) -> None:
    global _investigation_runner
    _investigation_runner = runner


def set_webhook_secret(secret: str) -> None:
    global _webhook_secret
    _webhook_secret = secret


def set_dedup_window(seconds: int) -> None:
    global _dedup_window_seconds
    _dedup_window_seconds = seconds


class WebhookAlert(BaseModel):
    """Normalized alert from any monitoring source."""

    alert_id: str = ""
    alert_name: str = ""
    severity: str = "warning"
    source: str = "generic"
    service: str = ""
    environment: str = "production"
    description: str = ""
    timestamp: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    status: str = "accepted"
    alerts_processed: int = 0
    alerts_deduplicated: int = 0
    investigation_ids: list[str] = Field(default_factory=list)


# ── Payload Adapters ──────────────────────────────────────────────


def adapt_datadog(payload: dict[str, Any]) -> list[WebhookAlert]:
    """Parse Datadog webhook payload."""
    alerts: list[WebhookAlert] = []
    # Datadog sends event_type, title, body, tags, etc.
    event_id = payload.get("id", payload.get("event_id", ""))
    title = payload.get("title", payload.get("event_title", ""))
    body = payload.get("body", payload.get("event_msg", ""))
    tags = payload.get("tags", "")
    priority = payload.get("priority", "normal")

    severity_map = {"low": "low", "normal": "warning", "high": "high", "critical": "critical"}

    # Extract service from tags
    service = ""
    env = "production"
    tag_list = tags.split(",") if isinstance(tags, str) else (tags or [])
    for tag in tag_list:
        tag = tag.strip()
        if tag.startswith("service:"):
            service = tag.split(":", 1)[1]
        elif tag.startswith("env:"):
            env = tag.split(":", 1)[1]

    alerts.append(
        WebhookAlert(
            alert_id=str(event_id),
            alert_name=title,
            severity=severity_map.get(priority, "warning"),
            source="datadog",
            service=service,
            environment=env,
            description=body,
            labels={t.split(":")[0]: t.split(":", 1)[1] for t in tag_list if ":" in t},
            raw_payload=payload,
        )
    )
    return alerts


def adapt_pagerduty(payload: dict[str, Any]) -> list[WebhookAlert]:
    """Parse PagerDuty V2 webhook payload."""
    alerts: list[WebhookAlert] = []
    messages = payload.get("messages", [])
    if not messages:
        # Single event format
        messages = [payload]

    for msg in messages:
        event = msg.get("event", msg)
        incident = event.get("data", event.get("incident", event))

        alert_id = incident.get("id", incident.get("incident_number", ""))
        title = incident.get("title", incident.get("description", ""))
        urgency = incident.get("urgency", "low")
        service_data = incident.get("service", {})
        service_name = service_data.get("name", "") if isinstance(service_data, dict) else ""

        severity_map = {"low": "low", "high": "high", "critical": "critical"}

        alerts.append(
            WebhookAlert(
                alert_id=str(alert_id),
                alert_name=title,
                severity=severity_map.get(urgency, "warning"),
                source="pagerduty",
                service=service_name,
                description=incident.get("description", title),
                raw_payload=payload,
            )
        )
    return alerts


def adapt_grafana(payload: dict[str, Any]) -> list[WebhookAlert]:
    """Parse Grafana webhook (Alertmanager-compatible) payload."""
    alerts: list[WebhookAlert] = []

    # Grafana sends an 'alerts' array
    raw_alerts = payload.get("alerts", [])
    if not raw_alerts:
        # Single alert format
        raw_alerts = [payload]

    for raw in raw_alerts:
        labels = raw.get("labels", {})
        annotations = raw.get("annotations", {})
        status = raw.get("status", "firing")

        if status != "firing":
            continue  # Skip resolved alerts

        alert_name = labels.get("alertname", annotations.get("summary", "Grafana Alert"))
        severity = labels.get("severity", "warning")
        service = labels.get("service", labels.get("job", ""))
        env = labels.get("environment", labels.get("env", "production"))

        alerts.append(
            WebhookAlert(
                alert_id=raw.get("fingerprint", ""),
                alert_name=alert_name,
                severity=severity,
                source="grafana",
                service=service,
                environment=env,
                description=annotations.get("description", annotations.get("summary", "")),
                labels=labels,
                annotations=annotations,
                raw_payload=raw,
            )
        )
    return alerts


def adapt_opsgenie(payload: dict[str, Any]) -> list[WebhookAlert]:
    """Parse OpsGenie webhook payload."""
    alerts: list[WebhookAlert] = []
    alert_data = payload.get("alert", payload)
    action = payload.get("action", "Create")

    if action.lower() not in ("create", "escalate"):
        return alerts  # Only process new alerts

    priority = alert_data.get("priority", "P3")
    priority_map = {"P1": "critical", "P2": "high", "P3": "warning", "P4": "low", "P5": "info"}

    tags = alert_data.get("tags", [])
    service = ""
    env = "production"
    for tag in tags:
        if tag.startswith("service:"):
            service = tag.split(":", 1)[1]
        elif tag.startswith("env:"):
            env = tag.split(":", 1)[1]

    alerts.append(
        WebhookAlert(
            alert_id=alert_data.get("alertId", alert_data.get("tinyId", "")),
            alert_name=alert_data.get("message", "OpsGenie Alert"),
            severity=priority_map.get(priority, "warning"),
            source="opsgenie",
            service=service,
            environment=env,
            description=alert_data.get("description", ""),
            labels={t.split(":")[0]: t.split(":", 1)[1] for t in tags if ":" in t},
            raw_payload=payload,
        )
    )
    return alerts


def adapt_generic(payload: dict[str, Any]) -> list[WebhookAlert]:
    """Parse generic JSON alert payload."""
    # Support both single alert and array
    items = payload.get("alerts", [payload])
    alerts: list[WebhookAlert] = []

    for item in items:
        alerts.append(
            WebhookAlert(
                alert_id=item.get("alert_id", item.get("id", "")),
                alert_name=item.get("alert_name", item.get("name", item.get("title", "Alert"))),
                severity=item.get("severity", item.get("priority", "warning")),
                source="generic",
                service=item.get("service", item.get("source", "")),
                environment=item.get("environment", item.get("env", "production")),
                description=item.get("description", item.get("message", "")),
                labels=item.get("labels", {}),
                raw_payload=item,
            )
        )
    return alerts


# Adapter registry
ADAPTERS: dict[str, Any] = {
    "datadog": adapt_datadog,
    "pagerduty": adapt_pagerduty,
    "grafana": adapt_grafana,
    "opsgenie": adapt_opsgenie,
    "generic": adapt_generic,
}


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature."""
    if not secret:
        return True  # No secret configured, skip verification
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _fingerprint(alert: WebhookAlert) -> str:
    """Generate dedup fingerprint for an alert."""
    raw = f"{alert.source}:{alert.alert_id}:{alert.alert_name}:{alert.service}"
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()  # noqa: S324


def _is_duplicate(fingerprint: str) -> bool:
    """Check if alert was already processed within dedup window."""
    now = time.time()
    # Clean old entries
    expired = [k for k, v in _dedup_cache.items() if now - v > _dedup_window_seconds]
    for k in expired:
        del _dedup_cache[k]

    if fingerprint in _dedup_cache:
        return True
    _dedup_cache[fingerprint] = now
    return False


async def _trigger_investigation(alert: WebhookAlert) -> str | None:
    """Trigger an investigation from a webhook alert."""
    if not _investigation_runner:
        logger.warning("webhook_no_runner", alert_id=alert.alert_id)
        return None

    alert_data = {
        "alert_id": alert.alert_id,
        "alert_name": alert.alert_name,
        "severity": alert.severity,
        "source": alert.source,
        "description": alert.description,
        "environment": alert.environment,
        "service": alert.service,
        "labels": alert.labels,
    }

    try:
        result = await _investigation_runner.investigate(alert_data)
        inv_id: str | None = getattr(result, "investigation_id", None) or result.get(
            "investigation_id", ""
        )
        logger.info(
            "webhook_investigation_triggered",
            alert_id=alert.alert_id,
            investigation_id=inv_id,
        )
        return inv_id
    except Exception as e:
        logger.error("webhook_investigation_failed", alert_id=alert.alert_id, error=str(e))
        return None


# ── Routes ────────────────────────────────────────────────────────


@router.post("/webhooks/{source}")
async def receive_webhook(
    source: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_signature: str = Header("", alias="X-Webhook-Signature"),
) -> WebhookResponse:
    """Receive webhook from external monitoring tool.

    Supported sources: datadog, pagerduty, grafana, opsgenie, generic
    """
    body = await request.body()

    # Verify signature
    if _webhook_secret and not _verify_signature(body, x_webhook_signature, _webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Get adapter
    adapter = ADAPTERS.get(source, adapt_generic)

    # Parse payload
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    # Adapt to normalized alerts
    alerts = adapter(payload)
    if not alerts:
        return WebhookResponse(status="no_alerts", alerts_processed=0)

    # Dedup and trigger
    investigation_ids: list[str] = []
    deduped = 0

    for alert in alerts:
        fp = _fingerprint(alert)
        if _is_duplicate(fp):
            deduped += 1
            continue

        # Trigger investigation in background
        async def _trigger(a: WebhookAlert = alert) -> None:
            inv_id = await _trigger_investigation(a)
            if inv_id:
                investigation_ids.append(inv_id)

        background_tasks.add_task(_trigger)

    logger.info(
        "webhook_received",
        source=source,
        alerts=len(alerts),
        deduped=deduped,
    )

    return WebhookResponse(
        status="accepted",
        alerts_processed=len(alerts) - deduped,
        alerts_deduplicated=deduped,
        investigation_ids=investigation_ids,
    )


@router.get("/webhooks/adapters")
async def list_adapters() -> dict[str, Any]:
    """List available webhook adapters."""
    return {
        "adapters": list(ADAPTERS.keys()),
        "dedup_window_seconds": _dedup_window_seconds,
        "secret_configured": bool(_webhook_secret),
    }
