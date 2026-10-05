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
    assert "RULE_IQM_DANDELION_GLUCOSE" not in by_id
    assert {row["drug_class_id"] for row in dandelion["drug_class_rules"]} >= {
        "hypoglycemics_high_risk",
        "hypoglycemics_lower_risk",
        "hypoglycemics_unknown",
    }


@pytest.mark.parametrize("name", ["Ascorbic Acid", "non-GMO Ascorbic Acid", "organic Ascorbic Acid"])
def test_active_vitamin_c_is_not_a_preservative(pipeline, name):
    from scoring_input_contract import get_evidence_subject_rows
    from scoring_v4.scored_artifact import build_scored_artifact

    row = _raw_row(1, name, "Vitamin C (ascorbic acid)", category="vitamin", quantity=50, unit="mg")
    enriched = pipeline(_raw_product(990103, [row]))
    rows = _rows(enriched, name)
    assert rows and {r["canonical_id"] for r in rows} == {"vitamin_c"}
    assert {r["canonical_id"] for r in get_evidence_subject_rows(enriched)} == {"vitamin_c"}
    assert build_scored_artifact(enriched)["quality_score_status"] == "scored"


@pytest.mark.parametrize("name", ["Ascorbic Acid", "non-GMO Ascorbic Acid"])
def test_inactive_vitamin_c_keeps_the_preservative_owner(pipeline, name):
    raw = _raw_product(990104, [_raw_row(1, "Vitamin D3", "Vitamin D", category="vitamin", quantity=25, unit="mcg")])
    raw["otheringredients"] = {"text": name, "ingredients": [{"name": name, "ingredientGroup": "Vitamin C (ascorbic acid)", "category": "vitamin"}]}
    enriched = pipeline(raw)
    assert {r["canonical_id"] for r in enriched["inactiveIngredients"] if name in r.get("name", "")} == {"OI_ASCORBIC_ACID_PRESERVATIVE"}


@pytest.mark.parametrize("name", ["NEM", "NEM eggshell membrane", "Eggshell membrane"])
def test_membrane_does_not_inherit_hydrolyzed_peptide_form(pipeline, name):
    enriched = pipeline(_raw_product(990105, [_raw_row(1, name, "Collagen", category="non-nutrient/non-botanical", quantity=500, unit="mg")]))
    rows = [r for r in enriched["ingredient_quality_data"]["ingredients"]
            if r.get("raw_source_text") == name]
    assert rows
    assert all(r.get("form") != "hydrolyzed collagen peptides" and r.get("matched_form") != "hydrolyzed collagen peptides" for r in rows)


def test_extract_formula_is_not_relabelled_as_powder(pipeline):
    from scoring_input_contract import get_evidence_subject_rows
    row = _raw_row(1, "Triphala", "Blend (Herb/Botanical)", category="blend", quantity=90, unit="mg", forms=["Amla extract", "Belleric Myrobalan extract", "Chebula Myrobalan extract"])
    enriched = pipeline(_raw_product(990106, [row]))
    assert not any(r.get("canonical_id") == "triphala_powder" for r in get_evidence_subject_rows(enriched))
    assert not any(r.get("standard_name") == "Triphala Powder" for r in _rows(enriched, "Triphala"))


def test_fatty_oil_blend_is_a_header_not_a_volatile_oil_subject(pipeline):
    from scoring_input_contract import get_evidence_subject_rows
    row = _raw_blend("Essential Oil Blend", [("Evening Primrose Oil", "Evening Primrose oil"), ("Black Currant Seed Oil", "Black Currant Seed Oil")])
    row["ingredientGroup"] = "Blend (Fatty Acid or Fat/Oil Supplement)"
    row["notes"] = "These oils provide the following fatty acid profile"
    enriched = pipeline(_raw_product(990107, [row]))
    subjects = get_evidence_subject_rows(enriched)
    assert not any(r.get("canonical_id") == "essential_oil_blend" for r in subjects)
    assert any("primrose" in str(r.get("canonical_id")) for r in subjects)
    from scoring_input_contract import is_lent_blend_mass
    from scoring_v4.modules.generic_helpers import has_usable_individual_dose
    assert all(r.get("quantity", 0) in (0, None) or is_lent_blend_mass(r) for r in subjects)
    assert all(not has_usable_individual_dose(r) for r in subjects)


