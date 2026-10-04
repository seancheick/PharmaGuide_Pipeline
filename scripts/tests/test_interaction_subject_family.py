"""INTERACTION_SUBJECT_FAMILY is pinned to the IQM fields that define each family.

A family member answers to every interaction authored on its family id. A
member missing from the map silently drops those interactions (vitamin K in
July 2026; every probiotic strain until October 2026), so membership is
derived from the IQM and any new identity forces a decision here.
"""

import json
from pathlib import Path

from identity.interaction import INTERACTION_SUBJECT_FAMILY, interaction_subject_ids

SCRIPTS = Path(__file__).resolve().parents[1]
IQM = json.loads((SCRIPTS / "data" / "ingredient_quality_map.json").read_text())

# Not a live bacterium or yeast, so infection-risk rules on `probiotics` do not apply.
PROBIOTIC_CATEGORY_EXCLUDED = {"bacteriophages": "virus that infects bacteria, not a live microorganism dose"}


def _entries():
    return {k: v for k, v in IQM.items() if k != "_metadata" and isinstance(v, dict)}


def test_every_family_id_and_member_is_a_live_iqm_identity():
    entries = _entries()
    for member, family in INTERACTION_SUBJECT_FAMILY.items():
        assert member in entries, member
        assert family in entries, family


def test_every_family_is_declared_by_an_iqm_field():
    """A new family needs its IQM-declared group and an equality pin below."""
    assert set(INTERACTION_SUBJECT_FAMILY.values()) == {"vitamin_k", "probiotics"}


def test_vitamin_k_family_matches_iqm_nutrient_group():
    expected = {k for k, v in _entries().items() if v.get("nutrient_group_id") == "vitamin_k"}
    actual = {m for m, f in INTERACTION_SUBJECT_FAMILY.items() if f == "vitamin_k"}
    assert actual == expected


def test_probiotic_family_is_every_iqm_probiotic_organism():
    expected = {
        k for k, v in _entries().items()
        if v.get("category") == "probiotics" and k != "probiotics"
    } - set(PROBIOTIC_CATEGORY_EXCLUDED)
    actual = {m for m, f in INTERACTION_SUBJECT_FAMILY.items() if f == "probiotics"}
    assert actual == expected
    for excluded in PROBIOTIC_CATEGORY_EXCLUDED:
        assert IQM[excluded]["category"] == "probiotics"


def test_strain_tags_reach_the_generic_probiotic_subject():
    assert interaction_subject_ids("lactobacillus_rhamnosus") == ["lactobacillus_rhamnosus", "probiotics"]
    assert interaction_subject_ids("saccharomyces_boulardii") == ["saccharomyces_boulardii", "probiotics"]
    assert interaction_subject_ids("bacteriophages") == ["bacteriophages"]
