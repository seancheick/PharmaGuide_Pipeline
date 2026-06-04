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

from scoring_input_contract import build_scoring_classification  # noqa: E402
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
    assert contract["classification_schema_version"] == "1.0.0"
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
    product = _product("Zinc", [_row("zinc", "Zinc", 15, "mg")], primary_type="single_mineral")
    native = build_scoring_classification(
        _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg")], primary_type="omega_3"),
        classification_origin="native_enrichment",
    )
    product["product_scoring_classification"] = native

    contract = build_scoring_classification(product)

    assert contract["classification_origin"] == "native_enrichment"
    assert contract["route_module"] == "omega"


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
