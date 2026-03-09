"""DevSecOps Pipeline Gate — security gates for CI/CD pipelines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GateDecision(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class ScanType(StrEnum):
    SAST = "sast"
    DAST = "dast"
    SCA = "sca"
    CONTAINER = "container"
    SECRET = "secret"  # noqa: S105
    LICENSE = "license"


class ArtifactType(StrEnum):
    DOCKER_IMAGE = "docker_image"
    JAR = "jar"
    NPM_PACKAGE = "npm_package"
    PYTHON_WHEEL = "python_wheel"
    BINARY = "binary"


class VulnSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class ScanResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    artifact_type: ArtifactType = ArtifactType.DOCKER_IMAGE
    scan_type: ScanType = ScanType.SCA
    decision: GateDecision = GateDecision.PASS
    vuln_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SBOMEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    package_name: str = ""
    version: str = ""
    license: str = ""
    vulnerability_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class PipelineSecurityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_scans: int = 0
    total_sbom_entries: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    by_scan_type: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_artifact_type: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DevSecOpsPipelineGate:
    """Security gates for CI/CD pipelines."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
        max_critical: int = 0,
        max_high: int = 5,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._max_critical = max_critical
        self._max_high = max_high
        self._scans: list[ScanResult] = []
        self._sbom: list[SBOMEntry] = []
        logger.info(
            "devsecops_pipeline_gate.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    def scan_artifact(
        self,
        artifact_name: str,
        artifact_type: ArtifactType = ArtifactType.DOCKER_IMAGE,
        scan_type: ScanType = ScanType.SCA,
        vuln_count: int = 0,
        critical_count: int = 0,
        high_count: int = 0,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ScanResult:
        """Scan an artifact and record results."""
        decision = self._make_decision(critical_count, high_count, score)
        result = ScanResult(
            artifact_name=artifact_name,
            artifact_type=artifact_type,
            scan_type=scan_type,
            decision=decision,
            vuln_count=vuln_count,
            critical_count=critical_count,
            high_count=high_count,
            score=score,
            service=service,
            team=team,
        )
        self._scans.append(result)
        if len(self._scans) > self._max_records:
            self._scans = self._scans[-self._max_records :]
        logger.info(
            "devsecops_pipeline_gate.artifact_scanned",
            scan_id=result.id,
            artifact=artifact_name,
            decision=decision.value,
        )
        return result

    def _make_decision(
        self,
        critical_count: int,
        high_count: int,
        score: float,
    ) -> GateDecision:
        if critical_count > self._max_critical:
            return GateDecision.FAIL
        if high_count > self._max_high:
            return GateDecision.WARN
        if score < self._score_threshold:
            return GateDecision.WARN
        return GateDecision.PASS

    def evaluate_gate(self, scan_id: str) -> dict[str, Any]:
        """Evaluate gate decision for a scan result."""
        for s in self._scans:
            if s.id == scan_id:
                return {
                    "scan_id": scan_id,
                    "decision": s.decision.value,
                    "artifact": s.artifact_name,
                    "critical": s.critical_count,
                    "high": s.high_count,
                    "score": s.score,
                }
        return {"scan_id": scan_id, "error": "not_found"}

    def enforce_policy(
        self,
        artifact_name: str,
        max_critical: int | None = None,
        max_high: int | None = None,
    ) -> dict[str, Any]:
        """Enforce security policy on all scans for an artifact."""
        mc = max_critical if max_critical is not None else self._max_critical
        mh = max_high if max_high is not None else self._max_high
        scans = [s for s in self._scans if s.artifact_name == artifact_name]
        blocked = []
        for s in scans:
            if s.critical_count > mc or s.high_count > mh:
                s.decision = GateDecision.FAIL
                blocked.append(s.id)
        return {
            "artifact": artifact_name,
            "scans_evaluated": len(scans),
            "blocked": len(blocked),
            "blocked_ids": blocked,
        }

    def generate_sbom(
        self,
        artifact_name: str,
        package_name: str,
        version: str = "",
        license_name: str = "",
        vulnerability_ids: list[str] | None = None,
    ) -> SBOMEntry:
        """Generate an SBOM entry for an artifact."""
        entry = SBOMEntry(
            artifact_name=artifact_name,
            package_name=package_name,
            version=version,
            license=license_name,
            vulnerability_ids=vulnerability_ids or [],
        )
        self._sbom.append(entry)
        if len(self._sbom) > self._max_records:
            self._sbom = self._sbom[-self._max_records :]
        logger.info(
            "devsecops_pipeline_gate.sbom_generated",
            entry_id=entry.id,
            artifact=artifact_name,
            package=package_name,
        )
        return entry

    def get_pipeline_security_score(self) -> dict[str, Any]:
        """Compute overall pipeline security score."""
        if not self._scans:
            return {"total": 0, "avg_score": 0.0, "pass_rate": 0.0}
        scores = [s.score for s in self._scans]
        avg = round(sum(scores) / len(scores), 2)
        passed = sum(1 for s in self._scans if s.decision == GateDecision.PASS)
        rate = round(passed / len(self._scans) * 100, 2)
        return {
            "total": len(self._scans),
            "avg_score": avg,
            "pass_rate": rate,
            "total_vulns": sum(s.vuln_count for s in self._scans),
            "total_critical": sum(s.critical_count for s in self._scans),
        }

    def generate_report(self) -> PipelineSecurityReport:
        """Generate a comprehensive pipeline security report."""
        by_scan: dict[str, int] = {}
        by_dec: dict[str, int] = {}
        by_art: dict[str, int] = {}
        for s in self._scans:
            by_scan[s.scan_type.value] = by_scan.get(s.scan_type.value, 0) + 1
            by_dec[s.decision.value] = by_dec.get(s.decision.value, 0) + 1
            by_art[s.artifact_type.value] = by_art.get(s.artifact_type.value, 0) + 1
        scores = [s.score for s in self._scans]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        passed = sum(1 for s in self._scans if s.decision == GateDecision.PASS)
        rate = round(passed / len(self._scans) * 100, 2) if self._scans else 0.0
        issues = [s.artifact_name for s in self._scans if s.decision == GateDecision.FAIL][:5]
        recs: list[str] = []
        if issues:
            recs.append(f"{len(issues)} artifact(s) failed security gate")
        if avg < self._score_threshold:
            recs.append(f"Avg score {avg} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Pipeline security within healthy range")
        return PipelineSecurityReport(
            total_scans=len(self._scans),
            total_sbom_entries=len(self._sbom),
            pass_rate=rate,
            avg_score=avg,
            by_scan_type=by_scan,
            by_decision=by_dec,
            by_artifact_type=by_art,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for s in self._scans:
            key = s.scan_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_scans": len(self._scans),
            "total_sbom_entries": len(self._sbom),
            "score_threshold": self._score_threshold,
            "scan_type_distribution": dist,
            "unique_teams": len({s.team for s in self._scans}),
            "unique_services": len({s.service for s in self._scans}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._scans.clear()
        self._sbom.clear()
        logger.info("devsecops_pipeline_gate.cleared")
        return {"status": "cleared"}
