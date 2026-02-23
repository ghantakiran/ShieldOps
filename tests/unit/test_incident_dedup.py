"""Tests for shieldops.incidents.dedup_engine — IncidentDeduplicationEngine."""

from __future__ import annotations

from shieldops.incidents.dedup_engine import (
    DedupCandidate,
    DedupStrategy,
    IncidentDeduplicationEngine,
    IncidentSource,
    IncomingIncident,
    MergeDecision,
    MergedIncident,
)


def _engine(**kw) -> IncidentDeduplicationEngine:
    return IncidentDeduplicationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_strategy_exact(self):
        assert DedupStrategy.EXACT_MATCH == "exact_match"

    def test_strategy_fuzzy(self):
        assert DedupStrategy.FUZZY_MATCH == "fuzzy_match"

    def test_strategy_fingerprint(self):
        assert DedupStrategy.FINGERPRINT == "fingerprint"

    def test_strategy_content(self):
        assert DedupStrategy.CONTENT_SIMILARITY == "content_similarity"

    def test_decision_auto(self):
        assert MergeDecision.AUTO_MERGED == "auto_merged"

    def test_decision_candidate(self):
        assert MergeDecision.CANDIDATE == "candidate"

    def test_decision_rejected(self):
        assert MergeDecision.REJECTED == "rejected"

    def test_decision_manual(self):
        assert MergeDecision.MANUAL_MERGED == "manual_merged"

    def test_source_pagerduty(self):
        assert IncidentSource.PAGERDUTY == "pagerduty"

    def test_source_slack(self):
        assert IncidentSource.SLACK == "slack"

    def test_source_email(self):
        assert IncidentSource.EMAIL == "email"

    def test_source_monitoring(self):
        assert IncidentSource.MONITORING == "monitoring"

    def test_source_manual(self):
        assert IncidentSource.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_defaults(self):
        i = IncomingIncident(title="Server down")
        assert i.id
        assert i.title == "Server down"
        assert i.source == IncidentSource.MANUAL
        assert i.fingerprint == ""

    def test_candidate_defaults(self):
        c = DedupCandidate(incident_id="i-1", duplicate_of="i-2")
        assert c.decision == MergeDecision.CANDIDATE
        assert c.similarity == 0.0

    def test_merged_defaults(self):
        m = MergedIncident(primary_id="i-1")
        assert m.merged_ids == []
        assert m.source_count == 1


# ---------------------------------------------------------------------------
# submit_incident
# ---------------------------------------------------------------------------


