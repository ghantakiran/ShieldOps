"""Tests for GDPR data subject request processing.

Covers DSRType, DSRStatus enums, DataSubjectRequest model, GDPRProcessor
(create, process, list, access, erasure, portability, rectification),
DPAReport generation, and register_subject_data.
"""

from __future__ import annotations

import pytest

from shieldops.compliance.gdpr import (
    DataProcessingActivity,
    DataSubjectRequest,
    DPAReport,
    DSRStatus,
    DSRType,
    GDPRProcessor,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestDSRType:
    def test_access_value(self):
        assert DSRType.ACCESS == "access"

    def test_erasure_value(self):
        assert DSRType.ERASURE == "erasure"

    def test_portability_value(self):
        assert DSRType.PORTABILITY == "portability"

    def test_rectification_value(self):
        assert DSRType.RECTIFICATION == "rectification"

    def test_all_members(self):
        assert len(DSRType) == 4

    def test_is_str_enum(self):
        assert isinstance(DSRType.ACCESS, str)


class TestDSRStatus:
    def test_pending_value(self):
        assert DSRStatus.PENDING == "pending"

    def test_processing_value(self):
        assert DSRStatus.PROCESSING == "processing"

    def test_completed_value(self):
        assert DSRStatus.COMPLETED == "completed"

    def test_rejected_value(self):
        assert DSRStatus.REJECTED == "rejected"

    def test_all_members(self):
        assert len(DSRStatus) == 4


# ---------------------------------------------------------------------------
# DataSubjectRequest model
# ---------------------------------------------------------------------------


class TestDataSubjectRequest:
    def test_creation_minimal(self):
        req = DataSubjectRequest(
            subject_id="user-1",
            request_type=DSRType.ACCESS,
        )
        assert req.subject_id == "user-1"
        assert req.request_type == DSRType.ACCESS

    def test_auto_generated_id(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.id.startswith("dsr-")

    def test_unique_ids(self):
        r1 = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        r2 = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert r1.id != r2.id

    def test_default_status_pending(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.status == DSRStatus.PENDING

    def test_default_reason_empty(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.reason == ""

    def test_default_completed_at_none(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.completed_at is None

    def test_default_result_empty_dict(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.result == {}

    def test_requested_at_auto_set(self):
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        assert req.requested_at is not None
        assert req.requested_at.tzinfo is not None

    def test_custom_reason(self):
        req = DataSubjectRequest(
            subject_id="u1",
            request_type=DSRType.ERASURE,
            reason="User requested account deletion",
        )
        assert req.reason == "User requested account deletion"


# ---------------------------------------------------------------------------
# DPAReport model
# ---------------------------------------------------------------------------


class TestDPAReport:
    def test_default_organization(self):
        report = DPAReport()
        assert report.organization == "ShieldOps"

    def test_default_activities_empty(self):
        report = DPAReport()
        assert report.activities == []

    def test_default_total_subjects_zero(self):
        report = DPAReport()
        assert report.total_subjects == 0

    def test_default_dsr_summary_empty(self):
        report = DPAReport()
        assert report.dsr_summary == {}

    def test_generated_at_auto_set(self):
        report = DPAReport()
        assert report.generated_at is not None


# ---------------------------------------------------------------------------
# DataProcessingActivity model
# ---------------------------------------------------------------------------


class TestDataProcessingActivity:
    def test_creation(self):
        activity = DataProcessingActivity(
            name="Test Activity",
            purpose="Testing",
        )
        assert activity.name == "Test Activity"
        assert activity.purpose == "Testing"

    def test_defaults(self):
        activity = DataProcessingActivity(name="A", purpose="B")
        assert activity.data_categories == []
        assert activity.retention_days == 365
        assert activity.legal_basis == "legitimate_interest"
        assert activity.third_party_sharing is False


# ---------------------------------------------------------------------------
# GDPRProcessor
# ---------------------------------------------------------------------------


class TestGDPRProcessorCreate:
    def test_create_request(self):
        proc = GDPRProcessor()
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        result = proc.create_request(req)
        assert result.id == req.id

    def test_create_request_stored(self):
        proc = GDPRProcessor()
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        proc.create_request(req)
        assert proc.get_request(req.id) is not None

    def test_get_request_nonexistent(self):
        proc = GDPRProcessor()
        assert proc.get_request("nonexistent") is None


class TestGDPRProcessorList:
    def test_list_requests_empty(self):
        proc = GDPRProcessor()
        assert proc.list_requests() == []

    def test_list_requests_returns_all(self):
        proc = GDPRProcessor()
        for i in range(3):
            proc.create_request(DataSubjectRequest(subject_id=f"u{i}", request_type=DSRType.ACCESS))
        assert len(proc.list_requests()) == 3

    def test_list_requests_filter_by_status(self):
        proc = GDPRProcessor()
        req1 = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        req2 = DataSubjectRequest(
            subject_id="u2",
            request_type=DSRType.ACCESS,
            status=DSRStatus.COMPLETED,
        )
        proc.create_request(req1)
        proc.create_request(req2)
        pending = proc.list_requests(status="pending")
        assert len(pending) == 1
        assert pending[0].id == req1.id

    def test_list_requests_filter_completed(self):
        proc = GDPRProcessor()
        req = DataSubjectRequest(
            subject_id="u1",
            request_type=DSRType.ACCESS,
            status=DSRStatus.COMPLETED,
        )
        proc.create_request(req)
        completed = proc.list_requests(status="completed")
        assert len(completed) == 1

    def test_list_requests_limit(self):
        proc = GDPRProcessor()
        for i in range(10):
            proc.create_request(DataSubjectRequest(subject_id=f"u{i}", request_type=DSRType.ACCESS))
        result = proc.list_requests(limit=3)
        assert len(result) == 3


class TestGDPRProcessorAccess:
    @pytest.mark.asyncio
    async def test_process_access_returns_export(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "test@example.com", "name": "Test"})
        result = await proc.process_access("u1")
        assert result["subject_id"] == "u1"
        assert "data_export" in result
        assert result["data_export"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_process_access_categories(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com", "phone": "123"})
        result = await proc.process_access("u1")
        assert set(result["categories"]) == {"email", "phone"}

    @pytest.mark.asyncio
    async def test_process_access_no_data(self):
        proc = GDPRProcessor()
        result = await proc.process_access("unknown")
        assert result["data_export"] == {}
        assert result["categories"] == []

    @pytest.mark.asyncio
    async def test_process_access_includes_exported_at(self):
        proc = GDPRProcessor()
        result = await proc.process_access("u1")
        assert "exported_at" in result


class TestGDPRProcessorErasure:
    @pytest.mark.asyncio
    async def test_erasure_anonymizes_pii(self):
        proc = GDPRProcessor()
        proc.register_subject_data(
            "u1",
            {
                "email": "user@test.com",
                "name": "John Doe",
                "phone": "555-1234",
                "address": "123 Main St",
                "ip_address": "1.2.3.4",
                "preferences": {"theme": "dark"},
            },
        )
        result = await proc.process_erasure("u1")
        assert result["anonymized"] is True
        assert "email" in result["erased_fields"]
        assert "name" in result["erased_fields"]
        assert "phone" in result["erased_fields"]
        assert "address" in result["erased_fields"]
        assert "ip_address" in result["erased_fields"]
        # Non-PII should NOT be erased
        assert "preferences" not in result["erased_fields"]

    @pytest.mark.asyncio
    async def test_erasure_sets_redacted_values(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com", "name": "Test"})
        await proc.process_erasure("u1")
        data = proc._subject_data["u1"]
        assert data["email"] == "[REDACTED]"
        assert data["name"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_erasure_marks_anonymized(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        await proc.process_erasure("u1")
        data = proc._subject_data["u1"]
        assert data["_anonymized"] is True
        assert "_anonymized_at" in data

    @pytest.mark.asyncio
    async def test_erasure_no_data(self):
        proc = GDPRProcessor()
        result = await proc.process_erasure("unknown")
        assert result["erased_fields"] == []
        assert result["anonymized"] is True

    @pytest.mark.asyncio
    async def test_erasure_includes_processed_at(self):
        proc = GDPRProcessor()
        result = await proc.process_erasure("u1")
        assert "processed_at" in result


class TestGDPRProcessorProcessRequest:
    @pytest.mark.asyncio
    async def test_process_access_request(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        proc.create_request(req)
        result = await proc.process_request(req.id)
        assert result is not None
        assert result.status == DSRStatus.COMPLETED
        assert result.completed_at is not None
        assert "data_export" in result.result

    @pytest.mark.asyncio
    async def test_process_erasure_request(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ERASURE)
        proc.create_request(req)
        result = await proc.process_request(req.id)
        assert result.status == DSRStatus.COMPLETED
        assert result.result["anonymized"] is True

    @pytest.mark.asyncio
    async def test_process_portability_request(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.PORTABILITY)
        proc.create_request(req)
        result = await proc.process_request(req.id)
        assert result.status == DSRStatus.COMPLETED
        assert "data_export" in result.result

    @pytest.mark.asyncio
    async def test_process_rectification_request(self):
        proc = GDPRProcessor()
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.RECTIFICATION)
        proc.create_request(req)
        result = await proc.process_request(req.id)
        assert result.status == DSRStatus.COMPLETED
        assert "manual review" in result.result.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_process_nonexistent_request(self):
        proc = GDPRProcessor()
        result = await proc.process_request("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_status_transitions_through_processing(self):
        proc = GDPRProcessor()
        req = DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS)
        proc.create_request(req)
        assert req.status == DSRStatus.PENDING
        await proc.process_request(req.id)
        assert req.status == DSRStatus.COMPLETED


class TestGDPRProcessorDPAReport:
    def test_generate_report_default_activities(self):
        proc = GDPRProcessor()
        report = proc.generate_dpa_report()
        assert len(report.activities) == len(GDPRProcessor.DEFAULT_ACTIVITIES)

    def test_report_total_subjects(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        proc.register_subject_data("u2", {"email": "b@c.com"})
        report = proc.generate_dpa_report()
        assert report.total_subjects == 2

    def test_report_dsr_summary(self):
        proc = GDPRProcessor()
        proc.create_request(DataSubjectRequest(subject_id="u1", request_type=DSRType.ACCESS))
        proc.create_request(DataSubjectRequest(subject_id="u2", request_type=DSRType.ACCESS))
        proc.create_request(DataSubjectRequest(subject_id="u3", request_type=DSRType.ERASURE))
        report = proc.generate_dpa_report()
        assert report.dsr_summary["access"] == 2
        assert report.dsr_summary["erasure"] == 1

    def test_report_empty_processor(self):
        proc = GDPRProcessor()
        report = proc.generate_dpa_report()
        assert report.total_subjects == 0
        assert report.dsr_summary == {}

    def test_report_organization(self):
        proc = GDPRProcessor()
        report = proc.generate_dpa_report()
        assert report.organization == "ShieldOps"


class TestGDPRProcessorDefaultActivities:
    def test_default_activities_count(self):
        assert len(GDPRProcessor.DEFAULT_ACTIVITIES) == 5

    def test_default_activities_names(self):
        names = {a.name for a in GDPRProcessor.DEFAULT_ACTIVITIES}
        assert "Incident Investigation" in names
        assert "Remediation Execution" in names
        assert "Security Scanning" in names
        assert "User Authentication" in names
        assert "Audit Logging" in names

    def test_audit_logging_retention_7_years(self):
        audit = next(a for a in GDPRProcessor.DEFAULT_ACTIVITIES if a.name == "Audit Logging")
        assert audit.retention_days == 2555  # 7 years


class TestRegisterSubjectData:
    def test_register_and_retrieve(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "a@b.com"})
        assert proc._subject_data["u1"]["email"] == "a@b.com"

    def test_register_overwrites(self):
        proc = GDPRProcessor()
        proc.register_subject_data("u1", {"email": "old@b.com"})
        proc.register_subject_data("u1", {"email": "new@b.com"})
        assert proc._subject_data["u1"]["email"] == "new@b.com"
