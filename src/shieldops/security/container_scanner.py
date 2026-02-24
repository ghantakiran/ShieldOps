"""Container Image Scanner — vulnerability scanning, base image freshness, layers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImageRisk(StrEnum):
    CLEAN = "clean"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScanStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VulnerabilityFixStatus(StrEnum):
    FIX_AVAILABLE = "fix_available"
    NO_FIX = "no_fix"
    WONT_FIX = "wont_fix"
    PATCH_PENDING = "patch_pending"
    MITIGATED = "mitigated"


# --- Models ---


class ContainerImage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_name: str = ""
    tag: str = "latest"
    registry: str = ""
    base_image: str = ""
    size_mb: float = 0.0
    layer_count: int = 0
    scan_status: ScanStatus = ScanStatus.PENDING
    risk_level: ImageRisk = ImageRisk.CLEAN
    last_scanned_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ImageVulnerability(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_id: str = ""
    cve_id: str = ""
    severity: ImageRisk = ImageRisk.LOW
    package_name: str = ""
    installed_version: str = ""
    fixed_version: str = ""
    fix_status: VulnerabilityFixStatus = VulnerabilityFixStatus.NO_FIX
    created_at: float = Field(default_factory=time.time)


class ScanReport(BaseModel):
    total_images: int = 0
    scanned_count: int = 0
    vulnerable_count: int = 0
    total_vulnerabilities: int = 0
    critical_count: int = 0
    fixable_count: int = 0
    stale_image_count: int = 0
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


# Risk severity ordering for comparison (higher index = higher risk)
_RISK_ORDER: list[ImageRisk] = [
    ImageRisk.CLEAN,
    ImageRisk.LOW,
    ImageRisk.MEDIUM,
    ImageRisk.HIGH,
    ImageRisk.CRITICAL,
]


class ContainerImageScanner:
    """Container image vulnerability scanning, base image freshness, and layer analysis."""

    def __init__(
        self,
        max_images: int = 100000,
        stale_threshold_days: int = 90,
    ) -> None:
        self._max_images = max_images
        self._stale_threshold_days = stale_threshold_days
        self._images: list[ContainerImage] = []
        self._vulnerabilities: list[ImageVulnerability] = []
        logger.info(
            "container_scanner.initialized",
            max_images=max_images,
            stale_threshold_days=stale_threshold_days,
        )

    def register_image(
        self,
        image_name: str,
        tag: str = "latest",
        registry: str = "",
        base_image: str = "",
        size_mb: float = 0.0,
        layer_count: int = 0,
    ) -> ContainerImage:
        """Register a container image for scanning."""
        image = ContainerImage(
            image_name=image_name,
            tag=tag,
            registry=registry,
            base_image=base_image,
            size_mb=size_mb,
            layer_count=layer_count,
        )
        self._images.append(image)
        if len(self._images) > self._max_images:
            self._images = self._images[-self._max_images :]
        logger.info(
            "container_scanner.image_registered",
            image_id=image.id,
            image_name=image_name,
            tag=tag,
            registry=registry,
        )
        return image

    def get_image(self, image_id: str) -> ContainerImage | None:
        """Retrieve a single image by ID."""
        for img in self._images:
            if img.id == image_id:
                return img
        return None

    def list_images(
        self,
        scan_status: ScanStatus | None = None,
        risk_level: ImageRisk | None = None,
        limit: int = 100,
    ) -> list[ContainerImage]:
        """List images with optional filtering by scan status and risk level."""
        results = list(self._images)
        if scan_status is not None:
            results = [i for i in results if i.scan_status == scan_status]
        if risk_level is not None:
            results = [i for i in results if i.risk_level == risk_level]
        return results[-limit:]

    def record_vulnerability(
        self,
        image_id: str,
        cve_id: str,
        severity: ImageRisk = ImageRisk.LOW,
        package_name: str = "",
        installed_version: str = "",
        fixed_version: str = "",
        fix_status: VulnerabilityFixStatus = VulnerabilityFixStatus.NO_FIX,
    ) -> ImageVulnerability | None:
        """Record a vulnerability found in a container image."""
        image = self.get_image(image_id)
        if image is None:
            logger.warning(
                "container_scanner.image_not_found",
                image_id=image_id,
            )
            return None

        vuln = ImageVulnerability(
            image_id=image_id,
            cve_id=cve_id,
            severity=severity,
            package_name=package_name,
            installed_version=installed_version,
            fixed_version=fixed_version,
            fix_status=fix_status,
        )
        self._vulnerabilities.append(vuln)
        if len(self._vulnerabilities) > self._max_images * 10:
            self._vulnerabilities = self._vulnerabilities[-(self._max_images * 10) :]
        logger.info(
            "container_scanner.vulnerability_recorded",
            vuln_id=vuln.id,
            image_id=image_id,
            cve_id=cve_id,
            severity=severity,
        )
        return vuln

    def scan_image(self, image_id: str) -> ContainerImage | None:
        """Complete a scan for an image: set status to COMPLETED and calculate risk level.

        Risk is determined by the highest severity vulnerability found:
        - Any CRITICAL vuln -> CRITICAL risk
        - Any HIGH vuln -> HIGH risk
        - Any MEDIUM vuln -> MEDIUM risk
        - Any LOW vuln -> LOW risk
        - No vulns -> CLEAN
        """
        image = self.get_image(image_id)
        if image is None:
            return None

        image_vulns = [v for v in self._vulnerabilities if v.image_id == image_id]

        # Determine highest risk from vulnerabilities
        highest_risk = ImageRisk.CLEAN
        highest_idx = 0
        for vuln in image_vulns:
            try:
                vuln_idx = _RISK_ORDER.index(vuln.severity)
            except ValueError:
                vuln_idx = 0
            if vuln_idx > highest_idx:
                highest_idx = vuln_idx
                highest_risk = vuln.severity

        image.scan_status = ScanStatus.COMPLETED
        image.risk_level = highest_risk
        image.last_scanned_at = time.time()

        logger.info(
            "container_scanner.image_scanned",
            image_id=image_id,
            image_name=image.image_name,
            risk_level=highest_risk,
            vulnerability_count=len(image_vulns),
        )
        return image

    def detect_stale_images(self) -> list[ContainerImage]:
        """Detect images that have not been scanned within the stale threshold.

        Returns images whose last_scanned_at is older than stale_threshold_days
        or images that have never been scanned (last_scanned_at == 0).
        """
        now = time.time()
        threshold_seconds = self._stale_threshold_days * 86400
        stale: list[ContainerImage] = []
        for img in self._images:
            if img.last_scanned_at == 0.0 or (now - img.last_scanned_at) > threshold_seconds:
                stale.append(img)
        logger.info(
            "container_scanner.stale_images_detected",
            stale_count=len(stale),
            threshold_days=self._stale_threshold_days,
        )
        return stale

    def analyze_base_image_freshness(self) -> list[dict[str, Any]]:
        """Group images by base_image, count total and stale per base image."""
        stale_ids = {img.id for img in self.detect_stale_images()}

        base_groups: dict[str, dict[str, Any]] = {}
        for img in self._images:
            base = img.base_image if img.base_image else "unknown"
            if base not in base_groups:
                base_groups[base] = {
                    "base_image": base,
                    "total_images": 0,
                    "stale_count": 0,
                    "scanned_count": 0,
                    "avg_size_mb": 0.0,
                    "total_size_mb": 0.0,
                }
            entry = base_groups[base]
            entry["total_images"] += 1
            entry["total_size_mb"] += img.size_mb
            if img.id in stale_ids:
                entry["stale_count"] += 1
            if img.scan_status == ScanStatus.COMPLETED:
                entry["scanned_count"] += 1

        # Calculate averages and freshness score
        results: list[dict[str, Any]] = []
        for entry in base_groups.values():
            total = entry["total_images"]
            if total > 0:
                entry["avg_size_mb"] = round(entry["total_size_mb"] / total, 2)
                fresh_count = total - entry["stale_count"]
                entry["freshness_pct"] = round(fresh_count / total * 100, 1)
            else:
                entry["freshness_pct"] = 0.0
            del entry["total_size_mb"]
            results.append(entry)

        # Sort by staleness (most stale first)
        results.sort(key=lambda x: x["stale_count"], reverse=True)
        return results

    def identify_fixable_vulnerabilities(self) -> list[ImageVulnerability]:
        """Return all vulnerabilities that have a fix available."""
        fixable = [
            v for v in self._vulnerabilities if v.fix_status == VulnerabilityFixStatus.FIX_AVAILABLE
        ]
        logger.info(
            "container_scanner.fixable_vulns_identified",
            fixable_count=len(fixable),
            total_vulns=len(self._vulnerabilities),
        )
        return fixable

    def get_image_vulnerabilities(
        self, image_id: str, severity: ImageRisk | None = None
    ) -> list[ImageVulnerability]:
        """List all vulnerabilities for a specific image, optionally filtered by severity."""
        results = [v for v in self._vulnerabilities if v.image_id == image_id]
        if severity is not None:
            results = [v for v in results if v.severity == severity]
        return results

    def generate_scan_report(self) -> ScanReport:
        """Generate a comprehensive scan report across all images and vulnerabilities."""
        total_images = len(self._images)
        scanned_count = sum(1 for i in self._images if i.scan_status == ScanStatus.COMPLETED)

        # Images with at least one vulnerability
        image_ids_with_vulns = {v.image_id for v in self._vulnerabilities}
        vulnerable_count = sum(1 for i in self._images if i.id in image_ids_with_vulns)

        total_vulns = len(self._vulnerabilities)
        critical_count = sum(1 for v in self._vulnerabilities if v.severity == ImageRisk.CRITICAL)
        fixable_count = sum(
            1 for v in self._vulnerabilities if v.fix_status == VulnerabilityFixStatus.FIX_AVAILABLE
        )

        stale_images = self.detect_stale_images()
        stale_count = len(stale_images)

        # Risk distribution
        risk_dist: dict[str, int] = {}
        for img in self._images:
            key = img.risk_level.value
            risk_dist[key] = risk_dist.get(key, 0) + 1

        # Build recommendations
        recommendations: list[str] = []
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} CRITICAL vulnerabilities found — "
                f"patch these images immediately to reduce exposure"
            )

        if fixable_count > 0:
            recommendations.append(
                f"{fixable_count} vulnerabilities have fixes available — "
                f"schedule patch cycle to remediate known issues"
            )

        if stale_count > 0:
            recommendations.append(
                f"{stale_count} images not scanned within {self._stale_threshold_days} days — "
                f"re-scan to ensure current vulnerability posture"
            )

        latest_tag_count = sum(1 for i in self._images if i.tag == "latest")
        if latest_tag_count > 0:
            recommendations.append(
                f"{latest_tag_count} images use 'latest' tag — "
                f"pin to specific versions for reproducible deployments"
            )

        high_risk = risk_dist.get(ImageRisk.CRITICAL, 0) + risk_dist.get(ImageRisk.HIGH, 0)
        if high_risk > 0 and total_images > 0:
            pct = round(high_risk / total_images * 100, 1)
            recommendations.append(
                f"{pct}% of images have HIGH or CRITICAL risk — "
                f"establish a gate policy to block deployment of high-risk images"
            )

        report = ScanReport(
            total_images=total_images,
            scanned_count=scanned_count,
            vulnerable_count=vulnerable_count,
            total_vulnerabilities=total_vulns,
            critical_count=critical_count,
            fixable_count=fixable_count,
            stale_image_count=stale_count,
            risk_distribution=risk_dist,
            recommendations=recommendations,
        )
        logger.info(
            "container_scanner.report_generated",
            total_images=total_images,
            scanned_count=scanned_count,
            total_vulnerabilities=total_vulns,
            critical_count=critical_count,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored images and vulnerabilities."""
        self._images.clear()
        self._vulnerabilities.clear()
        logger.info("container_scanner.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about images and vulnerabilities."""
        scan_status_counts: dict[str, int] = {}
        risk_counts: dict[str, int] = {}
        registry_counts: dict[str, int] = {}
        for img in self._images:
            scan_status_counts[img.scan_status.value] = (
                scan_status_counts.get(img.scan_status.value, 0) + 1
            )
            risk_counts[img.risk_level.value] = risk_counts.get(img.risk_level.value, 0) + 1
            reg = img.registry if img.registry else "local"
            registry_counts[reg] = registry_counts.get(reg, 0) + 1

        severity_counts: dict[str, int] = {}
        fix_status_counts: dict[str, int] = {}
        for v in self._vulnerabilities:
            severity_counts[v.severity.value] = severity_counts.get(v.severity.value, 0) + 1
            fix_status_counts[v.fix_status.value] = fix_status_counts.get(v.fix_status.value, 0) + 1

        return {
            "total_images": len(self._images),
            "total_vulnerabilities": len(self._vulnerabilities),
            "scan_status_distribution": scan_status_counts,
            "risk_distribution": risk_counts,
            "registry_distribution": registry_counts,
            "vulnerability_severity_distribution": severity_counts,
            "fix_status_distribution": fix_status_counts,
            "max_images": self._max_images,
            "stale_threshold_days": self._stale_threshold_days,
        }