@pytest.mark.parametrize("name,forms", [("Triphala fruit extract", []), ("Triphala", ["Amla extract", "Belleric Myrobalan extract", "Chebula Myrobalan extract"])])
def test_cleaner_keeps_unowned_extract_preparation_explicit(name, forms):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    row = _raw_row(1, name, "Blend (Herb/Botanical)", category="blend", quantity=90, unit="mg", forms=forms)
    cleaned = EnhancedDSLDNormalizer().normalize_product(_raw_product(990108, [row]))
    parent = next(r for r in cleaned["activeIngredients"] if r["name"] == name)
    assert parent["canonical_id"] is None
    assert parent["standardName"] == name
    assert parent["quantity"] == 90
    if forms:
        assert [f["name"] for f in parent["forms"]] == forms
    else:
        assert any(f["name"] == "extract" for f in parent["forms"])


def test_declared_triphala_powder_keeps_its_existing_identity(pipeline):
    enriched = pipeline(_raw_product(990109, [_raw_row(1, "Triphala Powder", "Triphala", quantity=2000, unit="mg")]))
    assert {r["canonical_id"] for r in _rows(enriched, "Triphala Powder")} == {"triphala_powder"}


@pytest.mark.parametrize("name", ["Vitamin A", "organic Vitamin A"])
def test_qualified_vitamin_name_retains_its_full_form_unii(pipeline, name):
    row = _raw_row(1, name, "Vitamin A", category="vitamin", quantity=900, unit="mcg")
    row["forms"] = [{"name": "Beta-Carotene", "category": "vitamin", "ingredientGroup": "Beta Carotene", "uniiCode": "01YAE03M7J"}]
    enriched = pipeline(_raw_product(990110, [row]))
    rows = _rows(enriched, name)
    assert rows and {r["canonical_id"] for r in rows} == {"beta_carotene"}
    assert {r["bio_score"] for r in rows} == {5}


@pytest.mark.parametrize("name,group,expected", [("Triphala", "Blend (Herb/Botanical)", "triphala_powder"), ("Univestin", "Blend (Herb/Botanical)", "nha_univestin")])
def test_sole_formula_material_retains_its_evidence_subject(pipeline, name, group, expected):
    from scoring_input_contract import get_evidence_subject_rows
    enriched = pipeline(_raw_product(990111, [_raw_row(1, name, group, category="blend", quantity=1000, unit="mg")]))
    assert expected in {str(r.get("canonical_id")).lower() for r in get_evidence_subject_rows(enriched)}

@pytest.mark.parametrize("name", [
    "Essence of pure black pepper (fruit) oil",
    "Essence of pure black pepper oil extract",
    "Black Pepper Oil",
    "Organic black pepper essential oil",
])
def test_oil_preparation_cannot_inherit_isolated_marker_identity(pipeline, name):
    from scoring_v4.scored_artifact import build_scored_artifact
    from scoring_input_contract import get_evidence_subject_rows
    source = _raw_product(990113, [_raw_row(1, name, "Black Pepper", quantity=20, unit="mg")])
    enriched = pipeline(source)
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] is None
    assert active["standardName"] == name
    assert active["quantity"] == 20
    assert not any(r.get("canonical_id") == "piperine" for r in get_evidence_subject_rows(enriched))
    assert not any("PIPERINE" in rule for rule, _ in _hits(enriched, name))
    build_scored_artifact(enriched)

