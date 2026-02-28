"""Tests for shieldops.incidents.war_room_orchestrator."""

from __future__ import annotations

from shieldops.incidents.war_room_orchestrator import (
    IncidentWarRoomOrchestrator,
    WarRoomOrchestratorReport,
    WarRoomPriority,
    WarRoomRecord,
    WarRoomRole,
    WarRoomStatus,
    WarRoomTemplate,
)


def _engine(**kw) -> IncidentWarRoomOrchestrator:
    return IncidentWarRoomOrchestrator(**kw)


# ---------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------


class TestEnums:
    # WarRoomRole (5)
    def test_role_incident_commander(self):
        assert WarRoomRole.INCIDENT_COMMANDER == "incident_commander"

    def test_role_communications_lead(self):
        assert WarRoomRole.COMMUNICATIONS_LEAD == "communications_lead"

    def test_role_technical_lead(self):
        assert WarRoomRole.TECHNICAL_LEAD == "technical_lead"

    def test_role_scribe(self):
        assert WarRoomRole.SCRIBE == "scribe"

    def test_role_observer(self):
        assert WarRoomRole.OBSERVER == "observer"

    # WarRoomStatus (5)
    def test_status_assembling(self):
        assert WarRoomStatus.ASSEMBLING == "assembling"

    def test_status_active(self):
        assert WarRoomStatus.ACTIVE == "active"

    def test_status_monitoring(self):
        assert WarRoomStatus.MONITORING == "monitoring"

    def test_status_resolved(self):
        assert WarRoomStatus.RESOLVED == "resolved"

    def test_status_post_mortem(self):
        assert WarRoomStatus.POST_MORTEM == "post_mortem"

    # WarRoomPriority (5)
    def test_priority_sev1(self):
        assert WarRoomPriority.SEV1 == "sev1"

    def test_priority_sev2(self):
        assert WarRoomPriority.SEV2 == "sev2"

    def test_priority_sev3(self):
        assert WarRoomPriority.SEV3 == "sev3"

    def test_priority_sev4(self):
        assert WarRoomPriority.SEV4 == "sev4"

    def test_priority_sev5(self):
        assert WarRoomPriority.SEV5 == "sev5"


# ---------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------


class TestModels:
    def test_war_room_record_defaults(self):
        r = WarRoomRecord()
        assert r.id
        assert r.incident_name == ""
        assert r.role == WarRoomRole.INCIDENT_COMMANDER
        assert r.status == WarRoomStatus.ASSEMBLING
        assert r.priority == WarRoomPriority.SEV3
        assert r.participant_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_war_room_template_defaults(self):
        r = WarRoomTemplate()
        assert r.id
        assert r.template_name == ""
        assert r.role == WarRoomRole.INCIDENT_COMMANDER
        assert r.priority == WarRoomPriority.SEV3
        assert r.auto_escalate is True
        assert r.escalation_minutes == 30.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = WarRoomOrchestratorReport()
        assert r.total_war_rooms == 0
        assert r.total_templates == 0
        assert r.active_rate_pct == 0.0
        assert r.by_role == {}
        assert r.by_status == {}
        assert r.escalation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------
# record_war_room
# ---------------------------------------------------------------


