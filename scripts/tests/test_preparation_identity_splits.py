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
    for chemical in ['d-beta-tocopherol', 'd-gamma-tocopherol', 'd-delta-tocopherol', 'd-alpha-tocotrienol', 'd-beta-tocotrienol', 'd-gamma-tocotrienol', 'd-delta-tocotrienol']:
        rows = [r for r in assessments if chemical in r.get('source_label_key', '')]
        assert rows, chemical
        assert all(r['scoring_eligible'] is False and r['pct_rda'] is None for r in rows)
    alpha = [r for r in assessments if 'd-alpha-tocopherol:' in r.get('source_label_key', '')]
    assert alpha and any(r['scoring_eligible'] is True for r in alpha)


@pytest.mark.parametrize("group,unii", [("Algin", None), ("Sodium Alginate", None), ("Algin", "8C3Z4148WZ")])
def test_declared_alginic_acid_does_not_assert_sodium_salt(pipeline, group, unii):
    # Esophageal Guardian 232011/328450 declares acid, 1000 mg, not its sodium salt.
    row = _raw_row(1, "Alginic Acid", group, category="non-nutrient/non-botanical", quantity=1000, unit="mg")
    row["uniiCode"] = unii
    enriched = pipeline(_raw_product(990132, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == "Alginic Acid")
    assert active.get("canonical_id") is None
    assert active["quantity"] == 1000
    assert active["unit"] == "mg"
    assert active.get("standardName") == "Alginic Acid"
    assert "C269C4G2ZQ" not in json.dumps(active)
    assert "23665711" not in json.dumps(active)


@pytest.mark.parametrize("name", ["Sodium Alginate", "Alginic acid sodium salt"])
def test_declared_sodium_alginate_retains_existing_salt_owner(pipeline, name):
    row = _raw_row(1, name, "Algin", category="non-nutrient/non-botanical", quantity=1000, unit="mg")
    row["uniiCode"] = "C269C4G2ZQ"
    enriched = pipeline(_raw_product(990133, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active["canonical_id"].lower() == "pii_sodium_alginate"
    assert active["quantity"] == 1000


@pytest.mark.parametrize("pid,serving_unit", [(232011, "Tablet(s)"), (328450, "Vegetarian Chewable Tablet(s)")])
def test_esophageal_guardian_declared_acid_retains_source_facts(pipeline, pid, serving_unit):
    row = {
        "order": 4, "ingredientId": 282529, "description": "", "notes": "",
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 2,
                      "operator": "=", "quantity": 1000, "unit": "mg",
                      "dailyValueTargetGroup": [{"name": "Adults and children 4 or more years of age",
                                                  "operator": None, "percent": None,
                                                  "footnote": "Daily Value not established"}],
                      "servingSizeUnit": serving_unit}],
        "nestedRows": [], "name": "Alginic Acid", "category": "complex carbohydrate",
        "ingredientGroup": "Algin", "uniiCode": "8C3Z4148WZ", "alternateNames": [], "forms": [],
    }
    enriched = pipeline(_raw_product(pid, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == "Alginic Acid")
    assert active.get("canonical_id") is None
    assert active["raw_source_text"] == "Alginic Acid"
    assert active["quantity"] == 1000 and active["unit"] == "mg"
    assert active["raw_taxonomy"]["uniiCode"] == "8C3Z4148WZ"
    assert active["raw_source_path"] == "ingredientRows[0]"


def test_acid_literal_vetoes_conflicting_sodium_unii(pipeline):
    row = _raw_row(1, "Alginic Acid", "Algin", quantity=1000, unit="mg")
    row["uniiCode"] = "C269C4G2ZQ"
    enriched = pipeline(_raw_product(990134, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == "Alginic Acid")
    assert active.get("canonical_id") is None
    assert active["standardName"] == "Alginic Acid"


def test_polisure_declared_material_survives_strict_evidence_identity(pipeline):
    row = _raw_row(1, "Sugar Cane Wax Extract", "Sugar cane", quantity=10, unit="mg")
    row["forms"] = [{"name": "PoliSure", "ingredientId": 344472, "order": 1,
                     "prefix": None, "percent": None, "category": "non-nutrient/non-botanical",
                     "ingredientGroup": "Policosanol", "uniiCode": None}]
    enriched = pipeline(_raw_product(314749, [row]))
    from scoring_input_contract import get_evidence_subject_rows
    subjects = get_evidence_subject_rows(enriched)
    active = next(r for r in subjects if r["name"] == row["name"])
    assert active["canonical_id"] == "policosanol"
    assert active["quantity"] == 10 and active["unit"] == "mg"

    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r.get("canonical_id") == "policosanol")
    assert quality["source_label_name"] == row["name"]
    assert quality["label_display_name"] == row["name"]
    assert quality["form_match_status"] == "mapped"
    assert quality["matched_form"] == "sugar cane policosanol"
    assert quality["bio_score"] == 7  # identity verified; no marketing absorption bonus


def test_achiote_leaf_cannot_inherit_annatto_seed_carotenoid_identity(pipeline):
    row = _raw_row(1, "Achiote extract", "Annatto", quantity=500, unit="mg")
    row["ingredientId"] = 237672
    row["notes"] = "Achiote extract PlantPart: leaf Note: 4:1 "
    enriched = pipeline(_raw_product(213740, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == "Achiote extract")
    assert active.get("canonical_id") == "achiote_leaf"
    assert active.get("canonical_source_db") == "botanical_ingredients"
    assert active["quantity"] == 500 and active["unit"] == "mg"
    assert "6PQP1V1B6O" not in json.dumps(active)
    assert active["plantPart"] == "leaf"
    assert all(r.get("bio_score") is None for r in _rows(enriched, row["name"]))
    from scoring_input_contract import get_evidence_subject_rows
    # Verified leaf identity is not an assessable seed-material subject.
    assert not any(r.get("canonical_id") in {"oi_annatto_extract", "nha_annatto_variants"}
                   for r in get_evidence_subject_rows(enriched) if r["name"] == row["name"])


@pytest.mark.parametrize("name,owner", [("Annatto Extract", "oi_annatto_extract"), ("Annatto seed extract", "nha_annatto_variants"), ("Natural color annatto", "oi_annatto_extract")])
def test_annatto_seed_colorant_retains_existing_owner(pipeline, name, owner):
    row = _raw_row(1, name, "Annatto", quantity=5, unit="mg")
    row["uniiCode"] = "6PQP1V1B6O"
    enriched = pipeline(_raw_product(990135, [row]))
    active = next(r for r in enriched["activeIngredients"] if r["name"] == name)
    assert active.get("canonical_id", "").lower() == owner


@pytest.mark.parametrize("name,group,form,parent,expected", [
    ("Acai Berry Fruit Extract", "Acai", "Euterpe badiocarpa Fruit Extract",
     "acai_berry", "acai berry (unspecified)"),
    ("Acai Berry Extract", "Acai", "Euterpe badiocarpa Berry Extract",
     "acai_berry", "acai berry (unspecified)"),
    ("Acai Fruit Extract", "Acai", "Euterpe oleracea Fruit Extract",
     "acai_berry", "acai berry (unspecified)"),
    ("Pine Bark Extract", "Pine", "Pinus massoniana Bark Extract",
     "pine_bark_extract", "generic pine bark extract"),
])
def test_verified_botanical_form_alias_resolves_existing_owner(
    pipeline, name, group, form, parent, expected,
):
    raw = _raw_row(1, name, group, quantity=100, unit="mg", forms=[form])
    enriched = pipeline(_raw_product(990201, [raw]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == name)
    assert quality["canonical_id"] == parent
    assert not quality["unmapped_forms"]
    assert quality["matched_form"] == expected
    assert quality["quantity"] == 100
    from scoring_v4.scored_artifact import build_scored_artifact
    artifact = build_scored_artifact(enriched)
    assert "disclosed_form_unmapped" not in artifact["strict_scoring_contract"]["findings"]


def test_masson_pine_cannot_claim_branded_pycnogenol_form(pipeline):
    row = _raw_row(1, "Masson Pine Bark Extract", "Pine", quantity=100, unit="mg")
    enriched = pipeline(_raw_product(990202, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == row["name"])
    assert quality["canonical_id"] == "pine_bark_extract"
    assert quality["matched_form"] == "generic pine bark extract"
    assert quality["bio_score"] == 9


@pytest.mark.parametrize("name,source,expected", [
    ("Hesperidin", "Citrus aurantium", "hesperidin"),
    ("Hesperidin", "Citrus aurantium L.", "hesperidin"),
    ("Citrus Bioflavonoid Complex", "Bitter Orange", "citrus bioflavonoids complex"),
    ("Citrus Bioflavonoid Complex", "Citrus aurantium", "citrus bioflavonoids complex"),
])
def test_citrus_source_preserves_printed_preparation(pipeline, name, source, expected):
    row = _raw_row(1, name, "Hesperidin" if name == "Hesperidin" else "Flavonoid (mixture)",
                   category="non-nutrient/non-botanical", quantity=100, unit="mg")
    row["forms"] = [{"name": source, "order": 1, "category": "botanical",
                     "ingredientGroup": "Bitter orange", "prefix": None}]
    enriched = pipeline(_raw_product(990203, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == name)
    assert quality["canonical_id"] == "citrus_bioflavonoids"
    assert quality["matched_form"] == expected
    assert quality["unmapped_forms"] == []
    assert quality["source_label_name"] == name
    from scoring_v4.scored_artifact import build_scored_artifact
    scored = build_scored_artifact(enriched)
    assert "disclosed_form_unmapped" not in scored["strict_scoring_contract"]["findings"]


@pytest.mark.parametrize("name", ["Hesperetin", "Hesperidin Methyl Chalcone"])
def test_distinct_hesperidin_derivatives_do_not_inherit_hesperidin(pipeline, name):
    enriched = pipeline(_raw_product(990204, [
        _raw_row(1, name, name, category="non-nutrient/non-botanical",
                 quantity=100, unit="mg")]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == name)
    assert quality.get("matched_form") != "hesperidin"
    assert quality.get("scoreable_identity") is False


def test_unverified_citrus_source_is_still_held(pipeline):
    row = _raw_row(1, "Hesperidin", "Hesperidin",
                   category="non-nutrient/non-botanical", quantity=100, unit="mg")
    row["forms"] = [{"name": "Unknown Citrus Preparation", "order": 1,
                     "category": "botanical", "ingredientGroup": "Unknown Citrus",
                     "prefix": None}]
    enriched = pipeline(_raw_product(990205, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == "Hesperidin")
    assert quality["form_match_status"] == "unmapped"
    assert quality["unmapped_forms"] == ["Unknown Citrus Preparation"]


@pytest.mark.parametrize("name,group,category,form,parent,expected,grade", [
    ("Calcium", "Calcium", "mineral", "GIVOCAL", "calcium", "calcium glycerophosphate", 3),
    ("Magnesium", "Magnesium", "mineral", "GIVOMAG", "magnesium", "magnesium glycerophosphate", 2),
    ("Collagen Peptides", "Collagen", "protein", "KoACT Calcium Collagen Chelate",
     "collagen", "hydrolyzed collagen peptides", 11),
    ("Magnesium", "Magnesium", "mineral", "Magnesium HPC", "magnesium",
     "magnesium amino acid chelate", 11),
])
def test_verified_preparation_alias_keeps_existing_form_grade(
    pipeline, name, group, category, form, parent, expected, grade,
):
    row = _raw_row(1, name, group, category=category, quantity=100, unit="mg")
    row["forms"] = [{"name": form, "order": 1, "category": category,
                     "ingredientGroup": group, "prefix": None}]
    enriched = pipeline(_raw_product(990206, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == name)
    assert quality["canonical_id"] == parent
    assert quality["matched_form"] == expected
    assert quality["unmapped_forms"] == []
    assert quality["bio_score"] == grade
    assert quality["quantity"] == 100


def test_declared_sesame_lignan_mixture_keeps_family_identity(pipeline):
    row = _raw_row(1, "Sesame seed (Sesamum indicum) lignan extract", "Sesame",
                   category="botanical", quantity=20, unit="mg")
    enriched = pipeline(_raw_product(990207, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == row["name"])
    assert quality["canonical_id"] == "lignans"
    assert quality["matched_form"] != "sesamin (unspecified)"
    assert quality["identity_disposition"] != "identity_conflict"
    assert quality["quantity"] == 20


def test_singular_polyphenol_keeps_existing_family_identity(pipeline):
    row = _raw_row(1, "Polyphenol", "Polyphenol (unspecified)",
                   category="non-nutrient/non-botanical", quantity=10, unit="mg")
    enriched = pipeline(_raw_product(990208, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == row["name"])
    assert quality["canonical_id"] == "polyphenols"
    assert quality["identity_disposition"] != "identity_conflict"
    assert quality["quantity"] == 10


@pytest.mark.parametrize("name,group,parent,forms,grade", [
    ("Flavonoids", "Flavonoid (mixture)", "flavonoids", ["Monomers", "Oligomers"], 7),
    ("Masquelier's Original OPCs", "Proanthocyanidins", "opc",
     ["single and condensed (2-5) units of Flavanols & Polyphenols from grape seeds"], 5),
])
def test_composition_disclosure_does_not_invent_a_new_chemical_form(
    pipeline, name, group, parent, forms, grade,
):
    row = _raw_row(1, name, group, category="non-nutrient/non-botanical",
                   quantity=100, unit="mg", forms=forms)
    enriched = pipeline(_raw_product(990210, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
                   if r["name"] == name)
    assert quality["canonical_id"] == parent
    assert quality["unmapped_forms"] == []
    assert quality["bio_score"] == grade
    assert quality["quantity"] == 100


def test_shared_carotenoid_brand_keeps_disclosed_component_identity_and_amount(pipeline):
    rows = []
    for order, form, group, amount in [(1, "Lutein", "Lutein", 10),
                                       (2, "Zeaxanthin Isomers", "Zeaxanthin", 2)]:
        row = _raw_row(order, "Lutemax 2020", "Tagetes", quantity=amount, unit="mg")
        row["forms"] = [{"order": 1, "name": form, "category": "non-nutrient/non-botanical",
                         "ingredientGroup": group, "prefix": None, "percent": None}]
        rows.append(row)
    enriched = pipeline(_raw_product(298076, rows))
    subjects = enriched["activeIngredients"]
    assert [(r["canonical_id"], r["quantity"]) for r in subjects] == [("lutein", 10), ("zeaxanthin", 2)]
    quality = enriched["ingredient_quality_data"]["ingredients"]
    assert [(r["canonical_id"], r["quantity"]) for r in quality] == [("lutein", 10), ("zeaxanthin", 2)]
    assert all(not r["unmapped_forms"] for r in quality)


@pytest.mark.parametrize("case", ["partial", "multiple", "nested", "unreviewed_source", "marker_note"])
def test_source_component_routing_requires_one_complete_reviewed_declaration(case):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    row = _raw_row(1, "Lutemax 2020", "Tagetes", quantity=12, unit="mg")
    row["forms"] = [{"order": 1, "name": "Zeaxanthin Isomers",
                     "category": "non-nutrient/non-botanical", "ingredientGroup": "Zeaxanthin",
                     "prefix": None, "percent": None}]
    if case == "partial":
        row["forms"][0]["percent"] = 20
    elif case == "multiple":
        row["forms"].append({"name": "Lutein", "category": "non-nutrient/non-botanical",
                             "ingredientGroup": "Lutein"})
    elif case == "nested":
        row["nestedRows"] = [_raw_row(2, "Lutein", "Lutein", quantity=10, unit="mg")]
    elif case == "unreviewed_source":
        row["name"] = "Unknown Marigold Preparation"
    else:
        row["notes"] = "standardized to contain 20% zeaxanthin"
    assert EnhancedDSLDNormalizer()._single_declared_source_form_identity(row) is None


def test_lipo_cmax_source_preserves_separately_declared_calcium_amount(pipeline):
    row = _raw_row(1, "Calcium", "Calcium", category="mineral", quantity=40, unit="mg")
    row["forms"] = [{"order": 1, "name": "Lipo-Cmax", "category": "vitamin",
                     "ingredientGroup": "Vitamin C", "prefix": None, "percent": None}]
    enriched = pipeline(_raw_product(328794, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == "Calcium")
    assert quality["canonical_id"] == "calcium"
    assert quality["matched_form"] == "calcium ascorbate (as calcium source)"
    assert quality["unmapped_forms"] == []
    assert quality["quantity"] == 40 and quality["bio_score"] == 10


def test_phytopin_resolves_to_mixed_sterols_without_pine_bark_credit(pipeline):
    row = _raw_row(1, "Phytosterols", "Phytosterol (mixed)",
                   category="non-nutrient/non-botanical", quantity=500, unit="mg", forms=["PhytoPin"])
    enriched = pipeline(_raw_product(299745, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == "Phytosterols")
    assert quality["canonical_id"] == "phytosterols"
    assert quality["matched_form"] == "mixed phytosterols"
    assert quality["unmapped_forms"] == []
    assert quality["bio_score"] == 9 and quality["quantity"] == 500
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer()
    assert normalizer._resolve_canonical_identity("PhytoPin", raw_name="PhytoPin")[0] == "phytosterols"


@pytest.mark.parametrize("name,category,amount,parent,form,grade", [
    ("Vitamin C", "vitamin", 619, "vitamin_c", "calcium ascorbate", 13),
    ("Calcium", "mineral", 68, "calcium", "calcium ascorbate (as calcium source)", 10),
])
def test_chelamax_requires_exact_salt_context(pipeline, name, category, amount, parent, form, grade):
    row = _raw_row(1, name, name, category=category, quantity=amount, unit="mg")
    row["forms"] = [{"order": 1, "name": "ChelaMax", "category": "vitamin",
                     "ingredientGroup": "Calcium Ascorbate", "prefix": None}]
    enriched = pipeline(_raw_product(293952, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == name)
    assert quality["canonical_id"] == parent
    assert quality["matched_form"] == form and quality["bio_score"] == grade
    assert quality["unmapped_forms"] == [] and quality["quantity"] == amount


def test_unqualified_chelamax_does_not_invent_an_ascorbate_salt(pipeline):
    row = _raw_row(1, "Calcium", "Calcium", category="mineral", quantity=68, unit="mg", forms=["ChelaMax"])
    enriched = pipeline(_raw_product(990220, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == "Calcium")
    assert quality["form_match_status"] == "unmapped"
    assert quality["unmapped_forms"] == ["ChelaMax"]


def test_meriva_names_existing_preparation_without_changing_its_printed_mass(pipeline):
    row = _raw_row(1, "Meriva Turmeric Phytosome", "Turmeric", quantity=125, unit="mg")
    row["notes"] = "Meriva Turmeric Phytosome (Form: Turmeric (Curcuma longa) extract (Form: standardized to contain 18% Curcuminoids), and Phospholipid Complex)"
    row["forms"] = [{"order": 1, "name": "Phospholipid Complex", "category": "fat",
                     "ingredientGroup": "Phospholipid (unspecified)", "prefix": "and", "percent": None},
                    {"order": 2, "name": "Turmeric (Curcuma longa) extract", "category": "botanical",
                     "ingredientGroup": "Turmeric", "prefix": None, "percent": None}]
    enriched = pipeline(_raw_product(246351, [row]))
    quality = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == row["name"])
    assert quality["canonical_id"] == "curcumin"
    assert quality["matched_form"] == "meriva curcumin"
    assert quality["bio_score"] == 8
    assert quality["quantity"] == 125 and quality["unit"] == "mg"
    assert quality["unmapped_forms"] == []

@pytest.mark.parametrize("name,form", [("Protease", "Papain, Powder"), ("Protease II", "Papain")])
def test_specific_papain_declaration_uses_papain_owner(pipeline, name, form):
    row = _raw_row(1, name, "Proteolytic Enzymes (Proteases)", category="enzyme",
                   quantity=10, unit="mg", forms=(form,))
    row["forms"][0].update(ingredientGroup="Papain", category="enzyme", uniiCode="A236A06Y32")
    row["uniiCode"] = "0"
    enriched = pipeline(_raw_product("papain-specific", [row]))
    candidates = _rows(enriched, name)
    assert len(candidates) == 1
    assert candidates[0]["canonical_id"] == "papain"
    assert candidates[0]["form_match_status"] == "mapped"

@pytest.mark.parametrize("partial", [False, True])
def test_papain_source_mapping_does_not_claim_mixed_or_partial_enzyme_mass(partial):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    row = _raw_row(1, "Protease", "Proteolytic Enzymes (Proteases)", category="enzyme",
                   quantity=10, unit="mg", forms=("Papain",))
    row["forms"][0].update(category="enzyme", ingredientGroup="Papain")
    if partial:
        row["forms"][0]["percent"] = 50
    else:
        row["forms"].append({"name": "Bromelain", "category": "enzyme", "ingredientGroup": "Bromelain"})
    assert EnhancedDSLDNormalizer()._single_declared_source_form_identity(row) is None


def test_declared_smilax_china_does_not_borrow_sarsaparilla_species_grade(pipeline):
    row = _raw_row(1, "Sarsaparilla Root Extract", "Sarsaparilla", category="botanical",
                   quantity=1000, unit="mg", forms=("Smilax china Root Extract",))
    row["forms"][0].update(ingredientGroup="Chinese Smilax", category="botanical")
    enriched = pipeline(_raw_product("smilax-source", [row]))
    active = enriched["activeIngredients"][0]
    assert active["canonical_id"] == "chopchini"
    assert active["canonical_source_db"] == "botanical_ingredients"
    assert active["quantity"] == 1000
    assert active["forms"][0]["name"] == "Smilax china Root Extract"
    assert all(r.get("canonical_id") != "sarsaparilla" for r in _rows(enriched, row["name"]))


def test_achiote_leaf_is_a_botanical_material_not_seed_colorant(pipeline):
    row = _raw_row(1, "Achiote extract", "Annatto", category="botanical", quantity=500, unit="mg")
    row["notes"] = "Achiote extract PlantPart: leaf Note: 4:1 "
    enriched = pipeline(_raw_product("achiote-leaf", [row]))
    active = enriched["activeIngredients"][0]
    assert active["canonical_id"] == "achiote_leaf"
    assert active["canonical_source_db"] == "botanical_ingredients"
    assert active["quantity"] == 500
    assert active["plantPart"] == "leaf"
    assert active["notes"] == row["notes"]
    assert all(r.get("bio_score") is None for r in _rows(enriched, row["name"]))

@pytest.mark.parametrize("notes", ["", "Achiote extract PlantPart: seed", "Achiote extract PlantPart: unknown"])
def test_achiote_source_part_cannot_be_inferred_from_short_name(notes):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    row = _raw_row(1, "Achiote extract", "Annatto", category="botanical", quantity=500, unit="mg")
    row["notes"] = notes
    assert EnhancedDSLDNormalizer()._single_declared_source_form_identity(row) is None

@pytest.mark.parametrize("name,group,category,form,canonical", [
    ("White Willow Bark Extract", "White Willow", "botanical", "Salix babylonica Bark Extract", "weeping_willow_bark"),
    ("Pumpkin Seed Oil", "Pumpkin Seed Oil", "fat", "Cucurbita moschata Seed Oil", "butternut_squash_seed_oil"),
])
def test_specific_bark_or_seed_oil_does_not_borrow_another_species(pipeline, name, group, category, form, canonical):
    row = _raw_row(1, name, group, category=category, quantity=400, unit="mg", forms=(form,))
    row["forms"][0].update(category="botanical", ingredientGroup=form.split(" ")[0]+" "+form.split(" ")[1])
    if canonical == "weeping_willow_bark":
        row["uniiCode"] = "205MXS71H7"
        row["forms"][0]["uniiCode"] = "86LHC23T1R"
    enriched = pipeline(_raw_product("distinct-botanical-material", [row]))
    assert enriched["activeIngredients"][0]["canonical_id"] == canonical
    assert all(r.get("bio_score") is None for r in _rows(enriched, name))


def test_duplicate_chinese_wolfberry_forms_are_one_declared_species(pipeline):
    row = _raw_row(1, "Goji, Powder", "Goji", category="botanical", quantity=1000, unit="mg", forms=("Lycium chinense, Powder", "Lycium chinense, Powder"))
    for index, form in enumerate(row["forms"]):
        form.update(order=index+1, ingredientId=342854+index, category="botanical", ingredientGroup="Goji")
    enriched = pipeline(_raw_product("chinese-wolfberry", [row]))
    active = enriched["activeIngredients"][0]
    assert active["canonical_id"] == "chinese_wolfberry_fruit"
    assert active["quantity"] == 1000
    assert len(active["forms"]) == 2
    assert all(r.get("bio_score") is None for r in _rows(enriched, row["name"]))

@pytest.mark.parametrize("name,group,category,source,canonical,expected,grade", [
    ("Pycnogenol", "maritime Pine", "botanical", "French Maritime Pine Bark Extract, Dried", "pine_bark_extract", "pycnogenol", 10),
    ("Pycnogenol Maritime Pine extract", "maritime Pine", "botanical", "French Maritime Pines", "pine_bark_extract", "pycnogenol", 10),
    ("MBP", "Milk Basic Protein", "protein", "Milk Protein", "milk_basic_protein", "milk basic protein (unspecified)", 7),
    ("Omega-3", "Fish Oil", "fatty acid", "Fish Oil", "fish_oil", "fish oil (unspecified)", 8),
])
def test_existing_preparation_accepts_its_verified_parent_local_source(pipeline, name, group, category, source, canonical, expected, grade):
    row = _raw_row(1, name, group, category=category, quantity=40, unit="mg", forms=(source,))
    row["forms"][0]["category"] = {"protein":"protein", "fatty acid":"fat"}.get(category, "botanical")
    enriched = pipeline(_raw_product("existing-preparation-source", [row]))
    candidates = _rows(enriched, name)
    assert candidates and {r["canonical_id"] for r in candidates} == {canonical}
    expected_status = "n/a" if "(unspecified)" in expected else "mapped"
    assert all(r["form_match_status"] == expected_status and r["matched_form"] == expected and r["bio_score"] == grade for r in candidates)
    assert enriched["activeIngredients"][0]["quantity"] == 40


def test_standardized_botanical_keeps_whole_extract_identity_and_mass(pipeline):
    row = _raw_row(1, "Holixer", "Holy Basil", quantity=250, unit="mg")
    row["notes"] = "standardized to greater than or equal to 5% ocimum bioactive complex"
    row["forms"] = [
        {"name": "Apigenin-7-O-betaglucuronide", "category": "non-nutrient/non-botanical", "ingredientGroup": "TBD"},
        {"name": "Holy Basil Aerial Parts, Leaf Extract", "category": "botanical", "ingredientGroup": "Holy Basil"},
        {"name": "Luteolin-7-O-glucuronide", "category": "non-nutrient/non-botanical", "ingredientGroup": "TBD"},
        {"name": "Ociglycoside-I", "category": "non-nutrient/non-botanical", "ingredientGroup": "TBD"},
        {"name": "Rosmarinic Acid", "category": "non-nutrient/non-botanical", "ingredientGroup": "Rosmarinic Acid", "uniiCode": "MQE6XG29YI"},
        {"name": "Rabdosiin", "category": "non-nutrient/non-botanical", "ingredientGroup": "TBD"},
    ]
    enriched = pipeline(_raw_product("whole-standardized-botanical", [row]))
    active = enriched["activeIngredients"][0]
    assert active["canonical_id"] == "holy_basil"
    assert active["quantity"] == 250
    candidates = _rows(enriched, "Holixer")
    assert candidates and {r["canonical_id"] for r in candidates} == {"holy_basil"}
    assert all(r["matched_form"] == "holy basil extract" and r["bio_score"] == 10 for r in candidates)
    assert all(r["form_match_status"] == "mapped" and not r.get("unmapped_forms") for r in candidates)
    assert all(not r.get("delivers_markers") for r in candidates)
    standardization = enriched["formulation_data"]["standardized_botanicals"]
    assert standardization and all(r["percentage_found"] == 0 and not r["meets_threshold"] for r in standardization)


def test_disclosed_potassium_source_does_not_invent_a_chemical_salt(pipeline):
    row = _raw_row(1, "Potassium", "Potassium", category="mineral", quantity=70, unit="mg", forms=("Citrus Pectin, Modified",))
    row["forms"][0].update(category="fiber", ingredientGroup="Pectin", uniiCode="47EQO8LE7H")
    row["uniiCode"] = "RWP5GA015D"
    enriched = pipeline(_raw_product("pectin-carried-potassium", [row]))
    candidates = _rows(enriched, "Potassium")
    assert candidates and {r["canonical_id"] for r in candidates} == {"potassium"}
    assert all(r["form_match_status"] == "n/a" and r["matched_form"] == "potassium (unspecified)" and r["bio_score"] == 6 for r in candidates)
    assert enriched["activeIngredients"][0]["quantity"] == 70


def test_measurement_reference_does_not_become_an_isolated_flavonoid(pipeline):
    row = _raw_row(1, "Flavonoids", "Flavonoid (mixture)", category="non-nutrient/non-botanical", quantity=50, unit="mg", forms=("Hesperidin",))
    row["forms"][0].update(prefix="expressed as", ingredientGroup="Hesperidin")
    row["notes"] = "Flavonoids (Form: expressed as Hesperidin)"
    enriched = pipeline(_raw_product("flavonoid-measurement-reference", [row]))
    candidates = _rows(enriched, "Flavonoids")
    assert candidates and {r["canonical_id"] for r in candidates} == {"flavonoids"}
    assert all(r["form_match_status"] == "n/a" and r["matched_form"] == "flavonoids (unspecified)" and r["bio_score"] == 7 for r in candidates)
    assert enriched["activeIngredients"][0]["quantity"] == 50


def test_standardized_natto_enzyme_uses_activity_without_claiming_pure_enzyme_mass(pipeline):
    row = _raw_row(1, "Soy Natto extract", "Soy", quantity=100, unit="mg", forms=("Nattokinase",))
    row["forms"][0].update(category="enzyme", ingredientGroup="Nattokinase", prefix="supplying 2000 fibrinolytic units of")
    row["notes"] = "Soy Natto extract (Form: supplying 2000 fibrinolytic units of Nattokinase (Alt. Name: NSK-SD))"
    enriched = pipeline(_raw_product("natto-declared-enzyme-activity", [row]))
    candidates = _rows(enriched, "Soy Natto extract")
    assert candidates and {r["canonical_id"] for r in candidates} == {"nattokinase"}
    assert all(r["quantity"] == 100 and r["unit"] == "mg" for r in candidates)
    assert all(r["activity_quantity"] == 2000 and r["activity_unit"] == "FU" and r["dose_class"] == "enzyme_activity" for r in candidates)
    assert all(r["bio_score"] == 9 for r in candidates)
    assert any("NATTOKINASE" in alert["rule_id"] for alert in enriched["interaction_profile"]["ingredient_alerts"])
    from scoring_input_contract import get_evidence_subject_rows
    from scoring_v4.scored_artifact import build_scored_artifact
    build_scored_artifact(enriched)
    subjects = [r for r in get_evidence_subject_rows(enriched) if r.get("canonical_id") == "nattokinase"]
    assert any(r["quantity"] == 2000 and r["unit"] == "FU" for r in subjects)
    # The physical preparation row and activity projection retain the same
    # source; the former carries explicit activity rather than relabeling mg.
    assert all((r["quantity"] == 2000 and r["unit"] == "FU")
               or (r.get("activity_quantity") == 2000 and r.get("activity_unit") == "FU")
               for r in subjects)


def test_unqualified_fermented_soy_material_is_not_isolated_isoflavones_or_nattokinase(pipeline):
    enriched = pipeline(_raw_product("unqualified-natto-material", [_raw_row(1, "Soy Natto extract", "Soy", quantity=100, unit="mg")]))
    assert enriched["activeIngredients"][0]["canonical_id"] == "soybean"
    assert not any(r["canonical_id"] in {"nattokinase", "isoflavones"} for r in _rows(enriched, "Soy Natto extract"))


@pytest.mark.parametrize("source,expected,grade", [
    ("Fish Oil concentrate", "DHA fish oil triglyceride", 11),
    ("Algae Oil", "algal triglyceride", 12),
])
def test_long_dha_triglyceride_declaration_requires_its_actual_source(pipeline, source, expected, grade):
    child = _raw_row(2, "Docosahexaenoic Acid", "DHA (Docosahexaenoic Acid)", category="fatty acid", quantity=200, unit="mg", forms=("Docosahexaenoic Acid Triglyceride",))
    parent = _raw_row(1, source, source, category="fat", quantity=2410, unit="mg")
    parent["nestedRows"] = [child]
    enriched = pipeline(_raw_product("source-qualified-dha", [parent]))
    candidates = _rows(enriched, "Docosahexaenoic Acid")
    assert candidates and {r["canonical_id"] for r in candidates} == {"dha"}
    assert all(r["matched_form"] == expected and r["bio_score"] == grade and r["form_match_status"] == "mapped" for r in candidates)
    assert all(r["quantity"] == 200 for r in candidates)


def test_dha_triglyceride_without_source_does_not_choose_fish_algae_or_rtg(pipeline):
    child = _raw_row(1, "Docosahexaenoic Acid", "DHA (Docosahexaenoic Acid)", category="fatty acid", quantity=200, unit="mg", forms=("Docosahexaenoic Acid Triglyceride",))
    enriched = pipeline(_raw_product("unknown-source-dha", [child]))
    assert all(r["form_match_status"] == "unmapped" for r in _rows(enriched, "Docosahexaenoic Acid"))
