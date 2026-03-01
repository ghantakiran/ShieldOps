"""Tests for shieldops.security.lateral_movement — LateralMovementDetector."""

from __future__ import annotations

from shieldops.security.lateral_movement import (
    DetectionConfidence,
    LateralMovementDetector,
    LateralMovementReport,
    MovementHop,
    MovementRecord,
    MovementStage,
    MovementType,
)


def _engine(**kw) -> LateralMovementDetector:
    return LateralMovementDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_credential_hopping(self):
        assert MovementType.CREDENTIAL_HOPPING == "credential_hopping"

    def test_type_service_pivoting(self):
        assert MovementType.SERVICE_PIVOTING == "service_pivoting"

    def test_type_privilege_escalation(self):
        assert MovementType.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_type_data_staging(self):
        assert MovementType.DATA_STAGING == "data_staging"

    def test_type_network_scanning(self):
        assert MovementType.NETWORK_SCANNING == "network_scanning"

    def test_confidence_high(self):
        assert DetectionConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert DetectionConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert DetectionConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert DetectionConfidence.SPECULATIVE == "speculative"

    def test_confidence_false_positive(self):
        assert DetectionConfidence.FALSE_POSITIVE == "false_positive"

    def test_stage_initial_access(self):
        assert MovementStage.INITIAL_ACCESS == "initial_access"

    def test_stage_discovery(self):
        assert MovementStage.DISCOVERY == "discovery"

    def test_stage_lateral_move(self):
        assert MovementStage.LATERAL_MOVE == "lateral_move"

    def test_stage_collection(self):
        assert MovementStage.COLLECTION == "collection"

    def test_stage_exfiltration(self):
        assert MovementStage.EXFILTRATION == "exfiltration"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_movement_record_defaults(self):
        r = MovementRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.movement_type == MovementType.CREDENTIAL_HOPPING
        assert r.detection_confidence == DetectionConfidence.LOW
        assert r.movement_stage == MovementStage.INITIAL_ACCESS
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_movement_hop_defaults(self):
        h = MovementHop()
        assert h.id
        assert h.incident_id == ""
        assert h.movement_type == MovementType.CREDENTIAL_HOPPING
        assert h.source_host == ""
        assert h.destination_host == ""
        assert h.hop_count == 0
        assert h.description == ""
        assert h.created_at > 0

    def test_lateral_movement_report_defaults(self):
        r = LateralMovementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_hops == 0
        assert r.high_risk_movements == 0
        assert r.avg_risk_score == 0.0
        assert r.by_movement_type == {}
        assert r.by_confidence == {}
        assert r.by_stage == {}
        assert r.top_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_movement
# ---------------------------------------------------------------------------


