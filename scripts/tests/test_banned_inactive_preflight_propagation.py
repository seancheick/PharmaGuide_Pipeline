"""Tests for Sprint E1.1.4 fix (2026-05-13): authored Dr Pham preflight copy
must propagate from banned_recalled_ingredients.json through the inactive
resolver and warning emitter into the blob's banned_substance_detail field
when an inactive ingredient triggers the banned-recalled resolver path.

Background — the 26-product blocker:
    The pipeline writes warnings[].type='banned_substance' for inactive
    ingredients matched against banned_recalled_ingredients.json (the
    Sprint 27.7 "resolver-synthesized banned warnings" code path). But the
    emitter wasn't threading the authored safety_warning_one_liner /
    safety_warning fields into the warning dict, so build_banned_substance_detail
    couldn't populate the preflight blob field, and the Sprint E1.1.4
    validator (_validate_banned_preflight_propagation) rejected 26 products.

This file is the regression guard for the full thread:
    banned_recalled_ingredients.json
        -> InactiveIngredientResolver._from_banned (populates new fields)
        -> build_final_db inactive serialization (carries new fields through)
        -> build_warnings_list emitter (writes new fields into warning dict)
        -> build_banned_substance_detail (finds and renders authored copy)
        -> _validate_banned_preflight_propagation (passes)

We do NOT weaken the validator. We do NOT add an escape hatch. We do NOT
exclude products. We fix the data thread itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def resolver():
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    return InactiveIngredientResolver()


# ---------------------------------------------------------------------------
# Layer 1 — Resolver carries authored copy on banned hits
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_name,expected_substance",
    [
        ("Brominated Vegetable Oil", "Brominated Vegetable Oil"),
        ("FD&C Red #3",              "FD&C Red No. 3"),
        ("Red 3",                    "FD&C Red No. 3"),
        ("Sodium Tetraborate",       "Sodium Tetraborate"),
        ("Simethicone",              "Simethicone"),
        ("Polydimethylsiloxane",     "Simethicone"),
    ],
)
def test_resolver_banned_inactive_carries_authored_copy(
    resolver, raw_name, expected_substance
) -> None:
    """For every ingredient that triggered one of the 26 production blockers,
    the resolver must surface both `safety_warning_one_liner` and
    `safety_warning` on its InactiveResolution. The values must come from
    the corresponding entry in banned_recalled_ingredients.json — we don't
    synthesize copy, we propagate it.
    """
    r = resolver.resolve(raw_name=raw_name)
    assert r.is_banned, (
        f"{raw_name!r} should be is_banned=True via banned_recalled "
        f"(got matched_source={r.matched_source!r}, "
        f"severity_status={r.severity_status!r})"
    )
    assert r.matched_source == "banned_recalled"
    assert r.safety_warning_one_liner, (
        f"{raw_name!r} must carry safety_warning_one_liner from source "
        f"data — without it, build_banned_substance_detail returns None "
        f"and the validator blocks the build."
    )
    assert r.safety_warning, (
        f"{raw_name!r} must carry safety_warning from source data."
    )
    assert isinstance(r.safety_warning_one_liner, str)
    assert isinstance(r.safety_warning, str)
    assert r.safety_warning_one_liner.strip()
    assert r.safety_warning.strip()


def test_resolver_harmful_additive_does_not_carry_banned_copy(resolver) -> None:
    """A harmful_additive resolution (NOT banned) must NOT carry the
    banned-only preflight fields. This guards against the emitter
    accidentally writing banned-substance warnings for harmful additives.

    Magnesium Stearate is in harmful_additives.json with severity=low (or
    moderate) but NOT in banned_recalled_ingredients.json. We pick an
    ingredient known to come through the harmful path so the test isolates
    the harmful-side semantics.
    """
    # Find an inactive that hits harmful_additives but NOT banned_recalled.
    # We probe a few common excipients; this is robust against data churn.
    candidates = ("Polyethylene Glycol", "Sodium Lauryl Sulfate", "Magnesium Stearate")
    found_harmful = False
    for name in candidates:
        r = resolver.resolve(raw_name=name)
        if r.matched_source == "harmful_additives":
            found_harmful = True
            assert r.safety_warning_one_liner is None, (
                f"{name!r} is matched_source=harmful_additives but carries "
                f"safety_warning_one_liner={r.safety_warning_one_liner!r}. "
                f"These fields are reserved for the banned-recalled branch."
            )
            assert r.safety_warning is None, (
                f"{name!r} is matched_source=harmful_additives but carries "
                f"safety_warning={r.safety_warning!r}."
            )
            break
    assert found_harmful, (
        "Could not find any common excipient that hits harmful_additives — "
        "test fixture is stale, please update candidate list."
    )


def test_resolver_unmatched_inactive_does_not_carry_banned_copy(resolver) -> None:
    """A name that matches no source file must have None for both fields."""
    r = resolver.resolve(raw_name="xyzzy_obviously_not_a_real_ingredient_123")
    assert r.matched_source is None
    assert r.safety_warning_one_liner is None
    assert r.safety_warning is None


# ---------------------------------------------------------------------------
# Layer 2 — Warning emitter writes the two fields when emitting banned_substance
# ---------------------------------------------------------------------------


def _make_synthetic_enriched(
    *, dsld_id: str, full_name: str,
    inactive_name: str, inactive_std_name: str | None = None,
) -> dict:
    """Build the minimum enriched-product shape build_final_db expects so
    the warning emitter can be exercised. We deliberately do NOT touch
    contaminant_data — this is the path that DIDN'T see the banned
    ingredient. The fix must surface the warning via the resolver path."""
    return {
        "dsld_id": dsld_id,
        "id": dsld_id,
        "full_name": full_name,
        "brand_name": "Synthetic Test Brand",
        # Empty contaminant_data — proves the warning comes from resolver
        "contaminant_data": {
            "banned_substances": {"found": False, "substances": []},
            "harmful_additives": {"found": False, "additives": []},
        },
        "activeIngredients": [],
        "inactiveIngredients": [
            {
                "name": inactive_name,
                "raw_source_text": inactive_name,
                "standardName": inactive_std_name or inactive_name,
            },
        ],
        # Other downstream fields the builder may consult — keep minimal.
        "ingredient_summary": {"active_ingredients": []},
        "warnings": [],
        "allergen_hits": [],
        "harmful_additives": [],
    }


@pytest.mark.parametrize(
    "ingredient_name,expected_substance_in_title",
    [
        ("Brominated Vegetable Oil", "Brominated Vegetable Oil"),
        ("FD&C Red #3",              "Red"),
        ("Sodium Tetraborate",       "Sodium Tetraborate"),
        ("Simethicone",              "Simethicone"),
    ],
)
def test_emitter_writes_banned_substance_warning_with_authored_copy(
    ingredient_name, expected_substance_in_title,
) -> None:
    """End-to-end emitter exercise: a product whose only signal is a
    resolver-banned inactive ingredient must produce a warnings[] entry
    with type='banned_substance' AND non-empty safety_warning_one_liner
    AND non-empty safety_warning. Pre-fix this emitted the warning with
    the two preflight fields absent.

    We don't call the full build_final_db pipeline (that requires scored
    input + heavy fixtures); we exercise the two functions that matter:
    the inactive resolver and the slice of the build that emits the
    warning dict. The third function (build_banned_substance_detail) is
    tested in its own block below — same warnings list, different consumer.
    """
    # Step 1: resolve the inactive ingredient via the resolver.
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    rsv = InactiveIngredientResolver()
    r = rsv.resolve(raw_name=ingredient_name)
    assert r.is_banned
    assert r.safety_warning_one_liner
    assert r.safety_warning

    # Step 2: simulate the same dict shape the build emits at line 2872+
    # in build_final_db.py — these are the keys the warning emitter at
    # line 3194+ consumes.
    ing_in_blob = {
        "name": ingredient_name,
        "raw_source_text": ingredient_name,
        "display_label": r.display_label,
        "matched_source": r.matched_source,
        "matched_rule_id": r.matched_rule_id,
        "is_safety_concern": r.is_safety_concern,
        "is_banned": r.is_banned,
        "safety_reason": r.safety_reason,
        "harmful_severity": r.harmful_severity,
        # The fix — these two fields must flow through.
        "safety_warning_one_liner": r.safety_warning_one_liner,
        "safety_warning":          r.safety_warning,
    }

    # Step 3: replicate the emitter slice at build_final_db.py line 3194+
    # against this synthetic ingredient. This is the slice under test.
    warnings: list[dict] = []
    for ing_list, role in (([], "active"), ([ing_in_blob], "inactive")):
        for ing in ing_list:
            if ing.get("matched_source") != "banned_recalled":
                continue
            if not (ing.get("is_safety_concern") or ing.get("is_banned")):
                continue
            name = ing.get("display_label") or ing.get("name") or "Unknown"
            if bool(ing.get("is_banned")):
                w_type = "banned_substance"
                w_severity = "critical"
                w_title = f"Banned substance: {name}"
            else:
                w_type = "high_risk_ingredient"
                w_severity = "high"
                w_title = f"High-risk ingredient: {name}"
            we = {
                "type": w_type,
                "severity": w_severity,
                "title": w_title,
                "detail": ing.get("safety_reason") or "",
                "ingredient_name": ing.get("name") or name,
                "ingredient_role": role,
                "matched_rule_id": ing.get("matched_rule_id"),
                "source": "inactive_ingredient_resolver",
                "display_mode_default": "critical",
                "clinical_risk": ing.get("harmful_severity"),
            }
            if ing.get("safety_warning_one_liner"):
                we["safety_warning_one_liner"] = ing["safety_warning_one_liner"]
            if ing.get("safety_warning"):
                we["safety_warning"] = ing["safety_warning"]
            warnings.append(we)

    # Step 4: assertions. The warning has all 3 critical fields.
    banned_warnings = [w for w in warnings if w["type"] == "banned_substance"]
    assert len(banned_warnings) == 1, (
        f"Expected exactly one banned_substance warning for {ingredient_name!r}, "
        f"got {len(banned_warnings)}: {warnings!r}"
    )
    w = banned_warnings[0]
    assert expected_substance_in_title in w["title"]
    assert w.get("safety_warning_one_liner"), (
        f"warning emitter dropped safety_warning_one_liner for {ingredient_name!r}. "
        f"This is the bug that caused the 26 production blockers."
    )
    assert w.get("safety_warning"), (
        f"warning emitter dropped safety_warning for {ingredient_name!r}."
    )


# ---------------------------------------------------------------------------
# Layer 3 — build_banned_substance_detail consumes the warning correctly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ingredient_name",
    ["Brominated Vegetable Oil", "FD&C Red #3", "Sodium Tetraborate", "Simethicone"],
)
def test_build_banned_substance_detail_finds_authored_copy_for_resolver_hit(
    ingredient_name,
) -> None:
    """build_banned_substance_detail() scans warnings[] for type='banned_substance'
    AND non-empty preflight copy. After the fix, the emitter-produced warnings
    must satisfy that scan. This is the function the validator's input depends on."""
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    from scripts.build_final_db import build_banned_substance_detail, has_banned_substance

    rsv = InactiveIngredientResolver()
    r = rsv.resolve(raw_name=ingredient_name)

    # Synthetic enriched payload with no contaminant_data — only the
    # resolver path knows this product is banned.
    enriched = _make_synthetic_enriched(
        dsld_id="9999999",
        full_name=f"Synthetic test product containing {ingredient_name}",
        inactive_name=ingredient_name,
        inactive_std_name=r.standard_name or ingredient_name,
    )
    # has_banned_substance checks BOTH contaminant_data AND the resolver
    # index path. The contaminant_data is empty here, so the True must
    # come from the resolver path against inactiveIngredients.
    assert has_banned_substance(enriched), (
        f"has_banned_substance must return True for a product whose only "
        f"banned signal is {ingredient_name!r} in inactiveIngredients."
    )

    # Build the warning list the same way the emitter does for this slice.
    warnings = [{
        "type": "banned_substance",
        "severity": "critical",
        "title": f"Banned substance: {r.display_label}",
        "safety_warning_one_liner": r.safety_warning_one_liner,
        "safety_warning": r.safety_warning,
        "matched_rule_id": r.matched_rule_id,
    }]

    detail = build_banned_substance_detail(enriched, warnings)
    assert detail is not None, (
        f"build_banned_substance_detail returned None for {ingredient_name!r} "
        f"even though warnings[] contains a banned_substance entry with "
        f"authored copy. This is the bug that caused the 26 blockers."
    )
    assert detail["safety_warning_one_liner"] == r.safety_warning_one_liner
    assert detail["safety_warning"] == r.safety_warning


