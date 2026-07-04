#!/usr/bin/env python3
"""Verification-magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR: trust/verification point values, cert-scope points, and the
manufacturer D1-D5 + violation caps across the trust/manufacturer/brand-testing/
verification-bonus modules moved into
scoring_v4/config/quality_score.json (`verification_magnitudes.<module>`).
Empty diff verified across score_trust / score_manufacturer_trust /
score_manufacturer_violations / score_brand_testing_posture /
score_verification_bonus (564 entrypoint×product pairs).

Pins config to pre-hoist values + runtime parity. CLASS_I_LOOKBACK_DAYS (3*365)
stays in code as a documented window and is asserted unchanged.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    generic_trust, generic_manufacturer, brand_testing_posture,
    verification_bonus, omega_trust,
)

VM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["verification_magnitudes"]

ORIGINAL = {
    "generic_trust": {
        "dimension_cap": 15.0, "b4a_cap": 12.0,
        "b4a_scope_points": {"sku": [8.0, 4.0, 2.0], "product_line": [6.0, 3.0, 1.0],
                             "label_asserted_product": [2.0, 1.0, 0.0], "brand_only": [0.0, 0.0, 0.0],
                             "needs_review": [0.0, 0.0, 0.0], "claimed_only": [0.0, 0.0, 0.0]},
        "b4a_scope_strength": {"sku": 3, "product_line": 2, "label_asserted_product": 1},
        "b4b_gmp_certified": 4.0, "b4b_fda_registered": 2.0, "b4c_coa": 1.0, "b4c_batch_lookup": 1.0,
    },
    "manufacturer": {
        "manufacturer_trust_cap": 5.0, "d1_trusted": 2.0, "d1_mid_tier": 1.0, "d2_disclosure": 1.0,
        "d3_physician": 0.5, "d4_high_standard_region": 1.0, "d5_sustainability": 0.5, "d3_d4_d5_cap": 2.0,
        "mfg_cap_default": -25.0, "mfg_cap_two_class_i": -35.0, "mfg_cap_three_or_more_class_i": -50.0,
    },
    "brand_testing": {"hard_evidence_score": 2.0, "soft_quality_score": 1.0},
    "verification_bonus": {"cap": 8.0},
    "omega_trust": {"cap_trust": 15.0},
}


def test_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        assert VM[mod] == vals, f"verification_magnitudes.{mod} drifted from pre-hoist values"


def test_runtime_constants_read_from_config_no_drift():
    assert generic_trust.DIMENSION_CAP == 15.0
    assert generic_trust.B4A_CAP == 12.0
    assert generic_trust.B4A_SCOPE_POINTS == VM["generic_trust"]["b4a_scope_points"]
    assert generic_trust.B4A_SCOPE_STRENGTH == VM["generic_trust"]["b4a_scope_strength"]
    assert generic_trust.B4B_GMP_CERTIFIED == 4.0
    assert generic_manufacturer.MANUFACTURER_TRUST_CAP == 5.0
    assert generic_manufacturer.D3_PHYSICIAN == 0.5
    assert generic_manufacturer.MFG_CAP_THREE_OR_MORE_CLASS_I == -50.0
    assert brand_testing_posture.BRAND_TESTING_HARD_EVIDENCE_SCORE == 2.0
    assert verification_bonus.VERIFICATION_BONUS_CAP == 8.0
    assert omega_trust.CAP_TRUST == 15.0


def test_class_i_lookback_stays_in_code():
    # deliberately NOT hoisted (documented 3-year window, an expression not a point)
    assert generic_manufacturer.CLASS_I_LOOKBACK_DAYS == 3 * 365