class TestRecordMovement:
    def test_basic(self):
        eng = _engine()
        r = eng.record_movement(
            incident_id="INC-001",
            movement_type=MovementType.PRIVILEGE_ESCALATION,
            detection_confidence=DetectionConfidence.HIGH,
            movement_stage=MovementStage.LATERAL_MOVE,
            risk_score=92.0,
            service="auth-service",
            team="security",
        )
        assert r.incident_id == "INC-001"
        assert r.movement_type == MovementType.PRIVILEGE_ESCALATION
        assert r.detection_confidence == DetectionConfidence.HIGH
        assert r.movement_stage == MovementStage.LATERAL_MOVE
        assert r.risk_score == 92.0
        assert r.service == "auth-service"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_movement(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_movement
# ---------------------------------------------------------------------------


class TestGetMovement:
    def test_found(self):
        eng = _engine()
        r = eng.record_movement(
            incident_id="INC-001",
            detection_confidence=DetectionConfidence.HIGH,
        )
        result = eng.get_movement(r.id)
        assert result is not None
        assert result.detection_confidence == DetectionConfidence.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_movement("nonexistent") is None


# ---------------------------------------------------------------------------
# list_movements
# ---------------------------------------------------------------------------


class TestListMovements:
    def test_list_all(self):
        eng = _engine()
        eng.record_movement(incident_id="INC-001")
        eng.record_movement(incident_id="INC-002")
        assert len(eng.list_movements()) == 2

    def test_filter_by_movement_type(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            movement_type=MovementType.DATA_STAGING,
        )
        eng.record_movement(
            incident_id="INC-002",
            movement_type=MovementType.CREDENTIAL_HOPPING,
        )
        results = eng.list_movements(movement_type=MovementType.DATA_STAGING)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            detection_confidence=DetectionConfidence.HIGH,
        )
        eng.record_movement(
            incident_id="INC-002",
            detection_confidence=DetectionConfidence.LOW,
        )
        results = eng.list_movements(confidence=DetectionConfidence.HIGH)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_movement(incident_id="INC-001", service="api")
        eng.record_movement(incident_id="INC-002", service="web")
        results = eng.list_movements(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_movement(incident_id="INC-001", team="security")
        eng.record_movement(incident_id="INC-002", team="platform")
        results = eng.list_movements(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_movement(incident_id=f"INC-{i}")
        assert len(eng.list_movements(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_hop
# ---------------------------------------------------------------------------


class TestAddHop:
    def test_basic(self):
        eng = _engine()
        h = eng.add_hop(
            incident_id="INC-001",
            movement_type=MovementType.SERVICE_PIVOTING,
            source_host="host-a",
            destination_host="host-b",
            hop_count=3,
            description="Pivoting through service mesh",
        )
        assert h.incident_id == "INC-001"
        assert h.movement_type == MovementType.SERVICE_PIVOTING
        assert h.source_host == "host-a"
        assert h.destination_host == "host-b"
        assert h.hop_count == 3
        assert h.description == "Pivoting through service mesh"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_hop(incident_id=f"INC-{i}")
        assert len(eng._hops) == 2


# ---------------------------------------------------------------------------
# analyze_movement_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeMovementPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            movement_type=MovementType.CREDENTIAL_HOPPING,
            risk_score=70.0,
        )
        eng.record_movement(
            incident_id="INC-002",
            movement_type=MovementType.CREDENTIAL_HOPPING,
            risk_score=90.0,
        )
        result = eng.analyze_movement_patterns()
        assert "credential_hopping" in result
        assert result["credential_hopping"]["count"] == 2
        assert result["credential_hopping"]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_movement_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_movements
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskMovements:
    def test_detects_high_confidence(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            detection_confidence=DetectionConfidence.HIGH,
        )
        eng.record_movement(
            incident_id="INC-002",
            detection_confidence=DetectionConfidence.LOW,
        )
        results = eng.identify_high_risk_movements()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_movements() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_movement(incident_id="INC-001", service="api", risk_score=90.0)
        eng.record_movement(incident_id="INC-002", service="api", risk_score=80.0)
        eng.record_movement(incident_id="INC-003", service="web", risk_score=50.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_risk_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_movement_chains
# ---------------------------------------------------------------------------


class TestDetectMovementChains:
    def test_stable(self):
        eng = _engine()
        for count in [10, 10, 10, 10]:
            eng.add_hop(incident_id="INC-001", hop_count=count)
        result = eng.detect_movement_chains()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for count in [5, 5, 20, 20]:
            eng.add_hop(incident_id="INC-001", hop_count=count)
        result = eng.detect_movement_chains()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_movement_chains()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            movement_type=MovementType.PRIVILEGE_ESCALATION,
            detection_confidence=DetectionConfidence.HIGH,
            risk_score=95.0,
            service="auth-service",
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, LateralMovementReport)
        assert report.total_records == 1
        assert report.high_risk_movements == 1
        assert report.avg_risk_score == 95.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_movement(incident_id="INC-001")
        eng.add_hop(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._hops) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_hops"] == 0
        assert stats["movement_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_movement(
            incident_id="INC-001",
            movement_type=MovementType.NETWORK_SCANNING,
            service="api",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_incidents"] == 1
        assert "network_scanning" in stats["movement_type_distribution"]
