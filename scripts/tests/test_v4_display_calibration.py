"""V4 display-layer calibration (top-band, archetype-anchored).

Display-only normalization: corrects unreachable structural dimension ceilings so
each archetype's best-in-class reads ~95 for consumers, WITHOUT mutating the raw
audit score. Conservative k=3 convex LIFT (display = raw + (target - R_a) * t^k),
which never lowers a score and moves the 80-85 band only mildly. Gated by
top_band_eligibility (SAFE + raw>=80 + evidence + transparency + dose + no safety
flags). The confidence band is NOT a gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# ---- transform -------------------------------------------------------------

def test_transform_identity_at_and_below_floor() -> None:
    from scoring_v4.display_calibration import _transform
    assert _transform(80.0, R_a=86.5) == 80.0
    assert _transform(75.0, R_a=86.5) == 75.0  # below floor untouched


def test_transform_best_in_class_reaches_target() -> None:
    from scoring_v4.display_calibration import _transform
    # raw == R_a -> exactly target (95)
    assert _transform(86.5, R_a=86.5) == 95.0
    assert _transform(93.0, R_a=93.0) == 95.0


def test_transform_never_lowers_score() -> None:
    from scoring_v4.display_calibration import _transform
    # the corrected lift formula must never produce display < raw (the bug in the
    # naive "80 + 15*t^3" mapping, which dipped to 80.4 at raw 82 for R_a=86.5).
    for raw in [80.5, 81, 82, 83, 84, 85, 86, 86.5]:
        assert _transform(raw, R_a=86.5) >= raw - 1e-9


def test_transform_low_band_moves_mildly() -> None:
    from scoring_v4.display_calibration import _transform
    # k=3 keeps raw 82 (R_a=86.5) nearly fixed (< +0.5 lift); the strong lift is
    # reserved for near-anchor.
    assert _transform(82.0, R_a=86.5) - 82.0 < 0.5
    assert _transform(86.0, R_a=86.5) - 86.0 > 4.0  # near anchor lifts hard


def test_transform_monotonic_and_clamped() -> None:
    from scoring_v4.display_calibration import _transform
    prev = -1.0
    for raw in [80, 82, 84, 86, 88, 90, 93]:  # realistic raw range (max archetype ~93)
        d = _transform(float(raw), R_a=86.5)
        assert d >= prev  # monotonic non-decreasing
        assert d <= 96.0  # ceiling
        prev = d


def test_transform_never_lowers_above_ceiling() -> None:
    from scoring_v4.display_calibration import _transform
    # a (hypothetical) raw already above the 96 ceiling must pass through, not be
    # clamped DOWN — the audit score is never lowered by the display layer.
    assert _transform(99.0, R_a=86.5) == 99.0


# ---- eligibility gate ------------------------------------------------------

def _dims(form=20, dose=20, evidence=15, transparency=10, tcap=10):
    return {
        "formulation": {"score": form},
        "dose": {"score": dose},
        "evidence": {"score": evidence},
        "transparency": {"score": transparency, "max": tcap},
    }


def test_eligible_happy_path() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, _ = _eligible(verdict="SAFE", raw=85.0, dims=_dims(), safety_signals=[])
    assert ok is True


def test_gate_blocks_below_raw_80() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, reason = _eligible(verdict="SAFE", raw=79.9, dims=_dims(), safety_signals=[])
    assert ok is False and "raw" in reason


def test_gate_blocks_non_safe_verdict() -> None:
    from scoring_v4.display_calibration import _eligible
    for v in ["CAUTION", "POOR", "UNSAFE", "BLOCKED", "NOT_SCORED"]:
        ok, _ = _eligible(verdict=v, raw=90.0, dims=_dims(), safety_signals=[])
        assert ok is False


def test_gate_blocks_zero_evidence() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, reason = _eligible(verdict="SAFE", raw=85.0, dims=_dims(evidence=0), safety_signals=[])
    assert ok is False and "evidence" in reason


def test_gate_blocks_low_transparency() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, reason = _eligible(verdict="SAFE", raw=85.0, dims=_dims(transparency=3, tcap=10), safety_signals=[])
    assert ok is False and "transparency" in reason


def test_gate_blocks_zero_dose_disclosure() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, reason = _eligible(verdict="SAFE", raw=85.0, dims=_dims(dose=0), safety_signals=[])
    assert ok is False and "dose" in reason


def test_gate_blocks_safety_signals() -> None:
    from scoring_v4.display_calibration import _eligible
    ok, reason = _eligible(verdict="SAFE", raw=85.0, dims=_dims(),
                           safety_signals=["STIMULANT_CAFFEINE_HIGH_DOSE"])
    assert ok is False and "safety" in reason


# ---- archetype classifier --------------------------------------------------

def test_archetype_from_module() -> None:
    from scoring_v4.display_calibration import _archetype
    assert _archetype("sports", {}) == "sports_single"
    assert _archetype("omega", {}) == "omega"
    assert _archetype("probiotic", {}) == "probiotic"
    assert _archetype("multi_or_prenatal", {}) == "prenatal_multi"


def test_archetype_generic_split() -> None:
    from scoring_v4.display_calibration import _archetype
    botan = {"dimensions": {"formulation": {"metadata": {"botanical_profile_applied": True}}}}
    collagen = {"dimensions": {"formulation": {"metadata": {"collagen_profile_applied": True}}}}
    plain = {"dimensions": {"formulation": {"metadata": {}}}}
    assert _archetype("generic", botan) == "generic_botanical_branded"
    assert _archetype("generic", collagen) == "generic_botanical_branded"
    assert _archetype("generic", plain) == "generic_single_molecule"


# ---- integration: calibrate_display ---------------------------------------

def _shadow(raw, verdict="SAFE", module="probiotic", dims=None, safety_signals=None):
    return {
        "shadow_score_v4_100": raw,
        "shadow_score_v4_verdict": verdict,
        "shadow_score_v4_module": module,
        "shadow_score_v4_breakdown": {
            "module": {"dimensions": dims or _dims()},
            "safety_gate": {"safety_signals": safety_signals or []},
        },
    }


def test_calibrate_preserves_raw() -> None:
    from scoring_v4.display_calibration import calibrate_display
    sh = _shadow(86.5)
    out = calibrate_display(sh)
    assert out["shadow_score_v4_100"] == 86.5  # raw NEVER changes
    assert out["shadow_score_v4_display_100"] == 95.0  # best-in-class probiotic


def test_calibrate_emits_provenance() -> None:
    from scoring_v4.display_calibration import calibrate_display
    out = calibrate_display(_shadow(85.0))
    cal = out["shadow_score_v4_breakdown"]["display_calibration"]
    assert cal["applied"] is True
    assert cal["archetype"] == "probiotic"
    assert cal["raw_score_100"] == 85.0
    assert cal["display_score_100"] == out["shadow_score_v4_display_100"]
    assert "version" in cal and "reason" in cal


def test_calibrate_gated_product_display_equals_raw() -> None:
    from scoring_v4.display_calibration import calibrate_display
    # CAUTION product (e.g. stimulant) — never lifted
    out = calibrate_display(_shadow(88.0, verdict="CAUTION",
                                    safety_signals=["STIMULANT_CAFFEINE_HIGH_DOSE"]))
    assert out["shadow_score_v4_display_100"] == 88.0
    assert out["shadow_score_v4_breakdown"]["display_calibration"]["applied"] is False


def test_calibrate_below_80_display_equals_raw() -> None:
    from scoring_v4.display_calibration import calibrate_display
    out = calibrate_display(_shadow(72.0))
    assert out["shadow_score_v4_display_100"] == 72.0


def test_calibrate_null_score_is_noop() -> None:
    from scoring_v4.display_calibration import calibrate_display
    sh = {"shadow_score_v4_100": None, "shadow_score_v4_verdict": "BLOCKED",
          "shadow_score_v4_module": "generic", "shadow_score_v4_breakdown": {}}
    out = calibrate_display(sh)
    assert out["shadow_score_v4_display_100"] is None
