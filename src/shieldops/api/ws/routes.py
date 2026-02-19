"""WebSocket routes for real-time event streaming."""

from typing import Any

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from shieldops.api.auth.service import decode_token
from shieldops.api.ws.manager import ConnectionManager, get_ws_manager

logger = structlog.get_logger()

router = APIRouter()
manager = get_ws_manager()


def get_manager() -> ConnectionManager:
    return manager


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> dict[str, Any] | None:
    """Validate JWT from query parameter. Returns payload or None."""
    if not token:
        return None
    return decode_token(token)


@router.websocket("/ws/events")
async def ws_global_events(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Global event stream — broadcasts all investigation/remediation events."""
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await manager.connect(websocket, channel="global")
    try:
        while True:
            # Keep alive — client can send pings or we just wait
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel="global")


@router.websocket("/ws/investigations/{investigation_id}")
async def ws_investigation_events(
    websocket: WebSocket,
    investigation_id: str,
    token: str | None = Query(default=None),
) -> None:
    """Stream events for a specific investigation."""
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    channel = f"investigation:{investigation_id}"
    await manager.connect(websocket, channel=channel)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel)


@router.websocket("/ws/remediations/{remediation_id}")
async def ws_remediation_events(
    websocket: WebSocket,
    remediation_id: str,
    token: str | None = Query(default=None),
) -> None:
    """Stream events for a specific remediation."""
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    channel = f"remediation:{remediation_id}"
    await manager.connect(websocket, channel=channel)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel)


@router.websocket("/ws/vulnerabilities")
async def ws_vulnerability_events(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Stream vulnerability lifecycle events."""
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await manager.connect(websocket, channel="vulnerabilities")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel="vulnerabilities")


@router.websocket("/ws/security-chat/{session_id}")
async def ws_security_chat(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
) -> None:
    """WebSocket for AI security chat sessions."""
    payload = await _authenticate_ws(websocket, token)
    if payload is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    channel = f"security-chat:{session_id}"
    await manager.connect(websocket, channel=channel)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel)
