"""Tests for shieldops.vulnerability.dependency_mapper -- DependencyVulnerabilityMapper."""

from __future__ import annotations

import pytest

from shieldops.vulnerability.dependency_mapper import (
    DependencyDepth,
    DependencyNode,
    DependencyVulnerabilityMapper,
    ImpactAssessment,
    ImpactLevel,
    VulnerabilityMapping,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mapper(**kwargs) -> DependencyVulnerabilityMapper:
    return DependencyVulnerabilityMapper(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_impact_level_none(self):
        assert ImpactLevel.NONE == "none"

    def test_impact_level_low(self):
        assert ImpactLevel.LOW == "low"

    def test_impact_level_medium(self):
        assert ImpactLevel.MEDIUM == "medium"

    def test_impact_level_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_impact_level_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    def test_dependency_depth_direct(self):
        assert DependencyDepth.DIRECT == "direct"

    def test_dependency_depth_transitive(self):
        assert DependencyDepth.TRANSITIVE == "transitive"

    def test_dependency_depth_runtime_only(self):
        assert DependencyDepth.RUNTIME_ONLY == "runtime_only"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_node_defaults(self):
        n = DependencyNode(service="api", package_name="requests")
        assert n.id
        assert n.service == "api"
        assert n.package_name == "requests"
        assert n.version == ""
        assert n.depth == DependencyDepth.DIRECT
        assert n.parent_id == ""
        assert n.metadata == {}

    def test_vulnerability_mapping_defaults(self):
        m = VulnerabilityMapping(cve_id="CVE-2024-001", package_name="openssl")
        assert m.id
        assert m.cve_id == "CVE-2024-001"
        assert m.package_name == "openssl"
        assert m.affected_versions == []
        assert m.impact_level == ImpactLevel.MEDIUM
        assert m.description == ""

    def test_impact_assessment_defaults(self):
        a = ImpactAssessment(cve_id="CVE-2024-001", impact_level=ImpactLevel.HIGH)
        assert a.id
        assert a.cve_id == "CVE-2024-001"
        assert a.affected_services == []
        assert a.impact_level == ImpactLevel.HIGH
        assert a.total_affected == 0
        assert a.transitive_affected == 0
        assert a.recommendation == ""


# ---------------------------------------------------------------------------
# Register service dependencies
# ---------------------------------------------------------------------------


class TestRegisterServiceDependencies:
    def test_register_basic(self):
        m = _mapper()
        nodes = m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests", "version": "2.31.0"}],
        )
        assert len(nodes) == 1
        assert nodes[0].service == "api"
        assert nodes[0].package_name == "requests"
        assert nodes[0].version == "2.31.0"

    def test_register_multiple_deps(self):
        m = _mapper()
        nodes = m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "requests", "version": "2.31.0"},
                {"package_name": "flask", "version": "3.0.0"},
                {"package_name": "pydantic", "version": "2.5.0"},
            ],
        )
        assert len(nodes) == 3
        packages = {n.package_name for n in nodes}
        assert packages == {"requests", "flask", "pydantic"}

    def test_register_max_services_limit(self):
        m = _mapper(max_services=2)
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        m.register_service_dependencies(
            service="web",
            dependencies=[{"package_name": "flask"}],
        )
        with pytest.raises(ValueError, match="Maximum services"):
            m.register_service_dependencies(
                service="worker",
                dependencies=[{"package_name": "celery"}],
            )

    def test_register_same_service_does_not_hit_limit(self):
        m = _mapper(max_services=1)
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        nodes = m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "flask"}],
        )
        assert len(nodes) == 1

    def test_register_with_depth(self):
        m = _mapper()
        nodes = m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "urllib3", "depth": "transitive"},
            ],
        )
        assert nodes[0].depth == DependencyDepth.TRANSITIVE

    def test_register_with_parent_id(self):
        m = _mapper()
        parents = m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        children = m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "urllib3", "parent_id": parents[0].id, "depth": "transitive"},
            ],
        )
        assert children[0].parent_id == parents[0].id


# ---------------------------------------------------------------------------
# Map CVE impact
# ---------------------------------------------------------------------------


class TestMapCveImpact:
    def test_map_basic(self):
        m = _mapper()
        mapping = m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1", "1.1.2"],
        )
        assert mapping.cve_id == "CVE-2024-001"
        assert mapping.package_name == "openssl"
        assert mapping.affected_versions == ["1.1.1", "1.1.2"]
        assert mapping.impact_level == ImpactLevel.MEDIUM

    def test_map_with_all_fields(self):
        m = _mapper()
        mapping = m.map_cve_impact(
            cve_id="CVE-2024-999",
            package_name="log4j",
            affected_versions=["2.0", "2.14"],
            impact_level=ImpactLevel.CRITICAL,
            description="Remote code execution vulnerability",
        )
        assert mapping.impact_level == ImpactLevel.CRITICAL
        assert mapping.description == "Remote code execution vulnerability"
        assert mapping.id

    def test_map_multiple_cves_same_package(self):
        m = _mapper()
        m1 = m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        m2 = m.map_cve_impact(
            cve_id="CVE-2024-002",
            package_name="openssl",
            affected_versions=["1.1.2"],
        )
        assert m1.id != m2.id
        assert len(m.list_mappings()) == 2


# ---------------------------------------------------------------------------
# Get affected services
# ---------------------------------------------------------------------------


