"""v4 Probiotic Trust dimension — P2.4 tests.

Per §6 probiotic rubric, Testing & Trust 15 is identical to generic:

    B4a verified certs           up to 12 (scope-aware diminishing returns)
    B4b GMP / facility quality   up to 4
    B4c batch traceability       COA + batch lookup signals
    hard-clamp 15 across the three sub-lines

This slice wires the existing `score_trust()` from generic_trust into
the probiotic module. No probiotic-specific cert programs exist in the
catalog today (NSF / USP / Informed Choice are class-agnostic; IFOS is
omega-specific and filtered out by the marine-cert gate when supp_type
is not omega-like). If a future probiotic-specific verification appears
(per-batch CFU lot testing, etc.), it gets added in a later slice.

The cross-module Trust scope policy question (brand_only and
needs_review currently score 0) is tracked separately as P1.7 — it
affects probiotic NSF certs too, but should be solved generically
across all modules rather than patched in probiotic.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _trust_view(breakdown: dict) -> dict:
    """Phase 4 shim: reconstruct the legacy 0-15 trust-dimension view from the
    verification_bonus payload so these scorer tests keep their exact
    assertions. The bonus keeps the original 0-15 components and nests the
    trust scorer metadata under `trust_metadata`; source_trust_score_0_15 is
    the pre-rescale 0-15 score."""
    vb = breakdown["verification_bonus"]
    meta = vb.get("metadata", {})
    return {
        "score": meta.get("source_trust_score_0_15", 0.0),
        "max": 15,
        "components": vb.get("components", {}),
        "penalties": vb.get("penalties", {}),
        "metadata": meta.get("trust_metadata", {}),
    }


def _probiotic_product(*, verified_cert_programs=None, gmp=None, has_coa=False,
                       has_batch_lookup=False, **extra):
    """Build a probiotic product with optional cert signals."""
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "L. rhamnosus HN001", "canonical_id": "lacto_r",
                 "standard_name": "Lactobacillus rhamnosus", "mapped": True,
                 "has_dose": True}
            ],
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_billion_count": 20.0,
            "total_strain_count": 1,
            "clinical_strain_count": 1,
            "probiotic_blends": [
                {"name": "L. rhamnosus HN001",
                 "strains": ["Lactobacillus rhamnosus HN001"],
                 "cfu_data": {"has_cfu": False}}
            ],
            "clinical_strains": [
                {"name": "L. rhamnosus HN001",
                 "clinical_support_level": "high",
                 "adequacy_tier": None, "cfu_per_day": None}
            ],
        },
        "verified_cert_programs": verified_cert_programs or [],
        "certification_data": {
            "gmp": gmp or {},
            "batch_traceability": {
                "has_coa": has_coa, "has_batch_lookup": has_batch_lookup,
            },
        },
    }
    product.update(extra)
    return product


# --- Trust dimension contract on probiotic products ---------------------


def test_probiotic_trust_zero_when_no_certs() -> None:
    """The 3 real probiotic canaries (Spring Valley, GNC Ultra, GoL Prenatal)
    all have no SKU/product_line certs. Probiotic module must surface this
    accurately — Trust 0/15."""
    from scoring_v4.modules.probiotic import score_probiotic

    result = score_probiotic(_probiotic_product())
    breakdown = result.to_breakdown()
    trust_dim = _trust_view(breakdown)

    assert trust_dim["score"] == 0.0
    assert trust_dim["max"] == 15
    assert trust_dim["components"]["B4a_verified_certifications"] == 0.0
    assert trust_dim["components"]["B4b_gmp"] == 0.0
    assert trust_dim["components"]["B4c_batch_traceability"] == 0.0


def test_probiotic_trust_nsf_sport_sku_scores_8() -> None:
    """A probiotic with an SKU-verified cert earns B4a credit identical
    to the generic module — the v3-parity-locked path."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"}
        ]
    )
    result = score_probiotic(product)
    trust_dim =_trust_view( result.to_breakdown())

    assert trust_dim["score"] == 8.0
    assert trust_dim["components"]["B4a_verified_certifications"] == 8.0


