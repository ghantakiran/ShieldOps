"""Tests for shieldops.knowledge.knowledge_decay — KnowledgeDecayDetector."""

from __future__ import annotations

from shieldops.knowledge.knowledge_decay import (
    ArticleType,
    DecayRisk,
    DecaySignal,
    DecayThreshold,
    KnowledgeDecayDetector,
    KnowledgeDecayRecord,
    KnowledgeDecayReport,
)


def _engine(**kw) -> KnowledgeDecayDetector:
    return KnowledgeDecayDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # DecayRisk (5)
    def test_risk_fresh(self):
        assert DecayRisk.FRESH == "fresh"

    def test_risk_aging(self):
        assert DecayRisk.AGING == "aging"

    def test_risk_stale(self):
        assert DecayRisk.STALE == "stale"

    def test_risk_decayed(self):
        assert DecayRisk.DECAYED == "decayed"

    def test_risk_obsolete(self):
        assert DecayRisk.OBSOLETE == "obsolete"

    # ArticleType (5)
    def test_type_runbook(self):
        assert ArticleType.RUNBOOK == "runbook"

    def test_type_troubleshooting(self):
        assert ArticleType.TROUBLESHOOTING == "troubleshooting"

    def test_type_architecture(self):
        assert ArticleType.ARCHITECTURE == "architecture"

    def test_type_onboarding(self):
        assert ArticleType.ONBOARDING == "onboarding"

    def test_type_postmortem(self):
        assert ArticleType.POSTMORTEM == "postmortem"

    # DecaySignal (5)
    def test_signal_age(self):
        assert DecaySignal.AGE == "age"

    def test_signal_infra_change(self):
        assert DecaySignal.INFRA_CHANGE == "infra_change"

    def test_signal_service_deprecated(self):
        assert DecaySignal.SERVICE_DEPRECATED == "service_deprecated"

    def test_signal_negative_feedback(self):
        assert DecaySignal.NEGATIVE_FEEDBACK == "negative_feedback"

    def test_signal_low_usage(self):
        assert DecaySignal.LOW_USAGE == "low_usage"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_knowledge_decay_record_defaults(self):
        r = KnowledgeDecayRecord()
        assert r.id
        assert r.article_id == ""
        assert r.article_title == ""
        assert r.article_type == ArticleType.RUNBOOK
        assert r.decay_risk == DecayRisk.FRESH
        assert r.decay_score == 0.0
        assert r.signals == []
        assert r.age_days == 0
        assert r.last_reviewed_days_ago == 0
        assert r.usage_count_30d == 0
        assert r.created_at > 0

    def test_decay_threshold_defaults(self):
        t = DecayThreshold()
        assert t.id
        assert t.article_type == ArticleType.RUNBOOK
        assert t.stale_days == 180
        assert t.obsolete_days == 365
        assert t.min_usage_30d == 1
        assert t.created_at > 0

    def test_knowledge_decay_report_defaults(self):
        r = KnowledgeDecayReport()
        assert r.total_assessments == 0
        assert r.stale_count == 0
        assert r.obsolete_count == 0
        assert r.by_risk == {}
        assert r.by_type == {}
        assert r.top_decay_signals == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# assess_decay
# ---------------------------------------------------------------------------


