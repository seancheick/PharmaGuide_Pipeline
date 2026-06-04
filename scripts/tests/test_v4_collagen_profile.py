"""V4 Phase 7 — Collagen Profile (formulation + dose adapters).

Collagen is not a vitamin and not a botanical. Re-scoped Phase 7 (the plan's
"evidence 1.1/20" premise was stale — collagen evidence already ~6.3/20 via the
generic pipeline). The real gap is DOSE: collagen products borrow their
co-formulated vitamins' RDA dose, so an underdosed collagen (2.5 g vs the studied
10-20 g) over-scores. This profile scores collagen on its own clinical dose range
and formulation quality, mass-dominance routed (a multivitamin with token collagen
stays generic).

Spec: docs/superpowers/specs/2026-06-01-v4-collagen-profile-design.md
"""
from __future__ import annotations

from scoring_v4.modules.collagen_profile import (  # noqa: E402
    is_collagen_product,
    score_collagen_formulation,
    score_collagen_dose,
    COLLAGEN_FORMULATION_CAP,
)


def _collagen(name="Verisol Bioactive Collagen Peptides", standard_name="Collagen Peptides",
              canonical_id="collagen", form="hydrolyzed collagen peptides",
              quantity=12, unit="Gram(s)", **extra):
    row = {
        "name": name, "standard_name": standard_name, "canonical_id": canonical_id,
        "matched_form": form, "quantity": quantity, "unit": unit, "mapped": True,
        "raw_taxonomy": {"category": "protein", "forms": [{"name": form}]},
    }
    row.update(extra)
    return row


def _mineral(name="Vitamin C", canonical_id="vitamin_c_ascorbic_acid", quantity=90, unit="mg"):
    return {"name": name, "standard_name": name, "canonical_id": canonical_id,
            "quantity": quantity, "unit": unit, "mapped": True,
            "raw_taxonomy": {"category": "vitamin"}}


def _product(rows):
    return {"status": "active", "product_name": "Collagen",
            "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows,
                                        "total_active": len(rows)}}


def _blend_anchor_evidence(canonical_id: str, name: str, dose_value: float, dose_unit: str = "Gram(s)"):
    return {
        "name": name,
        "canonical_id": canonical_id,
        "clean_identity_id": canonical_id,
        "scoring_parent_id": canonical_id,
        "evidence_canonical_id": canonical_id,
        "canonical_source_db": "ingredient_quality_map",
        "evidence_origin": "compatibility_derived",
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": dose_value,
        "dose_unit": dose_unit,
        "source": "activeIngredients",
        "raw_source_path": "ingredientRows[1]",
        "evidence_scope": "blend_level",
        "linked_rows": ["ingredientRows[1]"],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
    }


# --- detector (mass-dominance routed) --------------------------------------

def test_collagen_dominant_is_collagen_product():
    assert is_collagen_product(_product([_collagen()])) is True


def test_multivitamin_with_token_collagen_is_not_collagen():
    # vitamins dominate (collagen a trace add-on) -> stays generic
    rows = [_mineral("Vitamin C", "vitamin_c_ascorbic_acid", 500, "mg"),
            _collagen(quantity=100, unit="mg")]  # 0.1 g collagen vs 500 mg vit C
    assert is_collagen_product(_product(rows)) is False


def test_collagen_with_small_vitamin_cofactors_is_collagen():
    # 12 g collagen dominates vitamin C 90 mg -> collagen product
    rows = [_collagen(quantity=12, unit="Gram(s)"), _mineral("Vitamin C", quantity=90)]
    assert is_collagen_product(_product(rows)) is True


def test_non_collagen_is_not_collagen():
    assert is_collagen_product(_product([_mineral("Magnesium", "magnesium", 400)])) is False


# --- dose adapter (10-20 g range, UNIT-AWARE) ------------------------------