def test_probiotic_trust_combined_sku_plus_gmp_plus_coa() -> None:
    """SKU 8 + GMP 4 + COA 1 = 13, well under the 15 clamp."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"}
        ],
        gmp={"nsf_gmp": True},
        has_coa=True,
    )
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())

    assert trust_dim["score"] == 13.0
    assert trust_dim["components"]["B4b_gmp"] == 4.0
    assert trust_dim["components"]["B4c_batch_traceability"] == 1.0


def test_probiotic_trust_clamps_at_15() -> None:
    """Stacking certs past the dimension cap clamps to 15."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"},
            {"program": "usp verified", "scope": "sku", "evidence_source": "registry"},
            {"program": "informed choice", "scope": "sku", "evidence_source": "registry"},
        ],
        gmp={"nsf_gmp": True},
        has_coa=True,
        has_batch_lookup=True,
    )
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())

    assert trust_dim["score"] == 15.0
    assert trust_dim["max"] == 15


def test_probiotic_trust_needs_review_cert_scores_zero() -> None:
    """Cross-module Trust policy: scope=needs_review is a 0-pt bucket
    (the GoL Prenatal canary case). P1.7 will revisit whether such
    scopes deserve fractional credit; until then we keep parity with
    generic."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "NSF Certified", "scope": "needs_review", "evidence_source": "registry"}
        ]
    )
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())
    assert trust_dim["score"] == 0.0


def test_probiotic_trust_fda_registered_only_scores_2() -> None:
    """B4b FDA-registered (without NSF/claimed GMP) = 2 pts."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(gmp={"fda_registered": True})
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())
    assert trust_dim["components"]["B4b_gmp"] == 2.0
    assert trust_dim["score"] == 2.0


def test_probiotic_trust_marine_cert_filter_holds() -> None:
    """A probiotic product with IFOS in its cert list should NOT receive
    marine-cert credit — the marine filter in score_trust gates on
    omega-like products, and a generic probiotic is not omega-like."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "ifos", "scope": "label_asserted_product",
             "evidence_source": "product_label"}
        ]
    )
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())
    # IFOS on a non-omega product is correctly filtered → 0 credit.
    assert trust_dim["score"] == 0.0


# --- Module wiring + roll-forward -----------------------------------------


def test_probiotic_module_phase_marker_rolls_forward_through_p24() -> None:
    """At-or-after P2.4: phase is at least P2.4. P2.5+ rolls forward."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    assert breakdown["phase"].startswith("P2."), (
        f"unexpected phase: {breakdown['phase']}"
    )


def test_probiotic_trust_metadata_carries_audit_fields() -> None:
    """Audit / score-delta tooling reads verified_programs_scored and
    verified_scope_counts to explain Trust credit. These must propagate
    through the module breakdown."""
    from scoring_v4.modules.probiotic import score_probiotic

    product = _probiotic_product(
        verified_cert_programs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"}
        ]
    )
    trust_dim =_trust_view( score_probiotic(product).to_breakdown())

    meta = trust_dim["metadata"]
    assert meta["phase"] == "P1.3.4_testing_trust"
    assert "nsf certified for sport" in meta["verified_programs_scored"]
    assert meta["verified_scope_counts"].get("sku") == 1


def test_probiotic_trust_independent_of_formulation_dose_evidence() -> None:
    """A product can have great formulation + evidence and still have 0
    trust if no certs are present. Verify the independence of dimensions."""
    from scoring_v4.modules.probiotic import score_probiotic

    # High-formulation probiotic, no certs
    high_form_no_certs = _probiotic_product()
    high_form_no_certs["probiotic_data"]["total_billion_count"] = 50.0
    high_form_no_certs["probiotic_data"]["total_strain_count"] = 10
    high_form_no_certs["probiotic_data"]["clinical_strain_count"] = 5
    high_form_no_certs["probiotic_data"]["prebiotic_present"] = True
    high_form_no_certs["probiotic_data"]["has_survivability_coating"] = True

    breakdown = score_probiotic(high_form_no_certs).to_breakdown()
    assert breakdown["dimensions"]["formulation"]["score"] > 20.0
    assert _trust_view(breakdown)["score"] == 0.0


def test_probiotic_trust_score_is_independent_of_other_dimensions() -> None:
    """Trust is computed independently — populating it doesn't depend on
    or pollute the other dimensions. (Originally locked Transparency to
    None; that assertion rolled forward at P2.5.)"""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    # Trust is fully populated at this slice or later.
    assert _trust_view(breakdown)["score"] is not None
    assert "B4a_verified_certifications" in _trust_view(breakdown)["components"]
