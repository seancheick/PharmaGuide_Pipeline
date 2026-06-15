from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_input_contract import (  # noqa: E402
    SCORING_CLASSIFICATION_SCHEMA_VERSION,
    build_scoring_classification,
    derive_product_scoring_evidence,
)
from scoring_v4.router import _legacy_class_for_product, class_for_product  # noqa: E402


def _row(canonical: str, name: str, quantity: float = 100, unit: str = "mg", **extra):
    row = {
        "canonical_id": canonical,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical}]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
    }
    row.update(extra)
    return row


def _product(name: str, rows: list[dict], *, primary_type: str = "general_supplement", **extra):
    product = {
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }
    product.update(extra)
    return product


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"supplement_taxonomy": None},
        {"ingredient_quality_data": {"ingredients_scorable": "bad-shape"}},
        {"ingredient_quality_data": {"ingredients_scorable": [None, "bad", {}]}},
        None,
    ],
)
def test_classification_builder_is_total_and_schema_valid(payload):
    contract = build_scoring_classification(payload)  # type: ignore[arg-type]
    assert contract["classification_schema_version"] == SCORING_CLASSIFICATION_SCHEMA_VERSION
    assert contract["classification_origin"] == "compatibility_derived"
    assert contract["route_module"] in {"generic", "probiotic", "multi_or_prenatal", "omega", "sports"}
    assert contract["route_confidence"] in {"high", "medium", "low", "failed"}
    assert isinstance(contract["ingredients"], list)
    assert isinstance(contract["profile_eligibility"], dict)


@pytest.mark.parametrize(
    "product",
    [
        _product("Vitamin C", [_row("vitamin_c", "Vitamin C")], primary_type="single_vitamin"),
        _product("Fish Oil EPA DHA", [_row("epa", "EPA"), _row("dha", "DHA")], primary_type="omega_3"),
        _product(
            "Creatine Monohydrate",
            [_row("creatine_monohydrate", "Creatine Monohydrate", 5, "g")],
            primary_type="general_supplement",
        ),
        _product(
            "Daily Probiotic",
            [],
            primary_type="probiotic",
            probiotic_data={"is_probiotic_product": True, "total_strain_count": 3, "has_cfu": True},
        ),
        _product(
            "Prenatal Multi",
            [
                _row("vitamin_b9_folate", "Folate", 400, "mcg"),
                _row("iron", "Iron", 18, "mg"),
                _row("iodine", "Iodine", 150, "mcg"),
                _row("choline", "Choline", 55, "mg"),
                _row("vitamin_d", "Vitamin D", 25, "mcg"),
            ],
            primary_type="general_supplement",
        ),
    ],
)
def test_router_public_api_matches_legacy_parity_baseline(product):
    assert class_for_product(product) == _legacy_class_for_product(product)
    assert build_scoring_classification(product)["route_module"] == _legacy_class_for_product(product)


# ── Multivitamin route-trust hardening ──────────────────────────────────────
# Every taxonomy route validates content (omega requires an EPA/DHA panel,
# sports a dose, b_complex ≥4 B-vitamins) EXCEPT plain `multivitamin`, which
# returned multi_or_prenatal on the native primary_type alone — the same
# "trust the native classification" pattern hardened for probiotic (casein/casei).
# A thin product mis-tagged `multivitamin` by taxonomy drift would be crushed by
# the prenatal-panel floors for nutrients it never contained.

def test_multivitamin_taxonomy_thin_panel_routes_generic():
    """primary_type=multivitamin but a thin panel (<4 multi-nutrients) and no
    multi* in the name is a mis-tag, not a real multivitamin. It must route
    generic, not multi_or_prenatal (which would impose prenatal-panel floors)."""
    p = _product(
        "Bulk Strawberry Kiwi",
        [
            _row("calcium", "Calcium", 50, "mg"),
            _row("magnesium", "Magnesium", 50, "mg"),
            _row("zinc", "Zinc", 5, "mg"),
        ],
        primary_type="multivitamin",
    )
    assert build_scoring_classification(p)["route_module"] == "generic"
    assert _legacy_class_for_product(p) == "generic"  # parity: both brains agree


def test_multivitamin_real_broad_panel_routes_multi():
    """A genuine multivitamin (≥4 distinct multi-panel nutrients) still routes
    multi_or_prenatal — regression guard so the hardening doesn't demote real
    multis."""
    p = _product(
        "Daily Foundation Formula",
        [
            _row("vitamin_a", "Vitamin A", 900, "mcg"),
            _row("vitamin_c", "Vitamin C", 90, "mg"),
            _row("vitamin_d", "Vitamin D", 25, "mcg"),
            _row("zinc", "Zinc", 11, "mg"),
            _row("magnesium", "Magnesium", 100, "mg"),
        ],
        primary_type="multivitamin",
    )
    assert build_scoring_classification(p)["route_module"] == "multi_or_prenatal"
    assert _legacy_class_for_product(p) == "multi_or_prenatal"


@pytest.mark.parametrize("primary_type", ["immune_support", "sleep_support", "herbal_botanical"])
def test_themed_legacy_multivitamin_with_broad_panel_routes_multi(primary_type):
    """The taxonomy can carry the product theme while the enriched product type
    still correctly says multivitamin. A broad multi-nutrient panel plus the
    legacy multivitamin signal should route to multi_or_prenatal instead of
    generic, without trusting the legacy field by itself."""
    p = _product(
        "Daily Pure Pack",
        [
            _row("vitamin_a", "Vitamin A", 900, "mcg"),
            _row("vitamin_c", "Vitamin C", 90, "mg"),
            _row("vitamin_d", "Vitamin D", 25, "mcg"),
            _row("vitamin_e", "Vitamin E", 15, "mg"),
            _row("vitamin_b12_cobalamin", "Vitamin B12", 100, "mcg"),
            _row("zinc", "Zinc", 11, "mg"),
            _row("magnesium", "Magnesium", 100, "mg"),
            _row("selenium", "Selenium", 55, "mcg"),
        ],
        primary_type=primary_type,
        supplement_type={"type": "multivitamin"},
    )
    assert build_scoring_classification(p)["route_module"] == "multi_or_prenatal"
    assert _legacy_class_for_product(p) == "multi_or_prenatal"


def test_themed_legacy_multivitamin_without_broad_panel_stays_generic():
    """The legacy multivitamin fallback is not a resurrection of the old
    over-eager router. Targeted sleep/beauty products still need a broad panel
    before they enter the multi/prenatal rubric."""
    p = _product(
        "Mighty Night Sleep Gummies",
        [
            _row("vitamin_b6_pyridoxine", "Vitamin B6", 2, "mg"),
            _row("melatonin", "Melatonin", 3, "mg"),
            _row("lemon_balm", "Lemon Balm", 100, "mg"),
        ],
        primary_type="sleep_support",
        supplement_type={"type": "multivitamin"},
    )
    assert build_scoring_classification(p)["route_module"] == "generic"
    assert _legacy_class_for_product(p) == "generic"


