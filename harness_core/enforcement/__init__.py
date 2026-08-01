"""Deterministic, fail-closed enforcement shared by hooks and CI.

This package is deliberately the only place that resolves Git ranges or turns
Git name-status records into policy inputs.  Adapters only pass provider/hook
facts in and serialize the returned audit record.
"""

from .core import (
    EnforcementError,
    VerificationResult,
    canonical_path,
    local_protected_roots,
    changed_file_events,
    resolve_outgoing_range,
    verify_outgoing,
    verify_local,
    worktree_changed_events,
    LocalVerificationResult,
    local_indeterminate_audit,
)

__all__ = [
    "EnforcementError",
    "VerificationResult",
    "canonical_path",
    "local_protected_roots",
    "changed_file_events",
    "resolve_outgoing_range",
    "verify_outgoing",
    "verify_local",
    "worktree_changed_events",
    "LocalVerificationResult",
    "local_indeterminate_audit",
]