def test_dose_within_studied_range_grams():
    # 5 g is within the verified hydrolyzed-peptide range (2.5-10 g)
    out = score_collagen_dose(_product([_collagen(quantity=5, unit="Gram(s)")]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_dose_below_studied_range_underdosed_collagen():
    # genuinely underdosed: 0.5 g is below even the 2.5 g skin floor.
    out = score_collagen_dose(_product([_collagen(quantity=500, unit="mg")]))
    assert out["score"] == 10.0
    assert out["band"] == "below_studied_range"


def test_dose_above_studied_range():
    out = score_collagen_dose(_product([_collagen(quantity=30, unit="Gram(s)")]))
    assert out["score"] == 12.0
    assert out["band"] == "above_studied_range"


def test_dose_primary_no_dose_scores_zero_not_excluded():
    out = score_collagen_dose(_product([_collagen(quantity=0, unit="")]))
    assert out["score"] == 0.0
    assert out["band"] == "primary_no_dose"


def test_dose_corrected_peptide_skin_dose_2500mg_is_within_range():
    # 2.5 g is the VERIFIED Verisol skin dose (PMID 24401291), not underdosed.
    # The old 10-20 g range wrongly crushed it; corrected range is 2.5-10 g.
    out = score_collagen_dose(_product([_collagen(quantity=2500, unit="mg")]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_dose_peptide_below_2g_is_below_range():
    out = score_collagen_dose(_product([_collagen(quantity=1000, unit="mg")]))
    assert out["band"] == "below_studied_range"


def test_dose_uc2_40mg_is_within_range():
    # UC-II / undenatured Type II is clinically dosed at 40 mg (PMID 26822714),
    # NOT the 10-20 g hydrolyzed-peptide range.
    row = _collagen(name="UC-II Undenatured Type II Collagen", standard_name="UC-II",
                    canonical_id="collagen", form="undenatured type ii collagen uc-ii",
                    quantity=40, unit="mg")
    out = score_collagen_dose(_product([row]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_dose_uc2_far_below_40mg_is_below():
    row = _collagen(name="UC-II", standard_name="UC-II", canonical_id="collagen",
                    form="undenatured type ii collagen uc-ii", quantity=10, unit="mg")
    out = score_collagen_dose(_product([row]))
    assert out["band"] == "below_studied_range"


def test_dose_biocell_hydrolyzed_type2_1000mg_within():
    row = _collagen(name="BioCell Collagen", standard_name="BioCell",
                    canonical_id="collagen", form="biocell hydrolyzed type ii collagen",
                    quantity=1000, unit="mg")
    out = score_collagen_dose(_product([row]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_scorer_prefers_enricher_emitted_collagen_subtype():
    # When the enricher stamps an authoritative collagen_subtype, the scorer uses
    # it instead of re-deriving from text. A 40 mg row flagged undenatured_type_ii
    # scores against the UC-II 40 mg range (within), even with generic form text.
    row = _collagen(name="Collagen", standard_name="Collagen", canonical_id="collagen",
                    form="collagen", quantity=40, unit="mg", collagen_subtype="undenatured_type_ii")
    out = score_collagen_dose(_product([row]))
    assert out["band"] == "within_studied_range"
    assert out["score"] == 21.0


def test_combo_peptides_plus_ucii_does_not_misroute_dominant_peptides():
    # "Collagen Peptides + UC-II" combo: 10 g peptides dominate a 40 mg UC-II
    # co-ingredient. The dominant peptide row must NOT be routed to the UC-II
    # 40 mg range just because the product NAME mentions UC-II (P2 review fix:
    # UC-II/NEM are identified from the row's own identity, not the title).
    peptides = _collagen(name="Hydrolyzed Collagen Peptides", canonical_id="collagen",
                         form="hydrolyzed collagen peptides", quantity=10, unit="Gram(s)")
    ucii = _collagen(name="UC-II", standard_name="UC-II", canonical_id="collagen",
                     form="undenatured type ii collagen uc-ii", quantity=40, unit="mg")
    product = _product([peptides, ucii])
    product["product_name"] = "Collagen Peptides Plus UC-II"
    out = score_collagen_dose(product)
    assert out["band"] == "within_studied_range"  # 10 g peptides, NOT UC-II 40 mg
    assert out["score"] == 21.0


def test_dose_pure_type2_1000mg_routes_hydrolyzed_type2_within():
    # A standalone "Type II Collagen" at 1 g is hydrolyzed Type II (BioCell class,
    # 500-2000 mg), NOT the 2.5-10 g peptide range. Must be within, not crushed.
    row = _collagen(name="Type II Collagen Complex", standard_name="Type II Collagen",
                    canonical_id="collagen", form="type ii collagen complex",
                    quantity=1000, unit="mg")
    out = score_collagen_dose(_product([row]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_dose_multitype_peptide_blend_uses_peptide_range_not_type2():
    # A multi-type "Type I, II & III" hydrolyzed blend at 10 g is a PEPTIDE blend
    # (2.5-10 g), not a pure Type-II joint ingredient — must NOT route to BioCell.
    row = _collagen(name="Collagen Types I II III", standard_name="Collagen Peptides",
                    canonical_id="collagen", form="hydrolyzed type i type ii type iii collagen peptides",
                    quantity=10, unit="Gram(s)")
    out = score_collagen_dose(_product([row]))
    assert out["band"] == "within_studied_range"  # 10 g within 2.5-10 g peptide range


def test_dose_eggshell_membrane_500mg_within():
    row = _collagen(name="NEM Eggshell Membrane", standard_name="Eggshell Membrane",
                    canonical_id="collagen", form="natural eggshell membrane nem",
                    quantity=500, unit="mg")
    out = score_collagen_dose(_product([row]))
    assert out["score"] == 21.0
    assert out["band"] == "within_studied_range"


def test_dose_gelatin_10g_within():
    row = _collagen(name="Gelatin", standard_name="Gelatin", canonical_id="collagen",
                    form="bovine gelatin", quantity=10, unit="Gram(s)")
    out = score_collagen_dose(_product([row]))
    assert out["band"] == "within_studied_range"


def test_dose_anchor_only_treated_as_blend_total():
    out = score_collagen_dose(_product([_collagen(quantity=12, unit="Gram(s)",
                                                  scoring_input_kind="product_level_evidence",
                                                  evidence_type="blend_anchor_mass")]))
    assert out["score"] == 7.0
    assert out["band"] == "blend_total_only"


def test_product_level_collagen_evidence_is_visible_to_profile_scorer():
    product = {
        "status": "active",
        "product_name": "Multi-Collagen Complex",
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": [], "total_active": 0},
        "product_scoring_evidence": [
            _blend_anchor_evidence("collagen", "Multi-Collagen Complex", 9.85)
        ],
    }

    assert is_collagen_product(product) is True
    out = score_collagen_dose(product)
    assert out["score"] == 7.0
    assert out["band"] == "blend_total_only"


# --- formulation adapter (max 15) ------------------------------------------

def test_formulation_full_signal_caps_at_15():
    # recognized(6)+hydrolyzed(2)+type(2)+source(3)+quantified(2)+branded(3)=18 -> cap 15
    row = _collagen(name="Verisol Bioactive Collagen Peptides",
                    form="hydrolyzed type I type III bovine collagen peptides")
    out = score_collagen_formulation(_product([row]))
    assert out["score"] == COLLAGEN_FORMULATION_CAP == 15.0
    c = out["components"]
    assert c["recognized_collagen_identity"] == 6.0
    assert c["hydrolyzed_peptides"] == 2.0
    assert c["type_disclosed"] == 2.0
    assert c["source_disclosed"] == 3.0
    assert c["quantified_dose_present"] == 2.0
    assert c["branded_clinically_studied"] == 3.0


def test_formulation_plain_hydrolyzed_no_type_no_source_modest():
    row = _collagen(name="Collagen Peptides", form="hydrolyzed collagen peptides",
                    canonical_id="collagen")
    out = score_collagen_formulation(_product([row]))
    c = out["components"]
    assert c.get("recognized_collagen_identity") == 6.0
    assert c.get("hydrolyzed_peptides") == 2.0
    assert c.get("quantified_dose_present") == 2.0
    assert "type_disclosed" not in c
    assert "source_disclosed" not in c
    assert out["score"] == 10.0


def test_formulation_unhydrolyzed_gelatin_scores_lower_than_peptides():
    # Gelatin (not hydrolyzed peptides) is lower bioavailability — it gets the
    # recognized base + dose but no hydrolyzed credit, so it scores below an
    # equivalent hydrolyzed-peptide product.
    gelatin = _collagen(name="Gelatin", standard_name="Gelatin", canonical_id="collagen",
                        form="bovine gelatin")
    out = score_collagen_formulation(_product([gelatin]))
    c = out["components"]
    assert c.get("recognized_collagen_identity") == 6.0
    assert "hydrolyzed_peptides" not in c
    assert c.get("source_disclosed") == 3.0  # bovine
    assert c.get("quantified_dose_present") == 2.0
    assert out["score"] == 11.0  # 6 + 3 source + 2 dose, no hydrolyzed bonus
