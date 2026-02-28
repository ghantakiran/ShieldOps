"""Tests for shieldops.incidents.comm_automator."""

from __future__ import annotations

from shieldops.incidents.comm_automator import (
    CommAudience,
    CommAutomatorReport,
    CommChannel,
    CommRecord,
    CommTemplate,
    CommType,
    IncidentCommunicationAutomator,
)


def _engine(**kw) -> IncidentCommunicationAutomator:
    return IncidentCommunicationAutomator(**kw)


# ---------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------


class TestEnums:
    # CommChannel (5)
    def test_channel_slack(self):
        assert CommChannel.SLACK == "slack"

    def test_channel_email(self):
        assert CommChannel.EMAIL == "email"

    def test_channel_teams(self):
        assert CommChannel.TEAMS == "teams"

    def test_channel_status_page(self):
        assert CommChannel.STATUS_PAGE == "status_page"

    def test_channel_executive_brief(self):
        assert CommChannel.EXECUTIVE_BRIEF == "executive_brief"

    # CommType (5)
    def test_type_initial_notification(self):
        assert CommType.INITIAL_NOTIFICATION == "initial_notification"

    def test_type_status_update(self):
        assert CommType.STATUS_UPDATE == "status_update"

    def test_type_escalation(self):
        assert CommType.ESCALATION == "escalation"

    def test_type_resolution(self):
        assert CommType.RESOLUTION == "resolution"

    def test_type_post_mortem(self):
        assert CommType.POST_MORTEM == "post_mortem"

    # CommAudience (5)
    def test_audience_engineering(self):
        assert CommAudience.ENGINEERING == "engineering"

    def test_audience_management(self):
        assert CommAudience.MANAGEMENT == "management"

    def test_audience_customers(self):
        assert CommAudience.CUSTOMERS == "customers"

    def test_audience_executives(self):
        assert CommAudience.EXECUTIVES == "executives"

    def test_audience_all_hands(self):
        assert CommAudience.ALL_HANDS == "all_hands"


# ---------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------


class TestModels:
    def test_comm_record_defaults(self):
        r = CommRecord()
        assert r.id
        assert r.incident_name == ""
        assert r.channel == CommChannel.SLACK
        assert r.comm_type == CommType.INITIAL_NOTIFICATION
        assert r.audience == CommAudience.ENGINEERING
        assert r.delivery_success is True
        assert r.details == ""
        assert r.created_at > 0

    def test_comm_template_defaults(self):
        r = CommTemplate()
        assert r.id
        assert r.template_name == ""
        assert r.channel == CommChannel.SLACK
        assert r.comm_type == CommType.INITIAL_NOTIFICATION
        assert r.audience == CommAudience.ENGINEERING
        assert r.auto_send is False
        assert r.delay_minutes == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CommAutomatorReport()
        assert r.total_comms == 0
        assert r.total_templates == 0
        assert r.delivery_rate_pct == 0.0
        assert r.by_channel == {}
        assert r.by_type == {}
        assert r.failed_delivery_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------
# record_comm
# ---------------------------------------------------------------