def test_legacy_multivitamin_targeted_formula_with_four_nutrients_stays_generic():
    """The legacy fallback needs stronger evidence than native multivitamin
    taxonomy. Four micronutrients plus functional actives is a targeted formula,
    not enough to override a generic/themed taxonomy into multi_or_prenatal."""
    p = _product(
        "Hist Reset",
        [
            _row("vitamin_c", "Vitamin C", 250, "mg"),
            _row("vitamin_b2_riboflavin", "Riboflavin", 5, "mg"),
            _row("vitamin_b3_niacin", "Niacin", 20, "mg"),
            _row("molybdenum", "Molybdenum", 100, "mcg"),
            _row("nac", "N-Acetyl L-Cysteine", 100, "mg"),
            _row("quercetin", "Quercetin", 300, "mg"),
            _row("digestive_enzymes", "Bromelain", 200, "mg"),
            _row("luteolin", "Luteolin", 100, "mg"),
            _row("citrus_bioflavonoids", "Rutin", 100, "mg"),
        ],
        primary_type="general_supplement",
        supplement_type={"type": "multivitamin"},
    )
    assert build_scoring_classification(p)["route_module"] == "generic"
    assert _legacy_class_for_product(p) == "generic"


def test_legacy_multivitamin_greens_collagen_identity_stays_generic():
    """A broad micronutrient sprinkle inside a greens/collagen product is not a
    themed multivitamin. The fallback must not capture non-multi primary
    identities just because legacy metadata says multivitamin."""
    p = _product(
        "Grass Fed Collagen Greens Beauty",
        [
            _row("vitamin_a", "Vitamin A", 14, "mcg"),
            _row("vitamin_d", "Vitamin D", 2, "mcg"),
            _row("vitamin_k", "Vitamin K", 96, "mcg"),
            _row("vitamin_b9_folate", "Folate", 28, "mcg"),
            _row("calcium", "Calcium", 73, "mg"),
            _row("iron", "Iron", 2, "mg"),
            _row("magnesium", "Magnesium", 25, "mg"),
            _row("collagen", "Collagen", 12, "g"),
            _row("bacillus_subtilis", "Bacillus subtilis", 5, "mg"),
        ],
        primary_type="greens_powder",
        supplement_type={"type": "multivitamin"},
    )
    assert build_scoring_classification(p)["route_module"] == "generic"
    assert _legacy_class_for_product(p) == "generic"


def test_multivitamin_name_override_routes_multi_even_thin():
    """A product whose NAME claims 'multivitamin' is taken at its word (mirrors
    the b-complex name override) — routes multi_or_prenatal so the panel-coverage
    scoring can rate the (mislabeled) product, rather than silently re-routing."""
    p = _product(
        "Daily Multivitamin",
        [_row("vitamin_d", "Vitamin D", 25, "mcg")],
        primary_type="multivitamin",
    )
    assert build_scoring_classification(p)["route_module"] == "multi_or_prenatal"
    assert _legacy_class_for_product(p) == "multi_or_prenatal"


def test_public_router_does_not_seed_contract_route():
    source = (SCRIPTS_ROOT / "scoring_v4" / "router.py").read_text()
    tree = ast.parse(source)
    class_for_product_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "class_for_product"
    )
    for node in ast.walk(class_for_product_node):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", "") != "build_scoring_classification":
            continue
        assert all(keyword.arg != "route_module" for keyword in node.keywords)


def test_domain_and_botanical_source_are_separate_for_amino_acid():
    product = _product(
        "L-Theanine 200 mg",
        [
            _row(
                "l_theanine",
                "L-Theanine",
                200,
                "mg",
                category="amino_acids",
                raw_taxonomy={"category": "amino acid"},
            )
        ],
    )
    ingredient = build_scoring_classification(product)["ingredients"][0]
    assert ingredient["ingredient_domain"] == "amino_acid"
    assert ingredient["botanical_source"]["value"] is False
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_botanical_source_requires_positive_source_evidence():
    product = _product(
        "Quercetin",
        [
            _row(
                "quercetin",
                "Quercetin",
                500,
                "mg",
                category="antioxidants",
                raw_taxonomy={"category": "non-nutrient/non-botanical", "forms": []},
            )
        ],
    )
    ingredient = build_scoring_classification(product)["ingredients"][0]
    assert ingredient["ingredient_domain"] == "botanical_marker"
    assert ingredient["botanical_source"]["value"] is False
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_botanical_source_form_on_isolated_marker_does_not_grant_botanical_profile():
    product = _product(
        "Quercetin Sophora Extract",
        [
            _row(
                "quercetin",
                "Quercetin",
                500,
                "mg",
                category="antioxidants",
                raw_taxonomy={
                    "category": "non-nutrient/non-botanical",
                    "forms": [{"name": "Sophora japonica extract", "category": "botanical"}],
                },
            )
        ],
    )
    ingredient = build_scoring_classification(product)["ingredients"][0]
    assert ingredient["botanical_source"]["value"] is True
    assert ingredient["ingredient_domain"] == "botanical_marker"
    assert "botanical_source_form" in ingredient["botanical_source"]["evidence"]
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_animal_tissue_extract_does_not_grant_botanical_source_text():
    product = _product(
        "DAO Enzyme",
        [_row("diamine_oxidase", "Porcine Kidney Extract", 4, "mg")],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]

    assert ingredient["botanical_source"]["value"] is False
    assert ingredient["ingredient_domain"] == "generic_active"
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_plant_part_extract_still_grants_botanical_source_text():
    product = _product(
        "Green Tea Extract",
        [_row("green_tea_extract", "Green Tea Leaf Extract", 500, "mg")],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]

    assert ingredient["botanical_source"]["value"] is True
    assert "botanical_source_text" in ingredient["botanical_source"]["evidence"]
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is True


def test_product_standardized_botanical_signal_grants_botanical_profile():
    product = _product(
        "Curcumin Phytosome 500 mg",
        [
            _row(
                "curcumin",
                "Curcumin Phytosome",
                500,
                "mg",
                raw_taxonomy={"category": "non-nutrient/non-botanical", "forms": []},
            )
        ],
        formulation_data={
            "standardized_botanicals": [
                {
                    "name": "Meriva",
                    "botanical_id": "curcumin",
                    "standard_name": "Curcumin",
                    "markers": ["curcuminoids"],
                    "percentage_found": 95.0,
                    "min_threshold": 95,
                    "meets_threshold": True,
                }
            ]
        },
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]
    contract = build_scoring_classification(product)

    assert ingredient["botanical_source"]["value"] is True
    assert "product_standardized_botanical" in ingredient["botanical_source"]["evidence"]
    assert ingredient["ingredient_domain"] == "herb"
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is True
    assert contract["profile_eligibility"]["botanical"]["eligible"] is True


def test_isolated_carotenoid_keeps_source_but_not_botanical_profile():
    product = _product(
        "Lycopene 10 mg",
        [
            _row(
                "lycopene",
                "Lycopene",
                10,
                "mg",
                category="antioxidants",
                matched_form="lycopene extract",
                raw_taxonomy={"category": "non-nutrient/non-botanical"},
            )
        ],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]
    contract = build_scoring_classification(product)

    assert ingredient["botanical_source"]["value"] is True
    assert ingredient["ingredient_domain"] == "botanical_marker"
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False
    assert contract["profile_eligibility"]["botanical"]["eligible"] is False


