"""Regression tests for proprietary-blend dedupe and parsing (finding C10)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from proprietary_blend_detector import ProprietaryBlendDetector


def _partial_blend() -> dict:
    return {
        "name": "Digestive Enzyme Blend",
        "amount": 500,
        "unit": "mg",
        "ingredients": ["Amylase", "Protease"],
    }


def test_same_blend_projected_in_two_sections_is_penalized_once() -> None:
    detector = ProprietaryBlendDetector()
    blend = _partial_blend()

    result = detector.analyze_product({
        "activeIngredients": [blend],
        "otherIngredients": [dict(blend)],
    })

    assert len(result.blends_detected) == 1
    assert result.total_penalty_applicable == -5


def test_comma_formatted_embedded_amount_is_parsed_without_crashing() -> None:
    detector = ProprietaryBlendDetector()

    result = detector.analyze_product({
        "activeIngredients": [{
            "name": "Digestive Enzyme Blend",
            "amount": 500,
            "unit": "mg",
            "ingredients": ["Amylase 1,000 mg"],
        }]
    })

    detected = result.blends_detected[0]
    assert detected.ingredients_with_amounts[0]["amount"] == 1000.0
    assert detected.disclosure_level == "full"


def test_normalized_nested_disclosure_and_parent_quantity_are_read():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Proprietary Blend', 'quantity': 500, 'unit': 'mg',
        'nestedIngredients': [{'name': 'Collagen', 'quantity': 300, 'unit': 'mg'},
                              {'name': 'Hyaluronic Acid', 'quantity': 50, 'unit': 'mg'}],
    }]}).blends_detected
    assert blend.blend_total_amount == 500
    assert blend.disclosure_level == 'full'
    assert [r['amount'] for r in blend.ingredients_with_amounts] == [300, 50]


def test_typed_activity_is_disclosure_without_borrowing_the_parent_mass():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Digestive Enzyme Blend', 'quantity': 350, 'unit': 'mg',
        'nestedIngredients': [{'name': 'Protease', 'quantity': 0, 'unit': 'NP',
                               'activity_quantity': 75000, 'activity_unit': 'HUT'}],
    }]}).blends_detected
    assert blend.disclosure_level == 'full'
    assert blend.ingredients_with_amounts == [{'name': 'Protease', 'amount': 75000, 'unit': 'HUT'}]


def test_unknown_child_mass_does_not_become_full_disclosure():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Proprietary Blend', 'amount': 500, 'unit': 'mg',
        'ingredients': [{'name': 'One', 'quantity': -5, 'unit': 'mg'},
                        {'name': 'Two', 'quantity': float('nan'), 'unit': 'mg'}],
    }]}).blends_detected
    assert blend.disclosure_level == 'partial'
    assert blend.ingredients_with_amounts == []


def test_fully_disclosed_flattened_bcaa_members_reach_the_disclosure_owner():
    import json
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((Path(__file__).parent / "fixtures/bcaa_59952_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    before = deepcopy(cleaned)
    enricher = SupplementEnricherV3()
    disclosure = enricher._collect_proprietary_data(cleaned)
    assert cleaned == before
    [blend] = disclosure["blends"]
    assert blend["disclosure_level"] == "full"
    assert blend["source_row_ref"] == "ingredientRows[0]"
    assert [(r["name"], r["amount"]) for r in blend["child_ingredients"]] == [
        ("L-Leucine", 250), ("L-Isoleucine", 125), ("L-Valine", 125)]
    assert blend["hidden_count"] == 0
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    scored = build_scored_artifact(enriched)
    assert scored["quality_pillars_v4"]["transparency"]["score"] == 15
    assert scored["quality_pillars_v4"]["dose"]["score"] == 11.4
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == [
        "evidence_assessment_incomplete"]


def test_flattened_disclosure_restoration_rejects_incomplete_or_foreign_source_members():
    import json
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures/bcaa_59952_raw.json").read_text())
    original = EnhancedDSLDNormalizer().normalize_product(raw)
    enricher = SupplementEnricherV3()
    for change in ["hidden_amount", "missing_child", "foreign_parent", "duplicate_child"]:
        product = deepcopy(original)
        children = product["activeIngredients"]
        if change == "hidden_amount":
            children[1].update(quantity=0, unit="NP")
        elif change == "missing_child":
            children.pop()
        elif change == "foreign_parent":
            children[1]["parent_source_path"] = "ingredientRows[1]"
        else:
            children.append(deepcopy(children[1]))
        before = deepcopy(product)
        result = enricher._collect_proprietary_data(product)
        assert product == before
        assert result["blends"]
        assert not any(b["disclosure_level"] == "full" for b in result["blends"]), change


def test_real_whole_foods_blend_has_one_physical_header_and_all_source_paths():
    import json
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures/whole_foods_blend_176190_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    disclosure = SupplementEnricherV3()._collect_proprietary_data(cleaned)
    assert disclosure["blend_count"] == 2
    [whole] = [b for b in disclosure["blends"] if b["source_row_ref"] == "ingredientRows[1]"]
    assert [(c["name"], c["amount"]) for c in whole["child_ingredients"]] == [
        ("Green Tea extract", 364), ("Guarana seed extract", 50)]
    assert whole["disclosure_level"] == "full"
    assert whole["source_fields"] == ["activeIngredients[5]", "activeIngredients[6]", "activeIngredients[7]"]
    assert whole["evidence"]["source_fields"] == whole["source_fields"]


def _same_owner_blend_header_and_body():
    detector = {"name": "Superfood, Greens & Herbal Blends", "source_row_ref": "ingredientRows[1]",
                "source_field": "activeIngredients[5]", "total_weight": 0, "unit": "NP",
                "nested_count": 2, "sources": ["detector"], "disclosure_level": "full",
                "evidence": {"matched_text": "Whole Foods Blend"}}
    cleaner = {"name": "Whole Foods Blend:", "source_row_ref": "ingredientRows[1]",
               "source_field": "activeIngredients[5]", "source_fields": ["activeIngredients[5]", "activeIngredients[6]"],
               "total_weight": 0.0, "unit": "", "nested_count": 2,
               "child_ingredients": [{"name": "Green Tea extract", "amount": 364, "unit": "mg"}],
               "sources": ["cleaning"], "disclosure_level": "full",
               "evidence": {"source_fields": ["activeIngredients[5]", "activeIngredients[6]"]}}
    return detector, cleaner


def test_only_same_physical_unknown_zero_headers_merge_and_preserve_provenance():
    from enrich_supplements_v3 import SupplementEnricherV3

    detector, cleaner = _same_owner_blend_header_and_body()
    [merged] = SupplementEnricherV3()._merge_blend_evidence([detector], [cleaner])
    assert merged["source_row_ref"] == "ingredientRows[1]"
    assert merged["source_fields"] == cleaner["source_fields"]
    assert merged["evidence"]["source_fields"] == cleaner["evidence"]["source_fields"]


def test_distinct_physical_or_conflicting_positive_headers_remain_separate():
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()
    for change in ["different_source", "positive_conflict", "one_positive_one_unknown"]:
        detector, cleaner = _same_owner_blend_header_and_body()
        if change == "different_source":
            cleaner["source_row_ref"] = "ingredientRows[2]"
        elif change == "positive_conflict":
            detector.update(total_weight=400, unit="mg")
            cleaner.update(total_weight=500, unit="mg")
        else:
            detector.update(total_weight=400, unit="mg")
        assert len(enricher._merge_blend_evidence([detector], [cleaner])) == 2, change
