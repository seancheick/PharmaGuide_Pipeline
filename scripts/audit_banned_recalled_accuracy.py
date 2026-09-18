#!/usr/bin/env python3
"""Compatibility wrapper for scripts/api_audit/audit_banned_recalled_accuracy.py."""

import sys

from api_audit import audit_banned_recalled_accuracy as _impl
from api_audit.audit_banned_recalled_accuracy import *  # noqa: F401,F403

__doc__ = _impl.__doc__


if __name__ == "__main__":
    # sys.exit(main()), not main(): the implementation signals gate failures
    # through its RETURN CODE, and a bare main() call discards it. This wrapper
    # printed "RELEASE GATE FAILED" and still exited 0 -- a release gate that
    # reports failure and passes anyway.
    sys.exit(main())
