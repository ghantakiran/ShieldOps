"""AI Security Chat API endpoints.

Provides a conversational interface to the ShieldOps security agent.
Sessions are stored in-memory keyed by session_id; replace the
``_sessions`` dict with a Redis-backed store for production use.

Routes
------
POST /api/v1/security/chat          — send a message, receive an AI response
GET  /api/v1/security/chat/sessions — list all active sessions
GET  /api/v1/security/chat/sessions/{session_id} — fetch session history
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/security/chat", tags=["Security Chat"])

# Module-level singletons — injected at app startup via set_* helpers
_chat_agent: Any | None = None
_repository: Any | None = None
_session_store: Any | None = None


def set_chat_agent(agent: Any) -> None:
    """Wire the SecurityChatAgent instance (called from app lifespan)."""
    global _chat_agent
    _chat_agent = agent


def set_repository(repo: Any) -> None:
    """Wire the repository instance (called from app lifespan)."""
    global _repository
    _repository = repo


def set_session_store(store: Any) -> None:
    """Wire the ChatSessionStore backend (called from app lifespan)."""
    global _session_store
    _session_store = store


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Payload for a single chat turn."""

    message: str = Field(min_length=1, max_length=4096)
    session_id: str | None = Field(
        default=None,
        description="Continue an existing session; omit to start a new one.",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-supplied context (e.g. current vuln_id).",
    )


class ChatResponse(BaseModel):
    """Response from the AI security assistant for one chat turn."""

    response: str
    session_id: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class SessionSummary(BaseModel):
    """Lightweight summary of a single chat session."""

    id: str
    message_count: int
    created_at: str | None
    last_message: str | None


# ---------------------------------------------------------------------------
# In-memory session store (legacy fallback when no store is injected)
# ---------------------------------------------------------------------------

# Maps session_id → ordered list of {role, content, timestamp} dicts.
# Replaced by ChatSessionStore when available (see set_session_store).
_sessions: dict[str, list[dict[str, Any]]] = {}

_MAX_HISTORY = 50  # Hard cap per session to bound memory usage


def _get_history(session_id: str) -> list[dict[str, Any]]:
    """Get session history from store or in-memory fallback (sync helper)."""
    return _sessions.setdefault(session_id, [])


async def _get_history_async(session_id: str) -> list[dict[str, Any]]:
    """Get session history from ChatSessionStore if available."""
    if _session_store is not None:
        session = await _session_store.get_session(session_id)
        if session is not None:
            return [m.model_dump() if hasattr(m, "model_dump") else m for m in session.messages]
        return []
    return _sessions.setdefault(session_id, [])


