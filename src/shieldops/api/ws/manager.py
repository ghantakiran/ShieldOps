"""WebSocket connection manager — per-channel subscriber tracking."""

from collections import defaultdict
from typing import Any

import structlog
from starlette.websockets import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections with per-channel subscription."""

    def __init__(self) -> None:
        # channel -> set of connected websockets
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, channel: str = "global") -> None:
        await websocket.accept()
        self._channels[channel].add(websocket)
        logger.info("ws_connected", channel=channel)

    def disconnect(self, websocket: WebSocket, channel: str = "global") -> None:
        self._channels[channel].discard(websocket)
        if not self._channels[channel]:
            del self._channels[channel]
        logger.info("ws_disconnected", channel=channel)

    async def broadcast(self, channel: str, event: dict[str, Any]) -> None:
        """Send an event to all subscribers of a channel."""
        dead: list[WebSocket] = []
        for ws in self._channels.get(channel, set()):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._channels[channel].discard(ws)

    async def send_personal(self, websocket: WebSocket, event: dict[str, Any]) -> None:
        await websocket.send_json(event)

    @property
    def active_connections(self) -> int:
        return sum(len(subs) for subs in self._channels.values())


# Module-level singleton for cross-module access
_default_manager: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    """Get or create the default WebSocket connection manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ConnectionManager()
    return _default_manager
