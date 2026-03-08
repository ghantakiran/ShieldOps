"""WebSocket handler for real-time agent task step updates."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from shieldops.api.auth.service import decode_token

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket connections per task_id.

    Provides methods to connect, disconnect, and broadcast JSON messages
    to all clients subscribed to a specific agent task.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection for a task."""
        await websocket.accept()
        self._connections[task_id].add(websocket)
        logger.info("agent_ws_connected", task_id=task_id)

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from a task's subscriber set."""
        self._connections[task_id].discard(websocket)
        if not self._connections[task_id]:
            del self._connections[task_id]
        logger.info("agent_ws_disconnected", task_id=task_id)

    async def broadcast(self, task_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connections subscribed to a task.

        Dead connections are cleaned up automatically.
        """
        subscribers = list(self._connections.get(task_id, set()))
        if not subscribers:
            return

        async def _safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await ws.send_json(message)
            except Exception:
                return ws
            return None

        results = await asyncio.gather(*[_safe_send(ws) for ws in subscribers])
        for dead_ws in results:
            if dead_ws is not None:
                self._connections[task_id].discard(dead_ws)

    @property
    def active_tasks(self) -> int:
        """Return the number of tasks with active connections."""
        return len(self._connections)

    @property
    def active_connections(self) -> int:
        """Return the total number of active WebSocket connections."""
        return sum(len(subs) for subs in self._connections.values())


# Module-level singleton — importable by other routes (e.g. agent_tasks.py)
manager = ConnectionManager()


async def notify_step_update(
    task_id: str,
    step_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Broadcast a step update to all clients connected for a given task.

    Constructs the appropriate event type based on the status and broadcasts
    a JSON message matching the agent task step update schema.
    """
    event_type = "step_update"
    if status == "complete":
        event_type = "task_complete"
    elif status == "approval_required":
        event_type = "approval_required"
    elif status == "error":
        event_type = "error"

    message: dict[str, Any] = {
        "event": event_type,
        "step_id": step_id,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if result is not None:
        message["result"] = result
    if error is not None:
        message["error"] = error

    logger.info(
        "agent_step_update",
        task_id=task_id,
        step_id=step_id,
        event=event_type,
        status=status,
    )
    await manager.broadcast(task_id, message)


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> dict[str, Any] | None:
    """Validate JWT from query parameter. Returns payload or None."""
    if not token:
        return None
    return decode_token(token)


@router.websocket("/ws/agent-tasks/{task_id}")
async def ws_agent_task(
    websocket: WebSocket,
    task_id: str,
    token: str | None = Query(default=None),
) -> None:
    """Stream real-time step updates for an agent task execution.

    Sends JSON messages with the schema::

        {
            "event": "step_update" | "task_complete" | "approval_required" | "error",
            "step_id": "<str>",
            "status": "<str>",
            "result": { ... },      // optional
            "error": "<str>",       // optional
            "timestamp": "<iso8601>"
        }
    """
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await manager.connect(task_id, websocket)
    try:
        while True:
            # Keep connection alive — handles client pings and any incoming text
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
