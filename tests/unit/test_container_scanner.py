"""Tests for shieldops.security.container_scanner — ContainerImageScanner."""

from __future__ import annotations

import time

from shieldops.security.container_scanner import (
    ContainerImage,
    ContainerImageScanner,
    ImageRisk,
    ImageVulnerability,
    ScanReport,
    ScanStatus,
    VulnerabilityFixStatus,
)


def _engine(**kw) -> ContainerImageScanner:
    return ContainerImageScanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ImageRisk (5)
    def test_risk_clean(self):
        assert ImageRisk.CLEAN == "clean"

    def test_risk_low(self):
        assert ImageRisk.LOW == "low"

    def test_risk_medium(self):
        assert ImageRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert ImageRisk.HIGH == "high"

    def test_risk_critical(self):
        assert ImageRisk.CRITICAL == "critical"

    # ScanStatus (5)
    def test_status_pending(self):
        assert ScanStatus.PENDING == "pending"

    def test_status_scanning(self):
        assert ScanStatus.SCANNING == "scanning"

    def test_status_completed(self):
        assert ScanStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert ScanStatus.FAILED == "failed"

    def test_status_skipped(self):
        assert ScanStatus.SKIPPED == "skipped"

    # VulnerabilityFixStatus (5)
    def test_fix_status_fix_available(self):
        assert VulnerabilityFixStatus.FIX_AVAILABLE == "fix_available"

    def test_fix_status_no_fix(self):
        assert VulnerabilityFixStatus.NO_FIX == "no_fix"

    def test_fix_status_wont_fix(self):
        assert VulnerabilityFixStatus.WONT_FIX == "wont_fix"

    def test_fix_status_patch_pending(self):
        assert VulnerabilityFixStatus.PATCH_PENDING == "patch_pending"

    def test_fix_status_mitigated(self):
        assert VulnerabilityFixStatus.MITIGATED == "mitigated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_container_image_defaults(self):
        img = ContainerImage()
        assert img.id
        assert img.image_name == ""
        assert img.tag == "latest"
        assert img.registry == ""
        assert img.base_image == ""
        assert img.size_mb == 0.0
        assert img.layer_count == 0
        assert img.scan_status == ScanStatus.PENDING
        assert img.risk_level == ImageRisk.CLEAN
        assert img.last_scanned_at == 0.0
        assert img.created_at > 0

    def test_image_vulnerability_defaults(self):
        v = ImageVulnerability()
        assert v.id
        assert v.image_id == ""
        assert v.cve_id == ""
        assert v.severity == ImageRisk.LOW
        assert v.package_name == ""
        assert v.installed_version == ""
        assert v.fixed_version == ""
        assert v.fix_status == VulnerabilityFixStatus.NO_FIX
        assert v.created_at > 0

    def test_scan_report_defaults(self):
        r = ScanReport()
        assert r.total_images == 0
        assert r.scanned_count == 0
        assert r.vulnerable_count == 0
        assert r.total_vulnerabilities == 0
        assert r.critical_count == 0
        assert r.fixable_count == 0
        assert r.stale_image_count == 0
        assert r.risk_distribution == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_image
# ---------------------------------------------------------------------------


class TestRegisterImage:
    def test_basic_register(self):
        eng = _engine()
        img = eng.register_image(
            image_name="myapp",
            tag="v1.2.3",
            registry="gcr.io/project",
            base_image="python:3.12-slim",
            size_mb=150.0,
            layer_count=12,
        )
        assert img.image_name == "myapp"
        assert img.tag == "v1.2.3"
        assert img.registry == "gcr.io/project"
        assert img.base_image == "python:3.12-slim"
        assert img.size_mb == 150.0
        assert img.layer_count == 12
        assert img.scan_status == ScanStatus.PENDING

    def test_eviction_at_max(self):
        eng = _engine(max_images=3)
        for i in range(5):
            eng.register_image(image_name=f"img-{i}")
        assert len(eng._images) == 3


