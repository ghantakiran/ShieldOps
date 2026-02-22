"""Tests for git-backed playbook synchronization."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shieldops.playbooks.git_sync import (
    GitPlaybookSync,
    GitSyncError,
)


class TestGitPlaybookSync:
    def test_init_defaults(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        assert sync.repo_url == "https://github.com/test/repo.git"
        assert sync.branch == "main"
        assert not sync.is_cloned
        assert sync.last_sync is None

    def test_init_custom_params(self) -> None:
        sync = GitPlaybookSync(
            repo_url="https://github.com/test/repo.git",
            branch="develop",
            playbook_dir="runbooks",
        )
        assert sync.branch == "develop"

    @pytest.mark.asyncio
    async def test_clone_no_url_raises(self) -> None:
        sync = GitPlaybookSync(repo_url="")
        with pytest.raises(GitSyncError, match="No repository URL"):
            await sync.clone()

    @pytest.mark.asyncio
    async def test_clone_success(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")

        async def mock_run_git(*args, cwd=None):
            if args[0] == "clone":
                # Create the dir to simulate clone
                os.makedirs(sync.local_path, exist_ok=True)
                return (0, "", "")
            elif args[0] == "rev-parse":
                return (0, "abc123def456\n", "")
            return (0, "", "")

        sync._run_git = mock_run_git
        result = await sync.clone()

        assert result["action"] == "clone"
        assert sync.is_cloned
        assert sync.last_commit == "abc123def456"

    @pytest.mark.asyncio
    async def test_clone_failure(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/bad-repo.git")

        async def mock_run_git(*args, cwd=None):
            return (128, "", "fatal: repo not found")

        sync._run_git = mock_run_git
        with pytest.raises(GitSyncError, match="Clone failed"):
            await sync.clone()

    @pytest.mark.asyncio
    async def test_pull_clones_if_not_cloned(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")

        clone_called = False

        async def mock_run_git(*args, cwd=None):
            nonlocal clone_called
            if args[0] == "clone":
                clone_called = True
                os.makedirs(sync.local_path, exist_ok=True)
                return (0, "", "")
            elif args[0] == "rev-parse":
                return (0, "abc123\n", "")
            return (0, "", "")

        sync._run_git = mock_run_git
        await sync.pull()
        assert clone_called

    @pytest.mark.asyncio
    async def test_pull_success(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True
        sync._last_commit = "old123"

        call_count = 0

        async def mock_run_git(*args, cwd=None):
            nonlocal call_count
            call_count += 1
            if args[0] == "pull":
                return (0, "Updating old123..new456\n", "")
            elif args[0] == "rev-parse":
                return (0, "new456\n", "")
            elif args[0] == "diff":
                return (0, "file1.yaml\nfile2.yaml\n", "")
            return (0, "", "")

        sync._run_git = mock_run_git
        result = await sync.pull()

        assert result["action"] == "pull"
        assert result["commit"] == "new456"
        assert result["files_changed"] == 2
        assert sync.last_commit == "new456"

    @pytest.mark.asyncio
    async def test_diff_preview_not_cloned(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        changes = await sync.diff_preview()
        assert changes == []

    @pytest.mark.asyncio
    async def test_diff_preview_with_changes(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True

        async def mock_run_git(*args, cwd=None):
            if args[0] == "fetch":
                return (0, "", "")
            elif args[0] == "diff" and "--stat" in args:
                return (0, "2 files changed\n", "")
            elif args[0] == "diff" and "--name-status" in args:
                return (0, "M\tplaybooks/pod-crash.yaml\nA\tplaybooks/new-alert.yaml\n", "")
            return (0, "", "")

        sync._run_git = mock_run_git
        changes = await sync.diff_preview()
        assert len(changes) == 2
        assert changes[0]["status"] == "modified"
        assert changes[1]["status"] == "added"

    @pytest.mark.asyncio
    async def test_version_history(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True

        async def mock_run_git(*args, cwd=None):
            return (
                0,
                "abc123|John Doe|john@test.com|2026-01-01 10:00:00 +0000|Update playbook\n"
                "def456|Jane Smith|jane@test.com|2026-01-02 11:00:00 +0000|Add new playbook\n",
                "",
            )

        sync._run_git = mock_run_git
        history = await sync.get_version_history()
        assert len(history) == 2
        assert history[0]["author_name"] == "John Doe"
        assert history[1]["message"] == "Add new playbook"

    @pytest.mark.asyncio
    async def test_rollback_not_cloned(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        with pytest.raises(GitSyncError, match="not cloned"):
            await sync.rollback("abc123")

    @pytest.mark.asyncio
    async def test_rollback_success(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True
        sync._last_commit = "current123"

        async def mock_run_git(*args, cwd=None):
            return (0, "", "")

        sync._run_git = mock_run_git
        result = await sync.rollback("old456")
        assert result["action"] == "rollback"
        assert result["commit"] == "old456"
        assert result["previous_commit"] == "current123"

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        status = await sync.get_status()
        assert status["repo_url"] == "https://github.com/test/repo.git"
        assert not status["is_cloned"]

    @pytest.mark.asyncio
    async def test_get_status_cloned(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True

        # Create a temp dir with playbooks
        os.makedirs(os.path.join(sync.local_path, "playbooks"), exist_ok=True)
        Path(os.path.join(sync.local_path, "playbooks", "test.yaml")).write_text("name: test")

        async def mock_run_git(*args, cwd=None):
            return (0, "main\n", "")

        sync._run_git = mock_run_git
        status = await sync.get_status()
        assert status["is_cloned"]
        assert status["playbook_count"] == 1

    def test_sync_history(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._sync_history = [
            {"id": "sync-1", "action": "clone", "timestamp": "2026-01-01"},
            {"id": "sync-2", "action": "pull", "timestamp": "2026-01-02"},
        ]
        history = sync.get_sync_history()
        assert len(history) == 2
        # Most recent first
        assert history[0]["id"] == "sync-2"

    @pytest.mark.asyncio
    async def test_list_playbook_files_not_cloned(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        files = await sync.list_playbook_files()
        assert files == []

    @pytest.mark.asyncio
    async def test_list_playbook_files(self) -> None:
        sync = GitPlaybookSync(repo_url="https://github.com/test/repo.git")
        sync._is_cloned = True

        pb_dir = os.path.join(sync.local_path, "playbooks")
        os.makedirs(pb_dir, exist_ok=True)
        Path(os.path.join(pb_dir, "alert.yaml")).write_text("name: alert")
        Path(os.path.join(pb_dir, "restart.yml")).write_text("name: restart")

        files = await sync.list_playbook_files()
        assert len(files) == 2
        names = [f["name"] for f in files]
        assert "alert" in names
        assert "restart" in names


class TestGitPlaybookRoutes:
    """Tests for the git playbook API routes."""

    def test_git_status_not_configured(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import git_playbooks

        app = FastAPI()
        app.include_router(git_playbooks.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        original = git_playbooks._sync
        git_playbooks._sync = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/playbooks/git-status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is False

        git_playbooks._sync = original

    def test_sync_not_configured(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import git_playbooks

        app = FastAPI()
        app.include_router(git_playbooks.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        original = git_playbooks._sync
        git_playbooks._sync = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/playbooks/sync", json={})
        assert resp.status_code == 503

        git_playbooks._sync = original

    def test_diff_not_configured(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import git_playbooks

        app = FastAPI()
        app.include_router(git_playbooks.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        original = git_playbooks._sync
        git_playbooks._sync = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/playbooks/git-diff")
        assert resp.status_code == 200
        assert resp.json()["changes"] == []

        git_playbooks._sync = original

    def test_sync_history_not_configured(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import git_playbooks

        app = FastAPI()
        app.include_router(git_playbooks.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        original = git_playbooks._sync
        git_playbooks._sync = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/playbooks/sync-history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

        git_playbooks._sync = original
