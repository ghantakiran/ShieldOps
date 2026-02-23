"""Tests for shieldops.agents.collaboration – AgentCollaborationProtocol."""

from __future__ import annotations

import time

from shieldops.agents.collaboration import (
    AgentCollaborationProtocol,
    AgentMessage,
    MemoryScope,
    MessagePriority,
    SessionStatus,
)

# ---------------------------------------------------------------------------
# Messaging basics
# ---------------------------------------------------------------------------


class TestSendAndGetMessage:
    def test_send_message(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(
            from_agent="investigation",
            to_agent="remediation",
            subject="CPU spike detected",
            body="Host web-01 at 95% for 5 min",
        )
        result = proto.send_message(msg)
        assert result.id == msg.id
        assert result.from_agent == "investigation"

    def test_get_message_by_id(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(
            from_agent="security",
            to_agent="supervisor",
            subject="CVE alert",
        )
        proto.send_message(msg)
        fetched = proto.get_message(msg.id)
        assert fetched is not None
        assert fetched.subject == "CVE alert"

    def test_get_message_unknown_returns_none(self):
        proto = AgentCollaborationProtocol()
        assert proto.get_message("nonexistent") is None

    def test_message_has_default_priority_normal(self):
        msg = AgentMessage(from_agent="a", to_agent="b", subject="test")
        assert msg.priority == MessagePriority.NORMAL


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------


class TestInbox:
    def test_get_inbox_for_specific_agent(self):
        proto = AgentCollaborationProtocol()
        m1 = AgentMessage(from_agent="a", to_agent="remediation", subject="s1")
        m2 = AgentMessage(from_agent="b", to_agent="remediation", subject="s2")
        m3 = AgentMessage(from_agent="c", to_agent="security", subject="s3")
        proto.send_message(m1)
        proto.send_message(m2)
        proto.send_message(m3)
        inbox = proto.get_inbox("remediation")
        assert len(inbox) == 2
        subjects = {m.subject for m in inbox}
        assert subjects == {"s1", "s2"}

    def test_get_inbox_unacknowledged_only(self):
        proto = AgentCollaborationProtocol()
        m1 = AgentMessage(from_agent="a", to_agent="b", subject="s1")
        m2 = AgentMessage(from_agent="c", to_agent="b", subject="s2")
        proto.send_message(m1)
        proto.send_message(m2)
        proto.acknowledge(m1.id)
        inbox = proto.get_inbox("b", unacknowledged_only=True)
        assert len(inbox) == 1
        assert inbox[0].subject == "s2"

    def test_get_inbox_excludes_expired_messages(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(
            from_agent="a",
            to_agent="b",
            subject="expiring",
            expires_at=time.time() - 1,  # already expired
        )
        proto.send_message(msg)
        inbox = proto.get_inbox("b")
        assert len(inbox) == 0

    def test_get_inbox_respects_limit(self):
        proto = AgentCollaborationProtocol()
        for i in range(10):
            proto.send_message(AgentMessage(from_agent="a", to_agent="b", subject=f"s{i}"))
        inbox = proto.get_inbox("b", limit=3)
        assert len(inbox) == 3

    def test_inbox_ordered_most_recent_first(self):
        proto = AgentCollaborationProtocol()
        m1 = AgentMessage(from_agent="a", to_agent="b", subject="older")
        m2 = AgentMessage(from_agent="a", to_agent="b", subject="newer")
        proto.send_message(m1)
        proto.send_message(m2)
        inbox = proto.get_inbox("b")
        assert inbox[0].created_at >= inbox[1].created_at


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------


class TestAcknowledge:
    def test_acknowledge_message(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(from_agent="a", to_agent="b", subject="test")
        proto.send_message(msg)
        assert proto.acknowledge(msg.id) is True
        fetched = proto.get_message(msg.id)
        assert fetched.acknowledged is True

    def test_acknowledge_unknown_returns_false(self):
        proto = AgentCollaborationProtocol()
        assert proto.acknowledge("no-such-id") is False


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


class TestBroadcast:
    def test_broadcast_sends_to_multiple_agents(self):
        proto = AgentCollaborationProtocol()
        targets = ["investigation", "remediation", "security"]
        msgs = proto.broadcast(
            from_agent="supervisor",
            subject="global alert",
            agent_types=targets,
        )
        assert len(msgs) == 3
        recipients = {m.to_agent for m in msgs}
        assert recipients == set(targets)

    def test_broadcast_excludes_sender(self):
        proto = AgentCollaborationProtocol()
        targets = ["supervisor", "remediation"]
        msgs = proto.broadcast(
            from_agent="supervisor",
            subject="test",
            agent_types=targets,
        )
        recipients = {m.to_agent for m in msgs}
        assert "supervisor" not in recipients
        assert len(msgs) == 1

    def test_broadcast_uses_default_targets(self):
        proto = AgentCollaborationProtocol()
        msgs = proto.broadcast(from_agent="supervisor", subject="global")
        # Default targets exclude the sender
        assert len(msgs) >= 5
        assert all(m.from_agent == "supervisor" for m in msgs)

    def test_broadcast_with_priority(self):
        proto = AgentCollaborationProtocol()
        msgs = proto.broadcast(
            from_agent="security",
            subject="breach",
            agent_types=["supervisor", "remediation"],
            priority=MessagePriority.URGENT,
        )
        assert all(m.priority == MessagePriority.URGENT for m in msgs)


# ---------------------------------------------------------------------------
# Message expiry and pruning
# ---------------------------------------------------------------------------


class TestMessageExpiry:
    def test_expired_messages_excluded_from_inbox(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(
            from_agent="a",
            to_agent="b",
            subject="expires",
            expires_at=time.time() - 10,
        )
        proto.send_message(msg)
        assert proto.get_inbox("b") == []

    def test_non_expired_messages_included(self):
        proto = AgentCollaborationProtocol()
        msg = AgentMessage(
            from_agent="a",
            to_agent="b",
            subject="future",
            expires_at=time.time() + 3600,
        )
        proto.send_message(msg)
        inbox = proto.get_inbox("b")
        assert len(inbox) == 1

    def test_pruning_at_max_capacity(self):
        proto = AgentCollaborationProtocol(max_messages=10)
        for i in range(15):
            proto.send_message(AgentMessage(from_agent="a", to_agent="b", subject=f"m{i}"))
        assert len(proto._messages) <= 10


# ---------------------------------------------------------------------------
# Shared Memory: write / read / list / delete
# ---------------------------------------------------------------------------


class TestSharedMemory:
    def test_write_and_read_memory(self):
        proto = AgentCollaborationProtocol()
        entry = proto.write_memory("rca_result", {"cause": "OOM"}, written_by="investigation")
        assert entry.key == "rca_result"
        assert entry.value == {"cause": "OOM"}
        read = proto.read_memory("rca_result")
        assert read is not None
        assert read.value == {"cause": "OOM"}

    def test_read_nonexistent_key_returns_none(self):
        proto = AgentCollaborationProtocol()
        assert proto.read_memory("nope") is None

    def test_list_memory_all(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("k1", "v1")
        proto.write_memory("k2", "v2")
        entries = proto.list_memory()
        assert len(entries) == 2

    def test_list_memory_by_scope(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("k1", "v1", scope=MemoryScope.GLOBAL)
        proto.write_memory("k2", "v2", scope=MemoryScope.INCIDENT, scope_id="inc-1")
        global_entries = proto.list_memory(scope=MemoryScope.GLOBAL)
        assert len(global_entries) == 1
        assert global_entries[0].key == "k1"

    def test_list_memory_by_scope_id(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("k1", "v1", scope=MemoryScope.INCIDENT, scope_id="inc-1")
        proto.write_memory("k2", "v2", scope=MemoryScope.INCIDENT, scope_id="inc-2")
        entries = proto.list_memory(scope_id="inc-1")
        assert len(entries) == 1
        assert entries[0].key == "k1"

    def test_delete_memory(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("k", "v")
        assert proto.delete_memory("k") is True
        assert proto.read_memory("k") is None

    def test_delete_nonexistent_returns_false(self):
        proto = AgentCollaborationProtocol()
        assert proto.delete_memory("nope") is False


# ---------------------------------------------------------------------------
# Memory scopes
# ---------------------------------------------------------------------------


class TestMemoryScopes:
    def test_global_scope(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("g", 1, scope=MemoryScope.GLOBAL)
        entry = proto.read_memory("g", scope=MemoryScope.GLOBAL)
        assert entry is not None
        assert entry.scope == MemoryScope.GLOBAL

    def test_incident_scope_isolated(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("data", 1, scope=MemoryScope.INCIDENT, scope_id="inc-1")
        proto.write_memory("data", 2, scope=MemoryScope.INCIDENT, scope_id="inc-2")
        e1 = proto.read_memory("data", scope=MemoryScope.INCIDENT, scope_id="inc-1")
        e2 = proto.read_memory("data", scope=MemoryScope.INCIDENT, scope_id="inc-2")
        assert e1.value == 1
        assert e2.value == 2

    def test_session_scope(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("ctx", "abc", scope=MemoryScope.SESSION, scope_id="sess-1")
        entry = proto.read_memory("ctx", scope=MemoryScope.SESSION, scope_id="sess-1")
        assert entry is not None
        assert entry.value == "abc"


# ---------------------------------------------------------------------------
# Memory TTL expiry
# ---------------------------------------------------------------------------


class TestMemoryTTL:
    def test_memory_ttl_expiry(self):
        proto = AgentCollaborationProtocol()
        entry = proto.write_memory("temp", "val", ttl_seconds=1)
        # Force expiry by backdating updated_at
        entry.updated_at = time.time() - 10
        result = proto.read_memory("temp")
        assert result is None

    def test_memory_no_ttl_does_not_expire(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("perm", "val")
        result = proto.read_memory("perm")
        assert result is not None

    def test_expired_entries_excluded_from_list(self):
        proto = AgentCollaborationProtocol()
        entry = proto.write_memory("temp", "val", ttl_seconds=1)
        entry.updated_at = time.time() - 10
        entries = proto.list_memory()
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Memory versioning
# ---------------------------------------------------------------------------


class TestMemoryVersioning:
    def test_first_write_is_version_1(self):
        proto = AgentCollaborationProtocol()
        entry = proto.write_memory("key", "v1")
        assert entry.version == 1

    def test_overwrite_increments_version(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("key", "v1")
        entry2 = proto.write_memory("key", "v2")
        assert entry2.version == 2

    def test_multiple_overwrites(self):
        proto = AgentCollaborationProtocol()
        for i in range(5):
            entry = proto.write_memory("key", f"v{i}")
        assert entry.version == 5


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class TestSessions:
    def test_create_session(self):
        proto = AgentCollaborationProtocol()
        session = proto.create_session(
            participants=["investigation", "remediation"],
        )
        assert session.session_id
        assert session.status == SessionStatus.ACTIVE
        assert "investigation" in session.participants

    def test_get_session(self):
        proto = AgentCollaborationProtocol()
        session = proto.create_session(participants=["a", "b"])
        fetched = proto.get_session(session.session_id)
        assert fetched is not None
        assert fetched.session_id == session.session_id

    def test_get_session_unknown_returns_none(self):
        proto = AgentCollaborationProtocol()
        assert proto.get_session("no-such-session") is None

    def test_end_session(self):
        proto = AgentCollaborationProtocol()
        session = proto.create_session(participants=["a"])
        ended = proto.end_session(session.session_id)
        assert ended is not None
        assert ended.status == SessionStatus.ENDED
        assert ended.ended_at is not None

    def test_end_unknown_session_returns_none(self):
        proto = AgentCollaborationProtocol()
        assert proto.end_session("nope") is None

    def test_list_sessions(self):
        proto = AgentCollaborationProtocol()
        proto.create_session(participants=["a"])
        proto.create_session(participants=["b"])
        sessions = proto.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_by_status(self):
        proto = AgentCollaborationProtocol()
        s1 = proto.create_session(participants=["a"])
        proto.create_session(participants=["b"])
        proto.end_session(s1.session_id)
        active = proto.list_sessions(status=SessionStatus.ACTIVE)
        ended = proto.list_sessions(status=SessionStatus.ENDED)
        assert len(active) == 1
        assert len(ended) == 1

    def test_list_sessions_respects_limit(self):
        proto = AgentCollaborationProtocol()
        for _ in range(5):
            proto.create_session(participants=["a"])
        sessions = proto.list_sessions(limit=2)
        assert len(sessions) == 2


# ---------------------------------------------------------------------------
# Session expiry
# ---------------------------------------------------------------------------


class TestSessionExpiry:
    def test_session_expiry_marks_expired(self):
        proto = AgentCollaborationProtocol(session_timeout_minutes=1)
        session = proto.create_session(participants=["a"], timeout_minutes=1)
        # Backdate creation to force expiry
        session.created_at = time.time() - 120
        fetched = proto.get_session(session.session_id)
        assert fetched.status == SessionStatus.EXPIRED

    def test_active_session_not_expired(self):
        proto = AgentCollaborationProtocol()
        session = proto.create_session(participants=["a"], timeout_minutes=60)
        fetched = proto.get_session(session.session_id)
        assert fetched.status == SessionStatus.ACTIVE

    def test_ended_session_stays_ended_even_if_timed_out(self):
        proto = AgentCollaborationProtocol()
        session = proto.create_session(participants=["a"], timeout_minutes=1)
        proto.end_session(session.session_id)
        session.created_at = time.time() - 120
        fetched = proto.get_session(session.session_id)
        # Should remain ENDED, not flip to EXPIRED
        assert fetched.status == SessionStatus.ENDED


# ---------------------------------------------------------------------------
# Session status transitions
# ---------------------------------------------------------------------------


class TestSessionTransitions:
    def test_active_to_ended(self):
        proto = AgentCollaborationProtocol()
        s = proto.create_session(participants=["a"])
        assert s.status == SessionStatus.ACTIVE
        proto.end_session(s.session_id)
        assert proto.get_session(s.session_id).status == SessionStatus.ENDED

    def test_active_to_expired(self):
        proto = AgentCollaborationProtocol()
        s = proto.create_session(participants=["a"], timeout_minutes=1)
        s.created_at = time.time() - 120
        fetched = proto.get_session(s.session_id)
        assert fetched.status == SessionStatus.EXPIRED

    def test_session_metadata(self):
        proto = AgentCollaborationProtocol()
        s = proto.create_session(
            participants=["a"],
            metadata={"incident_id": "inc-42"},
        )
        assert s.metadata["incident_id"] == "inc-42"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_messages(self):
        proto = AgentCollaborationProtocol()
        proto.send_message(AgentMessage(from_agent="a", to_agent="b", subject="s"))
        stats = proto.get_stats()
        assert stats["total_messages"] == 1

    def test_stats_memory(self):
        proto = AgentCollaborationProtocol()
        proto.write_memory("k1", "v1")
        proto.write_memory("k2", "v2")
        stats = proto.get_stats()
        assert stats["total_memory_entries"] == 2

    def test_stats_sessions(self):
        proto = AgentCollaborationProtocol()
        proto.create_session(participants=["a"])
        proto.create_session(participants=["b"])
        stats = proto.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2

    def test_stats_active_sessions_decrements_on_end(self):
        proto = AgentCollaborationProtocol()
        s = proto.create_session(participants=["a"])
        proto.create_session(participants=["b"])
        proto.end_session(s.session_id)
        stats = proto.get_stats()
        assert stats["active_sessions"] == 1

    def test_stats_max_messages(self):
        proto = AgentCollaborationProtocol(max_messages=500)
        stats = proto.get_stats()
        assert stats["max_messages"] == 500

    def test_stats_empty(self):
        proto = AgentCollaborationProtocol()
        stats = proto.get_stats()
        assert stats["total_messages"] == 0
        assert stats["total_memory_entries"] == 0
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