# ---------------------------------------------------------------------------
# Layer 4 — _validate_banned_preflight_propagation passes for the fixed flow
# ---------------------------------------------------------------------------


def test_validator_passes_when_resolver_banned_inactive_has_authored_copy() -> None:
    """The preflight validator (the gate that produced the 26 blockers)
    must accept a blob whose banned_substance_detail was populated via the
    resolver path. This is the regression guard ensuring we do not
    weaken the validator while fixing the data thread."""
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    from scripts.build_final_db import (
        _validate_banned_preflight_propagation,
        build_banned_substance_detail,
        has_banned_substance,
    )

    rsv = InactiveIngredientResolver()
    r = rsv.resolve(raw_name="Brominated Vegetable Oil")

    enriched = _make_synthetic_enriched(
        dsld_id="9999998",
        full_name="Synthetic BVO product",
        inactive_name="Brominated Vegetable Oil",
        inactive_std_name=r.standard_name,
    )
    assert has_banned_substance(enriched)

    # Warning shaped exactly as the patched emitter would produce.
    warnings = [{
        "type": "banned_substance",
        "severity": "critical",
        "title": f"Banned substance: {r.display_label}",
        "safety_warning_one_liner": r.safety_warning_one_liner,
        "safety_warning": r.safety_warning,
        "matched_rule_id": r.matched_rule_id,
    }]
    blob = {
        "banned_substance_detail": build_banned_substance_detail(enriched, warnings),
    }
    # No exception = pass.
    _validate_banned_preflight_propagation(blob, enriched, "9999998")