@pytest.mark.parametrize(
    ("canonical", "name", "expected_domain"),
    [
        ("glucosamine", "Glucosamine Sulfate 2KCl", "generic_active"),
        ("d_limonene", "D-Limonene", "botanical_marker"),
        ("nattokinase", "Fermented Soy Extract", "enzyme"),
    ],
)
def test_clear_non_herb_domains_do_not_become_botanical_profile(canonical, name, expected_domain):
    product = _product(
        name,
        [
            _row(
                canonical,
                name,
                100,
                "mg",
                raw_taxonomy={
                    "category": "non-nutrient/non-botanical",
                    "forms": [{"name": "Botanical source extract", "category": "botanical"}],
                },
            )
        ],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]

    assert ingredient["botanical_source"]["value"] is True
    assert ingredient["ingredient_domain"] == expected_domain
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_kidney_bean_extract_is_not_blocked_as_animal_tissue():
    product = _product(
        "White Kidney Bean Extract",
        [_row("common_bean_extract", "White Kidney Bean Extract", 500, "mg")],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]

    assert ingredient["botanical_source"]["value"] is True
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is True


def test_recovered_botanical_adjuncts_do_not_make_vitamin_product_botanical():
    product = _product(
        "Vitamin D3 + K2",
        [
            _row("vitamin_d", "Vitamin D3", 25, "mcg", raw_taxonomy={"category": "vitamin"}),
            _row("vitamin_k", "Vitamin K2", 100, "mcg", raw_taxonomy={"category": "vitamin"}),
            _row(
                "acerola_cherry",
                "Acerola Cherry Extract",
                50,
                "mg",
                raw_taxonomy={"category": "botanical"},
            ),
        ],
        primary_type="single_vitamin",
    )

    contract = build_scoring_classification(product)

    assert contract["route_module"] == "generic"
    assert contract["profile_eligibility"]["botanical"]["eligible"] is False


def test_botanical_title_product_with_vitamin_adjunct_stays_botanical():
    product = _product(
        "Echinacea Root Complex with Vitamin C",
        [
            _row(
                "echinacea",
                "Echinacea Root Extract",
                900,
                "mg",
                raw_taxonomy={"category": "botanical"},
            ),
            _row("vitamin_c", "Vitamin C", 90, "mg", raw_taxonomy={"category": "vitamin"}),
        ],
        primary_type="immune_support",
    )

    contract = build_scoring_classification(product)

    assert contract["route_module"] == "generic"
    assert contract["profile_eligibility"]["botanical"]["eligible"] is True


def test_botanical_title_theme_does_not_override_enzyme_product_intent():
    product = _product(
        "Papaya Enzyme",
        [
            _row(
                "papaya",
                "Papaya Fruit Powder",
                20,
                "mg",
                raw_taxonomy={"category": "botanical"},
            ),
            _row(
                "digestive_enzymes",
                "Digestive Enzyme Blend",
                100,
                "mg",
                dose_class="enzyme_activity",
                raw_taxonomy={"category": "enzyme"},
            ),
        ],
        primary_type="fiber_digestive",
    )

    contract = build_scoring_classification(product)

    assert contract["route_module"] == "generic"
    assert contract["profile_eligibility"]["botanical"]["eligible"] is False


@pytest.mark.parametrize(
    ("canonical", "name", "expected_domain"),
    [
        ("vitamin_b7_biotin", "Biotin", "vitamin"),
        ("selenium", "Selenium", "mineral"),
    ],
)
def test_source_carrier_forms_do_not_override_known_identity_domain(canonical, name, expected_domain):
    product = _product(
        name,
        [
            _row(
                canonical,
                name,
                100,
                "mcg",
                raw_taxonomy={
                    "category": "vitamin" if expected_domain == "vitamin" else "mineral",
                    "forms": [
                        {
                            "name": "Saccharomyces cerevisiae",
                            "category": "botanical",
                            "ingredientGroup": "Saccharomyces cerevisiae",
                        }
                    ],
                },
            )
        ],
    )

    ingredient = build_scoring_classification(product)["ingredients"][0]

    assert ingredient["ingredient_domain"] == expected_domain
    assert ingredient["profile_eligibility"]["probiotic"]["eligible"] is False


def test_content_evidence_beats_title_for_omega_positive_and_negative():
    generic_title_with_epa = _product(
        "Essential Fatty Acids",
        [_row("epa", "Eicosapentaenoic Acid", 500, "mg")],
        primary_type="general_supplement",
    )
    omega_title_without_epa = _product(
        "Omega 3-6-9",
        [_row("alpha_linolenic_acid_ala", "Alpha Linolenic Acid", 1000, "mg")],
        primary_type="general_supplement",
    )
    assert build_scoring_classification(generic_title_with_epa)["route_module"] == "omega"
    assert build_scoring_classification(omega_title_without_epa)["route_module"] == "generic"


def test_mct_miscanonicalized_as_dha_does_not_route_omega():
    """Catalog regression: MCT/coconut rows were enriched as DHA and then
    inherited EPA/DHA dose + evidence. Source identity wins over the polluted
    canonical when the label clearly says MCT."""
    product = _product(
        "MCT Oil 3,000 mg Softgels",
        [
            _row(
                "dha",
                "Medium Chain Triglyceride Oil",
                3000,
                "mg",
                standardName="DHA (Docosahexaenoic Acid)",
                raw_source_text="Medium Chain Triglyceride Oil",
            )
        ],
        primary_type="general_supplement",
    )

    assert build_scoring_classification(product)["route_module"] == "generic"


def test_ala_omega3_parent_text_does_not_emit_epa_dha_aggregate_or_route_omega():
    """Catalog regression: ALA/flax rows labeled as omega-3 fatty acids were
    mapped to fish_oil and inherited marine EPA/DHA evidence."""
    row = _row(
        "fish_oil",
        "Omega-3 Fatty Acids",
        8,
        "Gram(s)",
        standardName="Fish Oil",
        display_label="Omega-3 Fatty Acids (Alpha-Linolenic Acid)",
        raw_source_text="Omega-3 Fatty Acids (Alpha-Linolenic Acid)",
    )
    product = _product(
        "Organic Flax Oil",
        [row],
        primary_type="omega_3",
        activeIngredients=[row],
    )

    assert build_scoring_classification(product)["route_module"] == "generic"
    evidence = derive_product_scoring_evidence(product)
    assert all(row.get("evidence_type") != "omega_epa_dha_aggregate" for row in evidence)