async def _save_history_async(session_id: str, messages: list[dict[str, Any]]) -> None:
    """Persist session history via ChatSessionStore or in-memory."""
    if _session_store is not None:
        from shieldops.api.routes.chat_session_store import ChatMessage, ChatSession

        chat_messages = [
            ChatMessage(
                role=m.get("role", "user"),
                content=m.get("content", ""),
                timestamp=m.get("timestamp", ""),
            )
            for m in messages
        ]
        session = ChatSession(session_id=session_id, messages=chat_messages)
        await _session_store.save_session(session)
    else:
        trimmed = messages[-_MAX_HISTORY:]
        _sessions[session_id] = trimmed


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user: UserResponse = Depends(get_current_user),
) -> ChatResponse:
    """Send a message to the AI security assistant and receive a reply.

    - Creates a new session when ``session_id`` is omitted.
    - Automatically pulls relevant vulnerability/team data into the agent
      context based on keywords in the user's message.
    - Falls back to a direct LLM call when no chat agent is configured.
    """
    session_id = body.session_id or f"chat-{uuid4().hex[:12]}"

    history = await _get_history_async(session_id)

    history.append(
        {
            "role": "user",
            "content": body.message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    # Enrich context from the repository before calling the agent
    context = await _build_context(body.message, body.context)

    response_text: str
    actions: list[dict[str, Any]] = []
    sources: list[str] = []

    if _chat_agent is not None:
        try:
            result = await _chat_agent.respond(
                message=body.message,
                history=history[:-1],  # Exclude the message we just appended
                context=context,
                user_id=user.id,
            )
            response_text = result.get("response", "I couldn't process that request.")
            actions = result.get("actions", [])
            sources = result.get("sources", [])
        except Exception as exc:
            logger.error("chat_agent_error", session=session_id, user=user.id, error=str(exc))
            response_text = "I encountered an error processing your request. Please try again."
    else:
        # No agent configured — use LLM directly (no tool-calling)
        logger.warning("chat_agent_not_configured", session=session_id)
        response_text = await _fallback_response(body.message, context, history)

    history.append(
        {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    # Persist via session store (or trim in-memory)
    await _save_history_async(session_id, history)

    logger.info(
        "chat_turn_complete",
        session=session_id,
        user=user.id,
        message_count=len(history),
    )

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        actions=actions,
        sources=[s for s in sources if s],  # strip empty strings
    )


@router.get("/sessions", response_model=dict[str, list[SessionSummary]])
async def list_sessions(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, list[SessionSummary]]:
    """Return a summary of all active chat sessions."""
    if _session_store is not None:
        sessions = await _session_store.list_sessions()
        summaries = [
            SessionSummary(
                id=s.session_id,
                message_count=len(s.messages),
                created_at=s.created_at if hasattr(s, "created_at") else None,
                last_message=s.updated_at if hasattr(s, "updated_at") else None,
            )
            for s in sessions
        ]
    else:
        summaries = [
            SessionSummary(
                id=sid,
                message_count=len(msgs),
                created_at=msgs[0]["timestamp"] if msgs else None,
                last_message=msgs[-1]["timestamp"] if msgs else None,
            )
            for sid, msgs in _sessions.items()
        ]
    return {"sessions": summaries}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve the full message history for a chat session.

    Raises 404 when the session does not exist or has been evicted.
    """
    messages = await _get_history_async(session_id)
    if not messages and session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "session_id": session_id,
        "messages": messages,
        "message_count": len(messages),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _build_context(
    message: str,
    provided_context: dict[str, Any],
) -> dict[str, Any]:
    """Enrich the agent context with data fetched from the repository.

    Only fetches what seems relevant to the current message to keep
    latency low. Repository errors are swallowed so a transient DB
    blip never breaks the chat flow.
    """
    context: dict[str, Any] = {**provided_context}

    if _repository is None:
        return context

    msg_lower = message.lower()

    try:
        vuln_keywords = {"vulnerability", "vuln", "cve", "finding", "critical", "high"}
        if any(kw in msg_lower for kw in vuln_keywords):
            context["vulnerability_stats"] = await _repository.get_vulnerability_stats()

            critical_vulns = await _repository.list_vulnerabilities(severity="critical", limit=10)
            context["critical_vulnerabilities"] = critical_vulns

        sla_keywords = {"sla", "breach", "overdue", "expired"}
        if any(kw in msg_lower for kw in sla_keywords):
            context["sla_breaches"] = await _repository.list_vulnerabilities(
                sla_breached=True, limit=20
            )

        team_keywords = {"team", "assign", "owner", "delegate"}
        if any(kw in msg_lower for kw in team_keywords):
            context["teams"] = await _repository.list_teams()

    except Exception as exc:
        logger.warning("chat_context_build_failed", error=str(exc))

    return context


async def _fallback_response(
    message: str,
    context: dict[str, Any],
    history: list[dict[str, Any]],
) -> str:
    """Generate a response using llm_structured without agent tools.

    Used when no SecurityChatAgent is wired up (e.g. cold-start or tests).
    """
    try:
        from pydantic import BaseModel as _BaseModel

        from shieldops.utils.llm import llm_structured

        class _ChatReply(_BaseModel):
            response: str

        context_lines: list[str] = []

        stats = context.get("vulnerability_stats")
        if stats:
            context_lines.append(
                f"Vulnerability stats: total={stats.get('total', 0)}, "
                f"by_severity={stats.get('by_severity', {})}, "
                f"sla_breaches={stats.get('sla_breaches', 0)}"
            )

        critical = context.get("critical_vulnerabilities", [])
        if critical:
            context_lines.append(f"Critical vulnerabilities ({len(critical)} found):")
            for vuln in critical[:5]:
                vuln_id = vuln.get("cve_id") or vuln.get("id", "?")
                title = vuln.get("title", "")[:80]
                status = vuln.get("status", "?")
                context_lines.append(f"  - {vuln_id}: {title} [{status}]")

        sla_breaches = context.get("sla_breaches", [])
        if sla_breaches:
            context_lines.append(f"SLA breaches: {len(sla_breaches)} vulnerabilities overdue")

        context_text = "\n".join(context_lines) if context_lines else "No live data available."

        history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history[-6:])

        system_prompt = (
            "You are a security operations assistant for ShieldOps, "
            "an enterprise SRE platform. Help security engineers understand "
            "vulnerability findings, plan remediation, and improve security posture.\n\n"
            f"Available data:\n{context_text}\n\n"
            f"Recent conversation:\n{history_text}"
        )

        result = await llm_structured(
            system_prompt=system_prompt,
            user_prompt=message,
            schema=_ChatReply,
        )
        return result.response  # type: ignore[union-attr]

    except Exception as exc:
        logger.error("chat_fallback_failed", error=str(exc))
        return (
            "I'm currently unable to process your request. "
            "Please try again or check the security dashboard for the latest data."
        )
