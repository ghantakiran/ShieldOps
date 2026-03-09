"""Tests for shieldops.security.purple_team_campaign_engine — PurpleTeamCampaignEngine."""

from __future__ import annotations

from shieldops.security.purple_team_campaign_engine import (
    AttackTechnique,
    CampaignPhase,
    CampaignRecord,
    DetectionOutcome,
    PurpleTeamCampaignEngine,
)


def _engine(**kw) -> PurpleTeamCampaignEngine:
    return PurpleTeamCampaignEngine(**kw)


class TestEnums:
    def test_campaign_phase(self):
        assert CampaignPhase.PLANNING == "planning"

    def test_attack_technique(self):
        assert AttackTechnique.LATERAL_MOVEMENT == "lateral_movement"

    def test_detection_outcome(self):
        assert DetectionOutcome.DETECTED == "detected"
        assert DetectionOutcome.MISSED == "missed"


class TestModels:
    def test_record_defaults(self):
        r = CampaignRecord()
        assert r.id
        assert r.detection_score == 0.0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            campaign_name="Q1-Purple",
            attack_technique=AttackTechnique.INITIAL_ACCESS,
            detection_outcome=DetectionOutcome.DETECTED,
            detection_score=0.9,
        )
        assert rec.campaign_name == "Q1-Purple"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(campaign_name=f"c-{i}")
        assert len(eng._records) == 3


class TestDetectionRate:
    def test_basic(self):
        eng = _engine()
        eng.add_record(campaign_name="c1", detection_outcome=DetectionOutcome.DETECTED)
        eng.add_record(campaign_name="c1", detection_outcome=DetectionOutcome.MISSED)
        result = eng.compute_detection_rate()
        assert isinstance(result, dict)


class TestCoverageGaps:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            campaign_name="c1",
            attack_technique=AttackTechnique.DATA_EXFILTRATION,
            detection_outcome=DetectionOutcome.MISSED,
        )
        result = eng.identify_coverage_gaps()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(campaign_name="c1", service="api")
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(campaign_name="c1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(campaign_name="c1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(campaign_name="c1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
