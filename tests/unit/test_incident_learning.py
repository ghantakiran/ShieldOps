"""Tests for shieldops.agents.incident_learning — IncidentLearningTracker."""

from __future__ import annotations

import pytest

from shieldops.agents.incident_learning import (
    IncidentLearningTracker,
    IncidentLesson,
    LessonApplication,
    LessonCategory,
    LessonPriority,
)


def _tracker(**kw) -> IncidentLearningTracker:
    return IncidentLearningTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LessonCategory (5 values)

    def test_lesson_category_root_cause(self):
        assert LessonCategory.ROOT_CAUSE == "root_cause"

    def test_lesson_category_detection(self):
        assert LessonCategory.DETECTION == "detection"

    def test_lesson_category_response(self):
        assert LessonCategory.RESPONSE == "response"

    def test_lesson_category_prevention(self):
        assert LessonCategory.PREVENTION == "prevention"

    def test_lesson_category_process(self):
        assert LessonCategory.PROCESS == "process"

    # LessonPriority (4 values)

    def test_lesson_priority_critical(self):
        assert LessonPriority.CRITICAL == "critical"

    def test_lesson_priority_high(self):
        assert LessonPriority.HIGH == "high"

    def test_lesson_priority_medium(self):
        assert LessonPriority.MEDIUM == "medium"

    def test_lesson_priority_low(self):
        assert LessonPriority.LOW == "low"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_lesson_defaults(self):
        lesson = IncidentLesson(
            incident_id="inc-1",
            title="Fix timeout",
            category=LessonCategory.ROOT_CAUSE,
        )
        assert lesson.id
        assert lesson.incident_id == "inc-1"
        assert lesson.title == "Fix timeout"
        assert lesson.description == ""
        assert lesson.priority == LessonPriority.MEDIUM
        assert lesson.action_items == []
        assert lesson.tags == []
        assert lesson.learned_by == ""
        assert lesson.created_at > 0

    def test_lesson_application_defaults(self):
        app = LessonApplication(lesson_id="les-1")
        assert app.id
        assert app.lesson_id == "les-1"
        assert app.applied_to == ""
        assert app.result == ""
        assert app.success is False
        assert app.applied_at > 0


# ---------------------------------------------------------------------------
# record_lesson
# ---------------------------------------------------------------------------


class TestRecordLesson:
    def test_basic_record(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Timeout root cause",
            LessonCategory.ROOT_CAUSE,
        )
        assert lesson.incident_id == "inc-1"
        assert lesson.title == "Timeout root cause"
        assert lesson.category == LessonCategory.ROOT_CAUSE
        assert tracker.get_lesson(lesson.id) is not None

    def test_record_assigns_unique_ids(self):
        tracker = _tracker()
        l1 = tracker.record_lesson(
            "inc-1",
            "L1",
            LessonCategory.PROCESS,
        )
        l2 = tracker.record_lesson(
            "inc-2",
            "L2",
            LessonCategory.PROCESS,
        )
        assert l1.id != l2.id

    def test_record_with_extra_fields(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-2",
            "Improve alerting",
            LessonCategory.DETECTION,
            description="Need faster alerts",
            priority=LessonPriority.HIGH,
            action_items=["Add PagerDuty rule"],
            tags=["alerting", "monitoring"],
        )
        assert lesson.description == "Need faster alerts"
        assert lesson.priority == LessonPriority.HIGH
        assert lesson.action_items == ["Add PagerDuty rule"]
        assert lesson.tags == ["alerting", "monitoring"]

    def test_evicts_at_max_lessons(self):
        tracker = _tracker(max_lessons=3)
        ids = []
        for i in range(4):
            lesson = tracker.record_lesson(
                f"inc-{i}",
                f"Lesson {i}",
                LessonCategory.PROCESS,
            )
            ids.append(lesson.id)
        # Oldest should be evicted
        assert tracker.get_lesson(ids[0]) is None
        assert tracker.get_lesson(ids[3]) is not None
        assert len(tracker.list_lessons()) == 3


# ---------------------------------------------------------------------------
# apply_lesson
# ---------------------------------------------------------------------------


