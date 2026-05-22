"""RC-1: Coffee routing — §8.5 cleanup + v6 contract completion.

Background

SB-2 (commit eff29b3d, 2026-05-22) introduced the v6
bonus-eligibility contract on standardized_botanicals.green_coffee_bean
and created a sibling plain-identity entry
botanical_ingredients.coffee_bean_plain for unstandardized
"Coffee Bean Extract" / "Coffea robusta Seed Extract" labels.

What SB-2 did NOT clean up

  - botanical_ingredients.coffee_fruit (UNII HOX6BEK27Q — coffea
    arabica FRUIT, not the bean) still carries BEAN aliases:
        'Svetol Green Coffee bean extract'
        'green coffee bean coffea robusta extract'
        'C. canephora robusta extract'
        'green coffee seed extract'
        'green coffee (beans) pe'
        'Slimpure decaffeinated green coffee extract' (+ variants)
        'decaffeinated green coffee extract'
    These are SEED/BEAN products misplaced into the FRUIT entry,
    classic §8.5 contamination. Seeds and fruits of Coffea arabica
    have different UNIIs, different chemistry, and different
    clinical literatures (NeuroFactor/CognatiQ for the fruit vs
    Svetol/GCA for the bean).

  - botanical_ingredients.coffee_bean_plain has external_ids={}
    — missing UNII. FDA cache has JFH385Y744 = 'coffee bean'
    (species-agnostic, the right canonical for the catch-all entry).

  - standardized_botanicals.coffeeberry has external_ids={} and
    NO v6 contract fields. CoffeeBerry® is the branded standardized
    extract of the whole coffee fruit (chlorogenic acid % marker).
    UNII HOX6BEK27Q (arabica fruit) is the correct identity.

  - standardized_botanicals.green_coffee_bean has external_ids={}
    — missing UNII. FDA cache has V5032728L7 = 'robusta coffee
    bean' / 'coffea robusta seed powder'; the Svetol/GCA chlorogenic-
    acid pathway is predominantly robusta-sourced and chemistry-wise
    that is the closest single substance UNII.

RC-1 scope

  1. Remove §8.5 bean aliases from coffee_fruit. Each bean alias
     either moves to coffee_bean_plain (no bonus) or stays only on
     green_coffee_bean (marker-explicit, runtime-gated bonus).
  2. Set external_ids.unii on coffee_bean_plain (JFH385Y744).
  3. Set external_ids.unii on green_coffee_bean (V5032728L7).
  4. Set external_ids.unii on coffeeberry (HOX6BEK27Q) and
     annotate with v6 contract (basis=branded_extract for
     CoffeeBerry®, marker_compounds=chlorogenic acids/polyphenols,
     bonus_rationale, sources).

Out of scope

  - Splitting coffee_bean_plain into species-precise arabica vs
    robusta entries — defer until products surface that need that
    granularity. The combined entry handles current label surface.
  - Moving CoffeeBerry® branded aliases (KonaRed, NeuroFactor®,
    CognatiQ) between coffee_fruit and coffeeberry — current
    placement keeps NeuroFactor/CognatiQ on the IDENTITY entry
    (coffee_fruit, no bonus) because their clinical literature
    cites whole-fruit chlorogenic acids, not standardized %.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def bot() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "botanical_ingredients.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def sbot() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "standardized_botanicals.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


# ----- coffee_fruit §8.5 cleanup -----

# Bean/seed phrases that have no business in the FRUIT entry. The
# test forbids any alias containing these substrings on coffee_fruit.
FORBIDDEN_BEAN_TOKENS_IN_FRUIT_ENTRY = (
    "svetol",
    "green coffee bean",
    "green coffee seed",
    "green coffee (beans)",
    "coffea robusta extract",
    "c. canephora robusta extract",
    "decaffeinated green coffee",  # decaffeinated GCB is bean prep
    "slimpure",  # Slimpure® = green coffee bean extract brand
)


def test_coffee_fruit_has_correct_unii(bot):
    e = _find(bot.get("botanical_ingredients", []), "coffee_fruit")
    assert e, "coffee_fruit entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "HOX6BEK27Q", (
        f"coffee_fruit external_ids.unii must be 'HOX6BEK27Q' "
        f"(COFFEA ARABICA FRUIT — the FRUIT/CHERRY, not the bean). "
        f"Got: {e.get('external_ids')}"
    )


def test_coffee_fruit_has_no_bean_aliases(bot):
    """§8.5: bean/seed aliases must not live in the FRUIT entry —
    they belong in coffee_bean_plain (plain) or green_coffee_bean
    (marker-standardized)."""
    e = _find(bot.get("botanical_ingredients", []), "coffee_fruit")
    aliases = _lc(e.get("aliases", []))
    violations = []
    for a in aliases:
        for forbidden in FORBIDDEN_BEAN_TOKENS_IN_FRUIT_ENTRY:
            if forbidden in a:
                violations.append((a, forbidden))
                break
    assert not violations, (
        f"§8.5: coffee_fruit (UNII HOX6BEK27Q, the FRUIT/CHERRY) "
        f"must not carry BEAN/SEED aliases. Each offending alias "
        f"belongs in either botanical_ingredients.coffee_bean_plain "
        f"(plain identity, no bonus) or "
        f"standardized_botanicals.green_coffee_bean "
        f"(marker-explicit, runtime-gated bonus). "
        f"Violations (alias → forbidden_token): {violations}"
    )


def test_coffee_fruit_retains_fruit_brand_aliases(bot):
    """Branded WHOLE-FRUIT extracts (CoffeeBerry®, NeuroFactor®,
    CognatiQ, KonaRed) should remain on the fruit identity entry
    — their clinical literature cites whole-fruit chlorogenic
    acids, not standardized marker %."""
    e = _find(bot.get("botanical_ingredients", []), "coffee_fruit")
    aliases = _lc(e.get("aliases", []))
    for required in ("coffee fruit extract", "coffeeberry"):
        assert any(required in a for a in aliases), (
            f"coffee_fruit must retain '{required}' (whole-fruit "
            f"identity). Got: {e.get('aliases')}"
        )


# ----- coffee_bean_plain UNII -----

def test_coffee_bean_plain_has_unii(bot):
    """coffee_bean_plain is the species-agnostic catch-all for
    unstandardized 'Coffee Bean Extract' / 'Coffea robusta Seed
    Extract' labels. FDA UNII 'coffee bean' (JFH385Y744) is the
    matching species-agnostic substance identifier."""
    e = _find(bot.get("botanical_ingredients", []), "coffee_bean_plain")
    assert e, "coffee_bean_plain entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "JFH385Y744", (
        f"coffee_bean_plain external_ids.unii must be 'JFH385Y744' "
        f"(COFFEE BEAN — species-agnostic). Got: {e.get('external_ids')}"
    )


def test_coffee_bean_plain_no_bonus_attribute(bot):
    """Per SB-2 contract: coffee_bean_plain explicitly does NOT
    grant the A5b bonus. attributes.bonus_eligible must remain
    false."""
    e = _find(bot.get("botanical_ingredients", []), "coffee_bean_plain")
    attrs = e.get("attributes") or {}
    assert attrs.get("bonus_eligible") is False, (
        f"coffee_bean_plain.attributes.bonus_eligible must remain "
        f"False (no bonus from plain identity). Got: "
        f"{attrs.get('bonus_eligible')!r}"
    )


# ----- green_coffee_bean UNII (v6 contract already done in SB-2) -----

def test_green_coffee_bean_has_unii(sbot):
    """SB-2 left external_ids={} on green_coffee_bean. The Svetol/GCA
    chlorogenic-acid pathway is predominantly robusta-sourced; FDA
    UNII V5032728L7 (ROBUSTA COFFEE BEAN / COFFEA ROBUSTA SEED
    POWDER) is the closest single canonical substance UNII for
    the standardized extract."""
    e = _find(sbot.get("standardized_botanicals", []), "green_coffee_bean")
    assert e, "green_coffee_bean entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "V5032728L7", (
        f"green_coffee_bean external_ids.unii must be 'V5032728L7' "
        f"(ROBUSTA COFFEE BEAN / COFFEA ROBUSTA SEED POWDER). "
        f"Got: {e.get('external_ids')}"
    )


def test_green_coffee_bean_v6_contract_preserved(sbot):
    """SB-2 added bonus_eligible / basis / marker_compounds /
    bonus_rationale / sources. Pin them so future edits cannot
    quietly remove the contract."""
    e = _find(sbot.get("standardized_botanicals", []), "green_coffee_bean")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("chlorogenic" in m or "gca" in m for m in markers), (
        f"green_coffee_bean marker_compounds must include "
        f"chlorogenic acids / GCA. Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


# ----- coffeeberry v6 contract + UNII -----

def test_coffeeberry_has_unii(sbot):
    """CoffeeBerry® is the branded standardized extract of the
    whole coffee fruit. Identity UNII HOX6BEK27Q (COFFEA ARABICA
    FRUIT) matches because the extract IS the fruit, standardized
    to chlorogenic acid %."""
    e = _find(sbot.get("standardized_botanicals", []), "coffeeberry")
    assert e, "coffeeberry entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "HOX6BEK27Q", (
        f"coffeeberry external_ids.unii must be 'HOX6BEK27Q' "
        f"(COFFEA ARABICA FRUIT — the branded standardized FRUIT "
        f"extract). Got: {e.get('external_ids')}"
    )


def test_coffeeberry_v6_contract_fields(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "coffeeberry")
    assert e.get("bonus_eligible") is True
    # CoffeeBerry® is a BRANDED standardized extract — branded_extract
    # basis is the correct annotation. marker_percent also acceptable
    # since the bonus actually fires on % chlorogenic acid label.
    assert e.get("standardization_basis") in ("branded_extract", "marker_percent"), (
        f"coffeeberry standardization_basis must be branded_extract "
        f"or marker_percent. Got: {e.get('standardization_basis')!r}"
    )
    markers = _lc(e.get("marker_compounds") or [])
    assert any("chlorogenic" in m or "polyphenol" in m for m in markers), (
        f"coffeeberry marker_compounds must include chlorogenic "
        f"acids / polyphenols. Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


def test_coffeeberry_carries_marker_explicit_alias(sbot):
    """CoffeeBerry® should carry a marker-explicit alias so the
    runtime meets_threshold gate has a fingerprint to detect."""
    e = _find(sbot.get("standardized_botanicals", []), "coffeeberry")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("chlorogenic" in a or "polyphenol" in a))
        or "% chlorogenic" in a
        or "coffeeberry" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"coffeeberry must carry at least one marker-explicit alias "
        f"(CoffeeBerry brand mention or chlorogenic-acid % phrase). "
        f"Got: {e.get('aliases')}"
    )


# ----- Cross-entry contract: Svetol routing -----

def test_svetol_lives_only_in_green_coffee_bean(bot, sbot):
    """Svetol® is a Naturex-branded green coffee BEAN extract
    (45-50% chlorogenic acids). It must live in
    standardized_botanicals.green_coffee_bean (the bonus pathway)
    and must NOT appear in coffee_fruit (it's not a fruit
    extract)."""
    fruit = _find(bot.get("botanical_ingredients", []), "coffee_fruit")
    gcb = _find(sbot.get("standardized_botanicals", []), "green_coffee_bean")
    fruit_aliases = _lc(fruit.get("aliases", []))
    gcb_aliases = _lc(gcb.get("aliases", []))
    assert not any("svetol" in a for a in fruit_aliases), (
        f"§8.5: 'Svetol' (green coffee BEAN extract) must not "
        f"alias coffee_fruit. Got: {fruit.get('aliases')}"
    )
    assert any("svetol" in a for a in gcb_aliases), (
        f"'Svetol' must alias green_coffee_bean (its actual "
        f"identity). Got: {gcb.get('aliases')}"
    )
