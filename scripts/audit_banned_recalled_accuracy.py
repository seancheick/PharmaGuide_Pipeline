#!/usr/bin/env python3
"""Compatibility wrapper for scripts/api_audit/audit_banned_recalled_accuracy.py."""

from api_audit import audit_banned_recalled_accuracy as _impl
from api_audit.audit_banned_recalled_accuracy import *  # noqa: F401,F403

__doc__ = _impl.__doc__


if __name__ == "__main__":
    main()