def test_flax_oil_name_only_signal_routes_generic():
    """Real-catalog pattern (dsld 293406): the ALA signal is ONLY in the product
    NAME ('Organic Flax Oil') — the mis-canonicalized row text is bare 'Omega-3
    Fatty Acids' with no ALA/flax token. The row-level guard misses it; the
    product-level guard must route it generic. (Codex's earlier flax test passed
    only because its synthetic row text included 'Alpha-Linolenic'.)"""
    row = _row(
        "epa_dha",
        "Omega-3 Fatty Acids",
        8,
        "Gram(s)",
        standardName="Omega-3 Fatty Acids",
        raw_source_text="Omega-3 Fatty Acids",
    )
    product = _product(
        "Organic Flax Oil",
        [row],
        primary_type="omega_3",
        activeIngredients=[row],
    )
    assert build_scoring_classification(product)["route_module"] == "generic"


def test_fiber_and_super_seed_name_signal_routes_generic():
    """Real-catalog patterns (dsld 299755 'Raw Organic Fiber', 274833 'Super
    Seed'): plant/seed omega_3 products with bare 'Omega-3 Fatty Acids' rows."""
    for name in ("Raw Organic Fiber", "Super Seed", "MCT Oil 3,000 mg"):
        row = _row(
            "epa_dha",
            "Omega-3 Fatty Acids",
            1,
            "Gram(s)",
            standardName="Omega-3 Fatty Acids",
            raw_source_text="Omega-3 Fatty Acids",
        )
        product = _product(
            name, [row], primary_type="omega_3", activeIngredients=[row]
        )
        assert build_scoring_classification(product)["route_module"] == "generic", name


def test_true_fish_oil_parent_still_routes_omega_without_epa_dha_dose_invention():
    product = _product(
        "Fish Oil 1000 mg",
        [_row("fish_oil", "Fish Oil", 1000, "mg", raw_source_text="Fish Oil")],
        primary_type="omega_3",
    )

    assert build_scoring_classification(product)["route_module"] == "omega"


def test_low_confidence_malformed_input_defaults_generic_not_not_scored():
    contract = build_scoring_classification({"ingredient_quality_data": {"ingredients_scorable": object()}})
    assert contract["route_module"] == "generic"
    assert contract["route_confidence"] in {"low", "medium"}
    assert contract["classification_failed"] is False


def test_classification_is_deterministic():
    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    assert build_scoring_classification(product) == build_scoring_classification(product)


def test_enricher_native_classification_matches_compat_builder():
    import logging
    from enrich_supplements_v3 import SupplementEnricherV3

    product = _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3")
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher.logger = logging.getLogger("classification-test")

    native = enricher._collect_product_scoring_classification(product)
    compat = build_scoring_classification(product)

    assert native["classification_origin"] == "native_enrichment"
    native_without_origin = dict(native)
    compat_without_origin = dict(compat)
    native_without_origin["classification_origin"] = "compatibility_derived"
    assert native_without_origin == compat_without_origin


def test_builder_prefers_valid_embedded_native_classification():
    product = _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3")
    native = build_scoring_classification(product, classification_origin="native_enrichment")
    product["product_scoring_classification"] = native

    contract = build_scoring_classification(product)

    assert contract["classification_origin"] == "native_enrichment"
    assert contract["route_module"] == "omega"


def test_builder_ignores_embedded_native_classification_when_route_drifted():
    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    native = build_scoring_classification(
        _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3"),
        classification_origin="native_enrichment",
    )
    product["product_scoring_classification"] = native

    contract = build_scoring_classification(product)

    assert contract["classification_origin"] == "compatibility_derived"
    assert contract["route_module"] == "generic"


def test_builder_falls_back_when_embedded_native_classification_is_stale_or_invalid():
    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    stale = build_scoring_classification(
        _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3"),
        classification_origin="native_enrichment",
    )
    stale["classification_schema_version"] = "0.0.0"
    product["product_scoring_classification"] = stale

    contract = build_scoring_classification(product)

    assert contract["classification_origin"] == "compatibility_derived"
    assert contract["route_module"] == "generic"


def test_enrichment_validator_accepts_native_classification_contract():
    from enrichment_contract_validator import EnrichmentContractValidator

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    product["product_scoring_classification"] = build_scoring_classification(
        product,
        classification_origin="native_enrichment",
    )
    violations = EnrichmentContractValidator().validate(product)
    assert [v for v in violations if v.rule.startswith("J.")] == []


def test_enrichment_validator_rejects_failed_nongeneric_classification():
    from enrichment_contract_validator import EnrichmentContractValidator

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    bad = build_scoring_classification(product, classification_origin="native_enrichment")
    bad["classification_failed"] = True
    bad["route_module"] = "omega"
    product["product_scoring_classification"] = bad
    violations = EnrichmentContractValidator().validate(product)
    assert any(v.rule == "J.6" for v in violations)


def test_route_audit_not_ready_when_failure_overrides_specialized_route():
    from api_audit.audit_v4_route_consistency import summarize

    summary = summarize(
        rows=[
            {
                "dsld_id": "x",
                "old_route": "omega",
                "contract_route": "generic",
                "public_route": "generic",
                "route_confidence": "failed",
                "classification_failed": True,
                "failure_overrode_old_route": True,
                "route_diverged": True,
                "v4_verdict": "SAFE",
            }
        ],
        canary_rows=[],
        allowlist={},
        elapsed_seconds=0.01,
    )
    assert summary["classification_failed_count"] == 1
    assert summary["failure_overrode_old_route_count"] == 1
    assert summary["ready"] is False


def test_route_audit_not_ready_when_performance_budget_is_exceeded():
    from api_audit.audit_v4_route_consistency import summarize

    summary = summarize(
        rows=[
            {
                "dsld_id": "x",
                "old_route": "generic",
                "contract_route": "generic",
                "public_route": "generic",
                "route_confidence": "medium",
                "classification_failed": False,
                "failure_overrode_old_route": False,
                "route_diverged": False,
                "v4_verdict": "SAFE",
            }
        ],
        canary_rows=[],
        allowlist={},
        elapsed_seconds=0.1,
        max_ms_per_product=10.0,
    )
    assert summary["ms_per_product"] == 100.0
    assert summary["performance_budget_exceeded"] is True
    assert summary["ready"] is False


def test_native_classification_parity_audit_allows_compatibility_missing_native():
    from api_audit.audit_v4_native_classification_parity import audit_products

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")

    summary = audit_products([product], require_native=False)

    assert summary["native_classification_count"] == 0
    assert summary["missing_native_classification_count"] == 1
    assert summary["ready"] is True


def test_native_classification_parity_audit_requires_native_for_release_gate():
    from api_audit.audit_v4_native_classification_parity import audit_products

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")

    summary = audit_products([product], require_native=True)

    assert summary["blocking_issue_count"] == 1
    assert summary["issues"][0]["issue"] == "missing_native_classification"
    assert summary["ready"] is False


def test_native_classification_parity_audit_detects_builder_mismatch():
    from api_audit.audit_v4_native_classification_parity import audit_products

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    product["product_scoring_classification"] = build_scoring_classification(
        _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3"),
        classification_origin="native_enrichment",
    )

    summary = audit_products([product], require_native=True)

    assert summary["native_classification_count"] == 1
    assert summary["native_builder_mismatch_count"] == 1
    assert summary["issues"][0]["issue"] == "native_builder_mismatch"
    assert summary["ready"] is False


