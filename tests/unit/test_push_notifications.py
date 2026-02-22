"""Tests for mobile push notifications."""

from __future__ import annotations

import pytest

from shieldops.integrations.notifications.push import PushDevice, PushNotifier


class TestPushNotifier:
    def test_register_device(self) -> None:
        notifier = PushNotifier()
        device = notifier.register_device(
            user_id="usr-1",
            token="fcm-token-123",
            platform="android",
        )
        assert device.device_id.startswith("dev-")
        assert device.user_id == "usr-1"
        assert device.platform == "android"
        assert "alerts" in device.topics

    def test_register_with_topics(self) -> None:
        notifier = PushNotifier()
        device = notifier.register_device(
            user_id="usr-1",
            token="token",
            topics=["alerts", "escalations", "security"],
        )
        assert len(device.topics) == 3

    def test_unregister_device(self) -> None:
        notifier = PushNotifier()
        device = notifier.register_device(user_id="usr-1", token="tok")
        assert notifier.unregister_device(device.device_id) is True
        assert notifier.unregister_device(device.device_id) is False

    def test_list_devices_by_user(self) -> None:
        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1")
        notifier.register_device(user_id="usr-1", token="t2")
        notifier.register_device(user_id="usr-2", token="t3")
        assert len(notifier.list_devices(user_id="usr-1")) == 2
        assert len(notifier.list_devices(user_id="usr-2")) == 1
        assert len(notifier.list_devices()) == 3

    def test_update_topics(self) -> None:
        notifier = PushNotifier()
        device = notifier.register_device(user_id="usr-1", token="tok")
        updated = notifier.update_topics(device.device_id, ["security", "cost"])
        assert updated is not None
        assert updated.topics == ["security", "cost"]

    def test_update_topics_nonexistent(self) -> None:
        notifier = PushNotifier()
        assert notifier.update_topics("fake", ["a"]) is None

    @pytest.mark.asyncio
    async def test_send_notification(self) -> None:
        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1")
        notifier.register_device(user_id="usr-2", token="t2")
        result = await notifier.send("Test alert", severity="warning")
        assert result is True
        assert len(notifier._sent_messages) == 2

    @pytest.mark.asyncio
    async def test_send_no_devices(self) -> None:
        notifier = PushNotifier()
        result = await notifier.send("No one to receive")
        assert result is True  # Vacuously true
        assert len(notifier._sent_messages) == 0

    @pytest.mark.asyncio
    async def test_send_escalation(self) -> None:
        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1", topics=["escalations"])
        notifier.register_device(user_id="usr-2", token="t2", topics=["security"])
        result = await notifier.send_escalation(
            title="Server Down",
            description="API server is unreachable",
            severity="critical",
        )
        assert result is True
        # Only device with escalations topic
        assert len(notifier._sent_messages) == 1

    @pytest.mark.asyncio
    async def test_send_to_user(self) -> None:
        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1")
        notifier.register_device(user_id="usr-1", token="t2")
        notifier.register_device(user_id="usr-2", token="t3")
        count = await notifier.send_to_user("usr-1", "Hello", "Test")
        assert count == 2

    @pytest.mark.asyncio
    async def test_send_to_topic(self) -> None:
        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1", topics=["security"])
        notifier.register_device(user_id="usr-2", token="t2", topics=["alerts"])
        notifier.register_device(user_id="usr-3", token="t3", topics=["security", "alerts"])
        count = await notifier.send_to_topic("security", "Security Alert", "CVE found")
        assert count == 2

    @pytest.mark.asyncio
    async def test_severity_to_priority(self) -> None:
        assert PushNotifier._severity_to_priority("critical") == "high"
        assert PushNotifier._severity_to_priority("high") == "high"
        assert PushNotifier._severity_to_priority("warning") == "normal"
        assert PushNotifier._severity_to_priority("info") == "normal"

    def test_format_payload(self) -> None:
        notifier = PushNotifier()
        payload = notifier._format_payload(
            title="Test Title",
            body="Test Body",
            severity="critical",
            priority="high",
        )
        assert payload["notification"]["title"] == "Test Title"
        assert payload["notification"]["body"] == "Test Body"
        assert payload["data"]["severity"] == "critical"
        assert payload["android"]["priority"] == "high"
        assert payload["apns"]["headers"]["apns-priority"] == "10"
        assert payload["apns"]["payload"]["aps"]["sound"] == "critical.aiff"

    def test_format_payload_truncation(self) -> None:
        notifier = PushNotifier()
        long_title = "A" * 200
        long_body = "B" * 500
        payload = notifier._format_payload(title=long_title, body=long_body)
        assert len(payload["notification"]["title"]) <= 100
        assert len(payload["notification"]["body"]) <= 256

    def test_device_to_dict(self) -> None:
        device = PushDevice(
            user_id="usr-1",
            token="tok",
            platform="ios",
            topics=["alerts"],
        )
        d = device.to_dict()
        assert d["user_id"] == "usr-1"
        assert d["platform"] == "ios"
        assert "created_at" in d


class TestDeviceRoutes:
    def test_register_device(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import devices

        app = FastAPI()
        app.include_router(devices.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-1", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        notifier = PushNotifier()
        devices.set_push_notifier(notifier)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/devices/register",
            json={
                "token": "fcm-token-123",
                "platform": "android",
                "topics": ["alerts", "security"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["device"]["user_id"] == "usr-1"

    def test_list_devices(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import devices

        app = FastAPI()
        app.include_router(devices.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-1", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        notifier = PushNotifier()
        notifier.register_device(user_id="usr-1", token="t1")
        devices.set_push_notifier(notifier)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/devices")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_delete_device(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import devices

        app = FastAPI()
        app.include_router(devices.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-1", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        notifier = PushNotifier()
        device = notifier.register_device(user_id="usr-1", token="t1")
        devices.set_push_notifier(notifier)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/devices/{device.device_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_other_user_device(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import devices

        app = FastAPI()
        app.include_router(devices.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-1", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        notifier = PushNotifier()
        device = notifier.register_device(user_id="usr-OTHER", token="t1")
        devices.set_push_notifier(notifier)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/devices/{device.device_id}")
        assert resp.status_code == 403

    def test_invalid_platform(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import devices

        app = FastAPI()
        app.include_router(devices.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-1", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        notifier = PushNotifier()
        devices.set_push_notifier(notifier)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/devices/register",
            json={
                "token": "tok",
                "platform": "blackberry",
            },
        )
        assert resp.status_code == 400
