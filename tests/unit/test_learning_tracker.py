"""Tests for shieldops.incidents.learning_tracker — IncidentLearningTracker."""

from __future__ import annotations

from shieldops.incidents.learning_tracker import (
    AdoptionLevel,
    IncidentLearningTracker,
    LearningTrackerReport,
    LessonApplication,
    LessonCategory,
    LessonRecord,
    LessonStatus,
)


def _engine(**kw) -> IncidentLearningTracker:
    return IncidentLearningTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LessonStatus (5)
    def test_status_identified(self):
        assert LessonStatus.IDENTIFIED == "identified"

    def test_status_documented(self):
        assert LessonStatus.DOCUMENTED == "documented"

    def test_status_shared(self):
        assert LessonStatus.SHARED == "shared"

    def test_status_applied(self):
        assert LessonStatus.APPLIED == "applied"

    def test_status_verified(self):
        assert LessonStatus.VERIFIED == "verified"

    # LessonCategory (5)
    def test_category_root_cause(self):
        assert LessonCategory.ROOT_CAUSE == "root_cause"

    def test_category_detection(self):
        assert LessonCategory.DETECTION == "detection"

    def test_category_response(self):
        assert LessonCategory.RESPONSE == "response"

    def test_category_communication(self):
        assert LessonCategory.COMMUNICATION == "communication"

    def test_category_architecture(self):
        assert LessonCategory.ARCHITECTURE == "architecture"

    # AdoptionLevel (5)
    def test_adoption_not_adopted(self):
        assert AdoptionLevel.NOT_ADOPTED == "not_adopted"

    def test_adoption_partially_adopted(self):
        assert AdoptionLevel.PARTIALLY_ADOPTED == "partially_adopted"

    def test_adoption_mostly_adopted(self):
        assert AdoptionLevel.MOSTLY_ADOPTED == "mostly_adopted"

    def test_adoption_fully_adopted(self):
        assert AdoptionLevel.FULLY_ADOPTED == "fully_adopted"

    def test_adoption_exceeds(self):
        assert AdoptionLevel.EXCEEDS == "exceeds"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_lesson_record_defaults(self):
        r = LessonRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.title == ""
        assert r.category == LessonCategory.ROOT_CAUSE
        assert r.status == LessonStatus.IDENTIFIED
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_lesson_application_defaults(self):
        r = LessonApplication()
        assert r.id
        assert r.lesson_id == ""
        assert r.team == ""
        assert r.adoption_level == AdoptionLevel.NOT_ADOPTED
        assert r.evidence == ""
        assert r.created_at > 0

    def test_learning_tracker_report_defaults(self):
        r = LearningTrackerReport()
        assert r.total_lessons == 0
        assert r.total_applications == 0
        assert r.adoption_rate_pct == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.unapplied_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_lesson
# -------------------------------------------------------------------