def test_native_classification_parity_audit_fails_on_zero_loaded_products():
    from api_audit.audit_v4_native_classification_parity import audit_products

    summary = audit_products([], require_native=True)

    assert summary["total_products"] == 0
    assert summary["blocking_issue_count"] == 1
    assert summary["issues"][0]["issue"] == "no_products_loaded"
    assert summary["ready"] is False


def test_native_classification_parity_loader_reads_temp_enriched_root(tmp_path):
    from api_audit.audit_v4_native_classification_parity import load_enriched_products

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    batch_path = tmp_path / "enriched" / "enriched_cleaned_batch_1.json"
    batch_path.parent.mkdir(parents=True)
    batch_path.write_text(json.dumps([product]) + "\n")

    products = load_enriched_products(tmp_path)

    assert len(products) == 1
    assert products[0]["product_name"] == "Zinc"


def test_enrichment_contract_validator_accepts_batch_payload_shape():
    from enrichment_contract_validator import validate_enriched_payload

    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")

    violations, product_count = validate_enriched_payload([product, "bad-row"])

    assert product_count == 1
    assert any(v.rule == "CLI.1" for v in violations)


def test_profile_audit_not_ready_on_unsigned_profile_divergence():
    from api_audit.audit_v4_profile_consistency import summarize

    summary = summarize(
        rows=[
            {
                "dsld_id": "x",
                "profile": "botanical",
                "old_profile_eligible": False,
                "contract_profile_eligible": True,
                "profile_diverged": True,
                "classification_failed": False,
                "failure_granted_profile": False,
                "failure_revoked_profile": False,
                "v4_verdict": "SAFE",
            }
        ],
        canary_rows=[],
        allowlist={},
        elapsed_seconds=0.01,
    )
    assert summary["profile_divergence_count"] == 1
    assert summary["unsigned_profile_divergence_count"] == 1
    assert summary["ready"] is False


def test_profile_audit_not_ready_when_failure_changes_profile():
    from api_audit.audit_v4_profile_consistency import summarize

    summary = summarize(
        rows=[
            {
                "dsld_id": "x",
                "profile": "collagen",
                "old_profile_eligible": True,
                "contract_profile_eligible": False,
                "profile_diverged": True,
                "classification_failed": True,
                "failure_granted_profile": False,
                "failure_revoked_profile": True,
                "v4_verdict": "SAFE",
            }
        ],
        canary_rows=[],
        allowlist={},
        elapsed_seconds=0.01,
    )
    assert summary["classification_failed_count"] == 1
    assert summary["failure_revoked_profile_count"] == 1
    assert summary["ready"] is False


def test_profile_audit_reports_divergence_reason_buckets():
    from api_audit.audit_v4_profile_consistency import summarize

    summary = summarize(
        rows=[
            {
                "dsld_id": "x",
                "profile": "botanical",
                "old_profile_eligible": False,
                "contract_profile_eligible": True,
                "profile_diverged": True,
                "profile_divergence_reason": "contract_grants_recovered_botanical_rows",
                "classification_failed": False,
                "failure_granted_profile": False,
                "failure_revoked_profile": False,
                "v4_verdict": "SAFE",
            },
            {
                "dsld_id": "y",
                "profile": "collagen",
                "old_profile_eligible": True,
                "contract_profile_eligible": False,
                "profile_diverged": True,
                "profile_divergence_reason": "contract_revokes_collagen_mass_or_product_intent",
                "classification_failed": False,
                "failure_granted_profile": False,
                "failure_revoked_profile": False,
                "v4_verdict": "SAFE",
            },
        ],
        canary_rows=[],
        allowlist={},
        elapsed_seconds=0.01,
    )

    assert summary["profile_divergence_reasons"] == {
        "contract_grants_recovered_botanical_rows": 1,
        "contract_revokes_collagen_mass_or_product_intent": 1,
    }
    assert summary["profile_divergence_reasons_by_profile"]["botanical"] == {
        "contract_grants_recovered_botanical_rows": 1,
    }


def test_profile_cutover_impact_summary_blocks_verdict_flips_and_large_deltas():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [
            {
                "dsld_id": "large-delta",
                "old_score": 70.0,
                "new_score": 63.0,
                "abs_score_delta": 7.0,
                "old_verdict": "SAFE",
                "new_verdict": "SAFE",
                "verdict_changed": False,
                "less_restrictive_verdict_flip": False,
                "more_restrictive_verdict_flip": False,
                "safety_verdict_flip": False,
                "not_scored_transition": False,
                "profile_diverged": True,
                "botanical_old": True,
                "botanical_contract": False,
                "botanical_reason": "contract_revokes_role_materiality_or_intent",
                "collagen_old": False,
                "collagen_contract": False,
            },
            {
                "dsld_id": "verdict-flip",
                "old_score": 42.0,
                "new_score": 41.0,
                "abs_score_delta": 1.0,
                "old_verdict": "SAFE",
                "new_verdict": "POOR",
                "verdict_changed": True,
                "less_restrictive_verdict_flip": False,
                "more_restrictive_verdict_flip": True,
                "safety_verdict_flip": False,
                "not_scored_transition": False,
                "profile_diverged": True,
                "botanical_old": False,
                "botanical_contract": True,
                "botanical_reason": "contract_grants_recovered_botanical_rows",
                "collagen_old": False,
                "collagen_contract": False,
            },
        ],
        elapsed_seconds=0.01,
    )

    assert summary["large_score_delta_ge_5_count"] == 1
    assert summary["verdict_flip_count"] == 1
    assert summary["unsigned_large_score_delta_ge_5_count"] == 1
    assert summary["unsigned_verdict_flip_count"] == 1
    assert summary["less_restrictive_verdict_flip_count"] == 0
    assert summary["more_restrictive_verdict_flip_count"] == 1
    assert summary["safety_verdict_flip_count"] == 0
    assert summary["not_scored_transition_count"] == 0
    assert summary["ready_for_cutover"] is False


def test_has_material_nonbotanical_deliverable_detects_vitamin_major():
    """Acerola-style: a botanical-owned product whose real deliverable is a
    material non-botanical nutrient (Vitamin C, role=major) is the bug class."""
    from api_audit.audit_v4_profile_cutover_impact import _has_material_nonbotanical_deliverable

    contract = {"ingredients": [
        {"ingredient_domain": "vitamin", "role": "major"},
        {"ingredient_domain": "herb", "role": "claim_prominent"},
    ]}
    assert _has_material_nonbotanical_deliverable(contract) is True


def test_has_material_nonbotanical_deliverable_false_for_pure_botanical():
    from api_audit.audit_v4_profile_cutover_impact import _has_material_nonbotanical_deliverable

    contract = {"ingredients": [
        {"ingredient_domain": "herb", "role": "primary"},
        {"ingredient_domain": "herb", "role": "adjunct"},
    ]}
    assert _has_material_nonbotanical_deliverable(contract) is False


