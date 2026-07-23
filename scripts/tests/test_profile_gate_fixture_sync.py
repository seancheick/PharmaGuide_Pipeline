#!/usr/bin/env python3
"""Fixture-sync drift gate for the profile_gate cross-runtime fixture.

`scripts/data/profile_gate_test_cases.json` is the CANONICAL shared fixture.
The Flutter app vendors a byte-identical copy at
`test/fixtures/profile_gate/profile_gate_test_cases.json` and locks it to the
SAME pinned hash (see that repo's
`test/services/warnings/profile_gate_fixture_sync_test.dart`).

Pinning the content hash makes any change to the fixture a deliberate,
reviewable act: whoever edits it must update PINNED_SHA256 here AND in the
app repo, and re-copy the file. That is the mechanism that stops the two
profile_gate evaluator implementations (Python reference + Dart production)
from silently drifting apart via a stale vendored copy.

Companion tests:
  - test_profile_gate_contract.py::test_shared_fixture_every_case_evaluates_correctly
    locks the Python evaluator to this fixture's expectations.
  - the app's profile_gate_evaluator_test.dart locks the Dart evaluator to it.
  - this file freezes the fixture *content* so neither of those can be quietly
    rebased onto a changed fixture.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[1] / "data" / "profile_gate_test_cases.json"
)

# SHA-256 of the canonical fixture bytes. MUST equal the pin in the app repo's
# test/services/warnings/profile_gate_fixture_sync_test.dart.
# To change the fixture: edit it, recompute `shasum -a 256`, update this pin
# AND the app pin, and re-copy the file into the app repo.
PINNED_SHA256 = "ea6e5ae87d46c8c8e1f1fe8220c15cab6aa1950cf9c8c6195a8de9defdc81e66"


def test_canonical_fixture_matches_pinned_hash():
    actual = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert actual == PINNED_SHA256, (
        "profile_gate fixture content changed.\n"
        f"  actual sha256: {actual}\n"
        f"  pinned sha256: {PINNED_SHA256}\n"
        "If this change is intentional, update PINNED_SHA256 here AND the pin in "
        "the app repo's test/services/warnings/profile_gate_fixture_sync_test.dart, "
        "then re-copy the fixture into the app repo."
    )


def test_fixture_entry_counts_are_consistent():
    data = json.loads(FIXTURE.read_text())
    meta = data["_metadata"]
    n = len(data["test_cases"])
    assert meta["total_entries"] == n, (
        f'_metadata.total_entries={meta["total_entries"]} != {n} actual cases'
    )
    assert meta["case_count"] == n, (
        f'_metadata.case_count={meta["case_count"]} != {n} actual cases'
    )
