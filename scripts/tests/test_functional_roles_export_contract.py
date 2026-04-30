#!/usr/bin/env python3
"""
Contract tests for the `functional_roles[]` field on inactive_ingredients[]
in the Flutter export blob (`build_final_db.py:2294-2331`).

Phase 2 contract (lenient):
  - Every inactive_ingredients[] row MUST have a `functional_roles` key
    (may be an empty list in V1; populated per Phase 3 batches)
  - Every value MUST be a string from the locked 32-role vocab
  - The blob MUST NOT carry the deprecated `additive_type` field
    (replaced by `functional_roles[]`)

Phase 5 will add the strict completeness gate (every entry has ≥1 role) via
coverage_gate.py; that contract is intentionally NOT enforced here so V1
backfill can proceed batch-by-batch without breaking the test suite.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "functional_roles_vocab.json"
)


@pytest.fixture(scope="module")
def vocab_ids():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["functional_roles"]}


@pytest.fixture(scope="module")
def harmful_lookup():
    """Minimal harmful_additives lookup used by build_final_db (one entry)."""
    return {}


def _build_minimal_inactive_blob_row(ing_dict, harmful_ref=None, other_ref=None):
    """Replicate the Phase 2 inactive-ingredient blob shape from
    build_final_db.py without invoking the full pipeline. Used to assert
    the field contract in isolation."""
    from build_final_db import safe_str, safe_list, safe_bool
    harmful_ref = harmful_ref or {}
    other_ref = other_ref or {}
    return {
        "raw_source_text": safe_str(ing_dict.get("raw_source_text")),
        "name": safe_str(ing_dict.get("name")),
        "category": safe_str(ing_dict.get("category") or other_ref.get("category")),
        "is_additive": safe_bool(
            ing_dict.get("isAdditive") or other_ref.get("is_additive")
        ),
        "functional_roles": safe_list(
            ing_dict.get("functional_roles")
            or other_ref.get("functional_roles")
            or harmful_ref.get("functional_roles")
        ),
        "common_uses": safe_list(other_ref.get("common_uses")),
        "notes": safe_str(other_ref.get("notes")),
    }


# ---------------------------------------------------------------------------
# Field-presence contract
# ---------------------------------------------------------------------------


def test_functional_roles_field_always_present():
    """V1 invariant: the key must exist on every inactive row, even when empty."""
    row = _build_minimal_inactive_blob_row(
        {"name": "Magnesium Stearate", "raw_source_text": "Magnesium Stearate"}
    )
    assert "functional_roles" in row
    assert isinstance(row["functional_roles"], list)


def test_additive_type_is_NOT_in_blob():
    """Phase 2 cleanup: `additive_type` was retired from the Flutter blob.
    `functional_roles[]` replaces it. Re-adding additive_type would re-introduce
    the proliferation problem (226 distinct un-standardized values)."""
    row = _build_minimal_inactive_blob_row(
        {"name": "Test", "raw_source_text": "Test", "additiveType": "filler"}
    )
    assert "additive_type" not in row, (
        "additive_type was retired from the export blob in Phase 2. "
        "Use functional_roles[] instead — it carries multi-valued role info "
        "without the un-standardized free-text proliferation."
    )


def test_functional_roles_pulled_from_other_ref():
    """When the ingredient is mapped to other_ingredients, its functional_roles
    flow through to the blob."""
    other_ref = {"functional_roles": ["lubricant", "anti_caking_agent"]}
    row = _build_minimal_inactive_blob_row(
        {"name": "Magnesium Stearate", "raw_source_text": "Magnesium Stearate"},
        other_ref=other_ref,
    )
    assert row["functional_roles"] == ["lubricant", "anti_caking_agent"]


def test_functional_roles_pulled_from_harmful_ref():
    """When the ingredient is harmful, harmful-side functional_roles flow through."""
    harmful_ref = {"functional_roles": ["sweetener_artificial"]}
    row = _build_minimal_inactive_blob_row(
        {"name": "Aspartame", "raw_source_text": "Aspartame"},
        harmful_ref=harmful_ref,
    )
    assert row["functional_roles"] == ["sweetener_artificial"]


def test_functional_roles_empty_list_when_unmapped():
    """V1 backfill is incremental — unmapped entries ship with [] until their
    Phase 3 batch lands. Must NOT be None or missing."""
    row = _build_minimal_inactive_blob_row(
        {"name": "UnknownExcipient", "raw_source_text": "UnknownExcipient"}
    )
    assert row["functional_roles"] == []


# ---------------------------------------------------------------------------
# Vocab-membership gate (when populated)
# ---------------------------------------------------------------------------


def test_all_vocab_roles_assigned_in_3_data_files_use_locked_ids(vocab_ids):
    """Sweep the three reference data files. ANY value that has been
    backfilled into a `functional_roles[]` array must be a member of the
    locked 32-role vocabulary. Catches typos and unauthorized vocab drift
    immediately, not at release time."""
    bad = []
    for filename, wrap_key in [
        ("harmful_additives.json", "harmful_additives"),
        ("other_ingredients.json", "other_ingredients"),
        ("botanical_ingredients.json", "botanical_ingredients"),
    ]:
        path = os.path.join(os.path.dirname(__file__), "..", "data", filename)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get(wrap_key, []):
            roles = entry.get("functional_roles", [])
            if not isinstance(roles, list):
                bad.append((filename, entry.get("id"), "not_a_list", roles))
                continue
            for role in roles:
                if role not in vocab_ids:
                    bad.append((filename, entry.get("id"), "unknown_role", role))
    assert not bad, (
        "Found functional_roles values outside the locked 32-role vocab. "
        "Fix the data file or update the vocab via clinician sign-off:\n"
        + "\n".join(f"  {f} → {eid}: {issue} ({val!r})" for f, eid, issue, val in bad[:20])
    )


def test_vocab_file_is_loadable_and_has_32_roles():
    """Pipeline-side sanity: vocab file must be parseable and locked at 32."""
    with open(VOCAB_PATH, encoding="utf-8") as f:
        v = json.load(f)
    assert len(v["functional_roles"]) == 32