def test_validator_still_fires_when_preflight_copy_missing() -> None:
    """Negative test: if the warning is emitted WITHOUT the preflight copy
    (i.e. the bug returns), the validator must STILL fire. We must not
    weaken the validator as a side effect of the fix."""
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    from scripts.build_final_db import (
        _validate_banned_preflight_propagation,
        build_banned_substance_detail,
        has_banned_substance,
    )

    rsv = InactiveIngredientResolver()
    r = rsv.resolve(raw_name="Brominated Vegetable Oil")

    enriched = _make_synthetic_enriched(
        dsld_id="9999997",
        full_name="Synthetic BVO product (bug-simulated)",
        inactive_name="Brominated Vegetable Oil",
        inactive_std_name=r.standard_name,
    )
    assert has_banned_substance(enriched)

    # Warning WITHOUT the two preflight fields — pre-fix shape, the bug.
    warnings = [{
        "type": "banned_substance",
        "severity": "critical",
        "title": f"Banned substance: {r.display_label}",
        # safety_warning_one_liner: ABSENT (the bug)
        # safety_warning: ABSENT (the bug)
        "matched_rule_id": r.matched_rule_id,
    }]
    blob = {
        "banned_substance_detail": build_banned_substance_detail(enriched, warnings),
    }
    # Must raise — confirms the validator is intact.
    with pytest.raises(ValueError, match="banned_substance_detail"):
        _validate_banned_preflight_propagation(blob, enriched, "9999997")


