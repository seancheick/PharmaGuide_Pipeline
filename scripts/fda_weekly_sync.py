#!/usr/bin/env python3
"""Compatibility wrapper for scripts/api_audit/fda_weekly_sync.py."""

from api_audit import fda_weekly_sync as _impl
from api_audit.fda_weekly_sync import *  # noqa: F401,F403

__doc__ = _impl.__doc__


if __name__ == "__main__":
    main()
