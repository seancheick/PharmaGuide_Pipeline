"""Regression test pinning Thorne Omega Plus inactive-ingredient parsing.

This product is the canonical example for two parsing bugs we shipped fixes
for on 2026-05-02:

1. "Glycerin (from vegetable source) gelcap" was being mis-canonicalized to
   OI_HPMC_COMPOSITE because four glycerin-gelcap aliases lived on the HPMC
   entry. They've been removed; the substance now routes to
   NHA_VEGETABLE_GLYCERIN.

2. "Vitamin E (mixed tocopherols)" was being mis-canonicalized to the
   generic NHA_NATURAL_PRESERVATIVES blend instead of the more specific
   OI_TOCOPHEROL_PRESERVATIVE. Six tocopherol-specific aliases have been
   removed from NHA_NATURAL_PRESERVATIVES.

Also pins the omega3_dose_bonus form_disclosed flag, which is the new
informational signal added 2026-05-02 explaining why no A2 premium-delivery
credit was awarded when EPA/DHA dose IS disclosed but the molecular form
(rTG/EE/PL) is not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_other_ingredients() -> dict[str, dict]:
    data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
    return {entry["id"]: entry for entry in data["other_ingredients"]}


@pytest.fixture(scope="module")
def other_ingredients() -> dict[str, dict]:
    return _load_other_ingredients()


def test_hpmc_composite_does_not_claim_glycerin_aliases(other_ingredients):
    """OI_HPMC_COMPOSITE must not carry glycerin-gelcap aliases.

    HPMC (hydroxypropyl methylcellulose) is a different excipient from
    glycerin. The alias collision was causing softgel-shell labels like
    "Purified Water and Glycerin (vegetable source) gelcap" to map to a
    vegan HPMC capsule entry.
    """
    hpmc = other_ingredients["OI_HPMC_COMPOSITE"]
    aliases_lower = {a.lower() for a in hpmc.get("aliases", [])}
    forbidden = {
        "glycerin (from vegetable source) gelcap",
        "glycerin (vegetable source) gelcap",
        "glycerin gelcap",
        "purified water and glycerin (vegetable source) gelcap",
    }
    leaked = forbidden & aliases_lower
    assert not leaked, (
        f"HPMC Composite aliases must not include glycerin-gelcap variants; "
        f"found: {leaked}"
    )


def test_vegetable_glycerin_owns_the_glycerin_alias(other_ingredients):
    """Generic 'glycerin' must route to NHA_VEGETABLE_GLYCERIN."""
    glyc = other_ingredients["NHA_VEGETABLE_GLYCERIN"]
    aliases_lower = {a.lower() for a in glyc.get("aliases", [])}
    assert "glycerin" in aliases_lower
    assert glyc.get("functional_roles") == ["humectant", "solvent"]


def test_natural_preservatives_does_not_steal_tocopherol_aliases(other_ingredients):
    """NHA_NATURAL_PRESERVATIVES must not carry tocopherol-specific aliases.

    Tocopherol-specific aliases ("mixed tocopherols", "d-alpha tocopherol
    acetate", "natural vitamin E", "tocopherol blend", "E306") belong on
    OI_TOCOPHEROL_PRESERVATIVE so Vitamin E label entries get the precise
    standard_name. The generic 'Natural Preservatives' entry is for
    rosemary / ascorbyl palmitate blends.
    """
    nat = other_ingredients["NHA_NATURAL_PRESERVATIVES"]
    aliases_lower = {a.lower() for a in nat.get("aliases", [])}
    forbidden = {
        "mixed tocopherols",
        "d-alpha tocopherol acetate",
        "d-alpha-tocopherol acetate",
        "natural vitamin E".lower(),
        "tocopherol blend",
        "e306",
    }
    leaked = forbidden & aliases_lower
    assert not leaked, (
        f"Natural Preservatives aliases must not include tocopherol-specific "
        f"variants; found: {leaked}"
    )


def test_tocopherol_preservative_keeps_specific_aliases(other_ingredients):
    """OI_TOCOPHEROL_PRESERVATIVE owns 'mixed tocopherols' and friends."""
    tp = other_ingredients["OI_TOCOPHEROL_PRESERVATIVE"]
    aliases_lower = {a.lower() for a in tp.get("aliases", [])}
    required = {"mixed tocopherols", "tocopherol", "natural tocopherol"}
    missing = required - aliases_lower
    assert not missing, (
        f"OI_TOCOPHEROL_PRESERVATIVE must keep tocopherol-specific aliases; "
        f"missing: {missing}"
    )


def test_thorne_omega_plus_inactive_ingredient_canonical_targets(other_ingredients):
    """End-to-end pin: the four inactive ingredients on the Thorne Omega
    Plus label resolve to the right canonical entries with the right
    functional_roles[].

    Label: "Other Ingredients: Gelatin (bovine), Purified Water and Glycerin
    (vegetable source) gelcap, Vitamin E (mixed tocopherols)."
    """
    # OI_TOCOPHEROL_PRESERVATIVE gained antioxidant roles when Vitamin E
    # inactive aliases were added by the unified resolver (commit 3a113c9).
    # Vitamin E in inactive contexts is genuinely both: preservative (FDA
    # GRAS, protects oils from oxidation) and antioxidant (mechanism). Both
    # roles route to the same display label so the user-facing copy is
    # unchanged — locking "preservative" must be present, allowing
    # antioxidant variants to coexist.
    required_roles = [
        ("PII_GELATIN_CAPSULE", {"coating", "gelling_agent"}, True),     # exact
        ("PII_PURIFIED_WATER", {"solvent"}, True),                       # exact
        ("NHA_VEGETABLE_GLYCERIN", {"humectant", "solvent"}, True),      # exact
        ("OI_TOCOPHEROL_PRESERVATIVE", {"preservative"}, False),         # superset OK
    ]
    for entry_id, expected_roles, exact in required_roles:
        entry = other_ingredients.get(entry_id)
        assert entry is not None, f"missing canonical entry {entry_id}"
        actual = set(entry.get("functional_roles") or [])
        if exact:
            assert actual == expected_roles, (
                f"{entry_id} functional_roles drift: "
                f"got {actual}, expected {expected_roles}"
            )
        else:
            missing = expected_roles - actual
            assert not missing, (
                f"{entry_id} must contain {expected_roles}; missing: {missing}; "
                f"actual: {actual}"
            )


def test_omega3_form_disclosed_helper_detects_premium_forms():
    """The new _is_omega3_form_disclosed helper must detect rTG / EE / PL."""
    from scripts.score_supplements import SupplementScorer  # type: ignore

    helper = SupplementScorer._is_omega3_form_disclosed

    # Disclosed: explicit triglyceride form on EPA
    disclosed = {
        "activeIngredients": [
            {
                "canonical_id": "epa",
                "forms": [{"name": "EPA fish oil triglyceride"}],
            }
        ]
    }
    assert helper(disclosed) is True

    # Disclosed: phospholipid (krill)
    krill = {
        "activeIngredients": [
            {"canonical_id": "dha", "forms": [{"name": "DHA krill phospholipid"}]}
        ]
    }
    assert helper(krill) is True

    # NOT disclosed: only "Fish Oil" carrier (Thorne Omega Plus shape)
    bare = {
        "activeIngredients": [
            {
                "canonical_id": "epa",
                "forms": [{"name": "Fish Oil", "ingredientGroup": "Fish Oil"}],
            },
            {
                "canonical_id": "dha",
                "forms": [{"name": "Fish Oil", "ingredientGroup": "Fish Oil"}],
            },
        ]
    }
    assert helper(bare) is False

    # Word-bounded: "ee" alone does NOT match "concentrate"
    coincidence = {
        "activeIngredients": [
            {"canonical_id": "epa", "forms": [{"name": "concentrate"}]}
        ]
    }
    assert helper(coincidence) is False
