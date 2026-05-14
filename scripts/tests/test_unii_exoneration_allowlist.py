#!/usr/bin/env python3
"""
Regression test for `scripts/data/unii_exoneration_allowlist.json`.

This allowlist is the gate for the pre-Sprint-1 blocker rule (see
`docs/UNII_TRIAGE_2026_05_14.md`):

  > No SAME_UNII_DIFFERENT_NAMES critical finding may remain in the
  > audit's post-exoneration output unless:
  >   1. It is in the explicit exoneration allowlist,
  >   2. It includes rationale,
  >   3. It includes FDA canonical name,
  >   4. It has a regression test.

This file is the (4). Each exonerated UNII is pinned: its FDA canonical
name must match `fda_unii_cache.json::unii_to_name`, and every listed
entry must still exist in the named reference file. If any of these
assumptions drifts, the test fails and the next audit run will refuse
to ship UNII-first matching until the allowlist is updated.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = REPO_ROOT / "scripts/data/unii_exoneration_allowlist.json"
FDA_CACHE_PATH = REPO_ROOT / "scripts/data/fda_unii_cache.json"

REF_FILES = {
    "ingredient_quality_map.json": None,  # top-level dict-of-dicts
    "botanical_ingredients.json": "botanical_ingredients",
    "other_ingredients.json": "other_ingredients",
    "standardized_botanicals.json": "standardized_botanicals",
}


@pytest.fixture(scope="module")
def allowlist():
    with open(ALLOWLIST_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fda_unii_to_name():
    with open(FDA_CACHE_PATH, encoding="utf-8") as f:
        cache = json.load(f)
    return cache.get("unii_to_name", {})


@pytest.fixture(scope="module")
def ref_entries():
    """{file_label: {entry_id: entry_dict}} across all reference files."""
    out: Dict[str, Dict[str, dict]] = {}
    for file_label, list_key in REF_FILES.items():
        path = REPO_ROOT / "scripts/data" / file_label
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        if list_key is None:
            # IQM: top-level dict-of-dicts, skip _-prefixed keys
            out[file_label] = {
                k: v for k, v in blob.items() if not k.startswith("_") and isinstance(v, dict)
            }
        else:
            out[file_label] = {}
            for entry in blob.get(list_key, []):
                if isinstance(entry, dict) and entry.get("id"):
                    out[file_label][entry["id"]] = entry
    return out


REQUIRED_FIELDS = {"unii", "fda_canonical_name", "entries", "rationale", "added_by"}


def test_metadata_block(allowlist):
    md = allowlist["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["purpose"] == "audit_exoneration"
    assert md["total_entries"] == len(allowlist["exonerations"])


def test_every_exoneration_has_required_fields(allowlist):
    for entry in allowlist["exonerations"]:
        keys = set(entry.keys())
        missing = REQUIRED_FIELDS - keys
        assert not missing, f"exoneration {entry.get('unii')!r} missing: {missing}"


def test_every_unii_matches_fda_canonical(allowlist, fda_unii_to_name):
    """Pre-Sprint-1 blocker rule #3: FDA canonical name must be authoritative."""
    drift = []
    for entry in allowlist["exonerations"]:
        unii = entry["unii"]
        our_canonical = entry["fda_canonical_name"]
        fda_canonical = fda_unii_to_name.get(unii)
        if fda_canonical != our_canonical:
            drift.append((unii, our_canonical, fda_canonical))
    assert not drift, (
        "FDA canonical name drift in exoneration allowlist (audit gate would fail). "
        "Each tuple is (unii, our_canonical, fda_canonical):\n"
        + "\n".join(f"  {u}: ours={o!r} fda={f!r}" for u, o, f in drift)
    )


def test_every_listed_entry_still_exists(allowlist, ref_entries):
    """If a referenced entry was deleted or renamed, the allowlist is stale."""
    missing = []
    for ex in allowlist["exonerations"]:
        for ref in ex["entries"]:
            file_label = ref["file"]
            entry_id = ref["entry_id"]
            if entry_id not in ref_entries.get(file_label, {}):
                missing.append((ex["unii"], file_label, entry_id))
    assert not missing, (
        "Allowlist references entries that no longer exist (stale allowlist):\n"
        + "\n".join(f"  UNII={u}, file={f}, entry_id={e}" for u, f, e in missing)
    )


def test_unii_format_strict(allowlist):
    """UNIIs must be exactly 10 alphanumeric uppercase characters (FDA contract)."""
    for entry in allowlist["exonerations"]:
        u = entry["unii"]
        assert isinstance(u, str), f"UNII not str: {u!r}"
        assert len(u) == 10, f"UNII not 10 chars: {u!r}"
        assert u.isalnum() and u.upper() == u, f"UNII not uppercase alphanumeric: {u!r}"


def test_rationale_is_non_empty(allowlist):
    """Pre-Sprint-1 blocker rule #2."""
    for entry in allowlist["exonerations"]:
        rationale = entry.get("rationale", "").strip()
        assert len(rationale) >= 30, (
            f"Allowlist entry {entry['unii']!r} has thin or missing rationale "
            f"({len(rationale)} chars). Require ≥30 chars per blocker rule."
        )


def test_every_entry_has_2_plus_references(allowlist):
    """An exoneration only makes sense when the UNII is shared across 2+ entries
    (otherwise it wouldn't be a SAME_UNII_DIFFERENT_NAMES finding in the first place)."""
    for entry in allowlist["exonerations"]:
        assert len(entry["entries"]) >= 2, (
            f"Exoneration {entry['unii']!r} only lists {len(entry['entries'])} "
            "entry; should be ≥2 (otherwise no audit finding to exonerate)."
        )


def test_referenced_entries_actually_carry_the_unii(allowlist, ref_entries):
    """Each referenced entry's external_ids.unii (or top-level unii) must equal
    the exoneration's UNII. Otherwise the audit didn't flag it for this UNII."""
    drift = []
    for ex in allowlist["exonerations"]:
        for ref in ex["entries"]:
            entry = ref_entries[ref["file"]].get(ref["entry_id"])
            if not entry:
                continue  # caught by test_every_listed_entry_still_exists
            actual = (entry.get("external_ids") or {}).get("unii") or entry.get("unii")
            if not actual or actual.upper() != ex["unii"]:
                drift.append((ex["unii"], ref["file"], ref["entry_id"], actual))
    assert not drift, (
        "Referenced entries no longer carry the documented UNII:\n"
        + "\n".join(
            f"  expected UNII={u}, file={f}, entry_id={e}, actual={a!r}"
            for u, f, e, a in drift
        )
    )