@pytest.mark.parametrize("name", ["Black Pepper", "organic black pepper"])
def test_whole_botanical_cannot_inherit_isolated_marker_identity(pipeline, name):
    enriched = pipeline(_raw_product(990114, [_raw_row(1, name, "Black Pepper", quantity=20, unit="mg")]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] == "black_pepper"
    assert active["standardName"] == "Black Pepper"
    assert active["quantity"] == 20

@pytest.mark.parametrize("name", ["Piperine", "BioPerine", "Black Pepper Extract"])
def test_declared_marker_preparation_retains_its_identity(pipeline, name):
    enriched = pipeline(_raw_product(990115, [_raw_row(1, name, "Black Pepper", quantity=20, unit="mg")]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] == "piperine"
    assert active["quantity"] == 20

@pytest.mark.parametrize("name", ["Olive Oil", "Pure Olive Oil", "Organic Olive Oil", "Virgin Olive Oil", "Cold-Pressed Olive Oil"])
def test_generic_oil_does_not_acquire_an_unprinted_quality_grade(pipeline, name):
    enriched = pipeline(_raw_product(990116, [_raw_row(1, name, "Olive Oil", quantity=100, unit="mg")]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] != "extra_virgin_olive_oil"
    assert active["standardName"] == "Olive Oil"
    assert active["quantity"] == 100

@pytest.mark.parametrize("name", ["Extra Virgin Olive Oil", "EVOO", "Extra Virgin Olive Fruit Oil", "organic, extra virgin Olive Oil", "organic cold pressed extra virgin olive oil", "Olive oil-extra virgin"])
def test_explicit_oil_grade_keeps_its_existing_owner(pipeline, name):
    enriched = pipeline(_raw_product(990117, [_raw_row(1, name, "Olive Oil", quantity=100, unit="mg")]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] == "extra_virgin_olive_oil"
    assert active["quantity"] == 100

@pytest.mark.parametrize("name,group", [
    ("D-Beta Tocopherol", "Vitamin E (beta tocopherol)"),
    ("D-Delta Tocopherol", "Vitamin E (delta tocopherol)"),
    ("D-Gamma Tocopherol", "Vitamin E (gamma tocopherol)"),
])
def test_active_nutrient_source_form_is_not_a_preservative_or_alpha_activity(pipeline, name, group):
    source = _raw_product(990118, [_raw_row(1, name, group, category="vitamin", quantity=50, unit="mg")])
    enriched = pipeline(source)
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"] == "vitamin_e"
    assert active["name"] == name
    assert active["quantity"] == 50
    assessments = enriched['rda_ul_data']['adequacy_results']
    assert not any(a.get('scoring_eligible') is True for a in assessments)

@pytest.mark.parametrize('declaration', ['name', 'unii'])
def test_authored_preparation_exclusion_covers_all_identity_lookup_routes(pipeline, declaration):
    row = _raw_row(1, 'Black Pepper Fruit Oil', 'Piperine', quantity=20, unit='mg')
    if declaration == 'unii':
        row['uniiCode'] = 'U71XL721QK'
    enriched = pipeline(_raw_product(990119, [row]))
    assert all(r.get('canonical_id') != 'piperine' for r in enriched['activeIngredients'])

@pytest.mark.parametrize('category,group', [
    ('botanical', 'Vitamin E (beta tocopherol)'),
    ('vitamin', 'Calcium (beta tocopherol)'),
    ('vitamin', 'Vitamin E (unidentified complex)'),
])
def test_parent_local_source_form_does_not_accept_unrelated_taxonomy(category, group):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    row = {'category': category, 'name': 'D-Beta Tocopherol', 'ingredientGroup': group}
    assert EnhancedDSLDNormalizer()._printed_nutrient_identity(row) is None

@pytest.mark.parametrize('name', ['D-Beta Tocopherol', 'D-Delta Tocopherol'])
def test_plain_nutrient_heading_uses_parent_local_source_alias(pipeline, name):
    enriched = pipeline(_raw_product(990120, [_raw_row(1, name, 'Vitamin E', category='vitamin', quantity=20, unit='mg')]))
    active = next(r for r in enriched['activeIngredients'] if r['name'] == name)
    assert active['canonical_id'] == 'vitamin_e'
    assert not any(a.get('scoring_eligible') is True for a in enriched['rda_ul_data']['adequacy_results'])

@pytest.mark.parametrize('name', ['Extra Virgin Olive Oil', 'organic cold pressed extra virgin olive oil', 'EVOO'])
def test_inactive_declared_grade_survives_generic_generated_alias(pipeline, name):
    raw = _raw_product(990121, [_raw_row(1, 'Vitamin D3', 'Vitamin D', category='vitamin', quantity=25, unit='mcg')])
    raw['otheringredients'] = {'text': name, 'ingredients': [{'name': name, 'ingredientGroup': 'Olive Oil', 'category': 'non-nutrient/non-botanical'}]}
    enriched = pipeline(raw)
    assert {r['canonical_id'] for r in enriched['inactiveIngredients'] if r.get('name') == name} == {'extra_virgin_olive_oil'}

@pytest.mark.parametrize('name', ['Black Pepper Fruit', 'Piper nigrum fruit powder'])
def test_whole_plant_part_does_not_inherit_generated_extract_alias(pipeline, name):
    enriched = pipeline(_raw_product(990122, [_raw_row(1, name, 'Black Pepper', quantity=20, unit='mg')]))
    active = next(r for r in enriched['activeIngredients'] if r['name'] == name)
    assert active['canonical_id'] == 'black_pepper'
    assert active['standardName'] == 'Black Pepper'


def test_declared_marker_with_carrier_form_keeps_marker_identity(pipeline):
    row = _raw_row(1, 'Piperine', 'Piperine', quantity=20, unit='mg', forms=['Olive Oil'])
    enriched = pipeline(_raw_product(990123, [row]))
    assert next(r for r in enriched['activeIngredients'] if r['name'] == 'Piperine')['canonical_id'] == 'piperine'


def test_declared_standardized_preparation_survives_generic_plant_group(pipeline):
    name = 'Bioperine Black Pepper (Piper nigrum) extract'
    row = _raw_row(1, name, 'Black Pepper', quantity=5.3, unit='mg')
    row['forms'] = [{'name': 'Piperine', 'category': 'non-nutrient/non-botanical', 'ingredientGroup': 'Piperine', 'percent': 95, 'prefix': 'standardized to contain'}]
    enriched = pipeline(_raw_product(990124, [row]))
    assert next(r for r in enriched['activeIngredients'] if r['name'] == name)['canonical_id'] == 'piperine'


@pytest.mark.parametrize('name,group', [('Black Pepper Fruit', ''), ('Piper nigrum fruit powder', ''), ('Black Pepper Fruit', 'Piperine')])
def test_unowned_whole_plant_does_not_borrow_constituent_from_generated_alias(pipeline, name, group):
    enriched = pipeline(_raw_product(990125, [_raw_row(1, name, group, quantity=20, unit='mg')]))
    assert next(r for r in enriched['activeIngredients'] if r['name'] == name)['canonical_id'] != 'piperine'


@pytest.mark.parametrize('form', ['BioPerine', 'Piperine'])
def test_constituent_descriptor_does_not_establish_whole_plant_marker_mass(pipeline, form):
    row = _raw_row(1, 'Black Pepper', 'Black Pepper', quantity=20, unit='mg', forms=[form])
    enriched = pipeline(_raw_product(990127, [row]))
    assert next(r for r in enriched['activeIngredients'] if r['name'] == 'Black Pepper')['canonical_id'] == 'black_pepper'

@pytest.mark.parametrize('name', ['Grapefruit Extract', 'Grapefruit (Citrus x paradisi) extract', 'Grapefruit flavonoid'])
def test_broad_source_extract_does_not_claim_isolated_flavanone(pipeline, name):
    enriched = pipeline(_raw_product(990128, [_raw_row(1, name, 'Grapefruit', quantity=85, unit='mg')]))
    active = next(r for r in enriched['activeIngredients'] if r['name'] == name)
    assert active['canonical_id'] not in {'naringenin', 'grape_seed_extract', 'grapefruit_seed'}
    assert active['quantity'] == 85
    from scoring_input_contract import get_scoring_ingredients
    assert not any(r.get('canonical_id') == 'naringenin' for r in get_scoring_ingredients(enriched, strict=True).rows)


def test_declared_isolated_flavanone_retains_its_chemical_owner(pipeline):
    enriched = pipeline(_raw_product(990129, [_raw_row(1, 'Naringenin', 'Naringenin', quantity=85, unit='mg')]))
    assert next(r for r in enriched['activeIngredients'] if r['name'] == 'Naringenin')['canonical_id'] == 'naringenin'


def test_nested_family_bounds_do_not_restore_nonalpha_adequacy(pipeline):
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'tocopherol_family_2528_raw.json').read_text())
    enriched = pipeline(raw)
    assessments = enriched['rda_ul_data']['adequacy_results']
    for chemical in ['d-beta-tocopherol', 'd-gamma-tocopherol', 'd-delta-tocopherol']:
        rows = [r for r in assessments if chemical in r.get('source_label_key', '')]
        assert rows, chemical
        assert all(r['scoring_eligible'] is False and r['pct_rda'] is None for r in rows)
    alpha = [r for r in assessments if 'd-alpha-tocopherol:' in r.get('source_label_key', '')]
    assert alpha and any(r['scoring_eligible'] is True for r in alpha)
