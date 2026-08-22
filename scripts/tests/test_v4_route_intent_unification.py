"""Reviewed route-intent regressions for the v4 scoring classifier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_input_contract import build_scoring_classification  # noqa: E402


def _row(canonical_id: str, quantity: float, unit: str, **extra) -> dict:
    return {
        "name": canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "source_section": "activeIngredients",
        "raw_source_path": extra.pop("raw_source_path", f"ingredientRows[{canonical_id}]"),
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
        **extra,
    }


def _evidence(canonical_id: str, quantity: float, unit: str, **extra) -> dict:
    evidence_type = extra.pop("evidence_type", "blend_anchor_mass")
    raw_source_path = extra.pop(
        "raw_source_path",
        f"product_scoring_evidence.{evidence_type}.{canonical_id}",
    )
    return {
        "name": extra.pop("name", canonical_id.replace("_", " ").title()),
        "canonical_id": canonical_id,
        "clean_identity_id": canonical_id,
        "scoring_parent_id": canonical_id,
        "evidence_canonical_id": canonical_id,
        "canonical_source_db": "test_fixture",
        "evidence_origin": "native_enrichment",
        "evidence_type": evidence_type,
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": quantity,
        "dose_unit": unit,
        "source": "test_fixture",
        "raw_source_path": raw_source_path,
        "evidence_scope": "blend_level",
        "linked_rows": [raw_source_path],
        "confidence": "high",
        "reason": "reviewed_test_fixture",
        **extra,
    }


def _product(
    name: str,
    rows: list[dict],
    *,
    primary_type: str = "general_supplement",
    evidence: list[dict] | None = None,
    observed_rows: list[dict] | None = None,
) -> dict:
    return {
        "product_name": name,
        "fullName": name,
        "brand_name": "Reviewed Fixture",
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": observed_rows if observed_rows is not None else list(rows),
        },
        "product_scoring_evidence": evidence or [],
    }


def _classification(product: dict) -> dict:
    return build_scoring_classification(
        product,
        classification_origin="native_enrichment",
    )


def test_nutrition_fiber_evidence_does_not_hijack_a_plain_vitamin() -> None:
    product = _product(
        "Vitamin C 500 mg",
        [_row("vitamin_c", 500, "mg")],
        primary_type="single_vitamin",
        evidence=[_evidence("fiber", 1, "g", name="Dietary Fiber")],
    )

    decision = _classification(product)

    assert decision["route_module"] == "generic"
    assert decision["route_reason"] == "taxonomy:single_vitamin"


def test_bare_plant_protein_with_mass_outranks_nutrition_fiber() -> None:
    product = _product(
        "Plant Protein",
        [],
        evidence=[
            _evidence("protein", 20, "g", name="Protein"),
            _evidence("fiber", 3, "g", name="Dietary Fiber"),
        ],
    )

    assert _classification(product)["route_module"] == "sports"


def test_colon_title_with_disclosed_fiber_mass_remains_fiber_digestive() -> None:
    product = _product(
        "Colon Pure Unflavored",
        [],
        evidence=[_evidence("fiber", 5, "g", name="Dietary Fiber")],
    )

    decision = _classification(product)

    assert decision["route_module"] == "fiber_digestive"
    assert "fiber_title_intent" in decision["route_evidence"]


def test_structural_fiber_blend_preserves_super_seed_intent() -> None:
    fiber_row = _row("fiber", 1, "g", name="Fiber, Soluble", category="fibers")
    observed = [
        fiber_row,
        {
            "name": "Perfect Fiber Blend",
            "quantity": 18,
            "unit": "g",
            "score_exclusion_reason": "blend_header_total",
            "role_classification": "inactive_non_scorable",
        },
    ]
    product = _product(
        "Super Seed",
        [fiber_row, _row("alpha_linolenic_acid", 1.1, "g")],
        observed_rows=observed,
    )

    decision = _classification(product)

    assert decision["route_module"] == "fiber_digestive"
    assert "declared_fiber_blend_intent" in decision["route_evidence"]


def test_material_fiber_cutoff_uses_the_reviewed_corpus_boundary() -> None:
    reviewed_boundary = _product(
        "Cleansing Formula",
        [
            _row("psyllium", 753.769, "mg"),
            _row("cascara_sagrada", 246.231, "mg"),
        ],
        primary_type="herbal_botanical",
    )
    below_boundary = _product(
        "Botanical Formula",
        [
            _row("psyllium", 753.768, "mg"),
            _row("cascara_sagrada", 246.232, "mg"),
        ],
        primary_type="herbal_botanical",
    )

    decision = _classification(reviewed_boundary)

    assert decision["route_module"] == "fiber_digestive"
    assert decision["route_reason"] == "material_fiber_panel"
    assert _classification(below_boundary)["route_module"] == "generic"


def test_dual_use_bromelain_requires_digestive_context() -> None:
    bromelain = _row("bromelain", 500, "mg", category="enzymes")

    assert _classification(_product("Bromelain 500 mg", [bromelain]))["route_module"] == "generic"
    assert (
        _classification(_product("Digestive Bromelain", [bromelain]))["route_module"]
        == "fiber_digestive"
    )


def test_dedicated_digestive_enzyme_identity_is_product_context() -> None:
    product = _product(
        "Flatter Me",
        [_row("digestive_enzymes", 249, "mg", category="enzymes")],
        primary_type="herbal_botanical",
    )

    decision = _classification(product)

    assert decision["route_module"] == "fiber_digestive"
    assert decision["route_reason"] == "digestive_enzyme_context"


def test_systemic_enzyme_does_not_inherit_digestive_route() -> None:
    product = _product(
        "Nattokinase Enzyme",
        [_row("nattokinase", 100, "mg", category="enzymes")],
    )

    assert _classification(product)["route_module"] == "generic"


def test_systemic_enzyme_name_overrides_noisy_digestive_canonical() -> None:
    product = _product(
        "Systemic Enzyme Complex",
        [
            _row(
                "digestive_enzymes",
                100,
                "mg",
                name="Serrapeptase Systemic Enzyme Blend",
                category="enzymes",
            )
        ],
    )

    assert _classification(product)["route_module"] == "generic"


def test_explicit_pancreatic_context_outranks_mixed_systemic_enzyme_wording() -> None:
    product = _product(
        "Mega-Zyme Pancreatic & Systemic Enzymes",
        [
            _row("pancreatin", 100, "mg", category="enzymes"),
            _row("serrapeptase", 20, "mg", category="enzymes"),
        ],
    )

    assert _classification(product)["route_module"] == "fiber_digestive"


@pytest.mark.parametrize(
    "title,canonical",
    (
        ("Pancreatic Enzyme Formula", "pancreatin"),
        ("Betaine HCl Pepsin and Gentian Bitters", "pepsin"),
        ("Original Dairy Relief", "lactase"),
    ),
)
def test_explicit_digestive_enzyme_products_keep_digestive_route(
    title: str,
    canonical: str,
) -> None:
    product = _product(
        title,
        [_row(canonical, 100, "mg", category="enzymes")],
    )

    assert _classification(product)["route_module"] == "fiber_digestive"


def test_explicit_b_complex_runs_before_broad_multivitamin() -> None:
    rows = [
        *[_row(canonical, 10, "mg") for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
            "vitamin_b12_cobalamin",
        )],
        _row("vitamin_c", 250, "mg"),
        _row("vitamin_e", 15, "mg"),
        _row("zinc", 10, "mg"),
        _row("copper", 1, "mg"),
    ]
    product = _product("Stress B-Complex with C and Zinc", rows, primary_type="multivitamin")

    decision = _classification(product)

    assert decision["route_module"] == "b_complex"
    assert decision["route_reason"] == "explicit_b_complex_panel"


def test_reviewed_b_aliases_count_as_explicit_b_complex_intent() -> None:
    rows = [
        _row(canonical, 10, "mg")
        for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
            "vitamin_b12_cobalamin",
        )
    ]

    for title in ("B-Right", "B-UnStressed", "Balanced B50", "B6 Complex"):
        decision = _classification(_product(title, rows, primary_type="b_complex"))
        assert decision["route_module"] == "b_complex", title
        assert decision["route_reason"] == "explicit_b_complex_panel", title


def test_titleless_b_dominant_panel_stays_generic() -> None:
    rows = [
        _row(canonical, 10, "mg")
        for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
            "vitamin_b12_cobalamin",
        )
    ]

    decision = _classification(
        _product("Fortify Dual Action Energy Support", rows, primary_type="b_complex")
    )

    assert decision["route_module"] == "generic"


def test_red_yeast_rice_with_b_vitamins_is_not_a_b_complex() -> None:
    product = _product(
        "HeartSure Red Yeast Rice with CoQ10",
        [
            _row("vitamin_b3_niacin", 20, "mg"),
            _row("vitamin_b6_pyridoxine", 2, "mg"),
            _row("vitamin_b9_folate", 400, "mcg"),
            _row("vitamin_b12_cobalamin", 6, "mcg"),
            _row("coq10", 100, "mg"),
        ],
        primary_type="b_complex",
    )

    assert _classification(product)["route_module"] == "generic"


def test_explicit_b_complex_boundary_is_the_reviewed_observed_share() -> None:
    b_rows = [
        _row(canonical, 10, "mg")
        for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
            "vitamin_b12_cobalamin",
        )
    ]
    reviewed_boundary = _product(
        "Stress B-Complex",
        [
            *b_rows,
            _row("vitamin_c", 100, "mg"),
            _row("vitamin_e", 15, "mg"),
            _row("zinc", 10, "mg"),
            _row("copper", 1, "mg"),
            _row("calcium", 100, "mg"),
        ],
        primary_type="multivitamin",
    )
    below_boundary = _product(
        "B-Complex Complete",
        [*reviewed_boundary["ingredient_quality_data"]["ingredients_scorable"], _row("iron", 18, "mg")],
        primary_type="multivitamin",
    )
    exact_old_cutoff = _product(
        "B-Complex Partial",
        [
            _row("vitamin_b1_thiamine", 10, "mg"),
            _row("vitamin_b2_riboflavin", 10, "mg"),
            _row("vitamin_b6_pyridoxine", 10, "mg"),
            _row("vitamin_c", 100, "mg"),
            _row("zinc", 10, "mg"),
        ],
        primary_type="multivitamin",
    )

    assert _classification(reviewed_boundary)["route_module"] == "b_complex"
    assert _classification(below_boundary)["route_module"] == "multi_or_prenatal"
    assert _classification(exact_old_cutoff)["route_module"] != "b_complex"


def test_b_cofactors_do_not_count_as_contrary_panel_identities() -> None:
    rows = [
        *[_row(canonical, 10, "mg") for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
            "vitamin_b12_cobalamin",
        )],
        _row("choline", 25, "mg"),
        _row("inositol", 25, "mg"),
        _row("paba", 25, "mg"),
    ]
    product = _product("Complete B-Complex", rows, primary_type="b_complex")

    decision = _classification(product)

    assert decision["route_module"] == "b_complex"
    assert "b_cofactor_panel" in decision["route_evidence"]


def test_recovery_panel_is_not_inferred_as_b_complex() -> None:
    rows = [
        *[_row(canonical, 10, "mg") for canonical in (
            "vitamin_b1_thiamine",
            "vitamin_b2_riboflavin",
            "vitamin_b3_niacin",
            "vitamin_b5_pantothenic",
            "vitamin_b6_pyridoxine",
            "vitamin_b7_biotin",
            "vitamin_b9_folate",
        )],
        _row("vitamin_c", 90, "mg"),
        _row("magnesium", 100, "mg"),
    ]
    product = _product(
        "Organic Plant-Based Recovery",
        rows,
        primary_type="b_complex",
    )

    assert _classification(product)["route_module"] != "b_complex"


def test_mineral_only_multimineral_does_not_enter_multivitamin_module() -> None:
    product = _product(
        "Chelated Solamins Multimineral",
        [
            _row("calcium", 500, "mg"),
            _row("magnesium", 200, "mg"),
            _row("zinc", 15, "mg"),
            _row("selenium", 100, "mcg"),
            _row("copper", 1, "mg"),
        ],
        primary_type="mineral_complex",
    )

    assert _classification(product)["route_module"] == "generic"


def test_mineral_only_panel_with_stale_multivitamin_taxonomy_stays_generic() -> None:
    product = _product(
        "Daily Mineral Foundation",
        [
            _row("calcium", 500, "mg"),
            _row("magnesium", 200, "mg"),
            _row("zinc", 15, "mg"),
            _row("selenium", 100, "mcg"),
            _row("copper", 1, "mg"),
        ],
        primary_type="multivitamin",
    )

    assert _classification(product)["route_module"] == "generic"


@pytest.mark.parametrize(
    "title",
    (
        "Protein",
        "Plant Protein",
        "Protein Isolate - Whey",
        "Hydrolyzed Rice Protein",
        "Mass Gainer",
    ),
)
def test_one_protein_intent_predicate_routes_supported_title_shapes(title: str) -> None:
    product = _product(
        title,
        [],
        evidence=[_evidence("protein", 20, "g", name="Protein")],
    )

    assert _classification(product)["route_module"] == "sports"


def test_route_decision_is_single_structured_classifier_result() -> None:
    decision = _classification(
        _product("Vitamin C 500 mg", [_row("vitamin_c", 500, "mg")])
    )

    assert decision["route_decision"] == {
        "module": decision["route_module"],
        "reason_codes": decision["route_evidence"],
        "confidence": decision["route_confidence"],
        "classifier_version": "1.1.0",
    }


def test_trace_enzyme_in_a_base_matrix_does_not_define_a_digestive_product() -> None:
    """A RAW-style food blend carries a token enzyme row.

    Presence alone routed Garden of Life Vitamin Code RAW Vitamin C -- a vitamin
    C product -- to the digestive module, where it was scored on fiber and
    enzyme dose.
    """
    product = _product(
        "Raw Vitamin C 500 mg",
        [
            _row("vitamin_c", 500, "mg"),
            _row("digestive_enzymes", 10, "mg", category="enzymes"),
            _row("orange", 100, "mg"),
            _row("broccoli", 100, "mg"),
            _row("blueberry", 100, "mg"),
        ],
        primary_type="single_vitamin",
    )

    assert _classification(product)["route_module"] == "generic"


def test_enzyme_dominant_panel_still_routes_digestive() -> None:
    """The dominance rule must not cost a genuine enzyme formula its module."""
    rows = [
        _row(canonical, 50, "mg", category="enzymes", raw_source_path=f"ingredientRows[{index}]")
        for index, canonical in enumerate(
            ("protease", "lipase", "amylase", "cellulase", "lactase")
        )
    ]
    rows.append(_row("ginger_extract", 25, "mg", raw_source_path="ingredientRows[5]"))
    product = _product("CompleteGest", rows, primary_type="herbal_botanical")

    decision = _classification(product)

    assert decision["route_module"] == "fiber_digestive"
    assert decision["route_reason"] == "digestive_enzyme_context"


def test_enzyme_activity_projections_count_toward_digestive_dominance() -> None:
    """Acid-Ease and Beat The Bloat disclose enzymes only as activity rollups.

    Weighing label rows alone would rate them non-digestive purely because the
    enzyme dose arrived as a projection.
    """
    product = _product(
        "Bloat Relief",
        [_row("dandelion", 50, "mg")],
        primary_type="herbal_botanical",
        evidence=[
            _evidence(
                "digestive_enzymes",
                100,
                "mg",
                evidence_type="enzyme_activity",
                raw_source_path=f"product_scoring_evidence.enzyme_activity.{index}",
            )
            for index in range(3)
        ],
    )

    decision = _classification(product)

    assert decision["route_module"] == "fiber_digestive"
    assert decision["route_reason"] == "digestive_enzyme_context"


def test_hyphenated_acid_ease_title_is_digestive_intent() -> None:
    """The title vocabulary listed `acid ease` but labels print `Acid-Ease`."""
    from scoring_v4.route_features import extract_route_features

    facts = extract_route_features(
        _product("Acid-Ease", [_row("slippery_elm", 200, "mg")]),
        [_row("slippery_elm", 200, "mg")],
    )

    assert facts["title_digestive_intent"] is True
