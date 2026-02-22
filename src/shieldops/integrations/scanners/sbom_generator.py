"""SBOM (Software Bill of Materials) generation and scanning.

Generates CycloneDX/SPDX SBOMs using syft (with Trivy fallback) and
optionally feeds them into vulnerability scanners.
"""

import asyncio
import json
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SBOMFormat(StrEnum):
    """Supported SBOM output formats."""

    CYCLONEDX_JSON = "cyclonedx-json"
    CYCLONEDX_XML = "cyclonedx-xml"
    SPDX_JSON = "spdx-json"
    SPDX_TAG_VALUE = "spdx-tag-value"


class SBOMComponent(BaseModel):
    """A single component entry in an SBOM."""

    name: str
    version: str = ""
    type: str = "library"
    purl: str = ""
    ecosystem: str = ""
    licenses: list[str] = Field(default_factory=list)


class SBOMResult(BaseModel):
    """Result of an SBOM generation."""

    target: str
    format: str
    tool: str
    component_count: int = 0
    components: list[SBOMComponent] = Field(default_factory=list)
    raw_sbom: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SBOMGenerator:
    """Generates SBOMs using syft (preferred) or trivy (fallback).

    Args:
        syft_path: Path to the syft binary.
        trivy_path: Fallback path to the trivy binary.
    """

    def __init__(
        self,
        syft_path: str = "syft",
        trivy_path: str = "trivy",
    ) -> None:
        self._syft_path = syft_path
        self._trivy_path = trivy_path

    async def generate(
        self,
        target: str,
        output_format: SBOMFormat = SBOMFormat.CYCLONEDX_JSON,
    ) -> SBOMResult:
        """Generate an SBOM for the given target.

        target: container image, directory, or archive path.
        """
        logger.info("sbom_generate_start", target=target, format=output_format)

        # Try syft first
        result = await self._generate_with_syft(target, output_format)
        if not result.errors:
            return result

        # Fallback to trivy
        logger.info("sbom_syft_fallback_to_trivy", target=target)
        return await self._generate_with_trivy(target, output_format)

    async def _generate_with_syft(self, target: str, output_format: SBOMFormat) -> SBOMResult:
        format_flag = self._syft_format_flag(output_format)

        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name

            proc = await asyncio.create_subprocess_exec(
                self._syft_path,
                target,
                "-o",
                f"{format_flag}={tmp_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                return SBOMResult(
                    target=target,
                    format=output_format,
                    tool="syft",
                    errors=[f"syft failed (exit {proc.returncode}): {err}"],
                )

            raw = json.loads(Path(tmp_path).read_text())
            components = self._parse_cyclonedx(raw) if "cyclonedx" in output_format else []

            return SBOMResult(
                target=target,
                format=output_format,
                tool="syft",
                component_count=len(components),
                components=components,
                raw_sbom=raw,
            )
        except FileNotFoundError:
            return SBOMResult(
                target=target,
                format=output_format,
                tool="syft",
                errors=["syft binary not found"],
            )
        except Exception as e:
            return SBOMResult(
                target=target,
                format=output_format,
                tool="syft",
                errors=[str(e)],
            )

    async def _generate_with_trivy(self, target: str, output_format: SBOMFormat) -> SBOMResult:
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name

            trivy_format = "cyclonedx" if "cyclonedx" in output_format else "spdx-json"

            proc = await asyncio.create_subprocess_exec(
                self._trivy_path,
                "image" if ":" in target else "fs",
                target,
                "--format",
                trivy_format,
                "--output",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                return SBOMResult(
                    target=target,
                    format=output_format,
                    tool="trivy",
                    errors=[f"trivy failed (exit {proc.returncode}): {err}"],
                )

            raw = json.loads(Path(tmp_path).read_text())
            components = self._parse_cyclonedx(raw) if "cyclonedx" in trivy_format else []

            return SBOMResult(
                target=target,
                format=output_format,
                tool="trivy",
                component_count=len(components),
                components=components,
                raw_sbom=raw,
            )
        except FileNotFoundError:
            return SBOMResult(
                target=target,
                format=output_format,
                tool="trivy",
                errors=["trivy binary not found"],
            )
        except Exception as e:
            return SBOMResult(
                target=target,
                format=output_format,
                tool="trivy",
                errors=[str(e)],
            )

    async def generate_and_scan(
        self,
        target: str,
        cve_sources: list[Any] | None = None,
        severity_threshold: str = "medium",
    ) -> dict[str, Any]:
        """Generate SBOM then scan all components for vulnerabilities."""
        sbom = await self.generate(target)

        if sbom.errors:
            return {
                "sbom": sbom.model_dump(),
                "vulnerabilities": [],
                "errors": sbom.errors,
            }

        vulnerabilities: list[dict[str, Any]] = []
        if cve_sources:
            for component in sbom.components:
                for source in cve_sources:
                    try:
                        findings = await source.scan(component.name, severity_threshold)
                        for f in findings:
                            f["sbom_component"] = component.name
                            f["sbom_version"] = component.version
                        vulnerabilities.extend(findings)
                    except Exception as e:
                        logger.warning(
                            "sbom_scan_component_failed",
                            component=component.name,
                            error=str(e),
                        )

        return {
            "sbom": sbom.model_dump(),
            "vulnerabilities": vulnerabilities,
            "total_vulnerabilities": len(vulnerabilities),
        }

    def _parse_cyclonedx(self, raw: dict[str, Any]) -> list[SBOMComponent]:
        components: list[SBOMComponent] = []
        for comp in raw.get("components", []):
            licenses: list[str] = []
            for lic in comp.get("licenses", []):
                if isinstance(lic, dict):
                    license_obj = lic.get("license", {})
                    if isinstance(license_obj, dict):
                        license_id = str(license_obj.get("id") or license_obj.get("name") or "")
                        licenses.append(license_id)
                    elif isinstance(license_obj, str):
                        licenses.append(license_obj)

            components.append(
                SBOMComponent(
                    name=comp.get("name", ""),
                    version=comp.get("version", ""),
                    type=comp.get("type", "library"),
                    purl=comp.get("purl", ""),
                    licenses=licenses,
                )
            )
        return components

    @staticmethod
    def _syft_format_flag(fmt: SBOMFormat) -> str:
        return {
            SBOMFormat.CYCLONEDX_JSON: "cyclonedx-json",
            SBOMFormat.CYCLONEDX_XML: "cyclonedx-xml",
            SBOMFormat.SPDX_JSON: "spdx-json",
            SBOMFormat.SPDX_TAG_VALUE: "spdx-tag-value",
        }.get(fmt, "cyclonedx-json")

    @staticmethod
    def supported_formats() -> list[str]:
        return [f.value for f in SBOMFormat]
