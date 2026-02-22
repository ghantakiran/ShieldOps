"""Tests for the TemplateLoader class.

Tests cover:
- load_all finds all YAML files
- get_template by ID
- get_template returns None for invalid ID
- search by category
- search by cloud provider
- search by tags
- search by free-text query
- search with no results
- deploy creates correct config
- deploy with missing required params raises ValueError
- deploy with unknown template raises ValueError
- featured returns only featured templates
- categories returns correct counts
- _make_id generates stable IDs
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shieldops.playbooks.template_loader import (
    AgentTemplate,
    TemplateLoader,
    TemplateParameter,
    TemplateStep,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "playbooks" / "templates"


@pytest.fixture
def loader() -> TemplateLoader:
    """Create and load a TemplateLoader from the real templates directory."""
    tl = TemplateLoader(templates_dir=TEMPLATES_DIR)
    tl.load_all()
    return tl


@pytest.fixture
def empty_loader(tmp_path: Path) -> TemplateLoader:
    """Create a TemplateLoader pointed at an empty directory."""
    tl = TemplateLoader(templates_dir=tmp_path)
    tl.load_all()
    return tl


# =================================================================
# 1. load_all finds all YAML files
# =================================================================


class TestLoadAll:
    def test_load_all_finds_8_templates(self, loader: TemplateLoader) -> None:
        templates = loader.all_templates()
        assert len(templates) == 8

    def test_load_all_empty_dir(self, empty_loader: TemplateLoader) -> None:
        templates = empty_loader.all_templates()
        assert len(templates) == 0

    def test_load_all_assigns_ids(self, loader: TemplateLoader) -> None:
        for t in loader.all_templates():
            assert t.id.startswith("tmpl-")

    def test_load_all_nonexistent_dir(self, tmp_path: Path) -> None:
        tl = TemplateLoader(templates_dir=tmp_path / "does_not_exist")
        tl.load_all()
        assert len(tl.all_templates()) == 0


# =================================================================
# 2. get_template
# =================================================================


class TestGetTemplate:
    def test_get_template_by_id(self, loader: TemplateLoader) -> None:
        t = loader.get_template("tmpl-aws-ec2-autoscale")
        assert t is not None
        assert t.name == "AWS EC2 Auto-Scale"

    def test_get_template_invalid_id(self, loader: TemplateLoader) -> None:
        t = loader.get_template("tmpl-nonexistent")
        assert t is None

    def test_get_all_templates_by_id(self, loader: TemplateLoader) -> None:
        expected_ids = [
            "tmpl-aws-ec2-autoscale",
            "tmpl-cert-rotation",
            "tmpl-cost-rightsize",
            "tmpl-db-connection-pool",
            "tmpl-disk-space-cleanup",
            "tmpl-incident-response",
            "tmpl-k8s-pod-restart",
            "tmpl-security-patch",
        ]
        for tid in expected_ids:
            t = loader.get_template(tid)
            assert t is not None, f"Template {tid} not found"


# =================================================================
# 3. search by category
# =================================================================


class TestSearchByCategory:
    def test_search_remediation(self, loader: TemplateLoader) -> None:
        results = loader.search(category="remediation")
        assert len(results) > 0
        for t in results:
            assert t.category == "remediation"

    def test_search_security(self, loader: TemplateLoader) -> None:
        results = loader.search(category="security")
        assert len(results) > 0
        for t in results:
            assert t.category == "security"

    def test_search_cost(self, loader: TemplateLoader) -> None:
        results = loader.search(category="cost")
        assert len(results) >= 1

    def test_search_nonexistent_category(self, loader: TemplateLoader) -> None:
        results = loader.search(category="nonexistent")
        assert len(results) == 0


# =================================================================
# 4. search by cloud provider
# =================================================================


class TestSearchByCloud:
    def test_search_aws(self, loader: TemplateLoader) -> None:
        results = loader.search(cloud="aws")
        assert len(results) > 0
        for t in results:
            assert "aws" in t.cloud_providers

    def test_search_kubernetes(self, loader: TemplateLoader) -> None:
        results = loader.search(cloud="kubernetes")
        assert len(results) > 0
        for t in results:
            assert "kubernetes" in t.cloud_providers


# =================================================================
# 5. search by tags
# =================================================================


class TestSearchByTags:
    def test_search_single_tag(self, loader: TemplateLoader) -> None:
        results = loader.search(tags=["auto-scaling"])
        assert len(results) >= 1
        for t in results:
            assert "auto-scaling" in t.tags

    def test_search_multiple_tags(self, loader: TemplateLoader) -> None:
        results = loader.search(tags=["security", "cve"])
        assert len(results) >= 1
        for t in results:
            assert "security" in t.tags or "cve" in t.tags


# =================================================================
# 6. search by free-text query
# =================================================================


class TestSearchByQuery:
    def test_search_by_name_fragment(self, loader: TemplateLoader) -> None:
        results = loader.search(query="certificate")
        assert len(results) >= 1

    def test_search_by_description_fragment(self, loader: TemplateLoader) -> None:
        results = loader.search(query="over-provisioned")
        assert len(results) >= 1

    def test_search_no_match(self, loader: TemplateLoader) -> None:
        results = loader.search(query="zzznotfound")
        assert len(results) == 0

    def test_search_case_insensitive(self, loader: TemplateLoader) -> None:
        upper = loader.search(query="KUBERNETES")
        lower = loader.search(query="kubernetes")
        assert len(upper) == len(lower)


# =================================================================
# 7. deploy
# =================================================================


class TestDeploy:
    def test_deploy_creates_correct_config(self, loader: TemplateLoader) -> None:
        result = loader.deploy(
            template_id="tmpl-k8s-pod-restart",
            org_id="org-test",
            environment="staging",
            params={
                "namespace": "production",
                "pod_selector": "app=web",
            },
        )
        assert result["template_id"] == "tmpl-k8s-pod-restart"
        assert result["template_name"] == "Kubernetes Pod Restart"
        assert result["org_id"] == "org-test"
        assert result["environment"] == "staging"
        assert result["status"] == "deployed"
        assert result["deployment_id"].startswith("deploy-")
        assert result["parameters"]["namespace"] == "production"
        assert result["parameters"]["pod_selector"] == "app=web"
        assert len(result["steps"]) > 0

    def test_deploy_fills_defaults(self, loader: TemplateLoader) -> None:
        result = loader.deploy(
            template_id="tmpl-disk-space-cleanup",
            org_id="org-test",
            environment="production",
            params={"target_host": "web-01"},
        )
        # disk_threshold_percent has default 85
        assert result["parameters"]["disk_threshold_percent"] == 85
        # target_host was explicitly provided
        assert result["parameters"]["target_host"] == "web-01"

    def test_deploy_unknown_template_raises(self, loader: TemplateLoader) -> None:
        with pytest.raises(ValueError, match="not found"):
            loader.deploy(
                template_id="tmpl-nonexistent",
                org_id="org-test",
                environment="production",
            )

    def test_deploy_missing_required_param_raises(self, loader: TemplateLoader) -> None:
        with pytest.raises(ValueError, match="Required parameter"):
            loader.deploy(
                template_id="tmpl-aws-ec2-autoscale",
                org_id="org-test",
                environment="production",
                params={},  # Missing required asg_name and region
            )


# =================================================================
# 8. featured
# =================================================================


class TestFeatured:
    def test_featured_returns_only_featured(self, loader: TemplateLoader) -> None:
        featured = loader.featured()
        assert len(featured) > 0
        for t in featured:
            assert t.featured is True

    def test_featured_count_matches_yaml(self, loader: TemplateLoader) -> None:
        all_featured = [t for t in loader.all_templates() if t.featured]
        assert len(loader.featured()) == len(all_featured)


# =================================================================
# 9. categories
# =================================================================


class TestCategories:
    def test_categories_returns_counts(self, loader: TemplateLoader) -> None:
        cats = loader.categories()
        assert "remediation" in cats
        assert "security" in cats
        total = sum(cats.values())
        assert total == 8

    def test_category_counts_are_positive(self, loader: TemplateLoader) -> None:
        for cat, count in loader.categories().items():
            assert count > 0, f"Category {cat} has zero count"


# =================================================================
# 10. _make_id
# =================================================================


class TestMakeId:
    def test_make_id_format(self) -> None:
        assert TemplateLoader._make_id("aws-ec2-autoscale") == "tmpl-aws-ec2-autoscale"

    def test_make_id_stable(self) -> None:
        a = TemplateLoader._make_id("test-template")
        b = TemplateLoader._make_id("test-template")
        assert a == b


# =================================================================
# 11. Pydantic models
# =================================================================


class TestPydanticModels:
    def test_agent_template_model(self) -> None:
        t = AgentTemplate(
            id="tmpl-test",
            name="Test Template",
            category="remediation",
            agent_type="remediation",
            risk_level="low",
        )
        assert t.id == "tmpl-test"
        assert t.parameters == []
        assert t.steps == []

    def test_template_parameter_model(self) -> None:
        p = TemplateParameter(
            name="test_param",
            type="string",
            required=True,
            description="A test parameter",
        )
        assert p.name == "test_param"
        assert p.default is None

    def test_template_step_model(self) -> None:
        s = TemplateStep(
            name="test_step",
            action="test_action",
            config={"key": "value"},
        )
        assert s.name == "test_step"
        assert s.config["key"] == "value"