class TestRecordLesson:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lesson(
            "INC-001",
            "Need better alerting",
            category=LessonCategory.DETECTION,
            team="sre-team",
        )
        assert r.incident_id == "INC-001"
        assert r.title == "Need better alerting"
        assert r.category == LessonCategory.DETECTION
        assert r.team == "sre-team"

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_lesson("INC-001", "L1")
        r2 = eng.record_lesson("INC-002", "L2")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lesson(f"INC-{i}", f"Lesson {i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_lesson
# -------------------------------------------------------------------


class TestGetLesson:
    def test_found(self):
        eng = _engine()
        r = eng.record_lesson("INC-001", "Lesson 1")
        assert eng.get_lesson(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_lesson("nonexistent") is None


# -------------------------------------------------------------------
# list_lessons
# -------------------------------------------------------------------


class TestListLessons:
    def test_list_all(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1")
        eng.record_lesson("INC-002", "L2")
        assert len(eng.list_lessons()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1")
        eng.record_lesson("INC-002", "L2")
        results = eng.list_lessons(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", category=LessonCategory.ROOT_CAUSE)
        eng.record_lesson("INC-002", "L2", category=LessonCategory.DETECTION)
        results = eng.list_lessons(category=LessonCategory.DETECTION)
        assert len(results) == 1
        assert results[0].title == "L2"

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", status=LessonStatus.IDENTIFIED)
        eng.record_lesson("INC-002", "L2", status=LessonStatus.APPLIED)
        results = eng.list_lessons(status=LessonStatus.APPLIED)
        assert len(results) == 1
        assert results[0].title == "L2"


# -------------------------------------------------------------------
# record_application
# -------------------------------------------------------------------


class TestRecordApplication:
    def test_basic(self):
        eng = _engine()
        lesson = eng.record_lesson("INC-001", "L1")
        app = eng.record_application(
            lesson.id,
            team="sre-team",
            adoption_level=AdoptionLevel.FULLY_ADOPTED,
            evidence="Implemented in prod",
        )
        assert app.lesson_id == lesson.id
        assert app.team == "sre-team"
        assert app.adoption_level == AdoptionLevel.FULLY_ADOPTED

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_application(f"lesson-{i}")
        assert len(eng._applications) == 2


# -------------------------------------------------------------------
# update_lesson_status
# -------------------------------------------------------------------


class TestUpdateLessonStatus:
    def test_found(self):
        eng = _engine()
        r = eng.record_lesson("INC-001", "L1")
        updated = eng.update_lesson_status(r.id, LessonStatus.APPLIED)
        assert updated is not None
        assert updated.status == LessonStatus.APPLIED

    def test_not_found(self):
        eng = _engine()
        assert eng.update_lesson_status("bad-id", LessonStatus.APPLIED) is None


# -------------------------------------------------------------------
# calculate_adoption_rate
# -------------------------------------------------------------------


class TestCalculateAdoptionRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", status=LessonStatus.APPLIED)
        eng.record_lesson("INC-002", "L2", status=LessonStatus.VERIFIED)
        eng.record_lesson("INC-003", "L3", status=LessonStatus.IDENTIFIED)
        result = eng.calculate_adoption_rate()
        assert result["total"] == 3
        assert result["applied"] == 2
        # 2/3 * 100 = 66.67
        assert result["adoption_rate_pct"] == 66.67

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_adoption_rate()
        assert result["total"] == 0
        assert result["adoption_rate_pct"] == 0.0


# -------------------------------------------------------------------
# identify_unapplied_lessons
# -------------------------------------------------------------------


class TestIdentifyUnappliedLessons:
    def test_with_unapplied(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", status=LessonStatus.IDENTIFIED)
        eng.record_lesson("INC-002", "L2", status=LessonStatus.APPLIED)
        eng.record_lesson("INC-003", "L3", status=LessonStatus.SHARED)
        results = eng.identify_unapplied_lessons()
        assert len(results) == 2  # IDENTIFIED + SHARED

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unapplied_lessons() == []

    def test_all_applied(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", status=LessonStatus.APPLIED)
        eng.record_lesson("INC-002", "L2", status=LessonStatus.VERIFIED)
        assert eng.identify_unapplied_lessons() == []


# -------------------------------------------------------------------
# analyze_team_learning
# -------------------------------------------------------------------


class TestAnalyzeTeamLearning:
    def test_with_data(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1", team="sre", status=LessonStatus.APPLIED)
        eng.record_lesson("INC-002", "L2", team="sre", status=LessonStatus.IDENTIFIED)
        eng.record_lesson("INC-003", "L3", team="platform", status=LessonStatus.VERIFIED)
        results = eng.analyze_team_learning()
        assert len(results) == 2
        # Sorted by adoption_rate desc: platform=100%, sre=50%
        assert results[0]["team"] == "platform"
        assert results[0]["adoption_rate_pct"] == 100.0
        assert results[1]["team"] == "sre"
        assert results[1]["adoption_rate_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_team_learning() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_adoption_rate_pct=80.0)
        eng.record_lesson(
            "INC-001",
            "L1",
            status=LessonStatus.APPLIED,
            category=LessonCategory.DETECTION,
        )
        eng.record_lesson(
            "INC-002",
            "L2",
            status=LessonStatus.IDENTIFIED,
            category=LessonCategory.ROOT_CAUSE,
        )
        eng.record_application("lesson-1", adoption_level=AdoptionLevel.FULLY_ADOPTED)
        report = eng.generate_report()
        assert report.total_lessons == 2
        assert report.total_applications == 1
        assert report.by_status != {}
        assert report.by_category != {}
        assert report.unapplied_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_lessons == 0
        assert report.adoption_rate_pct == 0.0
        # 0.0% < 80.0% min target, so recommendation warns about low adoption
        assert "below" in report.recommendations[0] or "0.0%" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1")
        eng.record_application("lesson-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._applications) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_lessons"] == 0
        assert stats["total_applications"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_lesson("INC-001", "L1")
        eng.record_lesson("INC-002", "L2")
        eng.record_application("lesson-1")
        stats = eng.get_stats()
        assert stats["total_lessons"] == 2
        assert stats["total_applications"] == 1
        assert stats["unique_incidents"] == 2
        assert stats["min_adoption_rate_pct"] == 80.0
