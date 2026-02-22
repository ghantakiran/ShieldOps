"""Mobile push notifications via FCM (Firebase Cloud Messaging)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class PushDevice:
    """Registered mobile device for push notifications."""

    def __init__(
        self,
        device_id: str = "",
        user_id: str = "",
        token: str = "",
        platform: str = "ios",  # ios, android, web
        topics: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.device_id = device_id or f"dev-{uuid4().hex[:12]}"
        self.user_id = user_id
        self.token = token
        self.platform = platform
        self.topics = topics or ["alerts"]
        self.created_at = created_at or datetime.now(UTC)
        self.last_seen_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "platform": self.platform,
            "topics": self.topics,
            "created_at": self.created_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
        }


class PushNotifier:
    """Push notification channel via FCM/APNs.

    Implements the NotificationChannel protocol.

    Features:
    - Device registration and management
    - Topic-based subscriptions
    - Priority routing (critical -> high priority push)
    - Platform-specific payload formatting
    """

    def __init__(
        self,
        fcm_server_key: str = "",
        apns_key: str = "",
        default_topic: str = "alerts",
    ) -> None:
        self._fcm_key = fcm_server_key
        self._apns_key = apns_key
        self._default_topic = default_topic
        self._devices: dict[str, PushDevice] = {}
        self._sent_messages: list[dict[str, Any]] = []  # For testing

    # ── NotificationChannel protocol ──────────────────────────

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a push notification to all registered devices."""
        priority = self._severity_to_priority(severity)
        payload = self._format_payload(
            title="ShieldOps Alert",
            body=message,
            severity=severity,
            priority=priority,
            data=details,
        )

        success = True
        for device in self._devices.values():
            if self._default_topic in device.topics:
                sent = await self._send_to_device(device, payload)
                if not sent:
                    success = False

        return success

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a high-priority escalation push notification."""
        payload = self._format_payload(
            title=f"[ESCALATION] {title}",
            body=description,
            severity=severity,
            priority="high",
            data={
                "source": source,
                "type": "escalation",
                **(details or {}),
            },
        )

        success = True
        for device in self._devices.values():
            if "escalations" in device.topics or "alerts" in device.topics:
                sent = await self._send_to_device(device, payload)
                if not sent:
                    success = False

        return success

    # ── Device management ─────────────────────────────────────

    def register_device(
        self,
        user_id: str,
        token: str,
        platform: str = "ios",
        topics: list[str] | None = None,
    ) -> PushDevice:
        """Register a device for push notifications."""
        device = PushDevice(
            user_id=user_id,
            token=token,
            platform=platform,
            topics=topics or [self._default_topic],
        )
        self._devices[device.device_id] = device
        logger.info("push_device_registered", device_id=device.device_id, platform=platform)
        return device

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device."""
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info("push_device_unregistered", device_id=device_id)
            return True
        return False

    def get_device(self, device_id: str) -> PushDevice | None:
        return self._devices.get(device_id)

    def list_devices(self, user_id: str | None = None) -> list[PushDevice]:
        devices = list(self._devices.values())
        if user_id:
            devices = [d for d in devices if d.user_id == user_id]
        return devices

    def update_topics(self, device_id: str, topics: list[str]) -> PushDevice | None:
        device = self._devices.get(device_id)
        if device:
            device.topics = topics
            logger.info("push_device_topics_updated", device_id=device_id, topics=topics)
        return device

    # ── Send helpers ──────────────────────────────────────────

    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> int:
        """Send push to all devices owned by a user. Returns count sent."""
        payload = self._format_payload(title=title, body=body, severity=severity, data=data)
        count = 0
        for device in self._devices.values():
            if device.user_id == user_id and await self._send_to_device(device, payload):
                count += 1
        return count

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> int:
        """Send push to all devices subscribed to a topic. Returns count sent."""
        payload = self._format_payload(title=title, body=body, severity=severity, data=data)
        count = 0
        for device in self._devices.values():
            if topic in device.topics and await self._send_to_device(device, payload):
                count += 1
        return count

    # ── Private helpers ───────────────────────────────────────

    def _format_payload(
        self,
        title: str,
        body: str,
        severity: str = "info",
        priority: str = "normal",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Format a push notification payload."""
        return {
            "notification": {
                "title": title[:100],  # FCM title limit
                "body": body[:256],  # Truncate body
            },
            "data": {
                "severity": severity,
                "priority": priority,
                "timestamp": datetime.now(UTC).isoformat(),
                **(data or {}),
            },
            "android": {
                "priority": priority,
                "notification": {
                    "channel_id": f"shieldops_{severity}",
                },
            },
            "apns": {
                "headers": {
                    "apns-priority": "10" if priority == "high" else "5",
                },
                "payload": {
                    "aps": {
                        "alert": {"title": title[:100], "body": body[:256]},
                        "sound": "critical.aiff" if severity == "critical" else "default",
                        "badge": 1,
                    },
                },
            },
        }

    async def _send_to_device(self, device: PushDevice, payload: dict[str, Any]) -> bool:
        """Send a push notification to a specific device.

        In production, this would call FCM/APNs HTTP API.
        """
        device.last_seen_at = datetime.now(UTC)
        self._sent_messages.append(
            {
                "device_id": device.device_id,
                "platform": device.platform,
                "payload": payload,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        logger.debug(
            "push_sent",
            device_id=device.device_id,
            platform=device.platform,
        )
        return True

    @staticmethod
    def _severity_to_priority(severity: str) -> str:
        """Map severity to push priority."""
        return "high" if severity in ("critical", "high") else "normal"
