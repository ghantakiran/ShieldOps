"""Rollback mechanisms for agent actions."""

from shieldops.policy.rollback.manager import RollbackManager
from shieldops.policy.rollback.registry import RollbackRegistry

__all__ = ["RollbackManager", "RollbackRegistry"]
