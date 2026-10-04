"""
Autonomous Self-Organization Tooling Package.
Provides decentralized lease management, task scheduling, resource gating,
and supervisor control loop for removing desktop/principal SPOFs.
"""

from .lease_manager import (
    Lease,
    LeaseAlreadyHeldError,
    LeaseError,
    LeaseExpiredError,
    LeaseManager,
    LeaseNotExpiredError,
    LeaseNotFoundError,
    LeaseStorageCorruptedError,
    FencingTokenMismatchError,
    HolderMismatchError,
)

__all__ = [
    "Lease",
    "LeaseAlreadyHeldError",
    "LeaseError",
    "LeaseExpiredError",
    "LeaseManager",
    "LeaseNotExpiredError",
    "LeaseNotFoundError",
    "LeaseStorageCorruptedError",
    "FencingTokenMismatchError",
    "HolderMismatchError",
]
