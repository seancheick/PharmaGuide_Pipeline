"""Label rows keep the organism and preparation they name (register Q18, Q25; 2026-09-26).

Each row below used to resolve to a different organism or preparation and met
that identity's interaction rules:
- "Bionectria ochroleuca" (Clonostachys rosea, NCBI Taxonomy 29856) was an alias
  of IQM cordyceps, a different fungal family.
- "fermented soybean powder" was an alias of IQM nattokinase, an isolated enzyme.
- Bergamot and chamomile essential oils were repaired to the fruit and flower by
  their DSLD group, although the cleaner had matched the oil entries exactly.
- Matcha (stone-ground whole leaf) was a form of IQM green_tea_extract and met the
  extract-only liver warning.
Raw DSLD rows go through the real cleaner and enricher.
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


def _raw_row(order, name, group, *, category="botanical", quantity=0, unit="NP", forms=()):
    return {
        "order": order, "ingredientId": 5000 + order, "name": name, "category": category,
        "ingredientGroup": group, "nestedRows": [], "alternateNames": [],
        "forms": [{"order": 1, "name": form, "ingredientGroup": group, "category": category}
                  for form in forms],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": quantity, "unit": unit, "dailyValueTargetGroup": [],
                      "servingSizeUnit": "Capsule(s)"}],
    }


def _raw_blend(name, children):
    blend = _raw_row(1, name, "Blend (non-nutrient/non-botanical)", category="blend",
                     quantity=500, unit="mg")
    blend["nestedRows"] = [_raw_row(i + 2, *child) for i, child in enumerate(children)]
    return blend


def _raw_product(pid, rows):
    return {"id": pid, "fullName": f"Identity split {pid}", "brandName": "Test",
            "ingredientRows": rows, "otheringredients": {"text": None, "ingredients": []},
            "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1,
                              "minDailyServings": 1, "maxDailyServings": 1,
                              "unit": "Capsule(s)"}]}


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(raw):
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return enriched

    return run


def _rows(enriched, name):
    iqd = enriched["ingredient_quality_data"]
    return [row for key in ("ingredients", "ingredients_skipped")
            for row in iqd.get(key) or [] if row.get("name") == name]


def _hits(enriched, name):
    hits = set()
    for alert in enriched["interaction_profile"]["ingredient_alerts"]:
        if alert.get("ingredient_name") != name:
            continue
        for hit in alert.get("condition_hits") or []:
            hits.add((alert["rule_id"], hit["condition_id"]))
        for hit in alert.get("drug_class_hits") or []:
            hits.add((alert["rule_id"], hit["drug_class_id"]))
    return hits


@pytest.mark.parametrize("name,group,expected,old_rule", [
    ("Bionectria ochroleuca", "Bionectria ochroleuca", "bionectria_ochroleuca",
     "RULE_IQM_CORDYCEPS_AUTOIMMUNE"),
    ("Fermented Soybean Powder", "Soy", "soybean", "RULE_IQM_NATTOKINASE_BLEEDING"),
    ("Essence of organic Bergamot (fruit) oil", "Bergamot Orange", "bergamot_essential_oil",
     "RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL"),
    ("Essence of organic Chamomile (leaf) oil", "Chamomile (unspecified)",
     "chamomile_essential_oil", "RULE_INGREDIENT_CHAMOMILE"),
])
def test_blend_child_keeps_the_organism_and_preparation_it_names(
    pipeline, name, group, expected, old_rule,
):
    enriched = pipeline(_raw_product(990101, [_raw_blend("Mushroom and Botanical Blend",
                                                         [(name, group)])]))
    rows = _rows(enriched, name)
    assert rows and {row["canonical_id"] for row in rows} == {expected}
    assert not any(rule == old_rule for rule, _ in _hits(enriched, name))


@pytest.mark.parametrize("name,forms", [
    ("Matcha, Powder", ["Camellia sinensis, Powder"]),
    ("Matcha Green Tea, Powder", []),
    ("organic Matcha Green Tea", []),
    ("organic Matcha Green Tea leaf powder", []),
    ("Matcha", []),
])
def test_matcha_is_whole_leaf_not_green_tea_extract(pipeline, name, forms):
    row = _raw_row(1, name, "Green Tea", quantity=750, unit="mg", forms=forms)
    enriched = pipeline(_raw_product(990102, [row]))
    assert {r["canonical_id"] for r in _rows(enriched, name)} == {"matcha_tea_powder"}
    hits = _hits(enriched, name)
    assert ("RULE_IQM_GREEN_TEA_HYPERTENSION", "liver_disease") not in hits
    # Brewed green tea and EGCG lower nadolol exposure; whole leaf keeps that warning.
    assert ("RULE_BOTAN_MATCHA_BETA_BLOCKERS", "beta_blockers") in hits


def test_green_tea_extract_keeps_the_liver_warning(pipeline):
    row = _raw_row(1, "Green Tea Extract", "Green Tea", quantity=500, unit="mg")
    enriched = pipeline(_raw_product(990103, [row]))
    assert {r["canonical_id"] for r in _rows(enriched, "Green Tea Extract")} == {"green_tea_extract"}
    assert ("RULE_IQM_GREEN_TEA_HYPERTENSION", "liver_disease") in _hits(enriched, "Green Tea Extract")


def test_wrong_identities_are_gone_from_their_old_owners():
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())

    def aliases(parent):
        return {alias.lower() for form in iqm[parent]["forms"].values()
                for alias in [*form.get("aliases", []), *form.get("same_identity_aliases", [])]}

    assert not {a for a in aliases("cordyceps") if "bionectria" in a}
    assert not {a for a in aliases("nattokinase") if "soy" in a}
    assert "matcha powder" not in iqm["green_tea_extract"]["forms"]
    assert not {a for a in aliases("green_tea_extract") if "matcha" in a}
    standardized = json.loads((DATA / "standardized_botanicals.json").read_text())
    green_tea = next(e for e in standardized["standardized_botanicals"] if e["id"] == "green_tea")
    assert "matcha" not in {a.lower() for a in green_tea["aliases"]}


def test_dandelion_root_answers_to_the_dandelion_rule():
    from identity.interaction import interaction_subject_ids

    assert interaction_subject_ids("dandelion_root") == ["dandelion_root", "dandelion"]
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    kidney = next(c for r in rules if r["id"] == "RULE_IQM_DANDELION_KIDNEY"
                  for c in r["condition_rules"] if c["condition_id"] == "kidney_disease")
    assert any("taraxacum-officinale-fh-wigg-radix" in s for s in kidney["sources"])


def test_dgl_aliases_are_owned_by_the_distinct_preparation():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    for raw_name in (
        "Deglycyrrhized Licorice",
        "Gutgard DGL",
        "deglycyrrhizinated licorice root extract",
    ):
        standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(raw_name, [])
        assert mapped is True
        assert standard_name == "DGL (Deglycyrrhizinated Licorice)"

    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping("licorice root extract", [])
    assert mapped is True
    assert standard_name == "Licorice"


def test_clinical_followups_use_routable_fields_and_one_policy_owner():
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    by_id = {rule["id"]: rule for rule in rules}

    serialized = json.dumps(rules)
    assert "form_exclusion" not in serialized

    eleuthero = by_id["RULE_IQM_SIBERIAN_GINSENG_PREGNANCY"]
    assert eleuthero["condition_rules"] == []
    assert eleuthero["drug_class_rules"] == []
    assert eleuthero["pregnancy_lactation"]["pregnancy_category"] == "avoid"
    assert eleuthero["pregnancy_lactation"]["lactation_category"] == "avoid"

    dandelion = by_id["RULE_IQM_DANDELION_KIDNEY"]
    assert {row["condition_id"] for row in dandelion["condition_rules"]} >= {
        "kidney_disease",
        "liver_disease",
    }
    assert dandelion["pregnancy_lactation"]["pregnancy_category"] == "avoid"
    assert "pregnancy_lactation" not in by_id["RULE_IQM_DANDELION_GLUCOSE"]