# ---------------------------------------------------------------------------
# get_image
# ---------------------------------------------------------------------------


class TestGetImage:
    def test_found(self):
        eng = _engine()
        img = eng.register_image(image_name="web-server", tag="v2.0")
        assert eng.get_image(img.id) is not None
        assert eng.get_image(img.id).image_name == "web-server"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_image("nonexistent") is None


# ---------------------------------------------------------------------------
# list_images
# ---------------------------------------------------------------------------


class TestListImages:
    def test_list_all(self):
        eng = _engine()
        eng.register_image(image_name="app-a")
        eng.register_image(image_name="app-b")
        assert len(eng.list_images()) == 2

    def test_filter_by_scan_status(self):
        eng = _engine()
        img_a = eng.register_image(image_name="app-a")
        eng.register_image(image_name="app-b")
        eng.scan_image(img_a.id)
        results = eng.list_images(scan_status=ScanStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].image_name == "app-a"

    def test_filter_by_risk_level(self):
        eng = _engine()
        img = eng.register_image(image_name="vulnerable-app")
        eng.record_vulnerability(img.id, "CVE-2025-001", severity=ImageRisk.HIGH)
        eng.scan_image(img.id)
        eng.register_image(image_name="clean-app")
        results = eng.list_images(risk_level=ImageRisk.HIGH)
        assert len(results) == 1
        assert results[0].image_name == "vulnerable-app"


# ---------------------------------------------------------------------------
# record_vulnerability
# ---------------------------------------------------------------------------


class TestRecordVulnerability:
    def test_basic_record(self):
        eng = _engine()
        img = eng.register_image(image_name="app")
        vuln = eng.record_vulnerability(
            image_id=img.id,
            cve_id="CVE-2025-12345",
            severity=ImageRisk.CRITICAL,
            package_name="openssl",
            installed_version="1.1.1",
            fixed_version="1.1.1w",
            fix_status=VulnerabilityFixStatus.FIX_AVAILABLE,
        )
        assert vuln is not None
        assert vuln.cve_id == "CVE-2025-12345"
        assert vuln.severity == ImageRisk.CRITICAL
        assert vuln.package_name == "openssl"
        assert vuln.fix_status == VulnerabilityFixStatus.FIX_AVAILABLE


# ---------------------------------------------------------------------------
# scan_image
# ---------------------------------------------------------------------------


class TestScanImage:
    def test_scan_with_vulns_sets_risk(self):
        eng = _engine()
        img = eng.register_image(image_name="app")
        eng.record_vulnerability(img.id, "CVE-2025-001", severity=ImageRisk.LOW)
        eng.record_vulnerability(img.id, "CVE-2025-002", severity=ImageRisk.HIGH)
        result = eng.scan_image(img.id)
        assert result is not None
        assert result.scan_status == ScanStatus.COMPLETED
        assert result.risk_level == ImageRisk.HIGH
        assert result.last_scanned_at > 0

    def test_scan_clean_image(self):
        eng = _engine()
        img = eng.register_image(image_name="clean-app")
        result = eng.scan_image(img.id)
        assert result is not None
        assert result.scan_status == ScanStatus.COMPLETED
        assert result.risk_level == ImageRisk.CLEAN


# ---------------------------------------------------------------------------
# detect_stale_images
# ---------------------------------------------------------------------------


class TestDetectStaleImages:
    def test_stale_and_fresh_images(self):
        eng = _engine(stale_threshold_days=90)
        # Never-scanned image is stale
        eng.register_image(image_name="never-scanned")
        # Recently scanned image is fresh
        img_fresh = eng.register_image(image_name="fresh")
        eng.scan_image(img_fresh.id)
        # Old-scanned image is stale
        img_old = eng.register_image(image_name="old")
        eng.scan_image(img_old.id)
        img_old.last_scanned_at = time.time() - (100 * 86400)
        stale = eng.detect_stale_images()
        assert len(stale) == 2
        stale_names = {s.image_name for s in stale}
        assert "never-scanned" in stale_names
        assert "old" in stale_names


