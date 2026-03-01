"""Tests for shieldops.compliance.compliance_evidence_chain — ComplianceEvidenceChainTracker."""

from __future__ import annotations

from shieldops.compliance.compliance_evidence_chain import (
    ChainRisk,
    ChainStatus,
    ChainValidation,
    ComplianceEvidenceChainReport,
    ComplianceEvidenceChainTracker,
    EvidenceChainRecord,
    EvidenceLink,
)


def _engine(**kw) -> ComplianceEvidenceChainTracker:
    return ComplianceEvidenceChainTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_complete(self):
        assert ChainStatus.COMPLETE == "complete"

    def test_status_partial(self):
        assert ChainStatus.PARTIAL == "partial"

    def test_status_broken(self):
        assert ChainStatus.BROKEN == "broken"

    def test_status_expired(self):
        assert ChainStatus.EXPIRED == "expired"

    def test_status_pending(self):
        assert ChainStatus.PENDING == "pending"

    def test_link_control_to_evidence(self):
        assert EvidenceLink.CONTROL_TO_EVIDENCE == "control_to_evidence"

    def test_link_evidence_to_artifact(self):
        assert EvidenceLink.EVIDENCE_TO_ARTIFACT == "evidence_to_artifact"

    def test_link_artifact_to_attestation(self):
        assert EvidenceLink.ARTIFACT_TO_ATTESTATION == "artifact_to_attestation"

    def test_link_attestation_to_report(self):
        assert EvidenceLink.ATTESTATION_TO_REPORT == "attestation_to_report"

    def test_link_report_to_audit(self):
        assert EvidenceLink.REPORT_TO_AUDIT == "report_to_audit"

    def test_risk_critical(self):
        assert ChainRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert ChainRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert ChainRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert ChainRisk.LOW == "low"

    def test_risk_none(self):
        assert ChainRisk.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_chain_record_defaults(self):
        r = EvidenceChainRecord()
        assert r.id
        assert r.chain_id == ""
        assert r.chain_status == ChainStatus.PENDING
        assert r.evidence_link == EvidenceLink.CONTROL_TO_EVIDENCE
        assert r.chain_risk == ChainRisk.NONE
        assert r.integrity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_chain_validation_defaults(self):
        v = ChainValidation()
        assert v.id
        assert v.chain_id == ""
        assert v.chain_status == ChainStatus.PENDING
        assert v.validation_score == 0.0
        assert v.threshold == 0.0
        assert v.breached is False
        assert v.description == ""
        assert v.created_at > 0

    def test_compliance_evidence_chain_report_defaults(self):
        r = ComplianceEvidenceChainReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_validations == 0
        assert r.broken_chains == 0
        assert r.avg_integrity_score == 0.0
        assert r.by_status == {}
        assert r.by_link == {}
        assert r.by_risk == {}
        assert r.top_broken == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_chain
# ---------------------------------------------------------------------------


class TestRecordChain:
    def test_basic(self):
        eng = _engine()
        r = eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.COMPLETE,
            evidence_link=EvidenceLink.CONTROL_TO_EVIDENCE,
            chain_risk=ChainRisk.LOW,
            integrity_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.chain_id == "CHAIN-001"
        assert r.chain_status == ChainStatus.COMPLETE
        assert r.evidence_link == EvidenceLink.CONTROL_TO_EVIDENCE
        assert r.chain_risk == ChainRisk.LOW
        assert r.integrity_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_chain(chain_id=f"CHAIN-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_chain
# ---------------------------------------------------------------------------


class TestGetChain:
    def test_found(self):
        eng = _engine()
        r = eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.COMPLETE,
        )
        result = eng.get_chain(r.id)
        assert result is not None
        assert result.chain_status == ChainStatus.COMPLETE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_chain("nonexistent") is None


# ---------------------------------------------------------------------------
# list_chains
# ---------------------------------------------------------------------------


