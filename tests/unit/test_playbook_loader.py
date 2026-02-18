"""Unit tests for the Playbook Loader."""

from pathlib import Path

import pytest

from shieldops.playbooks.loader import Playbook, PlaybookLoader, PlaybookTrigger


PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "playbooks"


class TestPlaybookLoader:
    """Tests for PlaybookLoader loading and matching."""

    def test_load_all_from_project(self):
        """Load all playbooks from the project's playbooks/ directory."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()
        playbooks = loader.all()
        assert len(playbooks) >= 10, f"Expected >= 10 playbooks, got {len(playbooks)}"

    def test_load_specific_playbooks(self):
        """Verify key playbooks are loaded."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        expected_names = [
            "pod-crash-loop",
            "high-latency",
            "oom-kill",
            "disk-pressure",
            "deployment-failed",
            "service-unavailable",
            "cpu-throttling",
            "pending-pods",
            "certificate-expiry",
            "database-connections",
        ]
        loaded_names = [pb.name for pb in loader.all()]
        for name in expected_names:
            assert name in loaded_names, f"Playbook '{name}' not loaded"

    def test_match_by_alert_type(self):
        """Test matching a playbook by alert type."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        pb = loader.match("KubePodCrashLooping")
        assert pb is not None
        assert pb.name == "pod-crash-loop"

    def test_match_with_severity_filter(self):
        """Test that severity filtering works."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        pb = loader.match("KubePodCrashLooping", severity="critical")
        assert pb is not None

        pb = loader.match("KubePodCrashLooping", severity="info")
        assert pb is None  # info not in severity list

    def test_match_no_match(self):
        """Test that unknown alert type returns None."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        pb = loader.match("NonExistentAlert")
        assert pb is None

    def test_get_by_name(self):
        """Test fetching a playbook by name."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        pb = loader.get("oom-kill")
        assert pb is not None
        assert pb.trigger.alert_type == "ContainerOOMKilled"

    def test_get_nonexistent(self):
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()
        assert loader.get("nonexistent") is None

    def test_decision_tree_parsed(self):
        """Test that decision tree conditions are properly parsed."""
        loader = PlaybookLoader(playbooks_dir=PLAYBOOKS_DIR)
        loader.load_all()

        pb = loader.get("pod-crash-loop")
        assert pb is not None
        tree = pb.decision_tree
        assert len(tree) >= 3
        assert tree[0].action == "increase_memory_limit"
        assert tree[0].risk_level == "medium"

    def test_load_nonexistent_dir(self):
        """Test loading from a directory that doesn't exist."""
        loader = PlaybookLoader(playbooks_dir=Path("/nonexistent/dir"))
        loader.load_all()
        assert len(loader.all()) == 0

    def test_playbook_model(self):
        """Test Playbook model instantiation."""
        pb = Playbook(
            name="test-playbook",
            version="1.0",
            description="Test",
            trigger=PlaybookTrigger(alert_type="TestAlert", severity=["critical"]),
            remediation={
                "decision_tree": [
                    {"condition": "default", "action": "restart", "risk_level": "low"}
                ]
            },
        )
        assert pb.name == "test-playbook"
        assert len(pb.decision_tree) == 1
        assert pb.decision_tree[0].action == "restart"
