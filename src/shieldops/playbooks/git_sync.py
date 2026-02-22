"""Git-backed playbook synchronization — Runbook-as-Code."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class GitSyncError(Exception):
    """Error during git sync operations."""


class PlaybookDiff(dict[str, Any]):
    """Represents a diff between local and remote playbook versions."""

    pass


class GitPlaybookSync:
    """Synchronizes playbooks from a remote git repository.

    Features:
    - Clone/pull from remote git repo
    - Track branch and commit history
    - Diff preview before applying changes
    - Version history with rollback support
    """

    def __init__(
        self,
        repo_url: str = "",
        branch: str = "main",
        local_path: str | None = None,
        playbook_dir: str = "playbooks",
        auto_sync: bool = False,
    ) -> None:
        self._repo_url = repo_url
        self._branch = branch
        self._local_path = local_path or os.path.join(
            tempfile.gettempdir(), f"shieldops-playbooks-{uuid4().hex[:8]}"
        )
        self._playbook_dir = playbook_dir
        self._auto_sync = auto_sync
        self._last_sync: datetime | None = None
        self._last_commit: str = ""
        self._sync_history: list[dict[str, Any]] = []
        self._is_cloned = False

    @property
    def repo_url(self) -> str:
        return self._repo_url

    @property
    def branch(self) -> str:
        return self._branch

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def last_sync(self) -> datetime | None:
        return self._last_sync

    @property
    def last_commit(self) -> str:
        return self._last_commit

    @property
    def is_cloned(self) -> bool:
        return self._is_cloned

    async def clone(self) -> dict[str, Any]:
        """Clone the remote repository."""
        if not self._repo_url:
            raise GitSyncError("No repository URL configured")

        # Clean up existing directory
        if os.path.exists(self._local_path):
            shutil.rmtree(self._local_path)

        returncode, stdout, stderr = await self._run_git(
            "clone",
            "--branch",
            self._branch,
            "--depth",
            "50",
            self._repo_url,
            self._local_path,
            cwd=None,
        )
        if returncode != 0:
            raise GitSyncError(f"Clone failed: {stderr}")

        self._is_cloned = True
        self._last_commit = await self._get_head_commit()
        self._last_sync = datetime.now(UTC)

        sync_entry = {
            "id": f"sync-{uuid4().hex[:12]}",
            "action": "clone",
            "commit": self._last_commit,
            "branch": self._branch,
            "timestamp": self._last_sync.isoformat(),
            "files_changed": 0,
        }
        self._sync_history.append(sync_entry)

        logger.info(
            "git_clone_complete",
            repo=self._repo_url,
            branch=self._branch,
            commit=self._last_commit,
        )
        return sync_entry

    async def pull(self) -> dict[str, Any]:
        """Pull latest changes from remote."""
        if not self._is_cloned:
            return await self.clone()

        old_commit = self._last_commit

        returncode, stdout, stderr = await self._run_git(
            "pull",
            "origin",
            self._branch,
            cwd=self._local_path,
        )
        if returncode != 0:
            raise GitSyncError(f"Pull failed: {stderr}")

        new_commit = await self._get_head_commit()
        self._last_commit = new_commit
        self._last_sync = datetime.now(UTC)

        # Count changed files
        files_changed = 0
        if old_commit != new_commit:
            _, diff_out, _ = await self._run_git(
                "diff",
                "--name-only",
                old_commit,
                new_commit,
                cwd=self._local_path,
            )
            files_changed = len([f for f in diff_out.strip().split("\n") if f])

        sync_entry = {
            "id": f"sync-{uuid4().hex[:12]}",
            "action": "pull",
            "commit": new_commit,
            "previous_commit": old_commit,
            "branch": self._branch,
            "timestamp": self._last_sync.isoformat(),
            "files_changed": files_changed,
            "up_to_date": old_commit == new_commit,
        }
        self._sync_history.append(sync_entry)

        logger.info(
            "git_pull_complete",
            commit=new_commit,
            files_changed=files_changed,
        )
        return sync_entry

    async def diff_preview(self) -> list[dict[str, Any]]:
        """Preview changes between local and remote without applying.

        Performs a fetch + diff without modifying working tree.
        """
        if not self._is_cloned:
            return []

        # Fetch without merge
        await self._run_git("fetch", "origin", self._branch, cwd=self._local_path)

        _, diff_output, _ = await self._run_git(
            "diff",
            f"HEAD..origin/{self._branch}",
            "--stat",
            cwd=self._local_path,
        )

        _, diff_names, _ = await self._run_git(
            "diff",
            f"HEAD..origin/{self._branch}",
            "--name-status",
            cwd=self._local_path,
        )

        changes: list[dict[str, Any]] = []
        for line in diff_names.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) >= 2:
                status_code = parts[0].strip()
                filepath = parts[1].strip()
                status_map = {
                    "A": "added",
                    "M": "modified",
                    "D": "deleted",
                    "R": "renamed",
                }
                changes.append(
                    {
                        "file": filepath,
                        "status": status_map.get(status_code, "unknown"),
                        "status_code": status_code,
                    }
                )

        return changes

    async def get_version_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get commit history for playbook files."""
        if not self._is_cloned:
            return []

        _, log_output, _ = await self._run_git(
            "log",
            f"--max-count={limit}",
            "--pretty=format:%H|%an|%ae|%ai|%s",
            "--",
            self._playbook_dir,
            cwd=self._local_path,
        )

        commits: list[dict[str, Any]] = []
        for line in log_output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) >= 5:
                commits.append(
                    {
                        "commit": parts[0],
                        "author_name": parts[1],
                        "author_email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    }
                )

        return commits

    async def rollback(self, commit_sha: str) -> dict[str, Any]:
        """Rollback playbooks to a specific commit."""
        if not self._is_cloned:
            raise GitSyncError("Repository not cloned")

        old_commit = self._last_commit

        returncode, _, stderr = await self._run_git(
            "checkout",
            commit_sha,
            "--",
            self._playbook_dir,
            cwd=self._local_path,
        )
        if returncode != 0:
            raise GitSyncError(f"Rollback failed: {stderr}")

        self._last_sync = datetime.now(UTC)

        sync_entry = {
            "id": f"sync-{uuid4().hex[:12]}",
            "action": "rollback",
            "commit": commit_sha,
            "previous_commit": old_commit,
            "branch": self._branch,
            "timestamp": self._last_sync.isoformat(),
        }
        self._sync_history.append(sync_entry)

        logger.info("git_rollback_complete", target_commit=commit_sha)
        return sync_entry

    async def get_status(self) -> dict[str, Any]:
        """Get current git sync status."""
        status: dict[str, Any] = {
            "repo_url": self._repo_url,
            "branch": self._branch,
            "local_path": self._local_path,
            "is_cloned": self._is_cloned,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "last_commit": self._last_commit,
            "auto_sync": self._auto_sync,
        }

        if self._is_cloned:
            _, branch_out, _ = await self._run_git(
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                cwd=self._local_path,
            )
            status["current_branch"] = branch_out.strip()

            # Count playbook files
            playbook_path = Path(self._local_path) / self._playbook_dir
            if playbook_path.exists():
                yaml_files = list(playbook_path.glob("**/*.yaml")) + list(
                    playbook_path.glob("**/*.yml")
                )
                status["playbook_count"] = len(yaml_files)
            else:
                status["playbook_count"] = 0

        return status

    def get_sync_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get sync operation history."""
        return list(reversed(self._sync_history[-limit:]))

    async def list_playbook_files(self) -> list[dict[str, Any]]:
        """List all playbook YAML files in the synced repo."""
        if not self._is_cloned:
            return []

        playbook_path = Path(self._local_path) / self._playbook_dir
        if not playbook_path.exists():
            return []

        files: list[dict[str, Any]] = []
        for pattern in ("**/*.yaml", "**/*.yml"):
            for f in playbook_path.glob(pattern):
                rel = f.relative_to(playbook_path)
                stat = f.stat()
                files.append(
                    {
                        "path": str(rel),
                        "name": f.stem,
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    }
                )

        files.sort(key=lambda x: x["path"])
        return files

    # ── Private helpers ──────────────────────────────────────────

    async def _run_git(self, *args: str, cwd: str | None) -> tuple[int, str, str]:
        """Run a git command asynchronously."""
        cmd = ["git"] + list(args)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            return (
                proc.returncode or 0,
                stdout_bytes.decode("utf-8", errors="replace"),
                stderr_bytes.decode("utf-8", errors="replace"),
            )
        except FileNotFoundError:
            return (1, "", "git command not found")
        except Exception as e:
            return (1, "", str(e))

    async def _get_head_commit(self) -> str:
        """Get the current HEAD commit SHA."""
        _, stdout, _ = await self._run_git(
            "rev-parse",
            "HEAD",
            cwd=self._local_path,
        )
        return stdout.strip()