class TestRecordWarRoom:
    def test_basic(self):
        eng = _engine()
        r = eng.record_war_room(
            "inc-a",
            role=WarRoomRole.INCIDENT_COMMANDER,
            status=WarRoomStatus.ACTIVE,
        )
        assert r.incident_name == "inc-a"
        assert r.role == WarRoomRole.INCIDENT_COMMANDER

    def test_with_priority(self):
        eng = _engine()
        r = eng.record_war_room(
            "inc-b",
            priority=WarRoomPriority.SEV1,
        )
        assert r.priority == WarRoomPriority.SEV1

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_war_room(f"inc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------
# get_war_room
# ---------------------------------------------------------------


class TestGetWarRoom:
    def test_found(self):
        eng = _engine()
        r = eng.record_war_room("inc-a")
        assert eng.get_war_room(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_war_room("nonexistent") is None


# ---------------------------------------------------------------
# list_war_rooms
# ---------------------------------------------------------------


class TestListWarRooms:
    def test_list_all(self):
        eng = _engine()
        eng.record_war_room("inc-a")
        eng.record_war_room("inc-b")
        assert len(eng.list_war_rooms()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_war_room("inc-a")
        eng.record_war_room("inc-b")
        results = eng.list_war_rooms(incident_name="inc-a")
        assert len(results) == 1

    def test_filter_by_role(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            role=WarRoomRole.SCRIBE,
        )
        eng.record_war_room(
            "inc-b",
            role=WarRoomRole.OBSERVER,
        )
        results = eng.list_war_rooms(role=WarRoomRole.SCRIBE)
        assert len(results) == 1


# ---------------------------------------------------------------
# add_template
# ---------------------------------------------------------------


class TestAddTemplate:
    def test_basic(self):
        eng = _engine()
        t = eng.add_template(
            "sev1-template",
            role=WarRoomRole.INCIDENT_COMMANDER,
            priority=WarRoomPriority.SEV1,
            auto_escalate=True,
            escalation_minutes=15.0,
        )
        assert t.template_name == "sev1-template"
        assert t.auto_escalate is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_template(f"tmpl-{i}")
        assert len(eng._templates) == 2


# ---------------------------------------------------------------
# analyze_war_room_effectiveness
# ---------------------------------------------------------------


class TestAnalyzeWarRoomEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.RESOLVED,
        )
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.ACTIVE,
        )
        result = eng.analyze_war_room_effectiveness("inc-a")
        assert result["incident_name"] == "inc-a"
        assert result["war_room_count"] == 2
        assert result["resolution_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_war_room_effectiveness("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_resolution_rate_pct=50.0)
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.RESOLVED,
        )
        result = eng.analyze_war_room_effectiveness("inc-a")
        assert result["meets_threshold"] is True


# ---------------------------------------------------------------
# identify_stalled_war_rooms
# ---------------------------------------------------------------


class TestIdentifyStalledWarRooms:
    def test_with_stalled(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.ACTIVE,
        )
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.ASSEMBLING,
        )
        eng.record_war_room(
            "inc-b",
            status=WarRoomStatus.RESOLVED,
        )
        results = eng.identify_stalled_war_rooms()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stalled_war_rooms() == []


# ---------------------------------------------------------------
# rank_by_participant_count
# ---------------------------------------------------------------


class TestRankByParticipantCount:
    def test_with_data(self):
        eng = _engine()
        eng.record_war_room("inc-a", participant_count=10)
        eng.record_war_room("inc-a", participant_count=20)
        eng.record_war_room("inc-b", participant_count=5)
        results = eng.rank_by_participant_count()
        assert results[0]["incident_name"] == "inc-a"
        assert results[0]["avg_participant_count"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_participant_count() == []


# ---------------------------------------------------------------
# detect_escalation_patterns
# ---------------------------------------------------------------


class TestDetectEscalationPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_war_room(
                "inc-a",
                status=WarRoomStatus.ACTIVE,
            )
        eng.record_war_room(
            "inc-b",
            status=WarRoomStatus.RESOLVED,
        )
        results = eng.detect_escalation_patterns()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-a"
        assert results[0]["escalation_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.ACTIVE,
        )
        assert eng.detect_escalation_patterns() == []


# ---------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            status=WarRoomStatus.RESOLVED,
        )
        eng.record_war_room(
            "inc-b",
            status=WarRoomStatus.ACTIVE,
        )
        eng.record_war_room(
            "inc-b",
            status=WarRoomStatus.ACTIVE,
        )
        eng.add_template("tmpl-1")
        report = eng.generate_report()
        assert report.total_war_rooms == 3
        assert report.total_templates == 1
        assert report.by_role != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_war_rooms == 0
        assert "below" in report.recommendations[0]


# ---------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_war_room("inc-a")
        eng.add_template("tmpl-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._templates) == 0


# ---------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_war_rooms"] == 0
        assert stats["total_templates"] == 0
        assert stats["role_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_war_room(
            "inc-a",
            role=WarRoomRole.INCIDENT_COMMANDER,
        )
        eng.record_war_room(
            "inc-b",
            role=WarRoomRole.SCRIBE,
        )
        eng.add_template("t1")
        stats = eng.get_stats()
        assert stats["total_war_rooms"] == 2
        assert stats["total_templates"] == 1
        assert stats["unique_incidents"] == 2
