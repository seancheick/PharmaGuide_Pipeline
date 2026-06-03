from __future__ import annotations

import ast
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
    assert ingredient["ingredient_domain"] == "generic_active"
    assert ingredient["botanical_source"]["value"] is False
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is False


def test_botanical_source_form_can_grant_botanical_eligibility():
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
    assert "botanical_source_form" in ingredient["botanical_source"]["evidence"]
    assert ingredient["profile_eligibility"]["botanical"]["eligible"] is True


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