class TestListChains:
    def test_list_all(self):
        eng = _engine()
        eng.record_chain(chain_id="CHAIN-001")
        eng.record_chain(chain_id="CHAIN-002")
        assert len(eng.list_chains()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.COMPLETE,
        )
        eng.record_chain(
            chain_id="CHAIN-002",
            chain_status=ChainStatus.BROKEN,
        )
        results = eng.list_chains(status=ChainStatus.COMPLETE)
        assert len(results) == 1

    def test_filter_by_link(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            evidence_link=EvidenceLink.CONTROL_TO_EVIDENCE,
        )
        eng.record_chain(
            chain_id="CHAIN-002",
            evidence_link=EvidenceLink.EVIDENCE_TO_ARTIFACT,
        )
        results = eng.list_chains(link=EvidenceLink.CONTROL_TO_EVIDENCE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_chain(chain_id="CHAIN-001", service="api-gateway")
        eng.record_chain(chain_id="CHAIN-002", service="auth-svc")
        results = eng.list_chains(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_chain(chain_id="CHAIN-001", team="sre")
        eng.record_chain(chain_id="CHAIN-002", team="platform")
        results = eng.list_chains(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_chain(chain_id=f"CHAIN-{i}")
        assert len(eng.list_chains(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_validation
# ---------------------------------------------------------------------------


class TestAddValidation:
    def test_basic(self):
        eng = _engine()
        v = eng.add_validation(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.BROKEN,
            validation_score=45.0,
            threshold=90.0,
            breached=True,
            description="Evidence missing",
        )
        assert v.chain_id == "CHAIN-001"
        assert v.chain_status == ChainStatus.BROKEN
        assert v.validation_score == 45.0
        assert v.threshold == 90.0
        assert v.breached is True
        assert v.description == "Evidence missing"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_validation(chain_id=f"CHAIN-{i}")
        assert len(eng._validations) == 2


# ---------------------------------------------------------------------------
# analyze_chain_integrity
# ---------------------------------------------------------------------------


class TestAnalyzeChainIntegrity:
    def test_with_data(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.COMPLETE,
            integrity_score=80.0,
        )
        eng.record_chain(
            chain_id="CHAIN-002",
            chain_status=ChainStatus.COMPLETE,
            integrity_score=90.0,
        )
        result = eng.analyze_chain_integrity()
        assert "complete" in result
        assert result["complete"]["count"] == 2
        assert result["complete"]["avg_integrity"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_chain_integrity() == {}


# ---------------------------------------------------------------------------
# identify_broken_chains
# ---------------------------------------------------------------------------


class TestIdentifyBrokenChains:
    def test_detects(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.BROKEN,
        )
        eng.record_chain(
            chain_id="CHAIN-002",
            chain_status=ChainStatus.COMPLETE,
        )
        results = eng.identify_broken_chains()
        assert len(results) == 1
        assert results[0]["chain_id"] == "CHAIN-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_broken_chains() == []


# ---------------------------------------------------------------------------
# rank_by_integrity
# ---------------------------------------------------------------------------


class TestRankByIntegrity:
    def test_ranked(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            service="api-gateway",
            integrity_score=120.0,
        )
        eng.record_chain(
            chain_id="CHAIN-002",
            service="auth-svc",
            integrity_score=30.0,
        )
        eng.record_chain(
            chain_id="CHAIN-001",
            service="api-gateway",
            integrity_score=80.0,
        )
        results = eng.rank_by_integrity()
        assert len(results) == 2
        # ascending: CHAIN-002 (30.0) first, CHAIN-001 (100.0) second
        assert results[0]["chain_id"] == "CHAIN-002"
        assert results[0]["avg_integrity"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_integrity() == []


# ---------------------------------------------------------------------------
# detect_chain_trends
# ---------------------------------------------------------------------------


class TestDetectChainTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_validation(chain_id="CHAIN-1", validation_score=val)
        result = eng.detect_chain_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_validation(chain_id="CHAIN-1", validation_score=val)
        result = eng.detect_chain_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_validation(chain_id="CHAIN-1", validation_score=val)
        result = eng.detect_chain_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_chain_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.BROKEN,
            evidence_link=EvidenceLink.CONTROL_TO_EVIDENCE,
            chain_risk=ChainRisk.HIGH,
            integrity_score=20.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ComplianceEvidenceChainReport)
        assert report.total_records == 1
        assert report.broken_chains == 1
        assert len(report.top_broken) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_chain(chain_id="CHAIN-001")
        eng.add_validation(chain_id="CHAIN-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._validations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_validations"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_chain(
            chain_id="CHAIN-001",
            chain_status=ChainStatus.COMPLETE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "complete" in stats["status_distribution"]