class TestGetAffectedServices:
    def test_finds_services_with_vulnerable_package(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "openssl", "version": "1.1.1"}],
        )
        m.register_service_dependencies(
            service="web",
            dependencies=[{"package_name": "openssl", "version": "1.1.2"}],
        )
        m.register_service_dependencies(
            service="worker",
            dependencies=[{"package_name": "requests"}],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1", "1.1.2"],
        )
        services = m.get_affected_services("CVE-2024-001")
        assert services == ["api", "web"]

    def test_empty_when_no_match(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        assert m.get_affected_services("CVE-2024-001") == []

    def test_empty_when_no_cve_mapping(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "openssl"}],
        )
        assert m.get_affected_services("CVE-NONEXISTENT") == []

    def test_sorted_alphabetically(self):
        m = _mapper()
        m.register_service_dependencies(
            service="zebra",
            dependencies=[{"package_name": "openssl"}],
        )
        m.register_service_dependencies(
            service="alpha",
            dependencies=[{"package_name": "openssl"}],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.0"],
        )
        services = m.get_affected_services("CVE-2024-001")
        assert services == ["alpha", "zebra"]


# ---------------------------------------------------------------------------
# Get service vulnerabilities
# ---------------------------------------------------------------------------


class TestGetServiceVulnerabilities:
    def test_finds_vulns_for_service_packages(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "openssl"},
                {"package_name": "requests"},
            ],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-002",
            package_name="requests",
            affected_versions=["2.30"],
        )
        vulns = m.get_service_vulnerabilities("api")
        assert len(vulns) == 2

    def test_empty_when_no_match(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        vulns = m.get_service_vulnerabilities("api")
        assert vulns == []

    def test_empty_when_service_not_registered(self):
        m = _mapper()
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        assert m.get_service_vulnerabilities("nonexistent") == []


# ---------------------------------------------------------------------------
# Build dependency tree
# ---------------------------------------------------------------------------


class TestBuildDependencyTree:
    def test_basic_tree(self):
        m = _mapper()
        parents = m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests", "version": "2.31.0"}],
        )
        m.register_service_dependencies(
            service="api",
            dependencies=[
                {
                    "package_name": "urllib3",
                    "version": "2.0.0",
                    "parent_id": parents[0].id,
                    "depth": "transitive",
                },
            ],
        )
        tree = m.build_dependency_tree("api")
        assert tree["service"] == "api"
        assert tree["total_dependencies"] == 2
        assert len(tree["dependencies"]) == 1
        root = tree["dependencies"][0]
        assert root["package_name"] == "requests"
        assert len(root["children"]) == 1
        assert root["children"][0]["package_name"] == "urllib3"

    def test_empty_tree(self):
        m = _mapper()
        tree = m.build_dependency_tree("api")
        assert tree["service"] == "api"
        assert tree["total_dependencies"] == 0
        assert tree["dependencies"] == []

    def test_tree_multiple_roots(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "requests"},
                {"package_name": "flask"},
            ],
        )
        tree = m.build_dependency_tree("api")
        assert tree["total_dependencies"] == 2
        assert len(tree["dependencies"]) == 2

    def test_tree_only_includes_target_service(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[{"package_name": "requests"}],
        )
        m.register_service_dependencies(
            service="web",
            dependencies=[{"package_name": "flask"}],
        )
        tree = m.build_dependency_tree("api")
        assert tree["total_dependencies"] == 1
        assert tree["dependencies"][0]["package_name"] == "requests"


# ---------------------------------------------------------------------------
# List mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_empty(self):
        m = _mapper()
        assert m.list_mappings() == []

    def test_list_with_data(self):
        m = _mapper()
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-002",
            package_name="requests",
            affected_versions=["2.30"],
        )
        assert len(m.list_mappings()) == 2


# ---------------------------------------------------------------------------
# Get assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    def test_get_found(self):
        m = _mapper()
        assessment = ImpactAssessment(
            cve_id="CVE-2024-001",
            impact_level=ImpactLevel.HIGH,
            affected_services=["api"],
            total_affected=1,
        )
        m._assessments[assessment.id] = assessment
        result = m.get_assessment(assessment.id)
        assert result is not None
        assert result.cve_id == "CVE-2024-001"

    def test_get_not_found(self):
        m = _mapper()
        assert m.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        m = _mapper()
        s = m.get_stats()
        assert s["total_nodes"] == 0
        assert s["total_mappings"] == 0
        assert s["total_assessments"] == 0
        assert s["unique_services"] == 0
        assert s["unique_packages"] == 0
        assert s["unique_cves"] == 0
        assert s["direct_dependencies"] == 0
        assert s["transitive_dependencies"] == 0

    def test_stats_with_data(self):
        m = _mapper()
        m.register_service_dependencies(
            service="api",
            dependencies=[
                {"package_name": "requests", "version": "2.31.0"},
                {"package_name": "urllib3", "version": "2.0.0", "depth": "transitive"},
            ],
        )
        m.register_service_dependencies(
            service="web",
            dependencies=[
                {"package_name": "flask", "version": "3.0.0"},
            ],
        )
        m.map_cve_impact(
            cve_id="CVE-2024-001",
            package_name="openssl",
            affected_versions=["1.1.1"],
        )
        s = m.get_stats()
        assert s["total_nodes"] == 3
        assert s["total_mappings"] == 1
        assert s["unique_services"] == 2
        assert s["unique_packages"] == 3
        assert s["unique_cves"] == 1
        assert s["direct_dependencies"] == 2
        assert s["transitive_dependencies"] == 1

    def test_stats_assessments_count(self):
        m = _mapper()
        a = ImpactAssessment(cve_id="CVE-2024-001", impact_level=ImpactLevel.HIGH)
        m._assessments[a.id] = a
        s = m.get_stats()
        assert s["total_assessments"] == 1