# ---------------------------------------------------------------------------
# analyze_base_image_freshness
# ---------------------------------------------------------------------------


class TestAnalyzeBaseImageFreshness:
    def test_grouped_results(self):
        eng = _engine()
        eng.register_image(image_name="app-a", base_image="python:3.12-slim", size_mb=150.0)
        eng.register_image(image_name="app-b", base_image="python:3.12-slim", size_mb=200.0)
        eng.register_image(image_name="app-c", base_image="node:20-alpine", size_mb=80.0)
        results = eng.analyze_base_image_freshness()
        assert len(results) == 2
        python_group = [r for r in results if r["base_image"] == "python:3.12-slim"][0]
        assert python_group["total_images"] == 2
        assert python_group["avg_size_mb"] == 175.0


# ---------------------------------------------------------------------------
# identify_fixable_vulnerabilities
# ---------------------------------------------------------------------------


class TestIdentifyFixableVulnerabilities:
    def test_with_fix_available(self):
        eng = _engine()
        img = eng.register_image(image_name="app")
        eng.record_vulnerability(
            img.id,
            "CVE-001",
            fix_status=VulnerabilityFixStatus.FIX_AVAILABLE,
        )
        eng.record_vulnerability(
            img.id,
            "CVE-002",
            fix_status=VulnerabilityFixStatus.NO_FIX,
        )
        eng.record_vulnerability(
            img.id,
            "CVE-003",
            fix_status=VulnerabilityFixStatus.FIX_AVAILABLE,
        )
        fixable = eng.identify_fixable_vulnerabilities()
        assert len(fixable) == 2
        cve_ids = {v.cve_id for v in fixable}
        assert "CVE-001" in cve_ids
        assert "CVE-003" in cve_ids


# ---------------------------------------------------------------------------
# generate_scan_report
# ---------------------------------------------------------------------------


class TestGenerateScanReport:
    def test_basic_report(self):
        eng = _engine()
        img_a = eng.register_image(image_name="app-a")
        img_b = eng.register_image(image_name="app-b")
        eng.record_vulnerability(
            img_a.id,
            "CVE-001",
            severity=ImageRisk.CRITICAL,
            fix_status=VulnerabilityFixStatus.FIX_AVAILABLE,
        )
        eng.record_vulnerability(
            img_a.id,
            "CVE-002",
            severity=ImageRisk.LOW,
        )
        eng.scan_image(img_a.id)
        eng.scan_image(img_b.id)
        report = eng.generate_scan_report()
        assert report.total_images == 2
        assert report.scanned_count == 2
        assert report.vulnerable_count == 1
        assert report.total_vulnerabilities == 2
        assert report.critical_count == 1
        assert report.fixable_count == 1
        assert len(report.risk_distribution) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        img = eng.register_image(image_name="app")
        eng.record_vulnerability(img.id, "CVE-001")
        assert len(eng._images) == 1
        assert len(eng._vulnerabilities) == 1
        eng.clear_data()
        assert len(eng._images) == 0
        assert len(eng._vulnerabilities) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_images"] == 0
        assert stats["total_vulnerabilities"] == 0
        assert stats["scan_status_distribution"] == {}
        assert stats["risk_distribution"] == {}
        assert stats["registry_distribution"] == {}
        assert stats["vulnerability_severity_distribution"] == {}
        assert stats["fix_status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        img = eng.register_image(image_name="app", registry="ecr.aws")
        eng.record_vulnerability(img.id, "CVE-001", severity=ImageRisk.HIGH)
        eng.scan_image(img.id)
        stats = eng.get_stats()
        assert stats["total_images"] == 1
        assert stats["total_vulnerabilities"] == 1
        assert stats["max_images"] == 100000
        assert stats["stale_threshold_days"] == 90
