"""Tests for shieldops.security.response_automator — SecurityResponseAutomator."""

from __future__ import annotations

from shieldops.security.response_automator import (
    ResponseAction,
    ResponseAutomatorReport,
    ResponseOutcome,
    ResponsePlaybook,
    ResponseRecord,
    ResponseUrgency,
    SecurityResponseAutomator,
)


def _engine(**kw) -> SecurityResponseAutomator:
    return SecurityResponseAutomator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResponseAction (5)
    def test_action_isolate_host(self):
        assert ResponseAction.ISOLATE_HOST == "isolate_host"

    def test_action_block_ip(self):
        assert ResponseAction.BLOCK_IP == "block_ip"

    def test_action_revoke_credentials(self):
        assert ResponseAction.REVOKE_CREDENTIALS == "revoke_credentials"

    def test_action_quarantine(self):
        assert ResponseAction.QUARANTINE == "quarantine"

    def test_action_escalate(self):
        assert ResponseAction.ESCALATE == "escalate"

    # ResponseOutcome (5)
    def test_outcome_success(self):
        assert ResponseOutcome.SUCCESS == "success"

    def test_outcome_partial(self):
        assert ResponseOutcome.PARTIAL == "partial"

    def test_outcome_failed(self):
        assert ResponseOutcome.FAILED == "failed"

    def test_outcome_rolled_back(self):
        assert ResponseOutcome.ROLLED_BACK == "rolled_back"

    def test_outcome_timeout(self):
        assert ResponseOutcome.TIMEOUT == "timeout"

    # ResponseUrgency (5)
    def test_urgency_immediate(self):
        assert ResponseUrgency.IMMEDIATE == "immediate"

    def test_urgency_high(self):
        assert ResponseUrgency.HIGH == "high"

    def test_urgency_standard(self):
        assert ResponseUrgency.STANDARD == "standard"

    def test_urgency_low(self):
        assert ResponseUrgency.LOW == "low"

    def test_urgency_scheduled(self):
        assert ResponseUrgency.SCHEDULED == "scheduled"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_response_record_defaults(self):
        r = ResponseRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.response_action == ResponseAction.ISOLATE_HOST
        assert r.response_outcome == ResponseOutcome.SUCCESS
        assert r.response_urgency == ResponseUrgency.STANDARD
        assert r.execution_time_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_response_playbook_defaults(self):
        r = ResponsePlaybook()
        assert r.id
        assert r.playbook_name == ""
        assert r.response_action == ResponseAction.BLOCK_IP
        assert r.response_urgency == ResponseUrgency.HIGH
        assert r.step_count == 0
        assert r.created_at > 0

    def test_response_automator_report_defaults(self):
        r = ResponseAutomatorReport()
        assert r.total_responses == 0
        assert r.total_playbooks == 0
        assert r.success_rate_pct == 0.0
        assert r.by_action == {}
        assert r.by_outcome == {}
        assert r.failure_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_response
# -------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            "inc-a",
            response_action=ResponseAction.ISOLATE_HOST,
            response_outcome=ResponseOutcome.SUCCESS,
        )
        assert r.incident_id == "inc-a"
        assert r.response_action == ResponseAction.ISOLATE_HOST

    def test_with_urgency(self):
        eng = _engine()
        r = eng.record_response("inc-b", response_urgency=ResponseUrgency.IMMEDIATE)
        assert r.response_urgency == ResponseUrgency.IMMEDIATE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(f"inc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_response
# -------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response("inc-a")
        assert eng.get_response(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# -------------------------------------------------------------------
# list_responses
# -------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response("inc-a")
        eng.record_response("inc-b")
        assert len(eng.list_responses()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_response("inc-a")
        eng.record_response("inc-b")
        results = eng.list_responses(incident_id="inc-a")
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_response("inc-a", response_action=ResponseAction.BLOCK_IP)
        eng.record_response("inc-b", response_action=ResponseAction.QUARANTINE)
        results = eng.list_responses(response_action=ResponseAction.BLOCK_IP)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_playbook
# -------------------------------------------------------------------


class TestAddPlaybook:
    def test_basic(self):
        eng = _engine()
        p = eng.add_playbook(
            "block-ip-playbook",
            response_action=ResponseAction.BLOCK_IP,
            response_urgency=ResponseUrgency.IMMEDIATE,
            step_count=5,
        )
        assert p.playbook_name == "block-ip-playbook"
        assert p.step_count == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_playbook(f"playbook-{i}")
        assert len(eng._playbooks) == 2


# -------------------------------------------------------------------
# analyze_response_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeResponseEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-a", response_outcome=ResponseOutcome.SUCCESS)
        eng.record_response("inc-a", response_outcome=ResponseOutcome.FAILED)
        result = eng.analyze_response_effectiveness("inc-a")
        assert result["incident_id"] == "inc-a"
        assert result["total_responses"] == 2
        assert result["success_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_response_effectiveness("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_responses
# -------------------------------------------------------------------


class TestIdentifyFailedResponses:
    def test_with_failures(self):
        eng = _engine()
        eng.record_response("inc-a", response_outcome=ResponseOutcome.FAILED)
        eng.record_response("inc-a", response_outcome=ResponseOutcome.FAILED)
        eng.record_response("inc-b", response_outcome=ResponseOutcome.SUCCESS)
        results = eng.identify_failed_responses()
        assert len(results) == 1
        assert results[0]["incident_id"] == "inc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_responses() == []


# -------------------------------------------------------------------
# rank_by_execution_speed
# -------------------------------------------------------------------


class TestRankByExecutionSpeed:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-a", execution_time_seconds=10.0)
        eng.record_response("inc-a", execution_time_seconds=20.0)
        eng.record_response("inc-b", execution_time_seconds=5.0)
        results = eng.rank_by_execution_speed()
        assert results[0]["incident_id"] == "inc-b"
        assert results[0]["avg_execution_time_seconds"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_execution_speed() == []


# -------------------------------------------------------------------
# detect_response_loops
# -------------------------------------------------------------------


class TestDetectResponseLoops:
    def test_with_loops(self):
        eng = _engine()
        for _ in range(5):
            eng.record_response("inc-a", response_outcome=ResponseOutcome.FAILED)
        eng.record_response("inc-b", response_outcome=ResponseOutcome.SUCCESS)
        results = eng.detect_response_loops()
        assert len(results) == 1
        assert results[0]["incident_id"] == "inc-a"
        assert results[0]["loop_detected"] is True

    def test_no_loops(self):
        eng = _engine()
        eng.record_response("inc-a", response_outcome=ResponseOutcome.FAILED)
        assert eng.detect_response_loops() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-a", response_outcome=ResponseOutcome.SUCCESS)
        eng.record_response("inc-b", response_outcome=ResponseOutcome.FAILED)
        eng.record_response("inc-b", response_outcome=ResponseOutcome.FAILED)
        eng.add_playbook("playbook-1")
        report = eng.generate_report()
        assert report.total_responses == 3
        assert report.total_playbooks == 1
        assert report.by_action != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_responses == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response("inc-a")
        eng.add_playbook("playbook-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._playbooks) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_responses"] == 0
        assert stats["total_playbooks"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response("inc-a", response_action=ResponseAction.ISOLATE_HOST)
        eng.record_response("inc-b", response_action=ResponseAction.BLOCK_IP)
        eng.add_playbook("p1")
        stats = eng.get_stats()
        assert stats["total_responses"] == 2
        assert stats["total_playbooks"] == 1
        assert stats["unique_incidents"] == 2