class TestRecordComm:
    def test_basic(self):
        eng = _engine()
        r = eng.record_comm(
            "inc-a",
            channel=CommChannel.SLACK,
            comm_type=CommType.INITIAL_NOTIFICATION,
        )
        assert r.incident_name == "inc-a"
        assert r.channel == CommChannel.SLACK

    def test_with_audience(self):
        eng = _engine()
        r = eng.record_comm(
            "inc-b",
            audience=CommAudience.EXECUTIVES,
        )
        assert r.audience == CommAudience.EXECUTIVES

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_comm(f"inc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------
# get_comm
# ---------------------------------------------------------------


class TestGetComm:
    def test_found(self):
        eng = _engine()
        r = eng.record_comm("inc-a")
        assert eng.get_comm(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_comm("nonexistent") is None


# ---------------------------------------------------------------
# list_comms
# ---------------------------------------------------------------


class TestListComms:
    def test_list_all(self):
        eng = _engine()
        eng.record_comm("inc-a")
        eng.record_comm("inc-b")
        assert len(eng.list_comms()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_comm("inc-a")
        eng.record_comm("inc-b")
        results = eng.list_comms(incident_name="inc-a")
        assert len(results) == 1

    def test_filter_by_channel(self):
        eng = _engine()
        eng.record_comm(
            "inc-a",
            channel=CommChannel.EMAIL,
        )
        eng.record_comm(
            "inc-b",
            channel=CommChannel.TEAMS,
        )
        results = eng.list_comms(channel=CommChannel.EMAIL)
        assert len(results) == 1


# ---------------------------------------------------------------
# add_template
# ---------------------------------------------------------------


class TestAddTemplate:
    def test_basic(self):
        eng = _engine()
        t = eng.add_template(
            "slack-notify",
            channel=CommChannel.SLACK,
            comm_type=CommType.INITIAL_NOTIFICATION,
            audience=CommAudience.ENGINEERING,
            auto_send=True,
            delay_minutes=5.0,
        )
        assert t.template_name == "slack-notify"
        assert t.auto_send is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_template(f"tmpl-{i}")
        assert len(eng._templates) == 2


# ---------------------------------------------------------------
# analyze_comm_effectiveness
# ---------------------------------------------------------------


class TestAnalyzeCommEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("inc-a", delivery_success=True)
        eng.record_comm("inc-a", delivery_success=False)
        result = eng.analyze_comm_effectiveness("inc-a")
        assert result["incident_name"] == "inc-a"
        assert result["comm_count"] == 2
        assert result["delivery_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_comm_effectiveness("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_delivery_rate_pct=50.0)
        eng.record_comm("inc-a", delivery_success=True)
        result = eng.analyze_comm_effectiveness("inc-a")
        assert result["meets_threshold"] is True


# ---------------------------------------------------------------
# identify_failed_deliveries
# ---------------------------------------------------------------


class TestIdentifyFailedDeliveries:
    def test_with_failures(self):
        eng = _engine()
        eng.record_comm("inc-a", delivery_success=False)
        eng.record_comm("inc-a", delivery_success=False)
        eng.record_comm("inc-b", delivery_success=True)
        results = eng.identify_failed_deliveries()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_deliveries() == []


# ---------------------------------------------------------------
# rank_by_comm_volume
# ---------------------------------------------------------------


class TestRankByCommVolume:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("inc-a")
        eng.record_comm("inc-a")
        eng.record_comm("inc-b")
        results = eng.rank_by_comm_volume()
        assert results[0]["incident_name"] == "inc-a"
        assert results[0]["comm_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_comm_volume() == []


# ---------------------------------------------------------------
# detect_comm_gaps
# ---------------------------------------------------------------


class TestDetectCommGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_comm("inc-a", delivery_success=False)
        eng.record_comm("inc-b", delivery_success=True)
        results = eng.detect_comm_gaps()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-a"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_comm("inc-a", delivery_success=False)
        assert eng.detect_comm_gaps() == []


# ---------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("inc-a", delivery_success=True)
        eng.record_comm("inc-b", delivery_success=False)
        eng.record_comm("inc-b", delivery_success=False)
        eng.add_template("tmpl-1")
        report = eng.generate_report()
        assert report.total_comms == 3
        assert report.total_templates == 1
        assert report.by_channel != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_comms == 0
        assert "below" in report.recommendations[0]


# ---------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_comm("inc-a")
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
        assert stats["total_comms"] == 0
        assert stats["total_templates"] == 0
        assert stats["channel_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_comm(
            "inc-a",
            channel=CommChannel.SLACK,
        )
        eng.record_comm(
            "inc-b",
            channel=CommChannel.EMAIL,
        )
        eng.add_template("t1")
        stats = eng.get_stats()
        assert stats["total_comms"] == 2
        assert stats["total_templates"] == 1
        assert stats["unique_incidents"] == 2
