#!/usr/bin/env python3
"""Compatibility wrapper for scripts/api_audit/audit_clinical_sources.py."""

from api_audit import audit_clinical_sources as _impl
from api_audit.audit_clinical_sources import *  # noqa: F401,F403

__doc__ = _impl.__doc__


if __name__ == "__main__":
    main()
