"""
Sprint E1.2.2 — pre-flight invariant (external-dev review, 2026-04-22).

BEFORE any E1.2.2 display-field logic lands, lock the contract:

  * Every existing ingredient-level field keeps byte-identical value.
  * Ingredient count is identical (no filter leak, no aggregation churn).
  * Warnings / score_bonuses / score_penalties unchanged (this task
    ADDS fields; it does not touch scoring).
  * display_label / display_dose_label / display_badge /
    standardization_note start as the only fields that MAY be new.

Intentionally strict. If a future E1.2.2 sub-task accidentally mutates
a pre-existing field, this invariant raises a clear assertion failure
that points to the exact dsld_id + field.

Runs against the 7 canary baseline blobs + their fresh rebuilds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The pre-flight baseline is "post-E1.2.1, pre-E1.2.2 code state" — locked
# at E1.2.2 kickoff. This filters out E1.0/E1.1/E1.2.1 already-in-flight
# changes + Dr Pham's tone-sweep commit 5dec46e (landed after the
# v2026.04.21.224445 dist build). That earlier snapshot remains frozen
# as the forever-reference at reports/baseline_v2026.04.21.224445/.
BASELINE_DIR = ROOT / "reports" / "baseline_pre_e1_2_2"
REBUILD_DIR = ROOT / "reports" / "canary_rebuild"

# Fields E1.2.2 is explicitly permitted to ADD (not mutate). Any other
# new field on ingredient objects triggers the pre-flight assertion.
E1_2_2_NEW_INGREDIENT_FIELDS = {
    "display_label",           # E1.2.2.a
    "display_dose_label",      # E1.2.2.b
    "display_badge",           # E1.2.2.d
    "standardization_note",    # E1.2.2.c
    "adequacy_tier",           # E1.3.2 per-strain adequacy
    "clinical_support_level",  # E1.3.2 per-strain adequacy
}

# Baseline rolls forward sub-task by sub-task. As each field lands, move
# the baseline pointer. Currently "post-E1.2.2.a" is the active pre-flight
# reference (contains display_label, not yet dose_label / badge / note).
# The test allows any subset of E1_2_2_NEW_INGREDIENT_FIELDS to be
# present in the rebuild but NOT in the baseline (additive-only).

# Known non-ingredient keys that have been added by earlier E1 tasks
# (E1.1.1 danger bucket, E1.1.4 banned_substance_detail). These are
# allowed to appear as new top-level keys in rebuilds; the pre-flight
# only polices ingredient-level shape.
E1_POST_E1_2_1_TOPLEVEL = {
    "banned_substance_detail",
    "raw_inactives_count",           # Sprint E1.2.4 additive instrumentation
    "raw_actives_count",             # Sprint E1.2.5 additive instrumentation
    "ingredients_dropped_reasons",   # Sprint E1.2.5 additive instrumentation
    # decision_highlights already existed pre-E1; only its shape grew.
}


# ---------------------------------------------------------------------------
# Fixture loading — skip cleanly when a canary hasn't been rebuilt yet.
# ---------------------------------------------------------------------------

CANARY_IDS = ["35491", "306237", "246324", "1002", "19067", "1036", "176872", "266975"]


@pytest.fixture(scope="module", params=CANARY_IDS)
def canary_pair(request):
    """Load (baseline_blob, rebuild_blob) for a canary. Skips if either
    file is missing (e.g., rebuild not yet run for a new canary)."""
    dsld_id = request.param
    baseline_path = BASELINE_DIR / f"{dsld_id}.json"
    rebuild_path = REBUILD_DIR / f"{dsld_id}.json"
    if not baseline_path.exists():
        pytest.skip(f"baseline {dsld_id}.json missing")
    if not rebuild_path.exists():
        pytest.skip(
            f"rebuild {dsld_id}.json missing — run "
            f"scripts/reports/canary_rebuild.py for this DSLD id first"
        )
    return (
        dsld_id,
        json.loads(baseline_path.read_text()),
        json.loads(rebuild_path.read_text()),
    )


# ---------------------------------------------------------------------------
# Invariant 1 — ingredient count unchanged
# ---------------------------------------------------------------------------

def test_ingredient_count_unchanged(canary_pair) -> None:
    dsld_id, baseline, rebuild = canary_pair
    assert len(baseline.get("ingredients") or []) == len(rebuild.get("ingredients") or []), (
        f"[{dsld_id}] ingredient count changed: "
        f"baseline={len(baseline.get('ingredients') or [])} "
        f"rebuild={len(rebuild.get('ingredients') or [])}"
    )
    assert len(baseline.get("inactive_ingredients") or []) == len(rebuild.get("inactive_ingredients") or []), (
        f"[{dsld_id}] inactive_ingredients count changed"
    )


# ---------------------------------------------------------------------------
# Invariant 2 — existing ingredient fields byte-identical
# ---------------------------------------------------------------------------

def test_ingredient_existing_fields_are_byte_identical(canary_pair) -> None:
    """For every ingredient, every field present in the baseline must
    appear with the SAME value in the rebuild. New fields in
    E1_2_2_NEW_INGREDIENT_FIELDS are allowed to appear; other net-new
    fields are flagged."""
    dsld_id, baseline, rebuild = canary_pair
    base_ings = baseline.get("ingredients") or []
    new_ings = rebuild.get("ingredients") or []

    violations = []
    extra_fields = []

    for i, (b, r) in enumerate(zip(base_ings, new_ings)):
        if not isinstance(b, dict) or not isinstance(r, dict):
            continue
        # 2a — pre-existing fields must be identical
        for key in b.keys():
            if b[key] != r.get(key):
                violations.append((dsld_id, i, b.get("name"), key, b[key], r.get(key)))
        # 2b — new fields on rebuild must be in the allowlist
        net_new = set(r.keys()) - set(b.keys()) - E1_2_2_NEW_INGREDIENT_FIELDS
        if net_new:
            extra_fields.append((dsld_id, i, b.get("name"), sorted(net_new)))

    assert not violations, (
        f"E1.2.2 pre-flight: {len(violations)} ingredient fields mutated. First 5:\n"
        + "\n".join(
            f"  [{did}][{idx}] {name!r}.{k}: baseline={bv!r} != rebuild={rv!r}"
            for did, idx, name, k, bv, rv in violations[:5]
        )
    )
    assert not extra_fields, (
        f"E1.2.2 pre-flight: unexpected net-new ingredient fields (not in allowlist "
        f"{sorted(E1_2_2_NEW_INGREDIENT_FIELDS)}). First 5:\n"
        + "\n".join(
            f"  [{did}][{idx}] {name!r}: extras={extras}"
            for did, idx, name, extras in extra_fields[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 3 — score arrays unchanged (E1.2.2 is additive, not scoring)
# ---------------------------------------------------------------------------

def test_score_arrays_unchanged(canary_pair) -> None:
    dsld_id, baseline, rebuild = canary_pair
    # Compare section_breakdown (scoring numeric output)
    assert baseline.get("section_breakdown") == rebuild.get("section_breakdown"), (
        f"[{dsld_id}] section_breakdown changed — E1.2.2 must not touch scoring"
    )
    # score_bonuses + score_penalties — shape and entries identical
    assert baseline.get("score_bonuses") == rebuild.get("score_bonuses"), (
        f"[{dsld_id}] score_bonuses changed"
    )
    assert baseline.get("score_penalties") == rebuild.get("score_penalties"), (
        f"[{dsld_id}] score_penalties changed"
    )


# ---------------------------------------------------------------------------
# Invariant 4 — warnings / warnings_profile_gated unchanged
# ---------------------------------------------------------------------------

def _warning_fingerprint(w: dict) -> tuple:
    """Stable identity for a warning independent of field-addition churn."""
    return (
        w.get("type"),
        w.get("severity"),
        w.get("canonical_id") or w.get("title"),
        w.get("condition_id"),
        w.get("drug_class_id"),
    )


def test_warnings_superset_unchanged(canary_pair) -> None:
    dsld_id, baseline, rebuild = canary_pair
    b = sorted(_warning_fingerprint(w) for w in (baseline.get("warnings") or []) if isinstance(w, dict))
    r = sorted(_warning_fingerprint(w) for w in (rebuild.get("warnings") or []) if isinstance(w, dict))
    assert b == r, f"[{dsld_id}] warnings[] set changed"

    bg = sorted(_warning_fingerprint(w) for w in (baseline.get("warnings_profile_gated") or []) if isinstance(w, dict))
    rg = sorted(_warning_fingerprint(w) for w in (rebuild.get("warnings_profile_gated") or []) if isinstance(w, dict))
    assert bg == rg, f"[{dsld_id}] warnings_profile_gated[] set changed"


# ---------------------------------------------------------------------------
# Invariant 5 — top-level keys only gained E1.x additive fields
# ---------------------------------------------------------------------------

def test_toplevel_keys_only_gained_known_e1_additions(canary_pair) -> None:
    dsld_id, baseline, rebuild = canary_pair
    b_keys = set(baseline.keys())
    r_keys = set(rebuild.keys())
    net_new = r_keys - b_keys - E1_POST_E1_2_1_TOPLEVEL
    assert not net_new, (
        f"[{dsld_id}] unexpected net-new top-level keys: {sorted(net_new)}"
    )
    lost = b_keys - r_keys
    assert not lost, (
        f"[{dsld_id}] top-level keys dropped in rebuild: {sorted(lost)}"
    )