def test_has_material_nonbotanical_deliverable_ignores_adjunct_nutrient():
    """A non-botanical nutrient present only as an adjunct does not count as a
    competing deliverable."""
    from api_audit.audit_v4_profile_cutover_impact import _has_material_nonbotanical_deliverable

    contract = {"ingredients": [
        {"ingredient_domain": "herb", "role": "primary"},
        {"ingredient_domain": "mineral", "role": "adjunct"},
    ]}
    assert _has_material_nonbotanical_deliverable(contract) is False


def test_profile_cutover_impact_summary_counts_affected_class_flags():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [
            {
                "dsld_id": "acerola",
                "old_score": 57.0, "new_score": 33.0, "score_delta": -24.0, "abs_score_delta": 24.0,
                "old_verdict": "SAFE", "new_verdict": "POOR", "verdict_changed": True,
                "less_restrictive_verdict_flip": False, "more_restrictive_verdict_flip": True,
                "safety_verdict_flip": False, "not_scored_transition": False, "profile_diverged": True,
                "botanical_old": False, "botanical_contract": True, "botanical_reason": "x",
                "collagen_old": False, "collagen_contract": False,
                "botanical_owned_with_material_nonbotanical_deliverable": True,
                "botanical_owned_large_drop_ge20": True,
                "active_selection_large_drop_ge20": False,
            },
        ],
        elapsed_seconds=0.01,
    )

    assert summary["botanical_owned_with_material_nonbotanical_deliverable_count"] == 1
    assert summary["botanical_owned_large_drop_ge20_count"] == 1
    assert summary["active_selection_large_drop_ge20_count"] == 0


def test_profile_cutover_gate_blocks_unsigned_large_route_swing():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [{
            "dsld_id": "acerola", "old_score": 57.0, "new_score": 33.0, "abs_score_delta": 24.0,
            "old_verdict": "SAFE", "new_verdict": "POOR", "verdict_changed": True,
            "safety_verdict_flip": False, "not_scored_transition": False,
            "less_restrictive_verdict_flip": False, "more_restrictive_verdict_flip": True,
            "botanical_old": True, "botanical_contract": False, "botanical_active_diverged": False,
            "collagen_old": False, "collagen_contract": False, "profile_diverged": True,
        }],
        elapsed_seconds=0.01,
    )
    assert summary["large_route_or_active_swing_count"] == 1
    assert summary["unsigned_large_route_or_active_swing_count"] == 1
    assert summary["ready_for_cutover"] is False


def test_profile_cutover_gate_blocks_active_selection_swing_without_ownership_change():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [{
            "dsld_id": "x", "old_score": 60.0, "new_score": 38.0, "abs_score_delta": 22.0,
            "old_verdict": "SAFE", "new_verdict": "POOR", "verdict_changed": True,
            "safety_verdict_flip": False, "not_scored_transition": False,
            "less_restrictive_verdict_flip": False, "more_restrictive_verdict_flip": True,
            "botanical_old": True, "botanical_contract": True, "botanical_active_diverged": True,
            "collagen_old": False, "collagen_contract": False, "profile_diverged": False,
        }],
        elapsed_seconds=0.01,
    )
    assert summary["large_route_or_active_swing_count"] == 1
    assert summary["ready_for_cutover"] is False


def test_profile_cutover_gate_signed_route_swing_passes():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [{
            "dsld_id": "signed", "old_score": 57.0, "new_score": 33.0, "abs_score_delta": 24.0,
            "old_verdict": "SAFE", "new_verdict": "SAFE", "verdict_changed": False,
            "safety_verdict_flip": False, "not_scored_transition": False,
            "less_restrictive_verdict_flip": False, "more_restrictive_verdict_flip": False,
            "botanical_old": True, "botanical_contract": False, "botanical_active_diverged": False,
            "collagen_old": False, "collagen_contract": False, "profile_diverged": True,
        }],
        elapsed_seconds=0.01,
        allowlist={"signed": {"human_signoff_status": "approved"}},
    )
    assert summary["large_route_or_active_swing_count"] == 1
    assert summary["unsigned_large_route_or_active_swing_count"] == 0
    assert summary["ready_for_cutover"] is True


# --- Phase 2: botanical owner_type classifier (canary families) -------------
# owner_type in {therapeutic_botanical, standardized_botanical, botanical_blend}
# => product SHOULD use botanical adapters; the others => it should NOT.

_OWNER_TYPES = {"therapeutic_botanical", "standardized_botanical", "botanical_blend"}


def _owner_case(*specs):
    """Build (rows, row_contracts) from (name, domain, role, mass_mg,
    botanical_eligible, evidence) tuples."""
    rows, contracts = [], []
    for name, domain, role, mass, bot_eligible, evidence in specs:
        cid = name.lower().replace(" ", "_")
        rows.append({"name": name, "canonical_id": cid, "quantity": mass, "unit": "mg"})
        contracts.append({
            "name": name, "canonical_id": cid, "row_ref": name,
            "ingredient_domain": domain, "role": role,
            "botanical_source": {"value": bot_eligible, "evidence": list(evidence or [])},
            "profile_eligibility": {"botanical": {"eligible": bot_eligible}},
        })
    return rows, contracts


def _owner(product_name, *specs):
    from scoring_input_contract import _classify_botanical_owner_type
    rows, contracts = _owner_case(*specs)
    return _classify_botanical_owner_type({"product_name": product_name}, rows, contracts)