class TestAssessDecay:
    def test_basic_fresh(self):
        eng = _engine()
        r = eng.assess_decay(article_id="art-1", age_days=10, usage_count_30d=10)
        assert r.article_id == "art-1"
        assert r.decay_risk == DecayRisk.FRESH
        assert r.decay_score < 0.2

    def test_with_params_stale(self):
        eng = _engine(stale_days=180)
        r = eng.assess_decay(
            article_id="art-2",
            article_title="Old Runbook",
            article_type=ArticleType.RUNBOOK,
            age_days=300,
            last_reviewed_days_ago=200,
            usage_count_30d=0,
            signals=[DecaySignal.INFRA_CHANGE.value],
        )
        assert r.article_title == "Old Runbook"
        assert r.decay_score > 0.4
        assert DecaySignal.AGE.value in r.signals
        assert DecaySignal.LOW_USAGE.value in r.signals
        assert DecaySignal.INFRA_CHANGE.value in r.signals

    def test_auto_adds_age_signal(self):
        eng = _engine(stale_days=180)
        r = eng.assess_decay(article_id="art-3", age_days=200)
        assert DecaySignal.AGE.value in r.signals

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.assess_decay(article_id=f"art-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.assess_decay(article_id="art-1")
        result = eng.get_assessment(r.id)
        assert result is not None
        assert result.article_id == "art-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1")
        eng.assess_decay(article_id="art-2")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_article_type(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1", article_type=ArticleType.RUNBOOK)
        eng.assess_decay(article_id="art-2", article_type=ArticleType.POSTMORTEM)
        results = eng.list_assessments(article_type=ArticleType.RUNBOOK)
        assert len(results) == 1
        assert results[0].article_type == ArticleType.RUNBOOK

    def test_filter_by_decay_risk(self):
        eng = _engine(stale_days=180)
        eng.assess_decay(article_id="art-fresh", age_days=10, usage_count_30d=10)
        eng.assess_decay(
            article_id="art-old", age_days=500, last_reviewed_days_ago=400, usage_count_30d=0
        )
        fresh = eng.list_assessments(decay_risk=DecayRisk.FRESH)
        assert len(fresh) == 1
        assert fresh[0].article_id == "art-fresh"


# ---------------------------------------------------------------------------
# set_threshold
# ---------------------------------------------------------------------------


class TestSetThreshold:
    def test_basic(self):
        eng = _engine()
        t = eng.set_threshold(article_type=ArticleType.RUNBOOK)
        assert t.article_type == ArticleType.RUNBOOK
        assert t.stale_days == 180
        assert t.obsolete_days == 365
        assert t.min_usage_30d == 1

    def test_with_custom_values(self):
        eng = _engine()
        t = eng.set_threshold(
            article_type=ArticleType.POSTMORTEM,
            stale_days=90,
            obsolete_days=180,
            min_usage_30d=5,
        )
        assert t.article_type == ArticleType.POSTMORTEM
        assert t.stale_days == 90
        assert t.obsolete_days == 180
        assert t.min_usage_30d == 5

    def test_overwrites_existing(self):
        eng = _engine()
        eng.set_threshold(article_type=ArticleType.RUNBOOK, stale_days=100)
        eng.set_threshold(article_type=ArticleType.RUNBOOK, stale_days=200)
        assert eng._thresholds[ArticleType.RUNBOOK.value].stale_days == 200


# ---------------------------------------------------------------------------
# calculate_decay_score
# ---------------------------------------------------------------------------


class TestCalculateDecayScore:
    def test_found(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1", age_days=100, usage_count_30d=5)
        result = eng.calculate_decay_score("art-1")
        assert result["found"] is True
        assert result["article_id"] == "art-1"
        assert result["decay_score"] >= 0.0

    def test_not_found(self):
        eng = _engine()
        result = eng.calculate_decay_score("nonexistent")
        assert result["found"] is False
        assert result["decay_score"] == 0.0


# ---------------------------------------------------------------------------
# identify_obsolete_articles
# ---------------------------------------------------------------------------


class TestIdentifyObsoleteArticles:
    def test_has_obsolete(self):
        eng = _engine(stale_days=180)
        eng.assess_decay(article_id="art-fresh", age_days=10, usage_count_30d=10)
        eng.assess_decay(
            article_id="art-old",
            article_title="Ancient Runbook",
            age_days=500,
            last_reviewed_days_ago=400,
            usage_count_30d=0,
            signals=[DecaySignal.SERVICE_DEPRECATED.value],
        )
        results = eng.identify_obsolete_articles()
        assert len(results) >= 1
        found_ids = [r["article_id"] for r in results]
        assert "art-old" in found_ids

    def test_none_obsolete(self):
        eng = _engine()
        eng.assess_decay(article_id="art-fresh", age_days=10, usage_count_30d=10)
        assert eng.identify_obsolete_articles() == []


# ---------------------------------------------------------------------------
# prioritize_for_review
# ---------------------------------------------------------------------------


class TestPrioritizeForReview:
    def test_has_items(self):
        eng = _engine(stale_days=180)
        eng.assess_decay(
            article_id="art-1", age_days=200, last_reviewed_days_ago=100, usage_count_30d=1
        )
        eng.assess_decay(article_id="art-2", age_days=10, usage_count_30d=10)
        results = eng.prioritize_for_review()
        # FRESH articles are excluded, so only non-fresh articles should appear
        for item in results:
            assert item["decay_risk"] != DecayRisk.FRESH.value

    def test_all_fresh(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1", age_days=5, usage_count_30d=10)
        results = eng.prioritize_for_review()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# detect_deprecated_references
# ---------------------------------------------------------------------------


class TestDetectDeprecatedReferences:
    def test_has_deprecated(self):
        eng = _engine()
        eng.assess_decay(
            article_id="art-1",
            signals=[DecaySignal.SERVICE_DEPRECATED.value],
        )
        eng.assess_decay(article_id="art-2")
        results = eng.detect_deprecated_references()
        assert len(results) == 1
        assert results[0]["article_id"] == "art-1"

    def test_no_deprecated(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1")
        assert eng.detect_deprecated_references() == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(stale_days=180)
        eng.assess_decay(article_id="art-1", age_days=10, usage_count_30d=10)
        eng.assess_decay(
            article_id="art-2",
            age_days=500,
            last_reviewed_days_ago=400,
            usage_count_30d=0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeDecayReport)
        assert report.total_assessments == 2
        assert len(report.by_risk) > 0
        assert len(report.by_type) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_assessments == 0
        assert report.stale_count == 0
        assert report.obsolete_count == 0
        assert "Knowledge base health is good" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.assess_decay(article_id="art-1")
        eng.set_threshold(article_type=ArticleType.RUNBOOK)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._thresholds) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_thresholds"] == 0
        assert stats["risk_distribution"] == {}
        assert stats["unique_articles"] == 0

    def test_populated(self):
        eng = _engine(stale_days=180)
        eng.assess_decay(article_id="art-1", age_days=10, usage_count_30d=10)
        eng.set_threshold(article_type=ArticleType.RUNBOOK)
        stats = eng.get_stats()
        assert stats["total_assessments"] == 1
        assert stats["total_thresholds"] == 1
        assert stats["stale_days"] == 180
        assert "fresh" in stats["risk_distribution"]
        assert stats["unique_articles"] == 1
