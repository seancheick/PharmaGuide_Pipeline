"""Audit of #188 (2026-10-20): statement clauses, presence precedence and export.

F1 a line break inside a list ("Contains:\\nMilk, Soy") split the list.
F2 "Free of dairy, which contains lactose." read the relative clause as a
   declaration. F3 "Allergen information:" lines were always "contains".
F4 a facility warning outranked a real ingredient. F5 the export wrote
   facility hits under "Contains:" and passed presence types the app does not
   know (facility_warning, ingredient_list). F6 the export matched "wheat"
   inside "buckwheat" and "pea" inside "peanut flavor".
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _hits(enricher, statement=None, ingredients=()):
    product = {
        "id": "99990", "fullName": "Test",
        "statements": [{"type": "Precautions", "notes": statement}] if statement else [],
        "activeIngredients": [{"name": "Vitamin C"}],
        "inactiveIngredients": [{"name": n} for n in ingredients],
    }
    return {h["allergen_id"]: h["presence_type"]
            for h in enricher._collect_contaminant_data(product)["allergens"]["allergens"]}


@pytest.mark.parametrize("statement,expected,presence", [
    ("Contains: milk,\nsoy", {"ALLERGEN_MILK", "ALLERGEN_SOY"}, "contains"),
    ("Contains:\nMilk, Soy", {"ALLERGEN_MILK", "ALLERGEN_SOY"}, "contains"),
    ("Contains: Milk\nSoy\nWheat", {"ALLERGEN_MILK", "ALLERGEN_SOY", "ALLERGEN_WHEAT"}, "contains"),
    ("Contains milk\tsoy", {"ALLERGEN_MILK", "ALLERGEN_SOY"}, "contains"),
    ("May contain:\nsoy, wheat", {"ALLERGEN_SOY", "ALLERGEN_WHEAT"}, "may_contain"),
    ("Contains:\r\nMilk.", {"ALLERGEN_MILK"}, "contains"),  # 287762
])
def test_f1_a_line_break_inside_a_list_keeps_the_list(enricher, statement, expected, presence):
    hits = _hits(enricher, statement)
    assert expected <= set(hits) and {hits[a] for a in expected} == {presence}


def test_f1_a_new_cue_on_a_new_line_still_starts_a_clause(enricher):
    hits = _hits(enricher, "Gluten-Free\r\nNon-GMO\r\nNo added sugar\r\nThis product contains whey protein isolate.")
    assert hits.get("ALLERGEN_MILK") == "contains"


@pytest.mark.parametrize("statement,absent", [
    ("Free of dairy, which contains lactose.", "ALLERGEN_MILK"),
    ("Made without wheat, which contains gluten.", "ALLERGEN_WHEAT"),
])
def test_f2_a_relative_clause_stays_in_the_negated_phrase(enricher, statement, absent):
    assert absent not in _hits(enricher, statement)


@pytest.mark.parametrize("statement,expected", [
    ("Allergen information: No milk, soy or wheat", {}),
    ("Allergen information: Manufactured in a facility that also processes milk and soy",
     {"ALLERGEN_MILK": "facility_warning", "ALLERGEN_SOY": "facility_warning"}),
    ("Allergens: Produced on equipment that also processes peanuts", {"ALLERGEN_PEANUTS": "facility_warning"}),
    ("Allergen Information: Fish, Soy", {"ALLERGEN_FISH": "contains", "ALLERGEN_SOY": "contains"}),
])
def test_f3_a_cue_inside_an_allergen_information_line_decides_presence(enricher, statement, expected):
    hits = _hits(enricher, statement)
    assert {a: hits[a] for a in hits if a in {"ALLERGEN_MILK", "ALLERGEN_SOY", "ALLERGEN_WHEAT", "ALLERGEN_PEANUTS", "ALLERGEN_FISH"}} == expected


def test_f4_an_ingredient_never_yields_to_a_facility_warning(enricher):
    # 76850 "Soft Chews Peanut Butter": peanuts are an ingredient.
    hits = _hits(enricher, "Manufactured in a facility that also processes peanuts and tree nuts.", ingredients=("Peanuts",))
    assert hits["ALLERGEN_PEANUTS"] == "ingredient_list"
    assert hits["ALLERGEN_TREE_NUTS"] == "facility_warning"


def test_probe_a_facility_quality_statement_names_no_allergen(enricher):
    assert "ALLERGEN_WHEAT" not in _hits(enricher, "Our facility tests every lot for gluten.")


def test_f5_export_maps_presence_to_the_app_vocabulary():
    from build_final_db import build_structured_allergens, generate_allergen_summary
    enriched = {"allergen_hits": [
        {"allergen_id": "ALLERGEN_MILK", "allergen_name": "Milk", "presence_type": "facility_warning", "severity_level": "moderate"},
        {"allergen_id": "ALLERGEN_SOY", "allergen_name": "Soy", "presence_type": "ingredient_list", "severity_level": "low"},
    ]}
    rows = {r["allergen_id"]: r["presence_type"] for r in build_structured_allergens(enriched)}
    assert rows == {"ALLERGEN_MILK": "manufactured_in_facility", "ALLERGEN_SOY": "contains"}
    summary = generate_allergen_summary(enriched)
    assert summary == "Contains: Soy. Made in a facility that also handles: Milk"


@pytest.mark.parametrize("pattern_text,term,expected", [
    ("wheat", "organic Buckwheat", False),     # 70066
    ("peanut flavor", "Pea", False),           # 78327
    ("peanut flavor", "yellow Peas", False),
    ("wheat grass", "organic Wheat Grass", True),
    ("fish", "Fish Gelatin", True),
])
def test_f6_export_allergen_row_matching_is_whole_word(pattern_text, term, expected):
    from build_final_db import matching_allergen_hits, normalize_text
    hit = {"allergen_id": "X"}
    assert bool(matching_allergen_hits([{"pattern": normalize_text(pattern_text), "hit": hit}], term)) is expected


def test_n1_cross_contact_penalty_rows_are_one_per_presence_type():
    # 239602: 8 facility allergens became 8 "What to consider" rows; the app
    # collapses only "Declared allergen source" rows (tradeoffs_section.dart
    # _collapseAllergenSources). Cross-contact rows are grouped here instead.
    from build_final_db import build_structured_allergens, derive_v4_tradeoffs
    facility = ["Wheat", "Eggs", "Fish", "Soy", "Tree Nuts", "Peanuts", "Crustaceans", "Sesame"]
    hits = [{"allergen_id": f"ALLERGEN_{n.upper().replace(' ', '_')}", "allergen_name": n,
             "presence_type": "facility_warning", "severity_level": "moderate"} for n in facility]
    hits += [
        {"allergen_id": "ALLERGEN_PEANUTS", "allergen_name": "Peanuts", "presence_type": "facility_warning", "severity_level": "high"},
        {"allergen_id": "ALLERGEN_SOY", "allergen_name": "Soy", "presence_type": "may_contain", "severity_level": "low"},
        {"allergen_id": "ALLERGEN_MILK", "allergen_name": "Milk", "presence_type": "may_contain", "severity_level": "moderate"},
        {"allergen_id": "ALLERGEN_MILK", "allergen_name": "Milk", "presence_type": "ingredient_list", "severity_level": "moderate"},
    ]
    enriched = {"allergen_hits": hits}
    rows = [p for p in derive_v4_tradeoffs({}, enriched)[1] if p["id"] == "B2"]
    assert [(r["presence"], r["label"]) for r in rows] == [
        ("contains", "Declared allergen source: Milk"),
        ("may_contain", "May contain: Milk, Soy"),
        ("manufactured_in_facility",
         "Made in a facility that also handles: Crustaceans, Eggs, Fish, Peanuts, Sesame, Soy, Tree Nuts, Wheat"),
    ]
    assert rows[2]["severity"] == "high"
    # The review-before-use card reads per-allergen blob allergens[], which stays one row each.
    assert len(build_structured_allergens(enriched)) >= 9


@pytest.mark.parametrize("statement", [
    "Allergen information: Tested for gluten",
    "Allergen information: Gluten tested",
    "Allergen information: Gluten < 20 ppm",
    "Allergen information: Below 20 ppm gluten",
    "Allergen information: zero gluten",
    "Allergen information: Wheat (gluten) free",
])
def test_n2_a_gluten_test_or_free_qualifier_is_not_a_contains_declaration(enricher, statement):
    assert "ALLERGEN_WHEAT" not in _hits(enricher, statement)


def test_n2_a_qualifier_drops_only_its_own_list_item(enricher):
    hits = _hits(enricher, "Allergen information: Milk, soy, gluten tested below 20 ppm")
    assert hits.get("ALLERGEN_MILK") == "contains" and hits.get("ALLERGEN_SOY") == "contains"
    assert "ALLERGEN_WHEAT" not in hits


@pytest.mark.parametrize("statement,absent", [
    ("Made in a facility that never handles peanuts.", "ALLERGEN_PEANUTS"),
    ("Produced on equipment that never processes peanuts.", "ALLERGEN_PEANUTS"),
    ("Produced in a facility that uses strict procedures to avoid gluten cross contamination.", "ALLERGEN_WHEAT"),
    ("Manufactured in a facility that tests every batch for gluten and processes no wheat.", "ALLERGEN_WHEAT"),
    ("Our facility uses testing to verify gluten levels.", "ALLERGEN_WHEAT"),
    # Already unflagged (no processing verb after the cue); kept as controls.
    ("We follow strict procedures to avoid gluten cross contamination in our facility.", "ALLERGEN_WHEAT"),
    ("Manufactured in a facility that tests for gluten.", "ALLERGEN_WHEAT"),
])
def test_n3_never_avoid_and_testing_wording_name_no_facility_source(enricher, statement, absent):
    assert absent not in _hits(enricher, statement)


@pytest.mark.parametrize("statement,expected", [
    ("Processed in a facility that also handles peanuts and wheat.",
     {"ALLERGEN_PEANUTS": "facility_warning", "ALLERGEN_WHEAT": "facility_warning"}),
    ("Made in a facility that tests for gluten and also processes milk and soy.",
     {"ALLERGEN_MILK": "facility_warning", "ALLERGEN_SOY": "facility_warning"}),
    ("Processed in a facility that also handles peanuts, fish (no shellfish).",
     {"ALLERGEN_PEANUTS": "facility_warning", "ALLERGEN_FISH": "facility_warning"}),
])
def test_n3_a_real_facility_source_still_reads(enricher, statement, expected):
    assert _hits(enricher, statement) == expected


@pytest.mark.parametrize("statement,expected", [
    ("Contains milk and may contain soy", {"ALLERGEN_MILK": "contains", "ALLERGEN_SOY": "may_contain"}),
    ("Contains milk, may contain soy", {"ALLERGEN_MILK": "contains", "ALLERGEN_SOY": "may_contain"}),
    ("Manufactured in a facility that contains milk and soy", {"ALLERGEN_MILK": "facility_warning", "ALLERGEN_SOY": "facility_warning"}),
    ("Contains Fish Processed in a facility that also processes milk and soy", {
        "ALLERGEN_FISH": "contains", "ALLERGEN_MILK": "facility_warning", "ALLERGEN_SOY": "facility_warning"}),
    ("Contains Fish. Processed in a facility that also processes milk and soy", {
        "ALLERGEN_FISH": "contains", "ALLERGEN_MILK": "facility_warning", "ALLERGEN_SOY": "facility_warning"}),
])
def test_presence_cues_keep_their_own_inline_lists(enricher, statement, expected):
    assert _hits(enricher, statement) == expected


@pytest.mark.parametrize("statement,expected", [
    ("Made in a dedicated facility, contains milk", {"ALLERGEN_MILK": "contains"}),
    ("Contains milk and not  manufactured in a facility that processes soy", {"ALLERGEN_MILK": "contains"}),
    ("Contains milk, packaged in a facility that processes soy", {"ALLERGEN_MILK": "contains", "ALLERGEN_SOY": "facility_warning"}),
    ("Processed in a facility with products that may contain, soy and wheat", {"ALLERGEN_SOY": "facility_warning", "ALLERGEN_WHEAT": "facility_warning"}),
])
def test_inline_cues_respect_relative_and_negated_facility_clauses(enricher, statement, expected):
    assert _hits(enricher, statement) == expected


@pytest.mark.parametrize("verb", ["manufactured", "made", "processed", "produced", "packaged", "bottled"])
@pytest.mark.parametrize("negator", ["not", "never"])
def test_negated_production_cues_do_not_declare_cross_contact(enricher, verb, negator):
    assert _hits(enricher, f"Contains milk and {negator}  {verb} in a facility that processes soy") == {
        "ALLERGEN_MILK": "contains"}


def test_bottled_facility_cue_still_names_cross_contact(enricher):
    assert _hits(enricher, "Contains milk and bottled in a facility that processes soy") == {
        "ALLERGEN_MILK": "contains", "ALLERGEN_SOY": "facility_warning"}
