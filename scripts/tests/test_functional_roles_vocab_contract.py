#!/usr/bin/env python3
"""
Contract tests for `data/functional_roles_vocab.json` (clinician-locked v1.0.0,
2026-04-30).

This vocab is the single source of truth for `functional_roles[]` IDs across
harmful_additives.json, other_ingredients.json, and botanical_ingredients.json.
It also ships as a bundled asset to the Flutter app for the tap-to-learn UI.

Locked decisions captured by these tests:
  - Exactly 32 roles, no more, no fewer (clinician sign-off)
  - Lean schema: 5 fields per role (id, name, notes, regulatory_references, examples)
  - No parallel description fields (no display_label, short_description, long_description)
  - notes ≤200 chars (Flutter UI char-limit contract)
  - All IDs unique, snake_case, stable
  - Every role has at least one regulatory_reference and one example
  - Every regulatory_reference has both jurisdiction and code

Adding a 33rd role or removing one requires a new clinician sign-off cycle and
should fail this test, not slip through silently.
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "functional_roles_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def roles(vocab):
    return vocab["functional_roles"]


# ---------------------------------------------------------------------------
# Top-level contract
# ---------------------------------------------------------------------------


def test_metadata_block_present(vocab):
    assert "_metadata" in vocab
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 32
    assert "LOCKED" in md["status"]
    assert "char_limit_notes" in md
    assert md["char_limit_notes"] == 200


def test_exactly_32_roles_locked(roles):
    """Adding/removing roles requires clinician re-signoff. Must fail loudly."""
    assert len(roles) == 32, (
        f"Vocab is clinician-locked at 32 roles; got {len(roles)}. "
        "Adding or removing roles requires a fresh clinician review cycle "
        "(scripts/audits/functional_roles/CLINICIAN_REVIEW.md)."
    )


# ---------------------------------------------------------------------------
# Per-role schema
# ---------------------------------------------------------------------------


REQUIRED_FIELDS = {"id", "name", "notes", "regulatory_references", "examples"}
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_every_role_has_exactly_5_required_fields(roles):
    """Lean schema: 5 fields. No bloat, no parallel description fields."""
    for r in roles:
        keys = set(r.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - REQUIRED_FIELDS
        assert not missing, f"role {r.get('id')!r} missing: {missing}"
        assert not extra, (
            f"role {r['id']!r} has unexpected fields: {extra}. "
            "Lean schema is locked at exactly: id, name, notes, "
            "regulatory_references, examples."
        )


def test_every_id_unique_and_snake_case(roles):
    ids = [r["id"] for r in roles]
    assert len(set(ids)) == len(ids), "duplicate role IDs"
    for rid in ids:
        assert SNAKE_CASE.match(rid), (
            f"role id {rid!r} is not snake_case (must match ^[a-z][a-z0-9_]*$)"
        )


def test_every_name_is_nonempty_display_string(roles):
    """`name` is the chip label shown to users. Must be non-empty and contain
    at least one uppercase letter for display polish. Allows scientific
    lowercase prefixes like 'pH Regulator' (deliberate convention)."""
    for r in roles:
        assert isinstance(r["name"], str) and r["name"].strip()
        assert any(c.isupper() for c in r["name"]), (
            f"role {r['id']!r} name {r['name']!r} has no uppercase letters; "
            "should be display-cased (e.g. 'Binder', 'Anti-Caking Agent', 'pH Regulator')."
        )


def test_notes_char_limit_contract(roles):
    """Flutter UI shows notes verbatim — char limit prevents truncation."""
    over = [(r["id"], len(r["notes"])) for r in roles if len(r["notes"]) > 200]
    assert not over, f"notes exceed 200-char limit: {over}"
    empty = [r["id"] for r in roles if not r["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_regulatory_references_well_formed(roles):
    for r in roles:
        refs = r["regulatory_references"]
        assert isinstance(refs, list) and refs, (
            f"role {r['id']!r} has no regulatory_references (must have ≥1)"
        )
        for ref in refs:
            assert isinstance(ref, dict)
            assert ref.get("jurisdiction"), f"{r['id']}: ref missing jurisdiction"
            assert ref.get("code"), f"{r['id']}: ref missing code"
            assert ref["jurisdiction"] in ("FDA", "EU"), (
                f"{r['id']}: unknown jurisdiction {ref['jurisdiction']!r}"
            )


def test_every_role_has_at_least_one_example(roles):
    for r in roles:
        ex = r["examples"]
        assert isinstance(ex, list) and ex, (
            f"role {r['id']!r} has no examples (clinician requested ≥1 for tap modal)"
        )
        for e in ex:
            assert isinstance(e, str) and e.strip()


# ---------------------------------------------------------------------------
# Specific clinician-locked role presence
# ---------------------------------------------------------------------------


CLINICIAN_LOCKED_IDS = {
    # 1A. Tablet/capsule mechanics
    "binder", "disintegrant", "lubricant", "glidant", "coating",
    # 1B. Bulk
    "filler",
    # 1C. Texture/structure
    "emulsifier", "surfactant", "thickener", "stabilizer",
    "gelling_agent", "humectant",
    # 1D. Preservation
    "preservative", "antioxidant",
    # 1E. Sensory (split mirrors colorant pattern)
    "colorant_natural", "colorant_artificial",
    "flavor_natural", "flavor_artificial", "flavor_enhancer",
    # 1F. Sweeteners
    "sweetener_natural", "sweetener_artificial", "sweetener_sugar_alcohol",
    # 1G. Manufacturing aids
    "anti_caking_agent", "anti_foaming_agent", "processing_aid", "solvent",
    # 1H. Delivery / chemistry
    "carrier_oil", "acidulant", "ph_regulator", "propellant", "glazing_agent",
    # 1I. Fiber / gut health (added by clinician)
    "prebiotic_fiber",
}


def test_all_clinician_locked_ids_present(roles):
    actual_ids = {r["id"] for r in roles}
    missing = CLINICIAN_LOCKED_IDS - actual_ids
    extra = actual_ids - CLINICIAN_LOCKED_IDS
    assert not missing, f"clinician-locked roles missing from vocab: {missing}"
    assert not extra, (
        f"vocab contains roles NOT in clinician-locked set: {extra}. "
        "Was a role added without a fresh review cycle?"
    )


def test_v1_excluded_roles_not_present(roles):
    """Per Section 1Z of CLINICIAN_REVIEW.md — these were considered and excluded
    from V1. Re-adding requires a fresh clinician sign-off."""
    excluded = {
        "chelating_agent",   # folded into preservative/antioxidant
        "enzyme",            # folded into processing_aid; actives go to active pipeline
        "firming_agent",     # absent in supplements
        "sequestrant",       # overlaps preservative/antioxidant
        "texturizer",        # synonymous with gelling_agent
        "vehicle",           # use solvent or carrier_oil instead
        "diluent",           # collapsed into filler (1B)
        "bulking_agent",     # collapsed into filler (1B)
        "antimicrobial",     # mechanistic subset of preservative
        "flavoring",         # split into flavor_natural / flavor_artificial
    }
    actual_ids = {r["id"] for r in roles}
    leaked = excluded & actual_ids
    assert not leaked, (
        f"V1-excluded roles found in vocab: {leaked}. "
        "These were intentionally collapsed/merged per clinician decision."
    )
