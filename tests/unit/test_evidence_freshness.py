"""Tests for shieldops.compliance.evidence_freshness — EvidenceFreshnessMonitor."""

from __future__ import annotations

import time

from shieldops.compliance.evidence_freshness import (
    AuditUrgency,
    EvidenceCategory,
    EvidenceFreshnessMonitor,
    FreshnessGap,
    FreshnessRecord,
    FreshnessReport,
    FreshnessStatus,
)


def _engine(**kw) -> EvidenceFreshnessMonitor:
    return EvidenceFreshnessMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # FreshnessStatus (5)
    def test_status_current(self):
        assert FreshnessStatus.CURRENT == "current"

    def test_status_aging(self):
        assert FreshnessStatus.AGING == "aging"

    def test_status_stale(self):
        assert FreshnessStatus.STALE == "stale"

    def test_status_expired(self):
        assert FreshnessStatus.EXPIRED == "expired"

    def test_status_missing(self):
        assert FreshnessStatus.MISSING == "missing"

    # EvidenceCategory (5)
    def test_category_access_review(self):
        assert EvidenceCategory.ACCESS_REVIEW == "access_review"

    def test_category_vulnerability_scan(self):
        assert EvidenceCategory.VULNERABILITY_SCAN == "vulnerability_scan"

    def test_category_policy_attestation(self):
        assert EvidenceCategory.POLICY_ATTESTATION == "policy_attestation"

    def test_category_configuration_audit(self):
        assert EvidenceCategory.CONFIGURATION_AUDIT == "configuration_audit"

    def test_category_penetration_test(self):
        assert EvidenceCategory.PENETRATION_TEST == "penetration_test"

    # AuditUrgency (5)
    def test_urgency_routine(self):
        assert AuditUrgency.ROUTINE == "routine"

    def test_urgency_upcoming(self):
        assert AuditUrgency.UPCOMING == "upcoming"

    def test_urgency_imminent(self):
        assert AuditUrgency.IMMINENT == "imminent"

    def test_urgency_overdue(self):
        assert AuditUrgency.OVERDUE == "overdue"

    def test_urgency_blocked(self):
        assert AuditUrgency.BLOCKED == "blocked"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_freshness_record_defaults(self):
        r = FreshnessRecord()
        assert r.id
        assert r.evidence_id == ""
        assert r.category == EvidenceCategory.ACCESS_REVIEW
        assert r.control_id == ""
        assert r.status == FreshnessStatus.CURRENT
        assert r.urgency == AuditUrgency.ROUTINE
        assert r.collected_at == 0.0
        assert r.expires_at == 0.0
        assert r.days_until_expiry == 0
        assert r.framework == ""
        assert r.owner == ""
        assert r.created_at > 0

    def test_freshness_gap_defaults(self):
        g = FreshnessGap()
        assert g.id
        assert g.category == EvidenceCategory.ACCESS_REVIEW
        assert g.control_id == ""
        assert g.expected_frequency_days == 90
        assert g.actual_gap_days == 0
        assert g.severity == "low"
        assert g.created_at > 0

    def test_freshness_report_defaults(self):
        r = FreshnessReport()
        assert r.total_evidence == 0
        assert r.current_count == 0
        assert r.stale_count == 0
        assert r.expired_count == 0
        assert r.freshness_score_pct == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_evidence
# ---------------------------------------------------------------------------


