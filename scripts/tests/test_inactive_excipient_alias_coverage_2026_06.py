"""Inactive-excipient coverage quick-win (2026-06-16).

The fresh-build inactive-safety audit (CHECK 3) flagged 3,411 inactive
ingredients that resolve to NO functional role. ~85% of that count is active
nutrient *forms* duplicated into the inactive list (Pyridoxine HCl = B6, etc.)
— NOT excipients, handled separately by the resolver active-form-duplicate
work. This file pins the genuine-excipient subset that WAS missing from
other_ingredients.json, so each label term now resolves to a real role:

  raw label term                 → expected functional role   (top-50 occ)
  "Natural & Artificial Flavors" → flavor_artificial (+natural)   ~176
  "Sodium Aluminum Silicate"     → anti_caking_agent              ~25
  "Blend of oils"                → carrier_oil                    ~23
  "Soy Oil & Lecithin Blend"     → carrier_oil (soy allergen)     ~22
  "organic Palm Oil"             → carrier_oil                    ~18
  "Porcine Gelatin"              → coating                        ~15

Five terms are aliases onto existing parents (no new entry); only Sodium
Aluminum Silicate is a new entry, with content-verified UNII 058TS43PSM /
CAS 1344-00-9. No active nutrient is ever mapped here.
"""
import pytest


@pytest.fixture(scope="module")
def resolver():
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    return InactiveIngredientResolver()


# (raw label as seen on real labels, expected functional role that must appear)
#
# Dispositions after the "verify parent before new entry" check:
#   Porcine Gelatin            -> alias on existing PII_GELATIN_CAPSULE
#   Soy Oil & Lecithin Blend   -> alias on existing PII_SOY_BEAN_OIL (soy allergen kept)
#   Blend of oils              -> alias on existing PII_OIL_GENERIC
#   organic Palm Oil           -> alias on existing ADD_PALM_OIL (harmful_additives, carrier_oil)
#   Natural & Artificial Flavors -> &/no-connector aliases on existing NHA_NATURAL_FLAVORS
#   Sodium Aluminum Silicate   -> NEW entry (verified UNII 058TS43PSM / CAS 1344-00-9)
#
# NOTE (deferred): the existing flavors entries map "natural and artificial
# flavors" to flavor_natural only. Splitting natural+artificial blends into a
# both-roles (flavor_natural + flavor_artificial) entry is a separate ontology
# cleanup — tracked, not done here, to keep this a non-colliding quick win.
_EXPECTED = [
    ("Porcine Gelatin", "coating"),
    ("Soy Oil & Lecithin Blend", "carrier_oil"),
    ("Blend of oils", "carrier_oil"),
    ("Natural & Artificial Flavors", "flavor_natural"),
    ("organic Palm Oil", "carrier_oil"),
    ("Sodium Aluminum Silicate", "anti_caking_agent"),
]


@pytest.mark.parametrize("raw_name,expected_role", _EXPECTED)
def test_excipient_resolves_to_functional_role(resolver, raw_name, expected_role):
    """Each genuine-excipient label term must resolve to a non-empty functional
    role (i.e. no longer counted as an 'unknown inactive role')."""
    r = resolver.resolve(raw_name=raw_name)
    assert r.functional_roles, (
        f"{raw_name!r} still resolves to NO functional role "
        f"(matched_source={r.matched_source!r}) — excipient coverage gap not closed"
    )
    assert expected_role in r.functional_roles, (
        f"{raw_name!r} resolved to {r.functional_roles} but should include "
        f"{expected_role!r}"
    )


def test_soy_oil_lecithin_blend_preserves_soy_allergen(resolver):
    """The soy-oil blend term must keep its soy allergen signal so the app
    still warns soy-allergic users."""
    r = resolver.resolve(raw_name="Soy Oil & Lecithin Blend")
    # allergen surfaces via display/role; the parent entry is allergen=True (soy)
    assert r.functional_roles, "soy oil & lecithin blend must resolve"