class TestApplyLesson:
    def test_creates_application_record(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Fix timeout",
            LessonCategory.ROOT_CAUSE,
        )
        app = tracker.apply_lesson(
            lesson.id,
            "web-service",
            result="Reduced timeouts",
            success=True,
        )
        assert app.lesson_id == lesson.id
        assert app.applied_to == "web-service"
        assert app.result == "Reduced timeouts"
        assert app.success is True

    def test_apply_defaults_success_false(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Fix",
            LessonCategory.PROCESS,
        )
        app = tracker.apply_lesson(lesson.id, "svc-a")
        assert app.success is False
        assert app.result == ""

    def test_multiple_applications_for_same_lesson(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Fix",
            LessonCategory.PROCESS,
        )
        tracker.apply_lesson(lesson.id, "svc-a", success=True)
        tracker.apply_lesson(lesson.id, "svc-b", success=False)
        apps = tracker.get_applications(lesson_id=lesson.id)
        assert len(apps) == 2

    def test_trims_to_max_applications(self):
        tracker = _tracker(max_applications=3)
        lesson = tracker.record_lesson(
            "inc-1",
            "Fix",
            LessonCategory.PROCESS,
        )
        for i in range(4):
            tracker.apply_lesson(lesson.id, f"svc-{i}")
        all_apps = tracker.get_applications()
        assert len(all_apps) == 3


# ---------------------------------------------------------------------------
# get_lesson
# ---------------------------------------------------------------------------


class TestGetLesson:
    def test_found(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Test",
            LessonCategory.ROOT_CAUSE,
        )
        result = tracker.get_lesson(lesson.id)
        assert result is not None
        assert result.id == lesson.id

    def test_not_found(self):
        tracker = _tracker()
        assert tracker.get_lesson("nonexistent") is None


# ---------------------------------------------------------------------------
# list_lessons
# ---------------------------------------------------------------------------


class TestListLessons:
    def test_filter_by_category(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "RCA",
            LessonCategory.ROOT_CAUSE,
        )
        tracker.record_lesson(
            "inc-2",
            "Detection",
            LessonCategory.DETECTION,
        )
        results = tracker.list_lessons(
            category=LessonCategory.ROOT_CAUSE,
        )
        assert len(results) == 1
        assert results[0].category == LessonCategory.ROOT_CAUSE

    def test_filter_by_priority(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Critical fix",
            LessonCategory.PROCESS,
            priority=LessonPriority.CRITICAL,
        )
        tracker.record_lesson(
            "inc-2",
            "Low fix",
            LessonCategory.PROCESS,
            priority=LessonPriority.LOW,
        )
        results = tracker.list_lessons(priority=LessonPriority.CRITICAL)
        assert len(results) == 1
        assert results[0].priority == LessonPriority.CRITICAL

    def test_filter_by_tag(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Tagged",
            LessonCategory.DETECTION,
            tags=["alerting", "monitoring"],
        )
        tracker.record_lesson(
            "inc-2",
            "No tag",
            LessonCategory.DETECTION,
        )
        results = tracker.list_lessons(tag="alerting")
        assert len(results) == 1
        assert "alerting" in results[0].tags

    def test_list_all_when_no_filter(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "L1",
            LessonCategory.ROOT_CAUSE,
        )
        tracker.record_lesson(
            "inc-2",
            "L2",
            LessonCategory.DETECTION,
        )
        tracker.record_lesson(
            "inc-3",
            "L3",
            LessonCategory.PROCESS,
        )
        results = tracker.list_lessons()
        assert len(results) == 3

    def test_filter_combined_category_and_priority(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "H-Root",
            LessonCategory.ROOT_CAUSE,
            priority=LessonPriority.HIGH,
        )
        tracker.record_lesson(
            "inc-2",
            "L-Root",
            LessonCategory.ROOT_CAUSE,
            priority=LessonPriority.LOW,
        )
        tracker.record_lesson(
            "inc-3",
            "H-Process",
            LessonCategory.PROCESS,
            priority=LessonPriority.HIGH,
        )
        results = tracker.list_lessons(
            category=LessonCategory.ROOT_CAUSE,
            priority=LessonPriority.HIGH,
        )
        assert len(results) == 1
        assert results[0].title == "H-Root"


# ---------------------------------------------------------------------------
# search_lessons
# ---------------------------------------------------------------------------


class TestSearchLessons:
    def test_finds_by_title_substring(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Database timeout fix",
            LessonCategory.ROOT_CAUSE,
        )
        tracker.record_lesson(
            "inc-2",
            "Memory leak patch",
            LessonCategory.PREVENTION,
        )
        results = tracker.search_lessons("timeout")
        assert len(results) == 1
        assert "timeout" in results[0].title.lower()

    def test_finds_by_description_substring(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Fix",
            LessonCategory.ROOT_CAUSE,
            description="The redis connection pool was exhausted",
        )
        results = tracker.search_lessons("redis")
        assert len(results) == 1

    def test_case_insensitive(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "DNS Failure Analysis",
            LessonCategory.ROOT_CAUSE,
        )
        results = tracker.search_lessons("dns failure")
        assert len(results) == 1

    def test_no_results_for_unmatched_query(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Timeout fix",
            LessonCategory.ROOT_CAUSE,
        )
        results = tracker.search_lessons("kubernetes")
        assert len(results) == 0

    def test_matches_multiple_lessons(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Redis timeout",
            LessonCategory.ROOT_CAUSE,
        )
        tracker.record_lesson(
            "inc-2",
            "API timeout",
            LessonCategory.RESPONSE,
        )
        tracker.record_lesson(
            "inc-3",
            "Memory leak",
            LessonCategory.PREVENTION,
        )
        results = tracker.search_lessons("timeout")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# get_applications
