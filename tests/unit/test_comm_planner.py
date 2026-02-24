"""Tests for shieldops.incidents.comm_planner — IncidentCommPlanner.

Covers:
- Audience, CommChannel, CommCadence enums
- CommPlan, CommMessage, CommPlannerReport model defaults
- create_plan (basic, unique IDs, extra fields, eviction at max)
- get_plan (found, not found)
- list_plans (all, filter by incident, filter by audience, limit)
- send_message (basic, plan not found)
- check_overdue_comms (overdue, none)
- calculate_comm_coverage (partial, full)
- analyze_response_times (with data, empty)
- detect_communication_gaps (gaps, no gaps)
- generate_comm_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.incidents.comm_planner import (
    Audience,
    CommCadence,
    CommChannel,
    CommMessage,
    CommPlan,
    CommPlannerReport,
    IncidentCommPlanner,
)


def _engine(**kw) -> IncidentCommPlanner:
    return IncidentCommPlanner(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # Audience (5 values)

    def test_audience_engineering(self):
        assert Audience.ENGINEERING == "engineering"

    def test_audience_leadership(self):
        assert Audience.LEADERSHIP == "leadership"

    def test_audience_customers(self):
        assert Audience.CUSTOMERS == "customers"

    def test_audience_partners(self):
        assert Audience.PARTNERS == "partners"

    def test_audience_regulators(self):
        assert Audience.REGULATORS == "regulators"

    # CommChannel (5 values)

    def test_channel_slack(self):
        assert CommChannel.SLACK == "slack"

    def test_channel_email(self):
        assert CommChannel.EMAIL == "email"

    def test_channel_status_page(self):
        assert CommChannel.STATUS_PAGE == "status_page"

    def test_channel_phone_bridge(self):
        assert CommChannel.PHONE_BRIDGE == "phone_bridge"

    def test_channel_sms(self):
        assert CommChannel.SMS == "sms"

    # CommCadence (5 values)

    def test_cadence_every_15min(self):
        assert CommCadence.EVERY_15MIN == "every_15min"

    def test_cadence_every_30min(self):
        assert CommCadence.EVERY_30MIN == "every_30min"

    def test_cadence_hourly(self):
        assert CommCadence.HOURLY == "hourly"

    def test_cadence_on_update(self):
        assert CommCadence.ON_UPDATE == "on_update"

    def test_cadence_on_resolution(self):
        assert CommCadence.ON_RESOLUTION == "on_resolution"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_comm_plan_defaults(self):
        p = CommPlan(incident_id="inc-1")
        assert p.id
        assert p.incident_id == "inc-1"
        assert p.audience == Audience.ENGINEERING
        assert p.channel == CommChannel.SLACK
        assert p.cadence == CommCadence.HOURLY
        assert p.template == ""
        assert p.last_sent_at == 0.0
        assert p.send_count == 0
        assert p.is_active is True
        assert p.created_at > 0

    def test_comm_message_defaults(self):
        m = CommMessage(plan_id="p-1", content="update")
        assert m.id
        assert m.plan_id == "p-1"
        assert m.audience == Audience.ENGINEERING
        assert m.channel == CommChannel.SLACK
        assert m.content == "update"
        assert m.sent_by == ""
        assert m.sent_at > 0
        assert m.created_at > 0

    def test_comm_planner_report_defaults(self):
        r = CommPlannerReport()
        assert r.total_plans == 0
        assert r.total_messages == 0
        assert r.avg_messages_per_incident == 0.0
        assert r.by_audience == {}
        assert r.by_channel == {}
        assert r.by_cadence == {}
        assert r.late_comms == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# create_plan
# -------------------------------------------------------------------


class TestCreatePlan:
    def test_basic(self):
        e = _engine()
        p = e.create_plan(
            incident_id="inc-1",
            audience=Audience.LEADERSHIP,
            channel=CommChannel.EMAIL,
        )
        assert p.incident_id == "inc-1"
        assert p.audience == Audience.LEADERSHIP
        assert p.channel == CommChannel.EMAIL

    def test_unique_ids(self):
        e = _engine()
        p1 = e.create_plan(incident_id="a")
        p2 = e.create_plan(incident_id="b")
        assert p1.id != p2.id

    def test_extra_fields(self):
        e = _engine()
        p = e.create_plan(
            incident_id="inc-1",
            cadence=CommCadence.EVERY_15MIN,
            template="Incident update: {status}",
        )
        assert p.cadence == CommCadence.EVERY_15MIN
        assert p.template == "Incident update: {status}"

    def test_evicts_at_max(self):
        e = _engine(max_plans=2)
        p1 = e.create_plan(incident_id="a")
        e.create_plan(incident_id="b")
        e.create_plan(incident_id="c")
        plans = e.list_plans()
        ids = {p.id for p in plans}
        assert p1.id not in ids
        assert len(plans) == 2


# -------------------------------------------------------------------
# get_plan
# -------------------------------------------------------------------


class TestGetPlan:
    def test_found(self):
        e = _engine()
        p = e.create_plan(incident_id="inc-1")
        assert e.get_plan(p.id) is not None
        assert e.get_plan(p.id).incident_id == "inc-1"

    def test_not_found(self):
        e = _engine()
        assert e.get_plan("nonexistent") is None


# -------------------------------------------------------------------
# list_plans
# -------------------------------------------------------------------


class TestListPlans:
    def test_list_all(self):
        e = _engine()
        e.create_plan(incident_id="a")
        e.create_plan(incident_id="b")
        e.create_plan(incident_id="c")
        assert len(e.list_plans()) == 3

    def test_filter_by_incident(self):
        e = _engine()
        e.create_plan(incident_id="inc-1")
        e.create_plan(incident_id="inc-2")
        filtered = e.list_plans(incident_id="inc-1")
        assert len(filtered) == 1
        assert filtered[0].incident_id == "inc-1"

    def test_filter_by_audience(self):
        e = _engine()
        e.create_plan(
            incident_id="a",
            audience=Audience.ENGINEERING,
        )
        e.create_plan(
            incident_id="b",
            audience=Audience.CUSTOMERS,
        )
        filtered = e.list_plans(audience=Audience.CUSTOMERS)
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.create_plan(incident_id=f"inc-{i}")
        assert len(e.list_plans(limit=3)) == 3


# -------------------------------------------------------------------
# send_message
# -------------------------------------------------------------------


class TestSendMessage:
    def test_basic(self):
        e = _engine()
        p = e.create_plan(incident_id="inc-1")
        msg = e.send_message(p.id, "Systems recovering", "alice")
        assert msg is not None
        assert msg.plan_id == p.id
        assert msg.content == "Systems recovering"
        assert msg.sent_by == "alice"
        assert p.send_count == 1
        assert p.last_sent_at > 0

    def test_plan_not_found(self):
        e = _engine()
        assert e.send_message("nonexistent", "msg", "bob") is None


# -------------------------------------------------------------------
# check_overdue_comms
# -------------------------------------------------------------------


class TestCheckOverdueComms:
    def test_overdue(self):
        e = _engine()
        p = e.create_plan(
            incident_id="inc-1",
            cadence=CommCadence.EVERY_15MIN,
        )
        # Simulate old creation time
        p.created_at = p.created_at - 3600
        overdue = e.check_overdue_comms()
        assert len(overdue) >= 1
        assert overdue[0]["plan_id"] == p.id

    def test_none_overdue(self):
        e = _engine()
        p = e.create_plan(
            incident_id="inc-1",
            cadence=CommCadence.HOURLY,
        )
        e.send_message(p.id, "update", "alice")
        overdue = e.check_overdue_comms()
        assert len(overdue) == 0


# -------------------------------------------------------------------
# calculate_comm_coverage
# -------------------------------------------------------------------


class TestCalculateCommCoverage:
    def test_partial(self):
        e = _engine()
        e.create_plan(
            incident_id="inc-1",
            audience=Audience.ENGINEERING,
        )
        e.create_plan(
            incident_id="inc-1",
            audience=Audience.LEADERSHIP,
        )
        result = e.calculate_comm_coverage("inc-1")
        assert result["total_plans"] == 2
        assert len(result["audiences_covered"]) == 2
        assert len(result["audiences_missing"]) == 3
        assert result["coverage_pct"] == 40.0

    def test_full(self):
        e = _engine()
        for aud in Audience:
            e.create_plan(incident_id="inc-1", audience=aud)
        result = e.calculate_comm_coverage("inc-1")
        assert result["coverage_pct"] == 100.0
        assert result["audiences_missing"] == []


# -------------------------------------------------------------------
# analyze_response_times
# -------------------------------------------------------------------


class TestAnalyzeResponseTimes:
    def test_with_data(self):
        e = _engine()
        p = e.create_plan(incident_id="inc-1")
        e.send_message(p.id, "first msg", "alice")
        result = e.analyze_response_times()
        assert result["plans_with_messages"] == 1
        assert result["avg_response_time_sec"] >= 0

    def test_empty(self):
        e = _engine()
        result = e.analyze_response_times()
        assert result["plans_with_messages"] == 0
        assert result["avg_response_time_sec"] == 0.0


# -------------------------------------------------------------------
# detect_communication_gaps
# -------------------------------------------------------------------


class TestDetectCommunicationGaps:
    def test_gaps(self):
        e = _engine()
        e.create_plan(
            incident_id="inc-1",
            audience=Audience.ENGINEERING,
        )
        gaps = e.detect_communication_gaps()
        assert len(gaps) == 1
        assert gaps[0]["incident_id"] == "inc-1"
        assert len(gaps[0]["missing_audiences"]) == 4

    def test_no_gaps(self):
        e = _engine()
        for aud in Audience:
            e.create_plan(incident_id="inc-1", audience=aud)
        gaps = e.detect_communication_gaps()
        assert len(gaps) == 0


# -------------------------------------------------------------------
# generate_comm_report
# -------------------------------------------------------------------


class TestGenerateCommReport:
    def test_populated(self):
        e = _engine()
        p = e.create_plan(
            incident_id="inc-1",
            audience=Audience.ENGINEERING,
            channel=CommChannel.SLACK,
        )
        e.send_message(p.id, "update", "alice")
        report = e.generate_comm_report()
        assert report.total_plans == 1
        assert report.total_messages == 1
        assert "engineering" in report.by_audience
        assert "slack" in report.by_channel
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_comm_report()
        assert report.total_plans == 0
        assert report.total_messages == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        p = e.create_plan(incident_id="inc-1")
        e.send_message(p.id, "msg", "alice")
        count = e.clear_data()
        assert count == 1
        assert e.list_plans() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_plans"] == 0
        assert stats["total_messages"] == 0
        assert stats["max_plans"] == 100000
        assert stats["max_overdue_minutes"] == 30
        assert stats["audience_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.create_plan(
            incident_id="inc-1",
            audience=Audience.ENGINEERING,
        )
        e.create_plan(
            incident_id="inc-2",
            audience=Audience.CUSTOMERS,
        )
        stats = e.get_stats()
        assert stats["total_plans"] == 2
        assert "engineering" in stats["audience_distribution"]
        assert "customers" in stats["audience_distribution"]
