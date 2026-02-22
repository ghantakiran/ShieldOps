"""Tests for custom webhook triggers."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import webhook_triggers
from shieldops.api.routes.webhook_triggers import (
    ADAPTERS,
    WebhookAlert,
    _fingerprint,
    _is_duplicate,
    _verify_signature,
    adapt_datadog,
    adapt_generic,
    adapt_grafana,
    adapt_opsgenie,
    adapt_pagerduty,
)


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level state between tests."""
    original_runner = webhook_triggers._investigation_runner
    original_secret = webhook_triggers._webhook_secret
    original_cache = webhook_triggers._dedup_cache.copy()
    webhook_triggers._investigation_runner = None
    webhook_triggers._webhook_secret = ""
    webhook_triggers._dedup_cache.clear()
    yield
    webhook_triggers._investigation_runner = original_runner
    webhook_triggers._webhook_secret = original_secret
    webhook_triggers._dedup_cache = original_cache


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(webhook_triggers.router, prefix="/api/v1")
    return app


class TestAdapters:
    def test_datadog_adapter(self) -> None:
        payload = {
            "id": "evt-123",
            "title": "High CPU Usage",
            "body": "CPU above 90%",
            "priority": "high",
            "tags": "service:api-server,env:production,team:platform",
        }
        alerts = adapt_datadog(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_id == "evt-123"
        assert alerts[0].alert_name == "High CPU Usage"
        assert alerts[0].severity == "high"
        assert alerts[0].source == "datadog"
        assert alerts[0].service == "api-server"
        assert alerts[0].environment == "production"

    def test_datadog_adapter_list_tags(self) -> None:
        payload = {
            "event_id": "evt-456",
            "event_title": "Disk Full",
            "event_msg": "Disk usage 95%",
            "priority": "critical",
            "tags": ["service:db", "env:staging"],
        }
        alerts = adapt_datadog(payload)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert alerts[0].service == "db"

    def test_pagerduty_adapter(self) -> None:
        payload = {
            "messages": [
                {
                    "event": {
                        "data": {
                            "id": "PD123",
                            "title": "Server Down",
                            "urgency": "high",
                            "service": {"name": "web-app"},
                            "description": "Server not responding",
                        }
                    }
                }
            ]
        }
        alerts = adapt_pagerduty(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_id == "PD123"
        assert alerts[0].severity == "high"
        assert alerts[0].source == "pagerduty"
        assert alerts[0].service == "web-app"

    def test_pagerduty_single_event(self) -> None:
        payload = {
            "event": {
                "data": {
                    "id": "PD789",
                    "title": "Latency Spike",
                    "urgency": "low",
                }
            }
        }
        alerts = adapt_pagerduty(payload)
        assert len(alerts) == 1
        assert alerts[0].severity == "low"

    def test_grafana_adapter(self) -> None:
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighMemory",
                        "severity": "critical",
                        "service": "cache-service",
                        "environment": "staging",
                    },
                    "annotations": {
                        "summary": "Memory usage above 95%",
                        "description": "Cache service memory critical",
                    },
                    "fingerprint": "abc123",
                }
            ]
        }
        alerts = adapt_grafana(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_name == "HighMemory"
        assert alerts[0].severity == "critical"
        assert alerts[0].source == "grafana"
        assert alerts[0].service == "cache-service"

    def test_grafana_skips_resolved(self) -> None:
        payload = {
            "alerts": [
                {"status": "resolved", "labels": {"alertname": "Test"}},
                {"status": "firing", "labels": {"alertname": "Active"}},
            ]
        }
        alerts = adapt_grafana(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_name == "Active"

    def test_opsgenie_adapter(self) -> None:
        payload = {
            "action": "Create",
            "alert": {
                "alertId": "og-123",
                "message": "Service Degraded",
                "priority": "P2",
                "description": "Latency above SLA",
                "tags": ["service:payments", "env:production"],
            },
        }
        alerts = adapt_opsgenie(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_id == "og-123"
        assert alerts[0].severity == "high"
        assert alerts[0].source == "opsgenie"
        assert alerts[0].service == "payments"

    def test_opsgenie_skips_close(self) -> None:
        payload = {"action": "Close", "alert": {"alertId": "og-456"}}
        alerts = adapt_opsgenie(payload)
        assert len(alerts) == 0

    def test_generic_adapter_single(self) -> None:
        payload = {
            "alert_id": "gen-001",
            "alert_name": "Custom Alert",
            "severity": "high",
            "service": "my-service",
        }
        alerts = adapt_generic(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_name == "Custom Alert"
        assert alerts[0].source == "generic"

    def test_generic_adapter_array(self) -> None:
        payload = {
            "alerts": [
                {"id": "1", "name": "Alert 1"},
                {"id": "2", "name": "Alert 2"},
            ]
        }
        alerts = adapt_generic(payload)
        assert len(alerts) == 2

    def test_all_adapters_registered(self) -> None:
        expected = {"datadog", "pagerduty", "grafana", "opsgenie", "generic"}
        assert set(ADAPTERS.keys()) == expected


class TestSignatureVerification:
    def test_no_secret_passes(self) -> None:
        assert _verify_signature(b"body", "any-sig", "") is True

    def test_valid_signature(self) -> None:
        import hashlib
        import hmac as hmac_mod

        secret = "test-secret"  # noqa: S105
        body = b'{"test": true}'
        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_signature(body, sig, secret) is True

    def test_invalid_signature(self) -> None:
        assert _verify_signature(b"body", "wrong-sig", "secret") is False


class TestDeduplication:
    def test_fingerprint_deterministic(self) -> None:
        alert = WebhookAlert(alert_id="123", alert_name="Test", source="dd", service="api")
        fp1 = _fingerprint(alert)
        fp2 = _fingerprint(alert)
        assert fp1 == fp2

    def test_dedup_detects_duplicate(self) -> None:
        alert = WebhookAlert(alert_id="dup-1", alert_name="Test", source="dd")
        fp = _fingerprint(alert)
        assert not _is_duplicate(fp)
        assert _is_duplicate(fp)

    def test_different_alerts_not_deduped(self) -> None:
        a1 = WebhookAlert(alert_id="1", alert_name="A", source="dd")
        a2 = WebhookAlert(alert_id="2", alert_name="B", source="dd")
        assert not _is_duplicate(_fingerprint(a1))
        assert not _is_duplicate(_fingerprint(a2))


class TestWebhookEndpoints:
    def test_receive_generic_webhook(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/generic",
            json={
                "alert_id": "test-1",
                "alert_name": "Test Alert",
                "severity": "warning",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["alerts_processed"] == 1

    def test_receive_datadog_webhook(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/datadog",
            json={
                "id": "dd-123",
                "title": "CPU Alert",
                "priority": "high",
                "tags": "service:api",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["alerts_processed"] == 1

    def test_receive_grafana_webhook(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/grafana",
            json={
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": "HighCPU", "severity": "critical"},
                        "annotations": {"summary": "CPU high"},
                        "fingerprint": "fp-123",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["alerts_processed"] == 1

    def test_invalid_signature_rejected(self) -> None:
        webhook_triggers._webhook_secret = "my-secret"  # noqa: S105
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/generic",
            json={"alert_id": "test"},
            headers={"X-Webhook-Signature": "bad-sig"},
        )
        assert resp.status_code == 401

    def test_dedup_in_endpoint(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        payload = {"alert_id": "dedup-1", "alert_name": "Same Alert"}

        resp1 = client.post("/api/v1/webhooks/generic", json=payload)
        assert resp1.json()["alerts_processed"] == 1
        assert resp1.json()["alerts_deduplicated"] == 0

        resp2 = client.post("/api/v1/webhooks/generic", json=payload)
        assert resp2.json()["alerts_processed"] == 0
        assert resp2.json()["alerts_deduplicated"] == 1

    def test_list_adapters(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/webhooks/adapters")
        assert resp.status_code == 200
        data = resp.json()
        assert "datadog" in data["adapters"]
        assert "pagerduty" in data["adapters"]

    def test_invalid_json(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/generic",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_unknown_source_uses_generic(self) -> None:
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/webhooks/unknown_source",
            json={
                "alert_id": "unknown-1",
                "name": "Unknown Source Alert",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["alerts_processed"] == 1