def test_owner_acerola_vitamin_c_is_nutrient_source_not_owner():
    out = _owner(
        "Acerola/Flavonoid",
        ("Vitamin C", "vitamin", "major", 300, False, []),
        ("Acerola", "herb", "claim_prominent", 100, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] == "nutrient_source"
    assert out["owner_reason_code"] == "nutrient_source_blocks_botanical"
    assert out["owner_type"] not in _OWNER_TYPES
    assert "Vitamin C" in out["blocking_row_refs"]
    assert "Acerola" in out["support_row_refs"]


def test_owner_red_wine_complex_with_vitc_is_not_owner():
    out = _owner(
        "Red Wine Complex",
        ("Vitamin C", "vitamin", "major", 60, False, []),
        ("Red Wine Complex", "herb", "claim_prominent", 200, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES


def test_owner_ksm66_is_standardized_botanical_owner():
    out = _owner(
        "KSM-66 Ashwagandha",
        ("KSM-66 Ashwagandha", "herb", "claim_prominent", 600, True, ["standardized_botanical_source_db"]),
    )
    assert out["owner_type"] == "standardized_botanical"
    assert out["owner_reason_code"] == "standardized_botanical_owner"


def test_owner_meriva_standardized_owns_even_with_vitamin():
    out = _owner(
        "Curcumin Phytosome with Vitamin C",
        ("Curcumin Phytosome", "herb", "claim_prominent", 500, True, ["product_standardized_botanical"]),
        ("Vitamin C", "vitamin", "major", 100, False, []),
    )
    assert out["owner_type"] == "standardized_botanical"


def test_owner_sambucus_title_alias_preserves_elderberry_owner():
    """Title-head matching must use botanical aliases, not only canonical IDs.

    DSLD rows often normalize Sambucus products to elderberry. If the title says
    Sambucus and the elderberry dose is still material, the product is a
    botanical intervention even when vitamin C is slightly higher by mass.
    """
    out = _owner(
        "Sambucus Relief for Kids",
        ("Vitamin C", "vitamin", "major", 30, False, []),
        ("Black Elderberry Extract", "herb", "major", 25, True, ["product_standardized_botanical"]),
    )
    assert out["owner_type"] == "standardized_botanical"
    assert out["owner_reason_code"] == "standardized_botanical_owner"


def test_owner_standardized_support_row_in_multivitamin_does_not_own():
    """A standardized botanical/source row inside a multi should not make the
    whole product use botanical formulation/dose adapters unless it owns the
    product surface or is at least as material as the competing deliverable."""
    out = _owner(
        "Kids Happy & Healthy Multi",
        ("Vitamin C", "vitamin", "major", 30, False, []),
        ("Blueberry Extract", "herb", "major", 20, True, ["product_standardized_botanical"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES
    assert out["owner_reason_code"] == "nutrient_source_blocks_botanical"


def test_owner_title_head_botanical_keeps_half_materiality_tolerance():
    out = _owner(
        "Ashwagandha with Magnesium",
        ("Ashwagandha", "herb", "claim_prominent", 300, True, ["botanical_source_text"]),
        ("Magnesium", "mineral", "major", 400, False, []),
    )
    assert out["owner_type"] == "therapeutic_botanical"


def test_owner_nonbotanical_blocker_must_be_material_by_mass():
    """A small nutrient add-on should not demote a material therapeutic
    botanical just because it is dose-checkable. The blocker must be comparable
    mass and cross the configured materiality fraction."""
    out = _owner(
        "Elderberry Syrup with Zinc",
        ("Elderberry", "herb", "claim_prominent", 1000, True, ["botanical_source_text"]),
        ("Zinc", "mineral", "major", 15, False, []),
    )
    assert out["owner_type"] == "therapeutic_botanical"
    assert out["blocking_row_refs"] == []


def test_owner_material_nonbotanical_blocker_records_blocking_ref():
    out = _owner(
        "Protein with Greens",
        ("Pea Protein", "sports_active", "primary", 20000, False, []),
        ("Spirulina", "herb", "major", 500, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES
    assert "Pea Protein" in out["blocking_row_refs"]


def test_owner_boswellia_is_therapeutic_botanical():
    out = _owner(
        "Boswellia Extract",
        ("Boswellia serrata", "herb", "claim_prominent", 300, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] == "therapeutic_botanical"


def test_owner_echinacea_only_no_ref_is_botanical_blend():
    # Echinacea has no therapeutic-dose-DB entry but is the sole material botanical.
    out = _owner(
        "Echinacea Root",
        ("Echinacea Root", "herb", "claim_prominent", 400, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] == "botanical_blend"


def test_owner_elderberry_with_zinc_owns_when_elderberry_is_title_head():
    out = _owner(
        "Elderberry Syrup with Zinc",
        ("Elderberry", "herb", "claim_prominent", 1000, True, ["botanical_source_text"]),
        ("Zinc", "mineral", "major", 15, False, []),
    )
    assert out["owner_type"] == "therapeutic_botanical"


def test_owner_zinc_plus_elderberry_does_not_own_when_zinc_is_deliverable():
    out = _owner(
        "Zinc + Elderberry",
        ("Zinc", "mineral", "claim_prominent", 15, False, []),
        ("Elderberry", "herb", "major", 100, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES


def test_owner_protein_with_greens_support_is_not_owner():
    out = _owner(
        "Protein with Greens",
        ("Pea Protein", "sports_active", "primary", 20000, False, []),
        ("Spirulina", "herb", "major", 500, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES
    assert "Pea Protein" in out["blocking_row_refs"]


def test_owner_collagen_with_berry_botanical_is_not_owner():
    out = _owner(
        "Collagen with Acai",
        ("Collagen Peptides", "collagen", "major", 10000, False, []),
        ("Acai", "herb", "claim_prominent", 100, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES


def test_owner_l_theanine_has_no_botanical_rows():
    out = _owner(
        "L-Theanine",
        ("L-Theanine", "amino_acid", "primary", 200, False, []),
    )
    assert out["owner_type"] == "not_botanical_owner"
    assert out["owner_reason_code"] == "no_botanical_rows"


def test_owner_resveratrol_is_isolated_marker_not_botanical_owner():
    out = _owner(
        "Trans-Resveratrol",
        ("Trans-Resveratrol", "botanical_marker", "claim_prominent", 100, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES
    assert out["owner_reason_code"] == "isolated_botanical_marker"


def test_owner_enzyme_product_with_fruit_support_is_not_owner():
    out = _owner(
        "Digestive Enzyme Complex",
        ("Bromelain", "enzyme", "primary", 100, False, []),
        ("Papaya", "herb", "major", 100, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] not in _OWNER_TYPES


def test_owner_digest_stem_title_with_enzyme_is_not_owner():
    """Organic Digest+ class (Phase 4): the title carries the 'digest' stem (not
    the exact word 'digestive'), the digestive enzymes are non-botanical adjunct
    rows, and the botanicals are 0-dose fruit/veg window-dressing. The enzyme-
    intent guard must de-botanize it — a 'digest'-stem title is digestive product
    intent, not only the literal word 'digestive'. Without the stem match this
    product is wrongly owned as a botanical_blend."""
    out = _owner(
        "Organic Digest+ Tropical Fruit Flavor",
        ("Botanical Greens Blend", "herb", "major", 500, True, ["botanical_source_text"]),
        ("Whole Food Enzyme Blend", "enzyme", "adjunct", 100, False, []),
    )
    assert out["owner_type"] not in _OWNER_TYPES
    assert out["owner_reason_code"] == "material_nonbotanical_deliverable"


def test_owner_digest_title_without_enzyme_stays_botanical():
    """The broadened 'digest'-stem title must NOT de-botanize a pure botanical
    cleanse with no enzymes — the enzyme guard requires an actual non-botanical
    enzyme row, so a Senna/Cascara 'Digestion' cleanse stays botanical-owned."""
    out = _owner(
        "Digestion & Elimination Cleanse",
        ("Senna Leaf", "herb", "claim_prominent", 500, True, ["botanical_source_text"]),
        ("Cascara Sagrada", "herb", "major", 300, True, ["botanical_source_text"]),
    )
    assert out["owner_type"] in _OWNER_TYPES


def test_standardized_botanicals_membership_requires_genuine_botanical_identity():
    """standardized_botanicals.json contains non-botanical branded compounds
    (e.g. Setria glutathione). Membership alone must NOT make a tripeptide a
    botanical row; a genuine botanical identity or therapeutic reference is
    required."""
    from scoring_input_contract import _botanical_source_evidence

    # Non-botanical (glutathione) flagged via standardized_botanicals membership
    # must NOT be granted the standardized-membership botanical evidence.
    non_botanical = {
        "canonical_id": "glutathione", "name": "Glutathione",
        "canonical_source_db": "standardized_botanicals",
    }
    _value, evidence = _botanical_source_evidence(non_botanical)
    assert "standardized_botanical_source_db" not in evidence
    assert "product_standardized_botanical" not in evidence

    # Genuine botanical (ashwagandha) -> standardized-membership evidence granted.
    genuine = {
        "canonical_id": "ashwagandha", "name": "Ashwagandha",
        "canonical_source_db": "standardized_botanicals",
    }
    _value, evidence = _botanical_source_evidence(genuine)
    assert "standardized_botanical_source_db" in evidence


def test_botanical_eligible_derives_from_owner_type():
    """Phase 3 behavior change: botanical `eligible` is driven by owner_type, not
    the legacy arbiter. Acerola (material herb) was botanized by the old arbiter;
    owner_type says nutrient_source so it must now be NOT eligible."""
    from scoring_input_contract import _product_botanical_profile_eligible

    # nutrient_source -> NOT eligible (old arbiter botanized this: acerola is material)
    rows, contracts = _owner_case(
        ("Vitamin C", "vitamin", "major", 300, False, []),
        ("Acerola", "herb", "claim_prominent", 200, True, ["botanical_source_text"]),
    )
    assert _product_botanical_profile_eligible({"product_name": "Acerola/Flavonoid"}, rows, contracts) is False

    # standardized botanical -> eligible
    rows, contracts = _owner_case(
        ("KSM-66 Ashwagandha", "herb", "claim_prominent", 600, True, ["standardized_botanical_source_db"]),
    )
    assert _product_botanical_profile_eligible({"product_name": "KSM-66"}, rows, contracts) is True

    # therapeutic botanical -> eligible
    rows, contracts = _owner_case(
        ("Boswellia serrata", "herb", "claim_prominent", 300, True, ["botanical_source_text"]),
    )
    assert _product_botanical_profile_eligible({"product_name": "Boswellia"}, rows, contracts) is True


def test_profile_cutover_impact_old_baseline_forces_legacy_selector():
    from api_audit.audit_v4_profile_cutover_impact import _profile_state

    product = _product(
        "Vitamin D3 Vegan",
        [
            _row("vitamin_d", "Vitamin D", 25, "mcg", category="vitamins", raw_taxonomy={"category": "vitamin"}),
            _row("lichen", "Lichen", 100, "mg", raw_taxonomy={"category": "botanical"}),
        ],
    )
    contract = build_scoring_classification(product)

    state = _profile_state(product, "botanical", "generic", contract)

    assert state["old"] is True
    assert state["contract"] is False
    assert state["diverged"] is True


def test_botanical_scoring_actives_use_composite_row_identity_for_duplicate_refs():
    import scoring_v4.modules.botanical_profile as botanical_profile

    product = _product(
        "Blueberry Blend",
        [
            _row(
                "phytomemory_proprietary_blend",
                "PhytoMemory Proprietary Blend",
                150,
                "mg",
                raw_source_path="ingredientRows[1]",
            ),
            _row(
                "blueberry",
                "Blueberry Fruit Extract",
                150,
                "mg",
                raw_source_path="ingredientRows[1]",
                raw_taxonomy={"category": "botanical"},
            ),
        ],
    )

    rows = {
        row["canonical_id"]: row
        for row in botanical_profile._scoring_actives(product)
    }

    assert rows["phytomemory_proprietary_blend"]["_scoring_classification"]["canonical_id"] == "phytomemory_proprietary_blend"
    assert rows["blueberry"]["_scoring_classification"]["canonical_id"] == "blueberry"
    assert botanical_profile._is_botanical_active(rows["phytomemory_proprietary_blend"]) is False
    assert botanical_profile._is_botanical_active(rows["blueberry"]) is True


def test_profile_cutover_impact_allowlist_signs_non_safety_changes():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    rows = [
        {
            "dsld_id": "large-delta",
            "old_score": 70.0,
            "new_score": 63.0,
            "abs_score_delta": 7.0,
            "old_verdict": "SAFE",
            "new_verdict": "SAFE",
            "verdict_changed": False,
            "less_restrictive_verdict_flip": False,
            "more_restrictive_verdict_flip": False,
            "safety_verdict_flip": False,
            "not_scored_transition": False,
            "profile_diverged": True,
        },
        {
            "dsld_id": "verdict-flip",
            "old_score": 42.0,
            "new_score": 41.0,
            "abs_score_delta": 1.0,
            "old_verdict": "SAFE",
            "new_verdict": "POOR",
            "verdict_changed": True,
            "less_restrictive_verdict_flip": False,
            "more_restrictive_verdict_flip": True,
            "safety_verdict_flip": False,
            "not_scored_transition": False,
            "profile_diverged": True,
        },
    ]
    allowlist = {
        "large-delta": {"human_signoff_status": "approved"},
        "verdict-flip": {"human_signoff_status": "approved"},
    }

    summary = summarize(rows, elapsed_seconds=0.01, allowlist=allowlist)

    assert summary["signed_large_score_delta_ge_5_count"] == 1
    assert summary["unsigned_large_score_delta_ge_5_count"] == 0
    assert summary["signed_verdict_flip_count"] == 1
    assert summary["unsigned_verdict_flip_count"] == 0
    assert summary["ready_for_cutover"] is True


def test_profile_cutover_impact_safety_flip_blocks_even_when_signed():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [
            {
                "dsld_id": "safety-flip",
                "old_score": 55.0,
                "new_score": 55.0,
                "abs_score_delta": 0.0,
                "old_verdict": "BLOCKED",
                "new_verdict": "SAFE",
                "verdict_changed": True,
                "less_restrictive_verdict_flip": True,
                "more_restrictive_verdict_flip": False,
                "safety_verdict_flip": True,
                "not_scored_transition": False,
                "profile_diverged": True,
            }
        ],
        elapsed_seconds=0.01,
        allowlist={"safety-flip": {"human_signoff_status": "approved"}},
    )

    assert summary["safety_verdict_flip_count"] == 1
    assert summary["signed_verdict_flip_count"] == 1
    assert summary["unsigned_verdict_flip_count"] == 0
    assert summary["ready_for_cutover"] is False


def test_profile_cutover_impact_counts_not_scored_transitions_separately():
    from api_audit.audit_v4_profile_cutover_impact import summarize

    summary = summarize(
        [
            {
                "dsld_id": "not-scored",
                "old_score": 55.0,
                "new_score": None,
                "abs_score_delta": None,
                "old_verdict": "SAFE",
                "new_verdict": "NOT_SCORED",
                "verdict_changed": True,
                "less_restrictive_verdict_flip": False,
                "more_restrictive_verdict_flip": True,
                "safety_verdict_flip": False,
                "not_scored_transition": True,
                "profile_diverged": True,
            }
        ],
        elapsed_seconds=0.01,
    )

    assert summary["not_scored_transition_count"] == 1
    assert summary["safety_verdict_flip_count"] == 0
    assert summary["ready_for_cutover"] is False
