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
      - fiber_digestive  (no test)
      - immune_support  (no test — but real catalog audit showed 40% miss rate)
    """
    missing = set(PRIMARY_TYPES) - COVERED_TYPES
    expected_gaps = {"collagen", "fiber_digestive", "immune_support"}
    new_gaps = missing - expected_gaps
    assert not new_gaps, (
        f"New PRIMARY_TYPES added without regression test: {new_gaps}. "
        f"Add a test_BUG_N or positive test for each."
    )