class TestRecordEvidence:
    def test_current_evidence(self):
        eng = _engine()
        now = time.time()
        r = eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
            framework="SOC2",
            owner="alice",
        )
        assert r.evidence_id == "ev-1"
        assert r.status == FreshnessStatus.CURRENT
        assert r.urgency == AuditUrgency.ROUTINE
        assert r.framework == "SOC2"
        assert r.owner == "alice"

    def test_expired_evidence(self):
        eng = _engine()
        now = time.time()
        r = eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now - 86400 * 200,
            expires_at=now - 86400,
        )
        assert r.status == FreshnessStatus.EXPIRED
        assert r.urgency == AuditUrgency.OVERDUE

    def test_missing_evidence(self):
        eng = _engine()
        r = eng.record_evidence(
            evidence_id="ev-3",
            category=EvidenceCategory.PENETRATION_TEST,
            control_id="ctrl-3",
            collected_at=0.0,
            expires_at=0.0,
        )
        assert r.status == FreshnessStatus.MISSING
        assert r.urgency == AuditUrgency.BLOCKED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        now = time.time()
        for i in range(5):
            eng.record_evidence(
                evidence_id=f"ev-{i}",
                category=EvidenceCategory.ACCESS_REVIEW,
                control_id=f"ctrl-{i}",
                collected_at=now,
                expires_at=now + 86400 * 365,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


class TestGetEvidence:
    def test_found(self):
        eng = _engine()
        now = time.time()
        r = eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        result = eng.get_evidence(r.id)
        assert result is not None
        assert result.evidence_id == "ev-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_evidence("nonexistent") is None


# ---------------------------------------------------------------------------
# list_evidence
# ---------------------------------------------------------------------------


class TestListEvidence:
    def test_list_all(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        assert len(eng.list_evidence()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.PENETRATION_TEST,
            control_id="ctrl-2",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        results = eng.list_evidence(category=EvidenceCategory.PENETRATION_TEST)
        assert len(results) == 1
        assert results[0].category == EvidenceCategory.PENETRATION_TEST

    def test_filter_by_status(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now - 86400 * 200,
            expires_at=now - 86400,
        )
        results = eng.list_evidence(status=FreshnessStatus.EXPIRED)
        assert len(results) == 1
        assert results[0].status == FreshnessStatus.EXPIRED


# ---------------------------------------------------------------------------
# assess_freshness
# ---------------------------------------------------------------------------


class TestAssessFreshness:
    def test_valid_record(self):
        eng = _engine()
        now = time.time()
        r = eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        result = eng.assess_freshness(r.id)
        assert result["found"] is True
        assert result["record_id"] == r.id
        assert result["evidence_id"] == "ev-1"
        assert result["new_status"] == FreshnessStatus.CURRENT.value

    def test_not_found(self):
        eng = _engine()
        result = eng.assess_freshness("nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# detect_gaps
# ---------------------------------------------------------------------------


class TestDetectGaps:
    def test_has_gaps(self):
        eng = _engine()
        time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=0.0,
            expires_at=0.0,
        )
        gaps = eng.detect_gaps()
        assert len(gaps) >= 1
        assert isinstance(gaps[0], FreshnessGap)
        assert gaps[0].control_id == "ctrl-1"
        assert gaps[0].severity == "critical"

    def test_no_gaps(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        gaps = eng.detect_gaps()
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# calculate_freshness_score
# ---------------------------------------------------------------------------


class TestCalculateFreshnessScore:
    def test_all_current(self):
        eng = _engine()
        now = time.time()
        for i in range(3):
            eng.record_evidence(
                evidence_id=f"ev-{i}",
                category=EvidenceCategory.ACCESS_REVIEW,
                control_id=f"ctrl-{i}",
                collected_at=now,
                expires_at=now + 86400 * 365,
            )
        result = eng.calculate_freshness_score()
        assert result["score_pct"] == 100.0
        assert result["total"] == 3
        assert result["current"] == 3

    def test_mixed(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now - 86400 * 200,
            expires_at=now - 86400,
        )
        result = eng.calculate_freshness_score()
        assert result["score_pct"] == 50.0
        assert result["total"] == 2
        assert result["current"] == 1
        assert result["non_current"] == 1


# ---------------------------------------------------------------------------
# identify_expiring_soon
# ---------------------------------------------------------------------------


class TestIdentifyExpiringSoon:
    def test_some_expiring(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 15,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        results = eng.identify_expiring_soon(days=30)
        assert len(results) == 1
        assert results[0]["evidence_id"] == "ev-1"
        assert results[0]["days_until_expiry"] <= 30

    def test_none_expiring(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        results = eng.identify_expiring_soon(days=30)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# rank_by_urgency
# ---------------------------------------------------------------------------


class TestRankByUrgency:
    def test_ranked_order(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-current",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-missing",
            category=EvidenceCategory.PENETRATION_TEST,
            control_id="ctrl-2",
            collected_at=0.0,
            expires_at=0.0,
        )
        ranked = eng.rank_by_urgency()
        assert len(ranked) == 2
        assert ranked[0]["urgency"] == AuditUrgency.BLOCKED.value
        assert ranked[1]["urgency"] == AuditUrgency.ROUTINE.value

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_urgency() == []


# ---------------------------------------------------------------------------
# generate_freshness_report
# ---------------------------------------------------------------------------


class TestGenerateFreshnessReport:
    def test_populated(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.record_evidence(
            evidence_id="ev-2",
            category=EvidenceCategory.VULNERABILITY_SCAN,
            control_id="ctrl-2",
            collected_at=now - 86400 * 200,
            expires_at=now - 86400,
        )
        report = eng.generate_freshness_report()
        assert isinstance(report, FreshnessReport)
        assert report.total_evidence == 2
        assert report.current_count == 1
        assert report.expired_count == 1
        assert report.freshness_score_pct == 50.0
        assert len(report.by_status) > 0
        assert len(report.by_category) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_freshness_report()
        assert report.total_evidence == 0
        assert report.freshness_score_pct == 0.0
        assert "All compliance evidence is current" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        eng.detect_gaps()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["status_distribution"] == {}
        assert stats["unique_controls"] == 0

    def test_populated(self):
        eng = _engine()
        now = time.time()
        eng.record_evidence(
            evidence_id="ev-1",
            category=EvidenceCategory.ACCESS_REVIEW,
            control_id="ctrl-1",
            collected_at=now,
            expires_at=now + 86400 * 365,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["stale_days"] == 90
        assert "current" in stats["status_distribution"]
        assert stats["unique_controls"] == 1
