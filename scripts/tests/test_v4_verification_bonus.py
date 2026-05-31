"""V4 Phase 4 — verification bonus (Trust → additive 0-8 bonus).

Parity is PER-MODULE: bonus == round(that module's trust_score * 8/15). The
generic and omega trust scorers are structurally different and are NOT expected
to agree cross-module.

Spec: docs/superpowers/specs/2026-05-31-v4-verification-bonus-design.md
"""
from __future__ import annotations

from scoring_v4.modules.verification_bonus import (  # noqa: E402
    score_verification_bonus,
    VERIFICATION_BONUS_CAP,
)
from scoring_v4.modules.generic_trust import score_trust as _generic_trust  # noqa: E402
from scoring_v4.modules.omega_trust import score_trust as _omega_trust  # noqa: E402

# Independent expected transform — deliberately NOT importing the module's
# _RESCALE, so a wrong rescale in the module is actually caught (no tautology).
_EXPECTED_RESCALE = 8.0 / 15.0


def _expected_bonus(trust_score: float) -> float:
    return round(min(VERIFICATION_BONUS_CAP, max(0.0, trust_score * _EXPECTED_RESCALE)), 4)


def _ingredient() -> dict:
    return {"name": "Magnesium", "standard_name": "Magnesium", "mapped": True,
            "quantity": 200, "unit": "mg"}


def _cert(program: str, scope: str) -> dict:
    return {"program": program, "scope": scope, "recency_status": "fresh"}


def _product(verified_cert_programs=None, gmp=None, batch_traceability=None) -> dict:
    return {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "verified_cert_programs": verified_cert_programs or [],
        "ingredient_quality_data": {
            "ingredients_scorable": [_ingredient()],
            "ingredients": [_ingredient()],
        },
        "certification_data": {
            "gmp": gmp or {},
            "batch_traceability": batch_traceability
            or {"has_coa": False, "has_batch_lookup": False, "has_qr_code": False},
        },
    }


def _verified_product() -> dict:
    return _product(
        verified_cert_programs=[_cert("usp verified", "sku")],
        gmp={"certified": True},
        batch_traceability={"has_coa": True, "has_batch_lookup": True, "has_qr_code": False},
    )


def test_no_cert_product_bonus_is_zero():
    out = score_verification_bonus(_product(), "generic")
    assert out["score"] == 0.0


def test_verified_product_gets_positive_bonus():
    assert score_verification_bonus(_verified_product(), "generic")["score"] > 0.0


def _max_verified_product() -> dict:
    # 2 SKU certs (B4a 8+4=12) + GMP (4) + COA & batch (2) = 18 -> trust clamps
    # at 15, so the bonus must clamp at its 8.0 cap.
    return _product(
        verified_cert_programs=[_cert("usp verified", "sku"), _cert("nsf", "sku")],
        gmp={"certified": True},
        batch_traceability={"has_coa": True, "has_batch_lookup": True, "has_qr_code": False},
    )


def test_bonus_never_exceeds_cap():
    out = score_verification_bonus(_verified_product(), "generic")
    assert 0.0 <= out["score"] <= VERIFICATION_BONUS_CAP


def test_bonus_rescale_and_clamp_hold_at_high_verification():
    out = score_verification_bonus(_max_verified_product(), "generic")
    src = out["metadata"]["source_trust_score_0_15"]
    # Heavily-verified product: source trust is high, the bonus is the rescaled
    # value, and it never exceeds the 8.0 cap (clamp is min(8, src*8/15)).
    assert src >= 12.0
    assert out["score"] == _expected_bonus(src)
    assert out["score"] <= VERIFICATION_BONUS_CAP


def test_clamp_caps_bonus_at_8_for_source_at_or_above_15():
    # Direct boundary check of the rescale+clamp on the dimension cap (15) and
    # a hypothetical over-cap value — clamp must hold at exactly 8.0.
    assert _expected_bonus(15.0) == VERIFICATION_BONUS_CAP
    assert _expected_bonus(99.0) == VERIFICATION_BONUS_CAP


def test_per_module_parity_generic():
    product = _verified_product()
    trust = float(_generic_trust(product)["score"])
    assert trust > 0.0  # fixture must actually verify, else parity is vacuous
    assert score_verification_bonus(product, "generic")["score"] == _expected_bonus(trust)


def test_per_module_parity_omega():
    product = _verified_product()
    trust = float(_omega_trust(product)["score"])
    assert score_verification_bonus(product, "omega")["score"] == _expected_bonus(trust)


def test_rescale_is_eight_fifteenths():
    # Pin the transform so a drifted constant is caught directly.
    from scoring_v4.modules.verification_bonus import _RESCALE
    assert abs(_RESCALE - 8.0 / 15.0) < 1e-9


def test_payload_shape_and_provenance():
    out = score_verification_bonus(_verified_product(), "generic")
    assert {"score", "max", "components", "penalties", "metadata"}.issubset(out)
    assert out["max"] == VERIFICATION_BONUS_CAP
    assert "source_trust_score_0_15" in out["metadata"]
    # the bonus is the rescaled source trust (independent transform)
    src = out["metadata"]["source_trust_score_0_15"]
    assert out["score"] == _expected_bonus(src)
