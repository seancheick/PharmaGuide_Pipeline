"""Regression tests for supplement_taxonomy.py bugs surfaced by the
v4-adoption audit (2026-05-20).

Each `test_BUG_*` documents a specific misclassification with a real
failing case. The tests are written RED-state — they FAIL on the current
classifier and pass once the taxonomy decision tree is fixed.

Test naming convention:
    test_BUG_<N>_<short_label>  — single failing case per bug, with full
    real-world context in the docstring.

To run only these regression tests:
    pytest scripts/tests/test_supplement_taxonomy_bugs.py -v

When a bug is fixed, leave the test in place — it becomes a permanent
regression guard.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supplement_taxonomy import classify_supplement, PRIMARY_TYPES


# ============================================================================
# BUG-1: Prenatal-with-DHA classifies as omega_3 instead of multivitamin
# ============================================================================

def test_BUG_1_prenatal_with_dha_misclassifies_as_omega_3():
    """The omega-3 decision-tree branch fires before the multivitamin branch.
    A prenatal multivitamin that happens to include DHA (Vitafusion PreNatal
    Gummy, SmartyPants PreNatal — both real catalog products) gets
    primary_type=omega_3 even though they have 10+ vitamins and 2+ minerals.

    The v4 router compensates via prenatal-keyword Priority 2, so routing
    is correct. But primary_type is misleading for downstream consumers
    (Flutter, percentile_category, scoring scope).

    Fix candidates:
      - Re-order decision tree so multivitamin check fires before omega-3
        when active_count >= 6 and vitamin_count + mineral_count >= 4
      - OR have the omega-3 branch require omega_signal AND not multi panel
    """
    product = {
        "product_name": "PreNatal Natural Raspberry Lemonade Flavor",
        "fullName": "PreNatal Natural Raspberry Lemonade Flavor",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamin", "quantity": 1500, "unit": "mcg"},
            {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin", "quantity": 60, "unit": "mg"},
            {"name": "Vitamin D3", "canonical_id": "vitamin_d", "category": "vitamin", "quantity": 25, "unit": "mcg"},
            {"name": "Vitamin E", "canonical_id": "vitamin_e", "category": "vitamin", "quantity": 15, "unit": "mg"},
            {"name": "Vitamin B6", "canonical_id": "vitamin_b6", "category": "vitamin", "quantity": 1.9, "unit": "mg"},
            {"name": "Folate", "canonical_id": "folate", "category": "vitamin", "quantity": 800, "unit": "mcg"},
            {"name": "Vitamin B12", "canonical_id": "vitamin_b12", "category": "vitamin", "quantity": 8, "unit": "mcg"},
            {"name": "Biotin", "canonical_id": "biotin", "category": "vitamin", "quantity": 300, "unit": "mcg"},
            {"name": "Iodine", "canonical_id": "iodine", "category": "mineral", "quantity": 150, "unit": "mcg"},
            {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 4, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "category": "fatty_acid", "quantity": 50, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "multivitamin", (
        f"Prenatal with DHA + 10 vitamins/minerals must classify as multivitamin, "
        f"got {result['primary_type']!r}. The omega-3 branch is firing first."
    )


# ============================================================================
# BUG-2: Sleep aid with herb plurality → herbal_botanical instead of sleep_support
# ============================================================================

def test_BUG_2_night_token_misses_sleep_classification():
    """Real product: Hum Mighty Night (DSLD 241699).

    Name is just `Mighty Night` with no other sleep-keyword context.
    Classifier returns `herbal_botanical` because:
      - `_SLEEP_NAME_TOKENS` = {sleep, melatonin, nighttime, night time,
        pm, rest, calm sleep} — does NOT include the standalone word
        "night"
      - The product has 5 herbs + 1 amino acid → herb plurality (>60%)
        wins over the (silent) sleep-name branch
      - Result: herbal_botanical conf=0.6

    Fix candidates:
      A. Add `night` (or `\bnight\b`) to `_SLEEP_NAME_TOKENS`.
         Risk: false positives like "midnight cream" — but the broader
         classifier already requires `active_count >= 2`, and gummy/
         topical products are filtered upstream.
      B. Add an explicit ingredient-canonical sleep-detection branch
         (`melatonin` canonical_id presence implies sleep intent).

    The synthetic ingredient composition mirrors DSLD 241699's real panel.
    """
    product = {
        "product_name": "Mighty Night",
        "fullName": "Mighty Night",
        "bundleName": "",
        "ingredient_quality_data": {"ingredients": [
            # Real product ships melatonin with category=other (not herb)
            {"name": "Melatonin", "canonical_id": "melatonin", "category": "other", "quantity": 3, "unit": "mg"},
            {"name": "Valerian Root", "canonical_id": "valerian", "category": "herb", "quantity": 200, "unit": "mg"},
            {"name": "Chamomile", "canonical_id": "chamomile", "category": "herb", "quantity": 100, "unit": "mg"},
            {"name": "Lavender", "canonical_id": "lavender", "category": "herb", "quantity": 50, "unit": "mg"},
            {"name": "Passion Flower", "canonical_id": "passion_flower", "category": "herb", "quantity": 100, "unit": "mg"},
            {"name": "L-Theanine", "canonical_id": "l_theanine", "category": "amino_acid", "quantity": 200, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "sleep_support", (
        f"Product named 'Mighty Night' with melatonin + valerian must "
        f"classify as sleep_support, got {result['primary_type']!r}. "
        f"The name token 'night' is not matching any sleep keyword."
    )


# ============================================================================
# BUG-3: Probiotic name + NP/zero-qty strains → general_supplement (active_count gate)
# ============================================================================

def test_BUG_3_probiotic_name_with_np_strains_misclassifies_as_general():
    """8 real catalog products surfaced with `probiotic` in the name +
    primary_type=general_supplement + confidence=0.0 (e.g. DSLD 18258,
    68872, 12141).

    Root cause: classify_supplement line 383 requires `active_count > 0`
    for the probiotic branch. When the enricher hasn't populated
    `probiotic_data.is_probiotic_product` AND all strains are NP/zero-qty,
    the NP filter excludes every row → active_count=0 → probiotic branch
    skipped → falls through to general_supplement.

    Fix: probiotic detection should fire on (probiotic name signal + at
    least one probiotic-strain row in non_quantified_rows) when
    active_count==0, with low confidence rather than no classification.
    """
    product = {
        "product_name": "Probiotic - Acidophilus",
        "fullName": "Probiotic - Acidophilus",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Lactobacillus acidophilus", "category": "probiotic",
             "quantity": 0, "unit": "NP"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "probiotic", (
        f"Product named 'Probiotic - Acidophilus' must classify as probiotic, "
        f"got {result['primary_type']!r} (confidence={result['classification_confidence']})."
    )


def test_probiotic_name_and_enriched_strain_identity_survive_empty_scorable_rows():
    product = {
        "product_name": "FloraMend Prime Probiotic",
        "activeIngredients": [
            {
                "name": "Lactobacillus gasseri KS-13",
                "canonical_id": "lactobacillus_gasseri",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "nested_display_only",
            }
        ],
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients": [],
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 3,
            "total_cfu": 0,
        },
    }

    result = classify_supplement(product)

    assert result["primary_type"] == "probiotic"
    assert result["classification_confidence"] >= 0.6


# ============================================================================
# BUG-4: BCAA / Essential Amino Acids → general_supplement
# ============================================================================

def test_BUG_4_bcaa_blend_misclassifies_as_general():
    """BCAA products (L-Leucine + L-Isoleucine + L-Valine) classify as
    general_supplement because the canonical_ids `l_leucine`, `l_isoleucine`,
    `l_valine` are NOT in `_AMINO_ACID_IDS`. Only `bcaa` (the compound
    canonical) is. Real catalog: DSLD 222713 "BCAA 1000 mg".

    Fix: either add l_leucine/l_isoleucine/l_valine to `_AMINO_ACID_IDS`,
    or add a name-keyword check for `bcaa`, `eaa`, `amino acid`, `essential
    amino` in the functional-name branch.
    """
    product = {
        "product_name": "BCAA 1000 mg",
        "ingredient_quality_data": {"ingredients": [
            {"name": "L-Leucine", "canonical_id": "l_leucine", "category": "amino_acid", "quantity": 500, "unit": "mg"},
            {"name": "L-Isoleucine", "canonical_id": "l_isoleucine", "category": "amino_acid", "quantity": 250, "unit": "mg"},
            {"name": "L-Valine", "canonical_id": "l_valine", "category": "amino_acid", "quantity": 250, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "amino_acid", (
        f"BCAA blend must classify as amino_acid, got {result['primary_type']!r}."
    )


def test_BUG_4b_essential_amino_acids_misclassifies_as_general():
    """Real catalog product: 'Essential Amino Acids' (DSLD 241772).
    Name is unambiguous but classifier returns general_supplement conf=0.3.

    Fix: add `amino acid`, `essential amino` to functional-name keyword
    detection.
    """
    product = {
        "product_name": "Essential Amino Acids",
        "ingredient_quality_data": {"ingredients": [
            {"name": "L-Lysine", "canonical_id": "l_lysine", "category": "amino_acid", "quantity": 500, "unit": "mg"},
            {"name": "L-Methionine", "canonical_id": "l_methionine", "category": "amino_acid", "quantity": 500, "unit": "mg"},
            {"name": "L-Threonine", "canonical_id": "l_threonine", "category": "amino_acid", "quantity": 500, "unit": "mg"},
            {"name": "L-Phenylalanine", "canonical_id": "l_phenylalanine", "category": "amino_acid", "quantity": 500, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "amino_acid", (
        f"Essential Amino Acids must classify as amino_acid, got {result['primary_type']!r}."
    )


# ============================================================================
# BUG-5: Single-ingredient functional products → general_supplement
# ============================================================================

def test_BUG_5a_melatonin_single_ingredient_misclassifies_as_general():
    """Single Melatonin product. The single-active branch at line 410
    handles vitamins, minerals, amino_acids, herbs, and collagen but
    nothing else. `melatonin` is neutral category (not herb in the data
    file), so it falls to general_supplement.

    Real catalog: DSLD 18142 'Melatonin All Natural Strawberry Flavor'.

    Fix: add a single-ingredient branch for sleep_support when
    canonical_id == melatonin or 5_htp.
    """
    product = {
        "product_name": "Melatonin 3 mg",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Melatonin", "canonical_id": "melatonin", "category": "other",
             "quantity": 3, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "sleep_support", (
        f"Single Melatonin must classify as sleep_support, "
        f"got {result['primary_type']!r}."
    )


def test_BUG_5b_msm_single_ingredient_misclassifies_as_general():
    """Single MSM product — joint-support ingredient. Real catalog:
    DSLD 1253 'Best MSM', 202773 'MSM with OptiMSM 1000 mg'.

    Fix: add joint_support single-ingredient branch for msm, glucosamine,
    chondroitin, hyaluronic_acid.
    """
    product = {
        "product_name": "MSM 1000 mg",
        "ingredient_quality_data": {"ingredients": [
            {"name": "MSM", "canonical_id": "msm", "category": "other",
             "quantity": 1000, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "joint_support", (
        f"Single MSM must classify as joint_support, got {result['primary_type']!r}."
    )


# ============================================================================
# BUG-7: Pre-Workout has no taxonomy branch → falls to amino_acid/other
# ============================================================================

def test_BUG_7_preworkout_has_no_branch():
    """`pre_workout` is defined in PRIMARY_TYPES (vocab) but the classifier
    has NO decision tree branch for it. Products are mis-classified to
    whatever else fires (amino_acid, multivitamin, general_supplement).

    Fix: add pre_workout branch using name signals (`pre-workout`,
    `pre workout`, `preworkout`) + caffeine/beta-alanine/creatine content
    heuristic.
    """
    product = {
        "product_name": "Pre-Workout Powder Citrus Burst",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Caffeine", "canonical_id": "caffeine", "category": "other", "quantity": 200, "unit": "mg"},
            {"name": "Beta Alanine", "canonical_id": "beta_alanine", "category": "amino_acid", "quantity": 2000, "unit": "mg"},
            {"name": "Creatine", "canonical_id": "creatine", "category": "amino_acid", "quantity": 5000, "unit": "mg"},
            {"name": "Citrulline Malate", "canonical_id": "l_citrulline", "category": "amino_acid", "quantity": 6000, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "pre_workout", (
        f"Pre-workout must classify as pre_workout, got {result['primary_type']!r}."
    )


# ============================================================================
# BUG-8: Protein products have no taxonomy branch
# ============================================================================

def test_BUG_8_protein_powder_has_no_branch():
    """`protein_powder` is in PRIMARY_TYPES but the classifier has no
    branch for it. Real catalog: 3 protein products in the sample swept
    all fell to general_supplement.

    Fix: add protein_powder branch on category=protein OR name keyword
    `whey`, `casein`, `pea protein`, `protein powder`, `protein isolate`.
    """
    product = {
        "product_name": "Whey Protein Isolate Vanilla",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Whey Protein Isolate", "canonical_id": "whey_protein",
             "category": "protein", "quantity": 25000, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "protein_powder", (
        f"Whey Protein Isolate must classify as protein_powder, "
        f"got {result['primary_type']!r}."
    )


# ============================================================================
# BUG-9: Greens powder has no taxonomy branch
# ============================================================================

def test_BUG_9_greens_powder_has_no_branch():
    """`greens_powder` is in PRIMARY_TYPES but no decision-tree branch.
    Greens products fall to herbal_botanical or vitamin_mineral_combo
    depending on composition.

    Fix: add greens_powder branch on name keyword `greens`, `reds powder`,
    `superfood`, OR composition with spirulina/chlorella/wheatgrass.
    """
    product = {
        "product_name": "Super Greens Powder",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Spirulina", "canonical_id": "spirulina", "category": "herb", "quantity": 1000, "unit": "mg"},
            {"name": "Chlorella", "canonical_id": "chlorella", "category": "herb", "quantity": 1000, "unit": "mg"},
            {"name": "Wheatgrass", "canonical_id": "wheatgrass", "category": "herb", "quantity": 500, "unit": "mg"},
            {"name": "Barley Grass", "canonical_id": "barley_grass", "category": "herb", "quantity": 500, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "greens_powder", (
        f"Greens powder must classify as greens_powder, "
        f"got {result['primary_type']!r}."
    )


# ============================================================================
# BUG-10: Electrolyte has no taxonomy branch
# ============================================================================

def test_BUG_10_electrolyte_has_no_branch():
    """`electrolyte` is in PRIMARY_TYPES but no decision-tree branch.
    A 4-mineral product with name=Electrolyte should not be
    vitamin_mineral_combo because the use case is hydration, not
    nutritional supplementation.
    """
    product = {
        "product_name": "Electrolyte Hydration Powder",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Sodium", "canonical_id": "sodium", "category": "mineral", "quantity": 1000, "unit": "mg"},
            {"name": "Potassium", "canonical_id": "potassium", "category": "mineral", "quantity": 200, "unit": "mg"},
            {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral", "quantity": 60, "unit": "mg"},
            {"name": "Calcium", "canonical_id": "calcium", "category": "mineral", "quantity": 60, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "electrolyte", (
        f"Electrolyte powder must classify as electrolyte, "
        f"got {result['primary_type']!r}."
    )


def test_BUG_11_ala_only_omega_3_label_does_not_classify_as_epa_dha_omega():
    """ALA is an omega-3 fatty acid, but it is NOT EPA/DHA fish-oil-class
    omega for v4 scoring or DRI semantics. A product labeled "Omega-3"
    with only alpha-linolenic acid must stay out of the omega_3 taxonomy
    class so the v4 router does not send it to the EPA/DHA module."""
    product = {
        "product_name": "ALA Omega-3",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Alpha-Linolenic Acid", "canonical_id": "ala",
             "category": "fatty_acid", "quantity": 1000, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "omega_3"


def test_BUG_11b_omega_3_fatty_acids_parent_does_not_classify_as_epa_dha_omega():
    """The broad omega_3_fatty_acids parent is too ambiguous for EPA/DHA
    taxonomy. It can represent ALA-style DRI semantics or parent mass and
    must not be treated as an EPA/DHA omega product without disclosed EPA
    or DHA children."""
    product = {
        "product_name": "Omega-3 Fatty Acids",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Omega-3 Fatty Acids", "canonical_id": "omega_3_fatty_acids",
             "category": "fatty_acid", "quantity": 1000, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "omega_3"


def test_BUG_12_sleep_short_tokens_are_word_boundary_matched():
    """Short sleep tokens must not match inside unrelated words.

    Regression cases found during SP vocab review:
      - forest -> contains "rest"
      - rpm -> contains "pm"

    Both used to classify as sleep_support when `_SLEEP_NAME_TOKENS`
    used raw substring matching.
    """
    false_positive_cases = [
        (
            "Forest Mushroom Complex",
            [{"name": "Reishi Mushroom", "canonical_id": "reishi", "category": "herb", "quantity": 500, "unit": "mg"}],
        ),
        (
            "RPM Energy Booster",
            [{"name": "Caffeine", "canonical_id": "caffeine", "category": "other", "quantity": 100, "unit": "mg"}],
        ),
    ]
    for name, ingredients in false_positive_cases:
        result = classify_supplement({
            "product_name": name,
            "ingredient_quality_data": {"ingredients": ingredients},
        })
        assert result["primary_type"] != "sleep_support", (
            f"{name!r} must not classify as sleep_support via a short-token "
            f"substring match; got reasons={result['classification_reasons']!r}."
        )


def test_BUG_12b_standalone_sleep_boundary_tokens_still_work():
    """Boundary-matching fix must preserve legitimate labels."""
    product = {
        "product_name": "Good Night Melatonin PM",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Melatonin", "canonical_id": "melatonin", "category": "other", "quantity": 3, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "sleep_support"


def test_BUG_13_functional_short_tokens_are_not_substring_false_positives():
    """Functional label tokens must not match inside unrelated words.

    Regression cases found during SP vocab review:
      - chairman -> contains "hair"
      - green tea superfood -> "superfood" alone is too broad for greens
    """
    false_positive_cases = [
        (
            "Chairman Daily Support",
            [{"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin", "quantity": 100, "unit": "mg"},
             {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 15, "unit": "mg"}],
            "beauty_hair_skin_nails",
        ),
        (
            "Green Tea Superfood",
            [{"name": "Green Tea Extract", "canonical_id": "green_tea", "category": "herb", "quantity": 500, "unit": "mg"},
             {"name": "Matcha", "canonical_id": "matcha", "category": "herb", "quantity": 500, "unit": "mg"}],
            "greens_powder",
        ),
    ]
    for name, ingredients, forbidden_type in false_positive_cases:
        result = classify_supplement({
            "product_name": name,
            "ingredient_quality_data": {"ingredients": ingredients},
        })
        assert result["primary_type"] != forbidden_type, (
            f"{name!r} must not classify as {forbidden_type} via broad "
            f"functional substring matching; got reasons={result['classification_reasons']!r}."
        )


def test_BUG_13b_functional_positive_cases_still_classify():
    """Tightened functional tokens must preserve intended positive cases."""
    cases = [
        (
            "Hair Skin Nails",
            [{"name": "Biotin", "canonical_id": "biotin", "category": "vitamin", "quantity": 5000, "unit": "mcg"},
             {"name": "Collagen", "canonical_id": "collagen", "category": "protein", "quantity": 1000, "unit": "mg"}],
            "beauty_hair_skin_nails",
        ),
        (
            "Digestive Fiber",
            [{"name": "Psyllium", "canonical_id": "psyllium", "category": "fiber", "quantity": 5, "unit": "g"},
             {"name": "Inulin", "canonical_id": "inulin", "category": "fiber", "quantity": 3, "unit": "g"}],
            "fiber_digestive",
        ),
        (
            "Digestive Enzymes",
            [{"name": "Amylase", "canonical_id": "amylase", "category": "enzyme", "quantity": 100, "unit": "DU"},
             {"name": "Protease", "canonical_id": "protease", "category": "enzyme", "quantity": 100, "unit": "HUT"}],
            "fiber_digestive",
        ),
        (
            "Super Greens Powder",
            [{"name": "Wheatgrass", "canonical_id": "wheatgrass", "category": "greens", "quantity": 500, "unit": "mg"},
             {"name": "Spirulina", "canonical_id": "spirulina", "category": "greens", "quantity": 500, "unit": "mg"}],
            "greens_powder",
        ),
    ]
    for name, ingredients, expected_type in cases:
        result = classify_supplement({
            "product_name": name,
            "ingredient_quality_data": {"ingredients": ingredients},
        })
        assert result["primary_type"] == expected_type


def test_fibrinolytic_enzymes_do_not_pollute_fiber_digestive_category():
    """Nattokinase/serrapeptase are systemic fibrinolytic enzymes, not digestive
    enzymes. They should not sit in the fiber/digestive percentile cohort."""
    for name, canonical_id in (
        ("Nattokinase 2,000 FU", "nattokinase"),
        ("Serrapeptase 120,000 SPU", "serrapeptase"),
    ):
        result = classify_supplement({
            "product_name": name,
            "ingredient_quality_data": {"ingredients": [
                {
                    "name": name,
                    "canonical_id": canonical_id,
                    "category": "enzyme",
                    "quantity": 100,
                    "unit": "mg",
                }
            ]},
        })
        assert result["primary_type"] != "fiber_digestive"
        assert result["secondary_type"] == canonical_id


def test_coq10_does_not_pollute_fiber_digestive_category():
    result = classify_supplement({
        "product_name": "CoQ10 200 mg Softgels",
        "ingredient_quality_data": {"ingredients": [
            {
                "name": "Coenzyme Q10",
                "canonical_id": "coq10",
                "category": "antioxidant",
                "quantity": 200,
                "unit": "mg",
            }
        ]},
    })

    assert result["primary_type"] != "fiber_digestive"
    assert result["secondary_type"] == "coq10"


def test_BUG_14_sodium_chloride_are_mineral_canonicals():
    """Electrolyte minerals should count as mineral actives in taxonomy."""
    product = {
        "product_name": "Sodium Chloride",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Sodium", "canonical_id": "sodium", "category": "mineral", "quantity": 200, "unit": "mg"},
            {"name": "Chloride", "canonical_id": "chloride", "category": "mineral", "quantity": 300, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "single_mineral"


# ============================================================================
# BUG-15: Collagen-with-1-strain misclassifies as probiotic
# ============================================================================

def _collagen_plus_one_strain_product(product_name: str, second_active_cid: str,
                                       second_active_name: str, strain_cid: str,
                                       strain_name: str) -> dict:
    """Shape mirroring Garden collagen+strain products (222902, 274304,
    327397-9, 321351). Two quantified actives: collagen/MCT/curcumin +
    a single probiotic strain."""
    return {
        "product_name": product_name,
        "fullName": product_name,
        "ingredient_quality_data": {"ingredients": [
            {"name": second_active_name, "canonical_id": second_active_cid,
             "category": "protein" if "collagen" in second_active_cid else "fat",
             "quantity": 10, "unit": "g"},
            {"name": strain_name, "canonical_id": strain_cid,
             "category": "probiotics", "quantity": 1.0, "unit": "Billion CFU"},
        ]},
    }


def test_BUG_15_collagen_plus_one_strain_is_not_probiotic():
    """Before 2026-05-23: probiotic_majority threshold was
    `ceil(active_count * 0.5)`, so a collagen product with 2 actives where
    1 is a probiotic strain (1 ≥ ceil(2*0.5)=1) routed to probiotic.

    Affected real Garden products (verified 2026-05-23):
      222902 Grass Fed Collagen CBD Unflavored — collagen + bacillus_subtilis
      274304 Grass Fed Collagen Peptides Unflavored — collagen + lactobacillus_plantarum
      321351 Multi-Sourced Collagen Turmeric — curcumin + lactobacillus_plantarum
      327397 Grass Fed Collagen Peptides Unflavored — collagen + bacillus_coagulans
      327398 Grass Fed Collagen Protein Fair Trade Chocolate — mct_oil + bacillus_coagulans
      327399 Grass Fed Collagen Protein Vanilla Flavor — mct_oil + bacillus_coagulans

    Fix: require probiotic_count ≥ 2 AND ≥ 50% share for the probiotic route.
    Single-active products where that one active IS a strain still route
    correctly via the sole_active_is_strain branch.
    """
    for product_name, second_cid, second_name, strain_cid, strain_name in [
        ("Grass Fed Collagen CBD Unflavored", "collagen", "Collagen", "bacillus_subtilis", "Bacillus subtilis"),
        ("Grass Fed Collagen Peptides Unflavored", "collagen", "Collagen", "lactobacillus_plantarum", "Lactobacillus plantarum"),
        ("Multi-Sourced Collagen Turmeric", "curcumin", "Curcumin", "lactobacillus_plantarum", "Lactobacillus plantarum"),
        ("Grass Fed Collagen Protein Fair Trade Chocolate", "mct_oil", "MCT Oil", "bacillus_coagulans", "Bacillus coagulans"),
    ]:
        product = _collagen_plus_one_strain_product(
            product_name, second_cid, second_name, strain_cid, strain_name
        )
        result = classify_supplement(product)
        assert result["primary_type"] != "probiotic", (
            f"{product_name!r}: 1-of-2 strain product must NOT route to probiotic "
            f"(got primary_type={result.get('primary_type')!r}, "
            f"reasons={result.get('classification_reasons')!r})"
        )


def test_BUG_15_single_strain_product_still_routes_probiotic():
    """Inverse guard: a product whose ONLY active is a probiotic strain
    must still route to probiotic via the sole_active_is_strain branch."""
    product = {
        "product_name": "Lactobacillus Plantarum 10 Billion CFU",
        "fullName": "Lactobacillus Plantarum 10 Billion CFU",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Lactobacillus plantarum", "canonical_id": "lactobacillus_plantarum",
             "category": "probiotics", "quantity": 10.0, "unit": "Billion CFU"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "probiotic"


def test_BUG_15_real_probiotic_panel_still_routes_probiotic():
    """Inverse guard: a real probiotic product with multiple strains
    (≥ 2 strains, ≥ 50% share) must still route to probiotic. Without
    this guard, the tightening could over-correct and miss real probiotics.
    """
    product = {
        "product_name": "Ultra Probiotic Complex 50 Billion CFUs",
        "fullName": "Ultra Probiotic Complex 50 Billion CFUs",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Lactobacillus acidophilus", "canonical_id": "lactobacillus_acidophilus",
             "category": "probiotics", "quantity": 20.0, "unit": "Billion CFU"},
            {"name": "Bifidobacterium lactis", "canonical_id": "bifidobacterium_lactis",
             "category": "probiotics", "quantity": 20.0, "unit": "Billion CFU"},
            {"name": "Lactobacillus plantarum", "canonical_id": "lactobacillus_plantarum",
             "category": "probiotics", "quantity": 10.0, "unit": "Billion CFU"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "probiotic"


def test_BUG_15_casein_decapeptide_does_not_match_l_casei():
    """Casein/milk peptides are not probiotic strains.

    The probiotic matcher must not substring-match the species token "casei"
    inside "casein"; otherwise Lactium/casein decapeptide products route through
    probiotic and get scored against CFU/strain rules.
    """
    product = {
        "product_name": "Bioactive Milk Peptides",
        "fullName": "Bioactive Milk Peptides",
        "ingredient_quality_data": {"ingredients": [
            {
                "name": "Casein Decapeptide",
                "canonical_id": "casein_hydrolysate",
                "category": "amino_acid",
                "quantity": 150.0,
                "unit": "mg",
            },
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "probiotic"


# ============================================================================
# BUG-16: MCT Oil with incidental DHA misclassifies as omega_3
# ============================================================================

def test_BUG_16_mct_oil_with_incidental_dha_is_not_omega_3():
    """Before 2026-05-23: the omega-3 branch fired on any product with an
    `dha`/`epa`/`epa_dha` canonical_id, regardless of name or DSLD
    productType context. A "MCT Oil Unflavored" product with one small DHA
    row got primary_type=omega_3.

    Affected real Garden product (verified 2026-05-23):
      327403 MCT Oil Unflavored — 1 DHA row, name has no omega keyword,
      DSLD productType="fat/fatty acid"

    Fix: when active_count==1, the name doesn't mention any omega keyword
    (omega / fish oil / krill / cod liver), AND the DSLD productType is
    the generic "fat/fatty acid" carrier-oil bucket, the omega branch
    falls through — the product is a carrier oil with incidental omega,
    not an omega-3 product.
    """
    product = {
        "product_name": "MCT Oil Unflavored",
        "fullName": "MCT Oil Unflavored",
        "productType": {"langualCodeDescription": "fat/fatty acid"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "DHA", "canonical_id": "dha", "category": "fat",
             "quantity": 100, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "omega_3", (
        f"MCT Oil with incidental DHA must NOT route to omega_3 "
        f"(got primary_type={result.get('primary_type')!r}, "
        f"reasons={result.get('classification_reasons')!r})"
    )


def test_BUG_16_real_fish_oil_still_routes_omega_3():
    """Inverse guard: a real fish-oil product with omega keyword in the
    name must still route to omega_3 even when the DSLD productType is
    'fat/fatty acid'. Locks the guard against over-correction."""
    product = {
        "product_name": "Fish Oil Omega-3 1000 mg",
        "fullName": "Fish Oil Omega-3 1000 mg",
        "productType": {"langualCodeDescription": "fat/fatty acid"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "EPA", "canonical_id": "epa", "category": "fat",
             "quantity": 500, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "omega_3"


def test_stress_defense_adaptogen_product_is_not_immune_support():
    """A broad word like "defense" is not enough to make an adaptogen/stress
    formula an immune-support product.

    Real audit case: Nature's Way Stress Defense was topping the immune cohort
    because the name token ``defense`` fired before composition. It should stay
    in the botanical/stress lane unless the label has an explicit immune token
    or immune-primary actives.
    """
    product = {
        "product_name": "Stress Defense",
        "fullName": "Stress Defense",
        "ingredient_quality_data": {"ingredients": [
            {"name": "Ashwagandha", "canonical_id": "ashwagandha", "category": "botanical", "quantity": 300, "unit": "mg"},
            {"name": "Panax Ginseng", "canonical_id": "ginseng", "category": "botanical", "quantity": 200, "unit": "mg"},
            {"name": "Rhodiola", "canonical_id": "rhodiola", "category": "botanical", "quantity": 100, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "immune_support"


def test_BUG_16_multi_omega_row_product_still_routes_omega_3():
    """Inverse guard: a multi-row EPA+DHA product (active_count > 1)
    still routes to omega_3 regardless of name keyword or productType."""
    product = {
        "product_name": "Algal Omega",  # No fish/krill keyword
        "fullName": "Algal Omega",
        "productType": {"langualCodeDescription": "fat/fatty acid"},
        "ingredient_quality_data": {"ingredients": [
            {"name": "EPA", "canonical_id": "epa", "category": "fat", "quantity": 250, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "category": "fat", "quantity": 500, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "omega_3"


# ============================================================================
# Coverage assertion: every PRIMARY_TYPE must have at least one regression test
# ============================================================================

# Maps primary_type → either an existing test in test_supplement_taxonomy.py
# (legacy) or one of the BUG-N tests above. If a type is in PRIMARY_TYPES
# but has no test anywhere, this assertion fails — flagging the gap.
COVERED_TYPES = {
    # Covered in test_supplement_taxonomy.py
    "single_vitamin", "single_mineral", "vitamin_mineral_combo",
    "multivitamin", "b_complex", "omega_3", "herbal_botanical",
    "sleep_support", "beauty_hair_skin_nails",
    # Covered by BUG-N tests in this file
    "probiotic",  # BUG-3
    "amino_acid",  # BUG-4
    "pre_workout",  # BUG-7
    "protein_powder",  # BUG-8
    "greens_powder",  # BUG-9
    "electrolyte",  # BUG-10
    "joint_support",  # BUG-5b
    "fiber_digestive",  # BUG-13b + fiber pollution guards
    # general_supplement is the residual — implicit fallback testing
    "general_supplement",
}


def test_every_primary_type_has_a_regression_test():
    """Every vocab type in PRIMARY_TYPES must have at least one positive
    or negative regression test. Catches future drift where someone adds
    a type to the vocab but forgets to wire up a classifier branch +
    test.

    Currently UNTESTED — flagged for follow-up:
      - collagen  (no test, taxonomy has _COLLAGEN_IDS but no real-catalog canary)
      - immune_support  (no test — but real catalog audit showed 40% miss rate)
    """
    missing = set(PRIMARY_TYPES) - COVERED_TYPES
    expected_gaps = {"collagen", "immune_support"}
    new_gaps = missing - expected_gaps
    assert not new_gaps, (
        f"New PRIMARY_TYPES added without regression test: {new_gaps}. "
        f"Add a test_BUG_N or positive test for each."
    )
