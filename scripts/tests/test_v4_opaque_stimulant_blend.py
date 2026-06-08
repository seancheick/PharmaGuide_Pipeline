"""P0 safety fix: opaque stimulant/energy blends must drive CAUTION.

Step-10 cohort review (omega+sports reviewer) caught a safety FALSE-NEGATIVE:
caffeine/stimulants HIDDEN inside an opaque proprietary blend (disclosure=none)
escaped CAUTION because _apply_stimulant_policy early-returned when no caffeine
ACTIVE ROW was surfaced. ~30 SKUs (GNC Amino Energy, Alive! "Stimulant Blends",
Mega Men energy blends) read SAFE despite an undisclosed stimulant the user
cannot dose. Fix: an opaque blend that hides a stimulant → CAUTION + needs_review.

Trigger (opaque = disclosure_level in {none, partial}), with NO surfaced caffeine row:
  (a) blend NAME ∈ {stimulant, thermogenic, fat burner, pre-workout}, OR
  (b) "caffeine" present in the blend's child_ingredients, OR
  (c) energy/metabolism-named blend + another stimulant (guarana/green tea/...) in children.
Guard: a benign opaque "energy" blend with no stimulant (B-vitamins only) must NOT warn,
and disclosed-caffeine products keep using the existing dose path.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _gate(product):
    from scoring_v4.gate_safety import evaluate_safety_gate
    return evaluate_safety_gate(product)


def _blend(name, disclosure="none", children=()):
    return {"name": name, "disclosure_level": disclosure,
            "child_ingredients": [{"name": c, "amount": None, "unit": ""} for c in children]}


def test_opaque_stimulant_named_blend_drives_caution() -> None:
    # Alive! / GNC Amino Energy pattern: an opaque blend literally named "Stimulant Blends".
    p = {"dsld_id": "T", "fullName": "X", "proprietary_blends": [_blend("Stimulant Blends")]}
    r = _gate(p)
    assert r.verdict == "CAUTION", f"opaque Stimulant Blend should CAUTION, got {r.verdict}"
    assert "STIMULANT_UNDISCLOSED_BLEND" in r.safety_signals
    assert r.short_circuits_scoring is False  # CAUTION, not a hard block


def test_caffeine_hidden_in_opaque_blend_drives_caution() -> None:
    p = {"dsld_id": "T", "fullName": "X",
         "proprietary_blends": [_blend("Proprietary Blend", children=["Caffeine Anhydrous", "Taurine"])]}
    assert _gate(p).verdict == "CAUTION"


def test_opaque_energy_blend_with_green_tea_drives_caution() -> None:
    # Mega Men "Energy & Metabolism Blend" w/ green tea pattern.
    p = {"dsld_id": "T", "fullName": "X",
         "proprietary_blends": [_blend("Advanced Energy Blend", children=["Green Tea Extract", "Asian Ginseng"])]}
    assert _gate(p).verdict == "CAUTION"


def test_benign_opaque_energy_blend_does_not_over_warn() -> None:
    # An opaque "Energy & Metabolism Blend" with only B-vitamins is NOT a stimulant
    # concern — must NOT falsely CAUTION (avoid over-warning the ~31 benign cases).
    p = {"dsld_id": "T", "fullName": "X",
         "proprietary_blends": [_blend("Energy & Metabolism Blend", children=["Vitamin B12", "Folate", "Biotin"])]}
    assert _gate(p).verdict != "CAUTION"


def test_disclosed_blend_does_not_trigger_blend_path() -> None:
    # A FULLY disclosed blend (doses shown) is not opaque → the hidden-stimulant rule
    # must not fire (the user can judge the dose).
    p = {"dsld_id": "T", "fullName": "X",
         "proprietary_blends": [_blend("Stimulant Blend", disclosure="full", children=["Caffeine"])]}
    assert _gate(p).verdict != "CAUTION"


def test_no_blend_no_false_caution() -> None:
    # A plain product with no proprietary blends and no caffeine must stay non-CAUTION.
    p = {"dsld_id": "T", "fullName": "Vitamin C 500mg",
         "activeIngredients": [{"name": "Vitamin C", "quantity": [{"quantity": 500, "unit": "mg"}]}]}
    assert _gate(p).verdict != "CAUTION"


def test_real_gnc_amino_energy_caution() -> None:
    """Real corpus product 66957 (GNC Amino Energy Advanced) has an opaque
    'Stimulant Blends' — must read CAUTION, not SAFE."""
    import json, glob
    for path in glob.glob(str(SCRIPTS_ROOT / "products" / "output_*_enriched" / "enriched" / "*.json")):
        try:
            data = json.loads(Path(path).read_text())
        except Exception:
            continue
        for p in (data if isinstance(data, list) else []):
            if isinstance(p, dict) and str(p.get("dsld_id")) == "66957":
                assert _gate(p).verdict == "CAUTION"
                return
    import pytest
    pytest.skip("66957 not in local corpus")
