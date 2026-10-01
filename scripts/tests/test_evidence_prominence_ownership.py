"""Generic Evidence reads prominence from the shared role owner (Phase 2).

``scoring_input_contract.classify_ingredient_roles`` decides which label rows
the product is about; ``evidence_resolver.evidence_prominent_row_keys`` is the
same owner decision read per row. Generic Evidence consumes it for the primary
floor anchor, the nutrition-authority floor, ingredient-evidence recovery and
collagen recovery instead of choosing a primary by mass.

The primary floor keeps one relative-mass comparison, on purpose: records
without a studied minimum have no other amount judgment in Evidence, so that
comparison is the uncovered exposure stand-in required by the Evidence -> Dose
transfer invariant. It never decides which row is the purpose.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product


FIXTURES = Path(__file__).parent / "fixtures"


def _enrich(fixture: str) -> dict:
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / fixture).read_text())
    return SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]


def _evidence(product: dict) -> dict:
    """The production Evidence dimension behind the public artifact."""
    from scoring_v4.scored_artifact import build_scored_artifact

    artifact = build_scored_artifact(product)
    return artifact["_v4_module_breakdown"]["dimensions"]["evidence"]


def _scored(product: dict) -> dict:
    from scoring_v4.modules.generic_evidence import score_evidence

    return score_evidence(product, apply_primary_floor=True, owner_scoped=True)


def _row(name, canonical_id, quantity, unit="mg", path=None, **extra):
    row = _ingredient(name=name, canonical_id=canonical_id, quantity=quantity, unit=unit)
    if path:
        row["raw_source_path"] = path
    row.update(extra)
    return row


# --- the owner decision, read per row ---------------------------------------

@pytest.mark.parametrize("leucine_mg", [1, 100, 10000])
def test_an_unrelated_ingredients_mass_never_changes_the_declared_purpose(leucine_mg):
    from evidence_resolver import evidence_owner_canonicals, evidence_prominent_row_keys

    product = _product(
        product_name="Sleep Melatonin",
        ingredients=[
            _row("Melatonin", "melatonin", 5, path="ingredientRows[0]"),
            _row("L-Leucine", "l_leucine", leucine_mg, path="ingredientRows[1]"),
        ],
        matches=[],
    )

    assert evidence_owner_canonicals(product) == {"melatonin"}
    assert evidence_prominent_row_keys(product) == {("ingredientRows[0]", "melatonin")}


def test_without_a_declared_or_material_purpose_no_row_is_prominent():
    """Retain-everything fallback (real 321604: boron 5 mg and hyaluronic acid
    3.3 mg beside a 401 mg UC-II blend). Only the blend's undisclosed member
    owns Evidence, and nothing with its own amount is the product's purpose,
    so no row may anchor a floor."""
    from evidence_resolver import evidence_prominent_row_keys

    product = _enrich("evidence_subject_321604_raw.json")
    assert {canonical for _, canonical in evidence_prominent_row_keys(product)} <= {"collagen"}
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor"] == 0.0
    assert evidence["metadata"]["nutrition_authority_canonical"] is None


# --- the primary floor --------------------------------------------------------

def test_a_heavier_undeclared_adjunct_never_anchors_the_floor():
    product = _product(
        product_name="Melatonin 3 mg",
        ingredients=[_row("Melatonin", "melatonin", 3, path="ingredientRows[0]"),
                     _row("L-Theanine", "l_theanine", 200, path="ingredientRows[1]")],
        matches=[_match(id="INGR_L_THEANINE", ingredient="L-Theanine",
                        standard_name="L-Theanine", study_type="rct_multiple",
                        matched_source_row_refs=["ingredientRows[1]"])],
    )

    payload = _scored(product)

    assert payload["metadata"]["evidence_owner_canonicals"] == ["melatonin"]
    assert payload["metadata"]["primary_evidence_floor"] == 0.0


def test_the_retained_exposure_stand_in_still_blocks_a_trace_declared_anchor():
    """Both are declared, but 2.5 mcg of vitamin D beside 600 mg of calcium is
    not floored at the consensus tier: no owner judges that anchor's exposure
    yet (decision packet D27). Calcium, the heavier declared purpose, anchors."""
    product = _product(
        product_name="Calcium with Vitamin D3",
        ingredients=[_row("Calcium", "calcium", 600, path="ingredientRows[0]"),
                     _row("Vitamin D3", "vitamin_d", 2.5, unit="mcg", path="ingredientRows[1]")],
        matches=[
            _match(id="INGR_CALCIUM", ingredient="Calcium", standard_name="Calcium",
                   matched_source_row_refs=["ingredientRows[0]"]),
            _match(id="INGR_VITAMIN_D3", ingredient="Vitamin D3", standard_name="Vitamin D3",
                   matched_source_row_refs=["ingredientRows[1]"]),
        ],
    )

    payload = _scored(product)

    assert payload["metadata"]["primary_evidence_floor_canonical"] == "calcium"
    assert payload["metadata"]["primary_evidence_floor"] == 14.0


def test_clinical_dose_gate_still_blocks_a_declared_purpose():
    product = _product(
        product_name="Melatonin 0.5 mg",
        ingredients=[_row("Melatonin", "melatonin", 0.5, path="ingredientRows[0]")],
        matches=[_match(id="INGR_MELATONIN", ingredient="Melatonin", standard_name="Melatonin",
                        min_clinical_dose=1.0, dose_unit="mg",
                        matched_source_row_refs=["ingredientRows[0]"])],
    )

    payload = _scored(product)

    assert payload["metadata"]["primary_evidence_floor"] == 0.0
    assert "SUB_CLINICAL_DOSE_DETECTED" in payload["metadata"]["flags"]


# --- the nutrition-authority floor --------------------------------------------

def test_authority_floor_follows_a_declared_essential_beside_a_heavier_co_purpose():
    """Both rows are named in the title; the essential one need not be heavier."""
    from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR

    product = _product(
        product_name="Zinc + Novel Root",
        ingredients=[_row("Zinc", "zinc", 15, path="ingredientRows[0]"),
                     _row("Novel Root", "novel_root", 600, path="ingredientRows[1]")],
        matches=[],
    )

    payload = _scored(product)

    assert payload["metadata"]["nutrition_authority_canonical"] == "zinc"
    assert payload["components"]["primary_evidence_floor"] == NUTRITION_AUTHORITY_FLOOR


def test_authority_floor_needs_a_disclosed_amount():
    product = _product(
        product_name="Zinc Blend",
        ingredients=[_row("Zinc Blend", "zinc_blend", 300, path="ingredientRows[0]",
                          is_proprietary_blend=True, cleaner_row_role="blend_header_total"),
                     _row("Zinc", "zinc", None, unit=None, path="ingredientRows[0].nestedRows[0]")],
        matches=[],
    )

    assert _scored(product)["metadata"]["nutrition_authority_canonical"] is None


# --- recovery ----------------------------------------------------------------

def test_ingredient_recovery_serves_a_prominent_dosed_row():
    """The title declares NAC; 1,000 mg of milk thistle no longer decides that
    its verified record can be recovered (the old rule required half its mass)."""
    product = _product(
        product_name="NAC 400 mg with Milk Thistle",
        ingredients=[_row("N-Acetyl Cysteine", "nac", 400, path="ingredientRows[0]",
                          standard_name="N-Acetylcysteine"),
                     _row("Milk Thistle", "milk_thistle", 1000, path="ingredientRows[1]")],
        matches=[],
    )

    assert "INGR_NAC" in _scored(product)["metadata"]["recovered_matches"]


def test_ingredient_recovery_never_serves_a_co_active_the_label_does_not_declare():
    product = _product(
        product_name="Milk Thistle Liver Support",
        ingredients=[_row("Milk Thistle", "milk_thistle", 1000, path="ingredientRows[0]"),
                     _row("N-Acetyl Cysteine", "nac", 600, path="ingredientRows[1]",
                          standard_name="N-Acetylcysteine")],
        matches=[],
    )

    assert "INGR_NAC" not in _scored(product)["metadata"]["recovered_matches"]


def test_collagen_recovery_follows_prominence():
    collagen = _row("Collagen Peptides", "collagen", 20, unit="Gram(s)", path="ingredientRows[0]",
                    standard_name="Collagen")
    declared = _product(product_name="Collagen Peptides", ingredients=[collagen], matches=[])
    assert _scored(declared)["metadata"]["recovered_matches"] == ["RECOVERED_COLLAGEN_PEPTIDES_V1"]

    token = _product(
        product_name="Biotin 5000 mcg",
        ingredients=[_row("Biotin", "vitamin_b7_biotin", 5000, unit="mcg", path="ingredientRows[0]"),
                     _row("Collagen Peptides", "collagen", 2, path="ingredientRows[1]",
                          standard_name="Collagen")],
        matches=[],
    )
    assert "RECOVERED_COLLAGEN_PEPTIDES_V1" not in _scored(token)["metadata"]["recovered_matches"]


# --- real DSLD labels through Clean -> Enrich -> Score ---------------------

def test_real_218600_a_lineage_owned_complex_never_demotes_the_active_it_supplies():
    """Solgar 218600 prints Phosphatidylserine 200 mg with its 1,000 mg
    supplying complex nested under it. The contract's competitor rule drops
    that complex (same mass counted twice), so the role owner's mass ratio must
    too (role test in test_v4_role_classification): PS stays the material
    purpose and keeps its floor."""
    from evidence_resolver import evidence_prominent_row_keys

    product = _enrich("prominence_lineage_218600_raw.json")
    assert ("ingredientRows[2]", "phosphatidylserine") in evidence_prominent_row_keys(product)
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "phosphatidylserine"
    assert evidence["components"]["primary_evidence_floor"] == 14.0


def test_real_210555_disclosed_members_of_the_title_named_blend_anchor_the_floor():
    """GNC Test 1700: the title names the "Test 1700 Activator" blend, whose
    disclosed members (Testofen 600 mg, KSM-66 600 mg) are the purpose."""
    from evidence_resolver import evidence_prominent_row_keys

    product = _enrich("prominence_blend_members_210555_raw.json")
    keys = evidence_prominent_row_keys(product)
    assert ("ingredientRows[2].nestedRows[0]", "fenugreek") in keys
    assert ("ingredientRows[2].nestedRows[1]", "ashwagandha") in keys
    assert not {key for key in keys if key[1] in {"magnesium", "zinc"}}
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "testofen fenugreek"
    assert evidence["components"]["primary_evidence_floor"] == 18.0


@pytest.mark.parametrize("fixture,member", [
    ("prominence_blend_total_328062_raw.json", "ashwagandha"),  # Sensoril in a 2-member 250 mg blend
    ("evidence_subject_219048_raw.json", "psyllium"),            # psyllium under a 3.1 g fiber blend
])
def test_real_blend_total_never_becomes_an_undisclosed_members_floor(fixture, member):
    """The member stays an Evidence owner and keeps its research points, but its
    own amount is not on the label, so the blend total cannot anchor a floor."""
    evidence = _evidence(_enrich(fixture))
    assert member in evidence["metadata"]["evidence_owner_canonicals"]
    assert evidence["metadata"]["primary_evidence_floor"] == 0.0
    assert evidence["components"]["clinical_evidence_pipeline"] > 0


@pytest.mark.parametrize("fixture", [
    "prominence_probiotic_species_236913_raw.json",  # title-named La-14, 0.5 mg
    "prominence_probiotic_species_232059_raw.json",  # BB536, the one pre-existing leak
])
def test_real_probiotic_organisms_never_borrow_generic_ingredient_recovery(fixture):
    """Live organisms are probiotic-Evidence owned. Generic contract recovery
    must not hand a species-level ingredient record to a strain row."""
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    _, recovered = resolved_clinical_matches(_enrich(fixture))
    assert recovered == []


@pytest.mark.parametrize("fixture,record,floor_canonical", [
    # INGR_GARLIC already links the 1,000 mg powder and its Allicin/Alliin rows
    ("prominence_rerecovery_217818_raw.json", "INGR_GARLIC", "garlic extract"),
    # INGR_OMEGA3 already links EPA, DHA and ALA
    ("prominence_rerecovery_1838_raw.json", "INGR_OMEGA3", "omega 3 fatty acids"),
])
def test_real_recovery_never_restamps_a_record_onto_a_row_it_already_links(
    fixture, record, floor_canonical,
):
    """Recovery supplies evidence enrichment did not link. Re-stamping an
    existing record onto one of its own rows would only narrow its source
    references (to a 1.5 mg Allicin marker, or to plant ALA)."""
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    product = _enrich(fixture)
    matches, recovered = resolved_clinical_matches(product, owner_scoped=True)
    assert recovered == []
    entry = next(m for m in matches if m.get("id") == record)
    assert len(entry.get("matched_source_row_refs") or []) > 1
    assert _evidence(product)["metadata"]["primary_evidence_floor_canonical"] == floor_canonical