# ---------------------------------------------------------------------------


class TestGetApplications:
    def test_filter_by_lesson_id(self):
        tracker = _tracker()
        l1 = tracker.record_lesson(
            "inc-1",
            "L1",
            LessonCategory.PROCESS,
        )
        l2 = tracker.record_lesson(
            "inc-2",
            "L2",
            LessonCategory.PROCESS,
        )
        tracker.apply_lesson(l1.id, "svc-a")
        tracker.apply_lesson(l2.id, "svc-b")
        results = tracker.get_applications(lesson_id=l1.id)
        assert len(results) == 1
        assert results[0].lesson_id == l1.id

    def test_all_applications_when_no_filter(self):
        tracker = _tracker()
        l1 = tracker.record_lesson(
            "inc-1",
            "L1",
            LessonCategory.PROCESS,
        )
        tracker.apply_lesson(l1.id, "svc-a")
        tracker.apply_lesson(l1.id, "svc-b")
        results = tracker.get_applications()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# get_effective_lessons
# ---------------------------------------------------------------------------


class TestGetEffectiveLessons:
    def test_lessons_with_successful_application(self):
        tracker = _tracker()
        l1 = tracker.record_lesson(
            "inc-1",
            "Good lesson",
            LessonCategory.PREVENTION,
        )
        l2 = tracker.record_lesson(
            "inc-2",
            "Unused lesson",
            LessonCategory.PREVENTION,
        )
        tracker.apply_lesson(l1.id, "svc-a", success=True)
        tracker.apply_lesson(l2.id, "svc-b", success=False)
        effective = tracker.get_effective_lessons()
        assert len(effective) == 1
        assert effective[0].id == l1.id

    def test_lesson_with_mixed_applications_counts(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Mixed",
            LessonCategory.PROCESS,
        )
        tracker.apply_lesson(lesson.id, "svc-a", success=False)
        tracker.apply_lesson(lesson.id, "svc-b", success=True)
        effective = tracker.get_effective_lessons()
        assert len(effective) == 1

    def test_empty_when_no_successes(self):
        tracker = _tracker()
        lesson = tracker.record_lesson(
            "inc-1",
            "Lesson",
            LessonCategory.PROCESS,
        )
        tracker.apply_lesson(lesson.id, "svc-a", success=False)
        effective = tracker.get_effective_lessons()
        assert len(effective) == 0

    def test_empty_when_no_applications(self):
        tracker = _tracker()
        tracker.record_lesson(
            "inc-1",
            "Lesson",
            LessonCategory.PROCESS,
        )
        effective = tracker.get_effective_lessons()
        assert len(effective) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        tracker = _tracker()
        stats = tracker.get_stats()
        assert stats["total_lessons"] == 0
        assert stats["total_applications"] == 0
        assert stats["successful_applications"] == 0
        assert stats["effective_lessons"] == 0
        assert stats["category_distribution"] == {}
        assert stats["priority_distribution"] == {}
        assert stats["application_success_rate"] == 0.0

    def test_stats_populated(self):
        tracker = _tracker()
        l1 = tracker.record_lesson(
            "inc-1",
            "RCA lesson",
            LessonCategory.ROOT_CAUSE,
            priority=LessonPriority.HIGH,
        )
        l2 = tracker.record_lesson(
            "inc-2",
            "Process lesson",
            LessonCategory.PROCESS,
            priority=LessonPriority.MEDIUM,
        )
        tracker.apply_lesson(l1.id, "svc-a", success=True)
        tracker.apply_lesson(l1.id, "svc-b", success=False)
        tracker.apply_lesson(l2.id, "svc-c", success=True)

        stats = tracker.get_stats()
        assert stats["total_lessons"] == 2
        assert stats["total_applications"] == 3
        assert stats["successful_applications"] == 2
        assert stats["effective_lessons"] == 2
        assert stats["category_distribution"][LessonCategory.ROOT_CAUSE] == 1
        assert stats["category_distribution"][LessonCategory.PROCESS] == 1
        assert stats["priority_distribution"][LessonPriority.HIGH] == 1
        assert stats["priority_distribution"][LessonPriority.MEDIUM] == 1
        assert stats["application_success_rate"] == pytest.approx(
            2 / 3,
            abs=0.001,
        )
