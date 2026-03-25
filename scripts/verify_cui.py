#!/usr/bin/env python3
"""Compatibility wrapper for scripts/api_audit/verify_cui.py."""

from api_audit import verify_cui as _impl
from api_audit.verify_cui import *  # noqa: F401,F403

__doc__ = _impl.__doc__


if __name__ == "__main__":
    main()
