#!/usr/bin/env python3
"""Scoring allowlists may only name canonicals the vocabulary actually defines.

An allowlist entry that no vocabulary defines can never match a row, so the
policy it encodes is silently inert -- it reads as active review and behaves as
a no-op. That failure mode has shipped more than once: ``negative_match_terms``
were validated for shape but never applied at match time, and
``DRI_ESSENTIAL_NUTRIENTS`` carried ``vitamin_b5_pantothenic_acid`` while every
label row canonicalises to ``vitamin_b5_pantothenic``.

The vocabulary sources here are the same files the production resolvers read,
so this gate cannot drift from what the pipeline can actually emit.
"""

from __future__ import annotations

import json
from typing import Dict, FrozenSet, Set

import pytest

from constants import INGREDIENT_QUALITY_MAP, STANDARDIZED_BOTANICALS
import scoring_input_contract as sic
from scoring_v4 import route_features as rf
from scoring_v4.modules import sports_helpers as sh
from scoring_v4.modules.generic_evidence import DRI_ESSENTIAL_NUTRIENTS


# Identities the pipeline mints for product-level dose projections. No
# ingredient vocabulary defines them because no label row declares them; they
# are produced by the scoring input contract itself.
PIPELINE_DERIVED_CANONICALS: FrozenSet[str] = frozenset({
    "epa_dha",
    "probiotic_cfu_total",
})


def _standardized_botanical_ids() -> Set[str]:
    raw = json.loads(STANDARDIZED_BOTANICALS.read_text())
    return {
        str(entry.get("id"))
        for entry in raw.get("standardized_botanicals", [])
        if isinstance(entry, dict) and entry.get("id")
    }


def _known_canonicals() -> Set[str]:
    """Every canonical id the enricher can emit for a label row."""
    iqm = set(json.loads(INGREDIENT_QUALITY_MAP.read_text()))
    return (
        {key for key in iqm if not key.startswith("_")}
        | set(sic._botanical_identity_lookup())
        | _standardized_botanical_ids()
        | set(PIPELINE_DERIVED_CANONICALS)
    )


# Allowlists whose members must be real, emittable canonical ids. Routing,
# evidence authority, and disqualification all key off canonical_id equality,
# so an entry outside the vocabulary is dead weight by construction.
GOVERNED_ALLOWLISTS: Dict[str, FrozenSet[str]] = {
    "generic_evidence.DRI_ESSENTIAL_NUTRIENTS": frozenset(DRI_ESSENTIAL_NUTRIENTS),
    "route_features.B_VITAMIN_CANONICALS": frozenset(rf.B_VITAMIN_CANONICALS),
    "route_features.NON_B_VITAMIN_CANONICALS": frozenset(rf.NON_B_VITAMIN_CANONICALS),
    "route_features.MINERAL_CANONICALS": frozenset(rf.MINERAL_CANONICALS),
    "scoring_input_contract._CLASSIFICATION_MINERAL_CANONICALS": frozenset(
        sic._CLASSIFICATION_MINERAL_CANONICALS
    ),
    "scoring_input_contract._ROUTE_MULTI_PANEL_CANONICALS": frozenset(
        sic._ROUTE_MULTI_PANEL_CANONICALS
    ),
    "scoring_input_contract._ROUTE_PRENATAL_PANEL_ANCHORS": frozenset(
        sic._ROUTE_PRENATAL_PANEL_ANCHORS
    ),
    "scoring_input_contract._ROUTE_OMEGA_PARENT_CANONICALS": frozenset(
        sic._ROUTE_OMEGA_PARENT_CANONICALS
    ),
    "scoring_input_contract._ROUTE_OMEGA_INGREDIENT_CANONICALS": frozenset(
        sic._ROUTE_OMEGA_INGREDIENT_CANONICALS
    ),
    "scoring_input_contract._ROUTE_EAA_CANONICALS": frozenset(sic._ROUTE_EAA_CANONICALS),
    "scoring_input_contract._ROUTE_BCAA_CANONICALS": frozenset(sic._ROUTE_BCAA_CANONICALS),
    "scoring_input_contract._ROUTE_B_COMPLEX_DISQUALIFY_CANONICALS": frozenset(
        sic._ROUTE_B_COMPLEX_DISQUALIFY_CANONICALS
    ),
    "sports_helpers.SPORTS_PROTEIN_CANONICALS": frozenset(sh.SPORTS_PROTEIN_CANONICALS),
    "sports_helpers.EAA_CANONICALS": frozenset(sh.EAA_CANONICALS),
}


@pytest.mark.parametrize("allowlist_name", sorted(GOVERNED_ALLOWLISTS))
def test_allowlist_canonicals_exist_in_vocabulary(allowlist_name: str) -> None:
    known = _known_canonicals()
    unknown = sorted(GOVERNED_ALLOWLISTS[allowlist_name] - known)
    assert not unknown, (
        f"{allowlist_name} names canonical ids no vocabulary defines: {unknown}. "
        "The enricher can never emit them, so every rule keyed on them is inert. "
        "Use the real canonical id, or add the ingredient to the vocabulary."
    )


def test_governed_allowlists_are_not_empty() -> None:
    """A parametrized gate over an empty mapping would pass vacuously."""
    assert GOVERNED_ALLOWLISTS
    for name, values in GOVERNED_ALLOWLISTS.items():
        assert values, f"{name} is empty; the gate would pass vacuously"


def test_pipeline_derived_canonicals_are_not_vocabulary_entries() -> None:
    """Keep the escape hatch honest.

    If a synthetic canonical later gains a real vocabulary entry it must leave
    this set, otherwise the allowance silently widens.
    """
    iqm = {
        key
        for key in json.loads(INGREDIENT_QUALITY_MAP.read_text())
        if not key.startswith("_")
    }
    vocabulary = (
        iqm | set(sic._botanical_identity_lookup()) | _standardized_botanical_ids()
    )
    overlap = sorted(PIPELINE_DERIVED_CANONICALS & vocabulary)
    assert not overlap, (
        f"{overlap} are now defined by the ingredient vocabulary; "
        "remove them from PIPELINE_DERIVED_CANONICALS."
    )


def test_taxonomy_recognises_every_routing_b_vitamin() -> None:
    """Taxonomy and routing must agree on what a B vitamin is.

    ``supplement_taxonomy`` intersects canonical ids against its own permissive
    alias sets. When routing learned a canonical the taxonomy set never gained,
    the same nutrient counted for the route and not for the taxonomy that feeds
    it.
    """
    from supplement_taxonomy import _B_VITAMIN_IDS, _VITAMIN_CANONICAL_IDS

    missing_b = sorted(rf.B_VITAMIN_CANONICALS - set(_B_VITAMIN_IDS))
    assert not missing_b, (
        f"supplement_taxonomy._B_VITAMIN_IDS does not recognise {missing_b}, "
        "which route_features counts as B vitamins."
    )
    all_vitamins = rf.B_VITAMIN_CANONICALS | rf.NON_B_VITAMIN_CANONICALS
    missing_vitamin = sorted(all_vitamins - set(_VITAMIN_CANONICAL_IDS))
    assert not missing_vitamin, (
        f"supplement_taxonomy._VITAMIN_CANONICAL_IDS does not recognise "
        f"{missing_vitamin}, which route_features counts as vitamins."
    )