class TestSubmitIncident:
    def test_basic_submit(self):
        eng = _engine()
        incident = eng.submit_incident("Server down")
        assert incident.title == "Server down"
        assert incident.fingerprint != ""

    def test_unique_ids(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        i2 = eng.submit_incident("Alert 2")
        assert i1.id != i2.id

    def test_evicts_at_max(self):
        eng = _engine(max_incidents=2)
        i1 = eng.submit_incident("Alert 1")
        eng.submit_incident("Alert 2")
        eng.submit_incident("Alert 3")
        assert i1.id not in eng._incidents


# ---------------------------------------------------------------------------
# compute_fingerprint
# ---------------------------------------------------------------------------


class TestComputeFingerprint:
    def test_deterministic(self):
        eng = _engine()
        fp1 = eng.compute_fingerprint("Server down", "auth-svc")
        fp2 = eng.compute_fingerprint("Server down", "auth-svc")
        assert fp1 == fp2

    def test_case_insensitive(self):
        eng = _engine()
        fp1 = eng.compute_fingerprint("Server Down", "Auth-Svc")
        fp2 = eng.compute_fingerprint("server down", "auth-svc")
        assert fp1 == fp2

    def test_different_inputs(self):
        eng = _engine()
        fp1 = eng.compute_fingerprint("Server down", "auth-svc")
        fp2 = eng.compute_fingerprint("Database slow", "auth-svc")
        assert fp1 != fp2


# ---------------------------------------------------------------------------
# find_duplicates
# ---------------------------------------------------------------------------


class TestFindDuplicates:
    def test_fingerprint_match(self):
        eng = _engine()
        i1 = eng.submit_incident("Server down", service="auth-svc")
        i2 = eng.submit_incident("Server down", service="auth-svc")
        dups = eng.find_duplicates(i2.id, strategy=DedupStrategy.FINGERPRINT)
        assert len(dups) == 1
        assert dups[0].duplicate_of == i1.id

    def test_no_duplicates(self):
        eng = _engine()
        i1 = eng.submit_incident("Server down", service="auth-svc")
        eng.submit_incident("Database slow", service="billing-svc")
        dups = eng.find_duplicates(i1.id, strategy=DedupStrategy.FINGERPRINT)
        assert len(dups) == 0

    def test_exact_match(self):
        eng = _engine()
        eng.submit_incident("Server down", service="auth")
        i2 = eng.submit_incident("Server down", service="auth")
        dups = eng.find_duplicates(i2.id, strategy=DedupStrategy.EXACT_MATCH)
        assert len(dups) == 1

    def test_not_found(self):
        eng = _engine()
        dups = eng.find_duplicates("nonexistent")
        assert len(dups) == 0


# ---------------------------------------------------------------------------
# auto_merge / manual_merge
# ---------------------------------------------------------------------------


class TestAutoMerge:
    def test_auto_merge(self):
        eng = _engine()
        i1 = eng.submit_incident("Server down", service="auth")
        i2 = eng.submit_incident("Server down", service="auth")
        eng.find_duplicates(i2.id, strategy=DedupStrategy.FINGERPRINT)
        merged = eng.auto_merge(i2.id)
        assert merged is not None
        assert merged.primary_id == i1.id

    def test_auto_merge_no_candidates(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        assert eng.auto_merge(i1.id) is None


class TestManualMerge:
    def test_manual_merge(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        i2 = eng.submit_incident("Alert 2")
        merged = eng.manual_merge(i1.id, [i2.id])
        assert merged is not None
        assert merged.primary_id == i1.id
        assert i2.id in merged.merged_ids

    def test_manual_merge_invalid_primary(self):
        eng = _engine()
        assert eng.manual_merge("nonexistent", ["x"]) is None

    def test_manual_merge_no_valid_ids(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        assert eng.manual_merge(i1.id, ["nonexistent"]) is None


# ---------------------------------------------------------------------------
# reject_candidate / list_candidates
# ---------------------------------------------------------------------------


class TestRejectCandidate:
    def test_reject(self):
        eng = _engine()
        eng.submit_incident("Server down", service="auth")
        i2 = eng.submit_incident("Server down", service="auth")
        dups = eng.find_duplicates(i2.id, strategy=DedupStrategy.FINGERPRINT)
        result = eng.reject_candidate(dups[0].id)
        assert result is not None
        assert result.decision == MergeDecision.REJECTED

    def test_reject_not_found(self):
        eng = _engine()
        assert eng.reject_candidate("nonexistent") is None


class TestListCandidates:
    def test_list_all(self):
        eng = _engine()
        eng.submit_incident("Alert", service="svc")
        i2 = eng.submit_incident("Alert", service="svc")
        eng.find_duplicates(i2.id)
        candidates = eng.list_candidates()
        assert len(candidates) >= 1

    def test_filter_by_decision(self):
        eng = _engine()
        eng.submit_incident("Alert", service="svc")
        i2 = eng.submit_incident("Alert", service="svc")
        dups = eng.find_duplicates(i2.id)
        eng.reject_candidate(dups[0].id)
        candidates = eng.list_candidates(decision=MergeDecision.REJECTED)
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# get_merged / list_merged / stats
# ---------------------------------------------------------------------------


class TestMerged:
    def test_get_merged(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        i2 = eng.submit_incident("Alert 2")
        merged = eng.manual_merge(i1.id, [i2.id])
        assert eng.get_merged(merged.id) is not None

    def test_get_merged_not_found(self):
        eng = _engine()
        assert eng.get_merged("nonexistent") is None

    def test_list_merged(self):
        eng = _engine()
        i1 = eng.submit_incident("Alert 1")
        i2 = eng.submit_incident("Alert 2")
        eng.manual_merge(i1.id, [i2.id])
        assert len(eng.list_merged()) == 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_incidents"] == 0
        assert stats["total_merged"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.submit_incident("Alert 1", source=IncidentSource.PAGERDUTY)
        eng.submit_incident("Alert 2", source=IncidentSource.SLACK)
        stats = eng.get_stats()
        assert stats["total_incidents"] == 2
        assert stats["source_distribution"][IncidentSource.PAGERDUTY] == 1
