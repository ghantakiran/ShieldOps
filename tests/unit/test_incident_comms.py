"""Tests for shieldops.incidents.incident_comms — IncidentCommunicationManager.

Covers MessageType and AudienceType enums, CommunicationTemplate / IncidentMessage /
CommunicationPlan models, and all IncidentCommunicationManager operations including
template management, message sending, acknowledgement, plans, and statistics.
"""

from __future__ import annotations

import pytest

from shieldops.incidents.incident_comms import (
    AudienceType,
    CommunicationPlan,
    CommunicationTemplate,
    IncidentCommunicationManager,
    IncidentMessage,
    MessageType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager(**kw) -> IncidentCommunicationManager:
    return IncidentCommunicationManager(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of MessageType and AudienceType."""

    # -- MessageType (5 members) ---------------------------------------------

    def test_message_type_status_update(self):
        assert MessageType.STATUS_UPDATE == "status_update"

    def test_message_type_stakeholder_notification(self):
        assert MessageType.STAKEHOLDER_NOTIFICATION == "stakeholder_notification"

    def test_message_type_public_update(self):
        assert MessageType.PUBLIC_UPDATE == "public_update"

    def test_message_type_internal_note(self):
        assert MessageType.INTERNAL_NOTE == "internal_note"

    def test_message_type_resolution_notice(self):
        assert MessageType.RESOLUTION_NOTICE == "resolution_notice"

    # -- AudienceType (5 members) --------------------------------------------

    def test_audience_engineering(self):
        assert AudienceType.ENGINEERING == "engineering"

    def test_audience_management(self):
        assert AudienceType.MANAGEMENT == "management"

    def test_audience_customers(self):
        assert AudienceType.CUSTOMERS == "customers"

    def test_audience_public(self):
        assert AudienceType.PUBLIC == "public"

    def test_audience_all(self):
        assert AudienceType.ALL == "all"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_communication_template_defaults(self):
        tmpl = CommunicationTemplate(
            name="t1",
            message_type=MessageType.STATUS_UPDATE,
        )
        assert tmpl.id
        assert tmpl.subject_template == ""
        assert tmpl.body_template == ""
        assert tmpl.audience == AudienceType.ENGINEERING
        assert tmpl.created_at > 0

    def test_incident_message_defaults(self):
        msg = IncidentMessage(
            incident_id="inc-1",
            message_type=MessageType.INTERNAL_NOTE,
        )
        assert msg.id
        assert msg.audience == AudienceType.ENGINEERING
        assert msg.subject == ""
        assert msg.body == ""
        assert msg.sent_by == ""
        assert msg.sent_at > 0
        assert msg.channels == []
        assert msg.acknowledged_by == []

    def test_communication_plan_defaults(self):
        plan = CommunicationPlan(incident_id="inc-1")
        assert plan.id
        assert plan.template_ids == []
        assert plan.escalation_minutes == [15, 30, 60]
        assert plan.auto_notify is True
        assert plan.created_at > 0


# ===========================================================================
# create_template
# ===========================================================================


class TestCreateTemplate:
    """Tests for IncidentCommunicationManager.create_template."""

    def test_basic_create(self):
        mgr = _manager()
        tmpl = mgr.create_template("t1", MessageType.STATUS_UPDATE)
        assert tmpl.name == "t1"
        assert tmpl.message_type == MessageType.STATUS_UPDATE
        assert mgr.get_template(tmpl.id) is tmpl

    def test_create_with_all_fields(self):
        mgr = _manager()
        tmpl = mgr.create_template(
            "t2",
            MessageType.PUBLIC_UPDATE,
            subject_template="Incident {{id}}",
            body_template="Status: {{status}}",
            audience=AudienceType.CUSTOMERS,
        )
        assert tmpl.subject_template == "Incident {{id}}"
        assert tmpl.body_template == "Status: {{status}}"
        assert tmpl.audience == AudienceType.CUSTOMERS

    def test_create_max_limit(self):
        mgr = _manager(max_templates=2)
        mgr.create_template("t1", MessageType.STATUS_UPDATE)
        mgr.create_template("t2", MessageType.INTERNAL_NOTE)
        with pytest.raises(ValueError, match="Maximum templates limit reached"):
            mgr.create_template("t3", MessageType.PUBLIC_UPDATE)


# ===========================================================================
# send_message
# ===========================================================================


class TestSendMessage:
    """Tests for IncidentCommunicationManager.send_message."""

    def test_basic_send(self):
        mgr = _manager()
        msg = mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "Investigating issue")
        assert msg.incident_id == "inc-1"
        assert msg.message_type == MessageType.STATUS_UPDATE
        assert msg.body == "Investigating issue"

    def test_send_with_all_fields(self):
        mgr = _manager()
        msg = mgr.send_message(
            "inc-1",
            MessageType.STAKEHOLDER_NOTIFICATION,
            "Major outage",
            subject="Incident Update",
            sent_by="oncall-eng",
            channels=["slack", "email"],
            audience=AudienceType.MANAGEMENT,
        )
        assert msg.subject == "Incident Update"
        assert msg.sent_by == "oncall-eng"
        assert msg.channels == ["slack", "email"]
        assert msg.audience == AudienceType.MANAGEMENT

    def test_trims_to_max(self):
        mgr = _manager(max_messages=3)
        for i in range(5):
            mgr.send_message("inc-1", MessageType.INTERNAL_NOTE, f"msg-{i}")
        messages = mgr.get_messages()
        assert len(messages) == 3
        # Should keep the most recent 3
        assert messages[0].body == "msg-2"


# ===========================================================================
# acknowledge_message
# ===========================================================================


class TestAcknowledgeMessage:
    """Tests for IncidentCommunicationManager.acknowledge_message."""

    def test_basic_acknowledge(self):
        mgr = _manager()
        msg = mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "update")
        result = mgr.acknowledge_message(msg.id, "alice")
        assert result is not None
        assert "alice" in result.acknowledged_by

    def test_duplicate_user_not_added(self):
        mgr = _manager()
        msg = mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "update")
        mgr.acknowledge_message(msg.id, "alice")
        mgr.acknowledge_message(msg.id, "alice")
        result = mgr.acknowledge_message(msg.id, "alice")
        assert result is not None
        assert result.acknowledged_by.count("alice") == 1

    def test_not_found(self):
        mgr = _manager()
        assert mgr.acknowledge_message("nonexistent", "alice") is None


# ===========================================================================
# create_plan
# ===========================================================================


class TestCreatePlan:
    """Tests for IncidentCommunicationManager.create_plan."""

    def test_basic_plan(self):
        mgr = _manager()
        plan = mgr.create_plan("inc-1")
        assert plan.incident_id == "inc-1"
        assert plan.template_ids == []
        assert mgr.get_plan("inc-1") is plan

    def test_plan_with_template_ids(self):
        mgr = _manager()
        tmpl = mgr.create_template("t1", MessageType.STATUS_UPDATE)
        plan = mgr.create_plan("inc-1", template_ids=[tmpl.id])
        assert tmpl.id in plan.template_ids


# ===========================================================================
# list_templates
# ===========================================================================


class TestListTemplates:
    """Tests for IncidentCommunicationManager.list_templates."""

    def test_list_all(self):
        mgr = _manager()
        mgr.create_template("t1", MessageType.STATUS_UPDATE)
        mgr.create_template("t2", MessageType.INTERNAL_NOTE)
        assert len(mgr.list_templates()) == 2

    def test_list_by_type(self):
        mgr = _manager()
        mgr.create_template("t1", MessageType.STATUS_UPDATE)
        mgr.create_template("t2", MessageType.INTERNAL_NOTE)
        result = mgr.list_templates(message_type=MessageType.STATUS_UPDATE)
        assert len(result) == 1
        assert result[0].message_type == MessageType.STATUS_UPDATE

    def test_list_empty(self):
        mgr = _manager()
        assert mgr.list_templates() == []


# ===========================================================================
# delete_template
# ===========================================================================


class TestDeleteTemplate:
    """Tests for IncidentCommunicationManager.delete_template."""

    def test_delete_existing(self):
        mgr = _manager()
        tmpl = mgr.create_template("t1", MessageType.STATUS_UPDATE)
        assert mgr.delete_template(tmpl.id) is True
        assert mgr.get_template(tmpl.id) is None

    def test_delete_nonexistent(self):
        mgr = _manager()
        assert mgr.delete_template("nonexistent") is False


# ===========================================================================
# get_messages
# ===========================================================================


class TestGetMessages:
    """Tests for IncidentCommunicationManager.get_messages."""

    def test_all_messages(self):
        mgr = _manager()
        mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "body1")
        mgr.send_message("inc-2", MessageType.INTERNAL_NOTE, "body2")
        assert len(mgr.get_messages()) == 2

    def test_by_incident(self):
        mgr = _manager()
        mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "body1")
        mgr.send_message("inc-2", MessageType.INTERNAL_NOTE, "body2")
        result = mgr.get_messages(incident_id="inc-1")
        assert len(result) == 1
        assert result[0].incident_id == "inc-1"

    def test_by_type(self):
        mgr = _manager()
        mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "body1")
        mgr.send_message("inc-1", MessageType.INTERNAL_NOTE, "body2")
        result = mgr.get_messages(message_type=MessageType.INTERNAL_NOTE)
        assert len(result) == 1
        assert result[0].message_type == MessageType.INTERNAL_NOTE


# ===========================================================================
# get_plan
# ===========================================================================


class TestGetPlan:
    """Tests for IncidentCommunicationManager.get_plan."""

    def test_existing(self):
        mgr = _manager()
        plan = mgr.create_plan("inc-1")
        assert mgr.get_plan("inc-1") is plan

    def test_not_found(self):
        mgr = _manager()
        assert mgr.get_plan("nonexistent") is None


# ===========================================================================
# get_stats
# ===========================================================================


class TestGetStats:
    """Tests for IncidentCommunicationManager.get_stats."""

    def test_empty_stats(self):
        mgr = _manager()
        stats = mgr.get_stats()
        assert stats["total_templates"] == 0
        assert stats["total_messages"] == 0
        assert stats["total_plans"] == 0
        assert stats["messages_by_type"] == {}
        assert stats["messages_by_audience"] == {}
        assert stats["acknowledgement_rate"] == 0.0

    def test_populated_stats(self):
        mgr = _manager()
        mgr.create_template("t1", MessageType.STATUS_UPDATE)
        mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "body1")
        mgr.send_message("inc-1", MessageType.INTERNAL_NOTE, "body2")
        mgr.create_plan("inc-1")
        stats = mgr.get_stats()
        assert stats["total_templates"] == 1
        assert stats["total_messages"] == 2
        assert stats["total_plans"] == 1
        assert stats["messages_by_type"]["status_update"] == 1
        assert stats["messages_by_type"]["internal_note"] == 1

    def test_acknowledgement_rate(self):
        mgr = _manager()
        msg1 = mgr.send_message("inc-1", MessageType.STATUS_UPDATE, "body1")
        mgr.send_message("inc-1", MessageType.INTERNAL_NOTE, "body2")
        mgr.acknowledge_message(msg1.id, "alice")
        stats = mgr.get_stats()
        # 1 out of 2 messages acknowledged => 50%
        assert stats["acknowledgement_rate"] == pytest.approx(50.0)
