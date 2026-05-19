"""v4 Generic Testing & Trust dimension — P1.3.4 tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(name: str = "Magnesium", standard_name: str | None = None) -> dict:
    return {
        "name": name,
        "standard_name": standard_name or name,
        "mapped": True,
        "quantity": 200,
        "unit": "mg",
    }


def _product(
    *,
    verified_cert_programs: list | None = None,
    gmp: dict | None = None,
    gmp_level: str | None = None,
    batch_traceability: dict | None = None,
    ingredients: list | None = None,
    supp_type: str = "single_nutrient",
    top_level: dict | None = None,
) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": supp_type},
        "verified_cert_programs": verified_cert_programs or [],
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "certification_data": {
            "gmp": gmp or {},
            "batch_traceability": batch_traceability
            or {"has_coa": False, "has_batch_lookup": False, "has_qr_code": False},
        },
    }
    if gmp_level is not None:
        product["gmp_level"] = gmp_level
    if top_level:
        product.update(top_level)
    return product


def _cert(program: str, scope: str, **extra) -> dict:
    row = {"program": program, "scope": scope, "recency_status": "fresh"}
    row.update(extra)
    return row


def _label(program: str, source: str = "product_label") -> dict:
    return _cert(program, "label_asserted_product", evidence_source=source)


def test_trust_payload_shape_and_phase() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(_product())

    assert payload["score"] == 0.0
    assert payload["max"] == 15.0
    assert payload["components"] == {
        "B4a_verified_certifications": 0.0,
        "B4b_gmp": 0.0,
        "B4c_batch_traceability": 0.0,
    }
    assert payload["penalties"] == {}
    assert payload["phase"] == "P1.3.4_testing_trust"
    assert payload["metadata"]["phase"] == "P1.3.4_testing_trust"


def test_two_sku_verified_certs_score_12_b4a() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _cert("NSF Sport", "sku"),
                _cert("NSF Certified", "sku"),
            ]
        )
    )

    assert payload["components"]["B4a_verified_certifications"] == 12.0
    assert payload["score"] == 12.0
    assert payload["metadata"]["verified_scope_counts"] == {"sku": 2}


def test_three_sku_certs_clamp_b4a_at_12() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _cert("NSF Sport", "sku"),
                _cert("NSF Certified", "sku"),
                _cert("USP Verified", "sku"),
            ]
        )
    )

    assert payload["components"]["B4a_verified_certifications"] == 12.0


def test_brand_only_needs_review_and_claimed_only_score_zero() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _cert("NSF Sport", "brand_only"),
                _cert("USP Verified", "needs_review"),
                _cert("Informed Choice", "claimed_only"),
            ]
        )
    )

    assert payload["components"]["B4a_verified_certifications"] == 0.0
    assert payload["metadata"]["verified_programs_scored"] == []


def test_stale_scoring_blocked_cert_scores_zero() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _cert("NSF Sport", "sku", scoring_blocked_reason="snapshot_too_stale"),
            ]
        )
    )

    assert payload["components"]["B4a_verified_certifications"] == 0.0


def test_label_asserted_whitelisted_program_scores_two() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(_product(verified_cert_programs=[_label("USP Verified")]))

    assert payload["components"]["B4a_verified_certifications"] == 2.0
    assert payload["metadata"]["verified_scope_counts"] == {"label_asserted_product": 1}


def test_label_asserted_manufacturer_source_scores_zero() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(_product(verified_cert_programs=[_label("USP Verified", source="manufacturer")]))

    assert payload["components"]["B4a_verified_certifications"] == 0.0


def test_label_asserted_duplicate_program_scores_once_strongest_scope_wins() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _label("USP Verified"),
                _label("USP Verified"),
                _cert("USP Verified", "sku"),
            ]
        )
    )

    assert payload["components"]["B4a_verified_certifications"] == 8.0
    assert payload["metadata"]["verified_scope_counts"] == {"sku": 1}
    assert payload["metadata"]["verified_programs_scored"] == ["usp verified"]


def test_ifos_label_asserted_scores_only_for_omega_product() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    non_omega = score_trust(_product(verified_cert_programs=[_label("IFOS")]))
    omega = score_trust(
        _product(
            verified_cert_programs=[_label("IFOS")],
            ingredients=[_ingredient(name="Fish Oil", standard_name="Omega-3 Fish Oil")],
        )
    )

    assert non_omega["components"]["B4a_verified_certifications"] == 0.0
    assert omega["components"]["B4a_verified_certifications"] == 2.0


def test_marine_sku_cert_scores_only_for_omega_product() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    non_omega = score_trust(_product(verified_cert_programs=[_cert("IFOS", "sku")]))
    omega = score_trust(
        _product(
            verified_cert_programs=[_cert("IFOS", "sku")],
            ingredients=[_ingredient(name="EPA DHA Fish Oil", standard_name="Omega-3 Fish Oil")],
        )
    )

    assert non_omega["components"]["B4a_verified_certifications"] == 0.0
    assert omega["components"]["B4a_verified_certifications"] == 8.0


def test_gmp_certified_scores_four_and_fda_registered_scores_two() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    certified = score_trust(_product(gmp={"claimed": True}))
    fda_registered = score_trust(_product(gmp={"fda_registered": True}))

    assert certified["components"]["B4b_gmp"] == 4.0
    assert fda_registered["components"]["B4b_gmp"] == 2.0


def test_top_level_gmp_level_scores() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    certified = score_trust(_product(gmp_level="certified"))
    fda_registered = score_trust(_product(gmp_level="fda_registered"))

    assert certified["components"]["B4b_gmp"] == 4.0
    assert fda_registered["components"]["B4b_gmp"] == 2.0


def test_batch_traceability_scores_coa_and_batch_lookup() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(batch_traceability={"has_coa": True, "has_batch_lookup": True})
    )

    assert payload["components"]["B4c_batch_traceability"] == 2.0


def test_batch_traceability_reads_top_level_fallbacks_and_qr_code() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    top_level = score_trust(_product(top_level={"has_coa": True, "has_batch_lookup": True}))
    qr = score_trust(_product(batch_traceability={"has_qr_code": True}))

    assert top_level["components"]["B4c_batch_traceability"] == 2.0
    assert qr["components"]["B4c_batch_traceability"] == 1.0


def test_dimension_hard_clamps_b4a_b4b_b4c_to_15() -> None:
    from scoring_v4.modules.generic_trust import score_trust

    payload = score_trust(
        _product(
            verified_cert_programs=[
                _cert("NSF Sport", "sku"),
                _cert("NSF Certified", "sku"),
            ],
            gmp={"claimed": True},
            batch_traceability={"has_coa": True, "has_batch_lookup": True},
        )
    )

    assert payload["components"] == {
        "B4a_verified_certifications": 12.0,
        "B4b_gmp": 4.0,
        "B4c_batch_traceability": 2.0,
    }
    assert payload["metadata"]["raw_testing_trust"] == 18.0
    assert payload["score"] == 15.0


def test_shadow_wires_trust_dimension() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product(verified_cert_programs=[_cert("NSF Sport", "sku")]))

    trust = out["shadow_score_v4_breakdown"]["module"]["dimensions"]["trust"]
    assert trust["score"] == 8.0
    assert trust["max"] == 15.0
    assert trust["metadata"]["phase"] == "P1.3.4_testing_trust"


def test_generic_trust_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_trust as gt

    source = Path(gt.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
