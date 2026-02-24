"""Tests for shieldops.security.incident_response — SecurityIncidentResponseTracker."""

from __future__ import annotations

from shieldops.security.incident_response import (
    ContainmentAction,
    ContainmentStatus,
    EvidenceType,
    ForensicEvidence,
    SecurityIncident,
    SecurityIncidentResponseTracker,
    SecurityIncidentType,
)


def _engine(**kw) -> SecurityIncidentResponseTracker:
    return SecurityIncidentResponseTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_unauthorized(self):
        assert SecurityIncidentType.UNAUTHORIZED_ACCESS == "unauthorized_access"

    def test_type_breach(self):
        assert SecurityIncidentType.DATA_BREACH == "data_breach"

    def test_type_malware(self):
        assert SecurityIncidentType.MALWARE == "malware"

    def test_type_priv_esc(self):
        assert SecurityIncidentType.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_type_insider(self):
        assert SecurityIncidentType.INSIDER_THREAT == "insider_threat"

    def test_type_ddos(self):
        assert SecurityIncidentType.DDOS == "ddos"

    def test_status_detected(self):
        assert ContainmentStatus.DETECTED == "detected"

    def test_status_analyzing(self):
        assert ContainmentStatus.ANALYZING == "analyzing"

    def test_status_containing(self):
        assert ContainmentStatus.CONTAINING == "containing"

    def test_status_contained(self):
        assert ContainmentStatus.CONTAINED == "contained"

    def test_status_eradicated(self):
        assert ContainmentStatus.ERADICATED == "eradicated"

    def test_status_recovered(self):
        assert ContainmentStatus.RECOVERED == "recovered"

    def test_evidence_log(self):
        assert EvidenceType.LOG_ENTRY == "log_entry"

    def test_evidence_network(self):
        assert EvidenceType.NETWORK_CAPTURE == "network_capture"

    def test_evidence_memory(self):
        assert EvidenceType.MEMORY_DUMP == "memory_dump"

    def test_evidence_filesystem(self):
        assert EvidenceType.FILESYSTEM_ARTIFACT == "filesystem_artifact"

    def test_evidence_access(self):
        assert EvidenceType.ACCESS_LOG == "access_log"

    def test_evidence_config(self):
        assert EvidenceType.CONFIGURATION_CHANGE == "configuration_change"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_defaults(self):
        i = SecurityIncident()
        assert i.id
        assert i.status == ContainmentStatus.DETECTED
        assert i.escalated is False
        assert i.closed is False

    def test_action_defaults(self):
        a = ContainmentAction()
        assert a.outcome == "pending"

    def test_evidence_defaults(self):
        e = ForensicEvidence()
        assert e.evidence_type == EvidenceType.LOG_ENTRY


# ---------------------------------------------------------------------------
# create_incident
# ---------------------------------------------------------------------------


class TestCreateIncident:
    def test_basic_create(self):
        eng = _engine()
        inc = eng.create_incident(title="Test breach")
        assert inc.title == "Test breach"
        assert inc.status == ContainmentStatus.DETECTED

    def test_unique_ids(self):
        eng = _engine()
        i1 = eng.create_incident(title="inc1")
        i2 = eng.create_incident(title="inc2")
        assert i1.id != i2.id

    def test_eviction_at_max(self):
        eng = _engine(max_incidents=3)
        for i in range(5):
            eng.create_incident(title=f"inc-{i}")
        assert len(eng._incidents) == 3

    def test_with_services(self):
        eng = _engine()
        inc = eng.create_incident(services_affected=["svc-a", "svc-b"])
        assert len(inc.services_affected) == 2


# ---------------------------------------------------------------------------
# get / list incidents
# ---------------------------------------------------------------------------


class TestGetIncident:
    def test_found(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        assert eng.get_incident(inc.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_incident("nonexistent") is None


class TestListIncidents:
    def test_list_all(self):
        eng = _engine()
        eng.create_incident(title="a")
        eng.create_incident(title="b")
        assert len(eng.list_incidents()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.create_incident(incident_type=SecurityIncidentType.MALWARE)
        eng.create_incident(incident_type=SecurityIncidentType.DDOS)
        results = eng.list_incidents(incident_type=SecurityIncidentType.MALWARE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.create_incident(title="a")
        results = eng.list_incidents(status=ContainmentStatus.DETECTED)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# containment / evidence / escalate / close
# ---------------------------------------------------------------------------


class TestContainmentAction:
    def test_add_action(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        action = eng.add_containment_action(inc.id, "Block IP range")
        assert action is not None
        assert action.action == "Block IP range"

    def test_action_advances_status(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        eng.add_containment_action(inc.id, "Block IP")
        assert inc.status == ContainmentStatus.CONTAINING

    def test_action_invalid_incident(self):
        eng = _engine()
        assert eng.add_containment_action("bad_id", "action") is None


class TestCollectEvidence:
    def test_collect(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        ev = eng.collect_evidence(inc.id, description="Suspicious log")
        assert ev is not None
        assert ev.incident_id == inc.id

    def test_collect_invalid_incident(self):
        eng = _engine()
        assert eng.collect_evidence("bad_id") is None


class TestEscalateIncident:
    def test_escalate(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        assert eng.escalate_incident(inc.id) is True
        assert inc.escalated is True

    def test_escalate_not_found(self):
        eng = _engine()
        assert eng.escalate_incident("nonexistent") is False


class TestCloseIncident:
    def test_close(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        assert eng.close_incident(inc.id) is True
        assert inc.closed is True
        assert inc.status == ContainmentStatus.RECOVERED

    def test_close_not_found(self):
        eng = _engine()
        assert eng.close_incident("nonexistent") is False


# ---------------------------------------------------------------------------
# timeline / active / stats
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_timeline(self):
        eng = _engine()
        inc = eng.create_incident(title="test")
        eng.add_containment_action(inc.id, "action1")
        eng.collect_evidence(inc.id, description="ev1")
        timeline = eng.get_timeline(inc.id)
        assert len(timeline) == 2


class TestActiveIncidents:
    def test_active(self):
        eng = _engine()
        eng.create_incident(title="open")
        inc2 = eng.create_incident(title="closed")
        eng.close_incident(inc2.id)
        active = eng.get_active_incidents()
        assert len(active) == 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_incidents"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.create_incident(incident_type=SecurityIncidentType.MALWARE, title="mal")
        inc2 = eng.create_incident(incident_type=SecurityIncidentType.DDOS, title="ddos")
        eng.escalate_incident(inc2.id)
        stats = eng.get_stats()
        assert stats["total_incidents"] == 2
        assert stats["escalated_incidents"] == 1
        assert stats["active_incidents"] == 2