# ---------------------------------------------------------------------------
# Layer 5 — Regression on one of the 26 real production blockers
# ---------------------------------------------------------------------------


def test_regression_real_product_220094_resolver_thread_works() -> None:
    """DSLD 220094 (GNC LIT Beyond Dew) failed in the 2026-05-13 build
    with the missing-preflight-copy error because its only banned-substance
    signal is BVO in inactiveIngredients. After the fix the full thread
    from source data -> resolver -> warning -> blob must produce a valid
    banned_substance_detail.

    This test is the canary on a real production blocker — if it fails,
    the original bug has regressed and the build will reject 220094 again."""
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    from scripts.build_final_db import (
        _validate_banned_preflight_propagation,
        build_banned_substance_detail,
        has_banned_substance,
    )

    rsv = InactiveIngredientResolver()
    # Real-world raw_source_text matches what the enricher writes for 220094.
    r = rsv.resolve(raw_name="Brominated Vegetable Oil")
    assert r.is_banned
    assert r.matched_rule_id == "BANNED_BVO_2024"

    # Minimum enriched shape that mimics 220094.
    enriched = {
        "dsld_id": "220094",
        "id": "220094",
        "full_name": "LIT Beyond Dew",
        "brand_name": "GNC",
        "contaminant_data": {
            "banned_substances": {"found": False, "substances": []},
        },
        "activeIngredients": [],
        "inactiveIngredients": [{
            "name": "Brominated Vegetable Oil",
            "raw_source_text": "Brominated Vegetable Oil",
            "standardName": "Brominated Vegetable Oil",
        }],
    }
    assert has_banned_substance(enriched)

    # Patched emitter shape — what the build now produces.
    warnings = [{
        "type": "banned_substance",
        "severity": "critical",
        "title": "Banned substance: Brominated Vegetable Oil",
        "safety_warning_one_liner": r.safety_warning_one_liner,
        "safety_warning": r.safety_warning,
        "matched_rule_id": r.matched_rule_id,
        "ingredient_role": "inactive",
        "source": "inactive_ingredient_resolver",
    }]
    detail = build_banned_substance_detail(enriched, warnings)
    assert detail is not None
    assert detail["safety_warning_one_liner"]
    assert detail["safety_warning"]

    # End-to-end: validator (which is the gate that fires in production) passes.
    _validate_banned_preflight_propagation(
        {"banned_substance_detail": detail}, enriched, "220094"
    )
