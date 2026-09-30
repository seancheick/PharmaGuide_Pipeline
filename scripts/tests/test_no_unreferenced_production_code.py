"""Ratchet: no production function or class that only tests, or nothing, names.

Dead code reads as a live path to the next agent. A new finding fails here: delete it with its
docs and tests (proof tags in scripts/audits/closure_20260921/REMOVALS_AND_RETENTIONS_20260921.md),
or add it to audit_dead_code.KEEP with the reason it must stay. A KEEP entry that is no longer a
finding fails too, so the list cannot rot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import audit_dead_code  # noqa: E402


@pytest.fixture(scope="module")
def scan():
    return audit_dead_code.scan_functions()


def test_every_unreferenced_or_test_only_definition_is_removed_or_kept_with_a_reason(scan):
    new = [f'{f["bucket"]}: {f["id"]} (line {f["start"]})' for f in scan["findings"]
           if f["id"] not in audit_dead_code.KEEP]
    assert not new, "Delete these, or keep them in audit_dead_code.KEEP with a reason:\n" + "\n".join(new)


def test_keep_entries_are_still_findings(scan):
    found = {f["id"] for f in scan["findings"]}
    stale = sorted(set(audit_dead_code.KEEP) - found)
    assert not stale, "No longer dead or already gone; remove from audit_dead_code.KEEP:\n" + "\n".join(stale)


def test_keep_reasons_are_written():
    assert all(reason.strip() for reason in audit_dead_code.KEEP.values())


def test_scanner_sees_a_production_only_reference_and_ignores_a_test_only_one(tmp_path):
    tree = audit_dead_code.ast.parse(
        "def used():\n    return 1\n\n"
        "def unused():\n    '''used() is named in a docstring only'''\n    return 2\n\n"
        "VALUE = used()\n"
    )
    defs = {d["name"]: d for d in audit_dead_code.definitions(tree, "scripts/example.py")}
    refs = [name for name, _ in audit_dead_code.references(tree)]
    assert set(defs) == {"used", "unused"}
    assert refs.count("used") == 1 and "unused" not in refs
