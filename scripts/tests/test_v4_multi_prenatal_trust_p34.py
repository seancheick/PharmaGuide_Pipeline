"""v4 P3.4 — multi/prenatal Trust dimension tests.

Testing & Trust is the same product-verification rubric used by generic
and probiotic:

    B4a verified certs           up to 12
    B4b GMP / facility quality   up to 4
    B4c batch traceability       COA + batch lookup signals

This slice wires the shared v4 `score_trust()` path into the multi /
prenatal module so certification policy stays class-consistent. It does
not relax `brand_only` or `needs_review`; curated product-line overrides
remain the path for uncertain registry matches.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _cert(program: str, scope: str, *, source: str = "registry", **extra: object) -> dict:
    row = {"program": program, "scope": scope, "evidence_source": source}
    row.update(extra)
    return row


def _multi_product(
    *,
    verified_cert_programs: list[dict] | None = None,
    gmp: dict | None = None,
    batch_traceability: dict | None = None,
    top_level: dict | None = None,
) -> dict:
    product = {
        "status": "active",
        "form_factor": "tablet",
        "product_name": "Complete Multivitamin 2 per Day",
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": 8,
            "ingredients_scorable": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "mapped": True, "quantity": 900, "unit": "mcg RAE"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "mapped": True, "quantity": 90, "unit": "mg"},
                {"name": "Vitamin D", "canonical_id": "vitamin_d", "mapped": True, "quantity": 25, "unit": "mcg"},
                {"name": "Vitamin E", "canonical_id": "vitamin_e", "mapped": True, "quantity": 15, "unit": "mg"},
                {"name": "Folate", "canonical_id": "vitamin_b9_folate", "mapped": True, "quantity": 400, "unit": "mcg DFE"},
                {"name": "Vitamin B12", "canonical_id": "vitamin_b12_cobalamin", "mapped": True, "quantity": 50, "unit": "mcg"},
                {"name": "Zinc", "canonical_id": "zinc", "mapped": True, "quantity": 11, "unit": "mg"},
                {"name": "Iodine", "canonical_id": "iodine", "mapped": True, "quantity": 150, "unit": "mcg"},
            ],
        },
        "verified_cert_programs": verified_cert_programs or [],
        "certification_data": {
            "gmp": gmp or {},
            "batch_traceability": batch_traceability or {},
        },
    }
    if top_level:
        product.update(top_level)
    return product


def _trust_breakdown(product: dict) -> dict:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    return score_multi_prenatal(product).to_breakdown()["dimensions"]["trust"]


def test_multi_prenatal_trust_zero_when_no_product_verification() -> None:
    trust = _trust_breakdown(_multi_product())

    assert trust["score"] == 0.0
    assert trust["max"] == 15
    assert trust["components"]["B4a_verified_certifications"] == 0.0
    assert trust["components"]["B4b_gmp"] == 0.0
    assert trust["components"]["B4c_batch_traceability"] == 0.0


def test_multi_prenatal_trust_scores_sku_certification_at_first_rung() -> None:
    trust = _trust_breakdown(
        _multi_product(verified_cert_programs=[
            _cert("NSF Certified for Sport", "sku"),
        ])
    )

    assert trust["score"] == 8.0
    assert trust["components"]["B4a_verified_certifications"] == 8.0
    assert trust["metadata"]["verified_programs_scored"] == ["nsf certified for sport"]
    assert trust["metadata"]["verified_scope_counts"] == {"sku": 1}


def test_multi_prenatal_trust_scores_product_line_certification_at_first_rung() -> None:
    trust = _trust_breakdown(
        _multi_product(verified_cert_programs=[
            _cert("USP Verified", "product_line"),
        ])
    )

    assert trust["score"] == 6.0
    assert trust["components"]["B4a_verified_certifications"] == 6.0
    assert trust["metadata"]["verified_scope_counts"] == {"product_line": 1}


def test_multi_prenatal_trust_uncertain_scopes_do_not_score() -> None:
    for scope in ("brand_only", "needs_review", "claimed_only"):
        trust = _trust_breakdown(
            _multi_product(verified_cert_programs=[
                _cert("USP Verified", scope),
            ])
        )
        assert trust["score"] == 0.0
        assert trust["metadata"]["verified_programs_scored"] == []


def test_multi_prenatal_label_asserted_whitelist_requires_product_label_source() -> None:
    label_claim = _trust_breakdown(
        _multi_product(verified_cert_programs=[
            _cert("USP Verified", "label_asserted_product", source="product_label"),
        ])
    )
    manufacturer_claim = _trust_breakdown(
        _multi_product(verified_cert_programs=[
            _cert("USP Verified", "label_asserted_product", source="manufacturer_site"),
        ])
    )

    assert label_claim["score"] == 2.0
    assert label_claim["components"]["B4a_verified_certifications"] == 2.0
    assert manufacturer_claim["score"] == 0.0


def test_multi_prenatal_marine_certifications_are_filtered_on_non_omega_products() -> None:
    trust = _trust_breakdown(
        _multi_product(verified_cert_programs=[
            _cert("IFOS", "sku"),
            _cert("Friend of the Sea", "product_line"),
        ])
    )

    assert trust["score"] == 0.0
    assert trust["metadata"]["verified_programs_scored"] == []


def test_multi_prenatal_trust_combines_sku_gmp_and_traceability() -> None:
    trust = _trust_breakdown(
        _multi_product(
            verified_cert_programs=[_cert("NSF Certified for Sport", "sku")],
            gmp={"nsf_gmp": True},
            top_level={"has_coa": True, "has_batch_lookup": True},
        )
    )

    assert trust["score"] == 14.0
    assert trust["components"] == {
        "B4a_verified_certifications": 8.0,
        "B4b_gmp": 4.0,
        "B4c_batch_traceability": 2.0,
        "B4d_brand_testing_posture": 0.0,
    }


def test_multi_prenatal_trust_nested_qr_code_counts_as_batch_lookup() -> None:
    trust = _trust_breakdown(
        _multi_product(batch_traceability={"has_coa": False, "has_qr_code": True})
    )

    assert trust["score"] == 1.0
    assert trust["components"]["B4c_batch_traceability"] == 1.0


def test_multi_prenatal_trust_fda_registered_only_scores_two_points() -> None:
    trust = _trust_breakdown(
        _multi_product(gmp={"fda_registered": True})
    )

    assert trust["score"] == 2.0
    assert trust["components"]["B4b_gmp"] == 2.0


def test_multi_prenatal_trust_clamps_dimension_at_15() -> None:
    trust = _trust_breakdown(
        _multi_product(
            verified_cert_programs=[
                _cert("NSF Certified for Sport", "sku"),
                _cert("USP Verified", "sku"),
                _cert("Informed Choice", "sku"),
            ],
            gmp={"nsf_gmp": True},
            top_level={"has_coa": True, "has_batch_lookup": True},
        )
    )

    assert trust["score"] == 15.0
    assert trust["metadata"]["cap_applied"] is True


def test_score_multi_prenatal_wires_trust_dimension() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(
        _multi_product(verified_cert_programs=[_cert("USP Verified", "product_line")])
    ).to_breakdown()

    trust = breakdown["dimensions"]["trust"]
    assert trust["score"] == 6.0
    assert trust["metadata"]["phase"] == "P1.3.4_testing_trust"
    assert breakdown["score_100"] is not None
    assert breakdown["phase"].startswith("P3.")
    assert breakdown["metadata"]["module_state"] in {
        "trust_partial",
        "dimensions_complete",
        "complete",
    }


def test_multi_prenatal_trust_does_not_import_v3_scorer() -> None:
    source_path = SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal.py"
    tree = ast.parse(source_path.read_text())

    forbidden = {"score_supplements", "score_supplements_v3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
