"""Vitamin K1/K2 must keep the warfarin (vitamin K antagonist) interaction.

The 2026-07-28 identity split gave vitamin K1 and K2 their own IQM parents
(`vitamin_k1`, `vitamin_k2`) and turned the old redirect into a display-only
`nutrient_group_id`. Every vitamin K interaction is authored on `vitamin_k`, so
from then on 659 K1/K2 products shipped with no warfarin caution on either the
product profile or the app's stack lookup (which joins on key_ingredient_tags).

The interaction subject family lives in one owner (identity/interaction.py) and
is consulted additively by both carriers. It is narrower than the display
group on purpose: beta-carotene rolls up to vitamin A for display but is a
provitamin, not a vitamer, and must not inherit preformed-retinol rules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DATA = SCRIPTS / "data"


def _iqm() -> dict:
    return json.loads((DATA / "ingredient_quality_map.json").read_text())


def _rules() -> list:
    return json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _profile(enricher, canonical_id: str, form_id: str, name: str) -> dict:
    row = {
        "name": name,
        "raw_source_text": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "form_id": form_id,
        "quantity": 100.0,
        "unit": "mcg",
        "unit_normalized": "mcg",
    }
    product = {
        "dsld_id": "TEST_VITAMIN_K",
        "product_name": name,
        "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
    }
    return enricher._collect_interaction_profile(product)


def _rule_ids(profile: dict) -> set:
    ids = set()
    for summary in (profile.get("drug_class_summary") or {}).values():
        ids.update(summary.get("rule_ids") or [])
    for summary in (profile.get("condition_summary") or {}).values():
        ids.update(summary.get("rule_ids") or [])
    return ids


@pytest.mark.parametrize(
    "canonical_id,form_id,name,expected",
    [
        ("vitamin_k2", "menaquinone-7 (MK-7)", "Vitamin K2 (as MK-7)",
         {"RULE_INGREDIENT_VITAMIN_K", "RULE_IQM_VITAMIN_K_MK7_FORM_ONLY"}),
        ("vitamin_k2", "menaquinone-4 (MK-4)", "Vitamin K2 (as MK-4)", {"RULE_INGREDIENT_VITAMIN_K"}),
        ("vitamin_k1", "phylloquinone", "Vitamin K1", {"RULE_INGREDIENT_VITAMIN_K"}),
    ],
)
def test_vitamin_k_vitamers_carry_the_vitamin_k_antagonist_caution(
    enricher, canonical_id, form_id, name, expected
):
    profile = _profile(enricher, canonical_id, form_id, name)
    assert "vitamin_k_antagonists" in (profile.get("drug_class_summary") or {})
    fired = _rule_ids(profile)
    assert expected <= fired
    if form_id != "menaquinone-7 (MK-7)":
        assert "RULE_IQM_VITAMIN_K_MK7_FORM_ONLY" not in fired


def test_provitamin_does_not_inherit_preformed_vitamin_a_rules(enricher):
    profile = _profile(enricher, "beta_carotene", "beta-carotene", "Beta-Carotene")
    assert "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE" not in _rule_ids(profile)


def test_export_interaction_tags_carry_the_vitamin_k_family():
    from identity.interaction import interaction_subject_ids

    assert interaction_subject_ids("vitamin_k2") == ["vitamin_k2", "vitamin_k"]
    assert interaction_subject_ids("vitamin_k1") == ["vitamin_k1", "vitamin_k"]
    assert interaction_subject_ids("beta_carotene") == ["beta_carotene"]
    assert interaction_subject_ids("magnesium") == ["magnesium"]


def test_interaction_family_is_a_subset_of_the_iqm_declared_groups():
    """The interaction family may only narrow the IQM identity groups."""
    from identity.interaction import INTERACTION_SUBJECT_FAMILY

    iqm = _iqm()
    for member, family in INTERACTION_SUBJECT_FAMILY.items():
        assert iqm[member].get("nutrient_group_id") == family, member


def test_every_rule_form_scope_names_a_real_form():
    """A form_scope key that no IQM form carries makes the rule silently dead."""
    from identity.interaction import INTERACTION_SUBJECT_FAMILY

    iqm = _iqm()
    members: dict = {}
    for member, family in INTERACTION_SUBJECT_FAMILY.items():
        members.setdefault(family, set()).add(member)
    dead = []
    for rule in _rules():
        scope = rule.get("form_scope")
        subject = rule.get("subject_ref") or {}
        if not scope or subject.get("db") != "ingredient_quality_map":
            continue
        parents = {subject["canonical_id"]} | members.get(subject["canonical_id"], set())
        forms = set().union(*((iqm.get(p) or {}).get("forms", {}).keys() for p in parents))
        dead += [(rule["id"], key) for key in scope if key not in forms]
    assert dead == []
