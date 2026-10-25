"""Exact printed sources override contradictory transcription, never unknown fractions."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3

@pytest.fixture(scope="module")
def sources():
    return json.loads((Path(__file__).parent / "fixtures/batch12_label_source_raw.json").read_text())

@pytest.fixture(scope="module")
def products(sources):
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid, raw in sources.items():
        clean = normalizer.normalize_product(deepcopy(raw))
        enriched, _ = enricher.enrich_product(clean)
        result[pid] = clean, enriched
    return result

def row(clean, path):
    return next(r for r in clean["activeIngredients"] if r.get("raw_source_path") == path)

def test_oil_directions_and_total_are_exact_edition_bound(products):
    clean, _ = products["312832"]
    statements = json.dumps(clean["statements"]).lower()
    assert "three times" not in statements and "24000" not in statements
    assert "2 softgels daily" in statements
    assert [r["quantity"] for r in clean["activeIngredients"][:3]] == [800, 800, 800]

def test_whole_oyster_is_not_shell_and_has_no_invented_mineral_amount(products):
    clean, _ = products["330191"]
    r = row(clean, "ingredientRows[0]")
    assert r["name"] == "Oyster Extract"
    assert "whole" in json.dumps(r["forms"]).lower()
    assert "shell extract" not in json.dumps(r["forms"]).lower()
    assert r["quantity"] == 500 and r.get("canonical_id") != "calcium"
    assert "shellfish" in json.dumps(clean["statements"]).lower()

def test_cranberry_keeps_exact_species_and_actual_label_servings_conflict(products, sources):
    clean, _ = products["330664"]
    r = row(clean, "ingredientRows[0]")
    assert "macrocarpon" in json.dumps(r["forms"]).lower()
    assert "oxycoccus" not in json.dumps(r["forms"]).lower()
    assert "fruit" in json.dumps(r["forms"]).lower()
    assert r["quantity"] == 5 and clean["servingsPerContainer"] == 20
    assert clean["statements"] == sources["330664"]["statements"]

def test_reishi_spores_do_not_inherit_fruit_body_standardization(products):
    clean, _ = products["328649"]
    spores = row(clean, "ingredientRows[1]")
    assert "spore" in spores["name"].lower() and spores["quantity"] == 150
    assert "spore" in json.dumps(spores["forms"]).lower()
    assert "13.5%" not in json.dumps(spores)
    assert row(clean, "ingredientRows[0]")["quantity"] == 980

def test_fruit_members_belong_to_fruit_blend_without_changing_source_paths(products):
    clean, _ = products["43662"]
    members = [r for r in clean["activeIngredients"] if r.get("raw_source_path", "").startswith("ingredientRows[3].nestedRows")]
    assert len(members) == 3
    assert all(r.get("parentBlend") == "FoodState Farm Fresh Fruit Phenolic Blend" for r in members)
    assert all(r["quantity"] == 0 and r["unit"] in {"NP", "unspecified"} for r in members)
    assert row(clean, "ingredientRows[3]")["quantity"] == 200

def test_vesisorb_combined_constituents_are_not_all_cannabinoids(products, sources):
    clean, _ = products["277705"]
    combined = row(clean, "ingredientRows[0].nestedRows[0]")
    assert combined["name"] == "Phytocannabinoids and terpenes"
    assert combined["quantity"] == 35 and combined["score_eligible_by_cleaner"] is False
    assert row(clean, "ingredientRows[0].nestedRows[3]")["quantity"] == 25
    assert clean["statements"] == sources["277705"]["statements"]

def test_archived_psyllium_servings_and_species_are_not_modernized(products):
    clean, _ = products["312947"]
    assert clean["servingsPerContainer"] == 120
    r = row(clean, "ingredientRows[0]")
    assert r["quantity"] == 1400 and "husk" in r["notes"].lower()
    assert "asiatica" in json.dumps(r["forms"]).lower()
    assert "ovata" not in json.dumps(r["forms"]).lower()
    from scoring_v4.scored_artifact import build_scored_artifact
    scored = build_scored_artifact(products["312947"][1])
    assert scored["quality_score_status"] == "not_scored"
    assert "identity_assessment_readiness" in scored["assessment_readiness"]["unavailable_reasons"]

def test_printed_six_plus_supervision_is_not_four_plus_metadata(products, sources):
    clean, _ = products["285637"]
    assert "Children 4 or More Years of Age" not in clean["targetGroups"]
    assert any("6" in x and "supervision" in x for x in clean["targetGroups"])
    assert clean["statements"] == sources["285637"]["statements"]

def test_coconut_warning_and_cross_contact_survive_false_free_from_repair(products):
    clean, _ = products["268493"]
    statements = clean["statements"]
    assert "contains tree nuts (coconut)" in json.dumps(statements).lower()
    for statement in statements:
        text = statement.get("notes", "").lower()
        if "not manufactured with" in text:
            assert "tree nuts" not in text
    assert "third-party, audited" not in json.dumps(statements)

def test_mct_acacia_total_is_not_a_nine_gram_pure_mct_dose(products):
    clean, enriched = products["268493"]
    assert not any(r.get("canonical_id") == "mct_oil" and r.get("quantity") == 9
                   and r.get("score_eligible_by_cleaner") for r in clean["activeIngredients"])
    header = row(clean, "ingredientRows[4]")
    assert header["dose_class"] == "blend_total_weight" and not header["score_eligible_by_cleaner"]
    members = [r for r in clean["activeIngredients"] if r.get("parentBlend") == header["name"]]
    assert len(members) == 2
    assert all(r["quantity"] == 0 and r["unit"] in {"NP", "unspecified"} for r in members)
    assert any(r.get("canonical_id") == "mct_oil" for r in members)
    assert not any(r.get("canonical_id") == "mct_oil" and r.get("quantity", 0) > 0
                   for r in enriched["ingredient_quality_data"].get("ingredients_scorable", []))
    assert any(r.get("quantity") == 9 and "acacia" in r.get("name", "").lower()
               for r in clean["activeIngredients"] + clean.get("display_ingredients", []))

@pytest.mark.parametrize("pid", ["312832","330191","330664","328649","43662","277705","312947","285637","268493"])
def test_source_changes_cannot_silently_inherit_a_reviewed_edition(sources, pid):
    raw = deepcopy(sources[pid])
    raw["statements"].append({"type": "Warning", "notes": "changed source edition"})
    with pytest.raises(ValueError, match="Reviewed serving source changed"):
        EnhancedDSLDNormalizer().normalize_product(raw)


@pytest.mark.parametrize("pid,field,changed", [
    ("312947", "servingsPerContainer", "121"),
    ("285637", "targetGroups", ["Children 2 years and older"]),
])
def test_top_level_source_metadata_is_independently_bound(sources, pid, field, changed):
    raw = deepcopy(sources[pid])
    raw[field] = changed
    with pytest.raises(ValueError, match="Reviewed product metadata changed"):
        EnhancedDSLDNormalizer().normalize_product(raw)


def test_corrections_preserve_original_input_and_unrelated_edition(sources):
    raw = deepcopy(sources["268493"])
    before = deepcopy(raw)
    EnhancedDSLDNormalizer().normalize_product(raw)
    assert raw == before
    unrelated = deepcopy(sources["312832"])
    unrelated["id"] = "294583"
    clean = EnhancedDSLDNormalizer().normalize_product(unrelated)
    assert clean["statements"] == unrelated["statements"]


def test_hierarchy_correction_rejects_cross_parent_mismatch(sources):
    n = EnhancedDSLDNormalizer()
    entry = deepcopy(n._label_corrections_by_dsld_id["43662"])
    entry["corrected_child_row_refs"][0]["raw_parent_source_path"] = "ingredientRows[4]"
    n._label_corrections_by_dsld_id = {"43662": entry}
    with pytest.raises(ValueError, match="Reviewed hierarchy child changed"):
        n.normalize_product(deepcopy(sources["43662"]))


def test_hierarchy_correction_rejects_final_graph_cycle_before_mutation():
    rows = [{"name": name, "raw_source_path": f"ingredientRows[{i}]",
             "quantity": [{"quantity": 1, "unit": "mg"}], "nestedRows": []}
            for i, name in enumerate(["A", "B"])]
    entries = []
    for i in range(2):
        entries.append({"raw_source_path": f"ingredientRows[{i}]", "raw_ingredient_text": rows[i]["name"],
            "raw_quantity_value": 1, "raw_quantity_unit": "mg",
            "corrected_child_row_refs": [{"raw_source_path": f"ingredientRows[{1-i}]",
                                          "raw_ingredient_text": rows[1-i]["name"], "raw_child_names": []}]})
    n = EnhancedDSLDNormalizer()
    n._label_corrections_by_dsld_id = {"test": {**entries[0], "additional_row_corrections": entries[1:]}}
    original = deepcopy(rows)
    with pytest.raises(ValueError, match="creates a cycle"):
        n._apply_label_corrections(rows, "test")
    assert rows == original


def test_cranberry_consumer_copy_does_not_deny_the_disclosed_fruit_powder(products):
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    _, enriched = products["330664"]
    blob = build_detail_blob(enriched, build_scored_artifact(enriched))
    ingredient = next(r for r in blob["ingredients"] if r.get("canonical_id") == "cranberry")
    assert "macrocarpon fruit powder" in ingredient["display_form_label"]
    assert "without identifying whole fruit" not in (ingredient.get("form_note") or "")
    assert "PAC" in ingredient["form_note"]
