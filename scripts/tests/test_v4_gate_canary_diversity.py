"""Real-catalog canaries for v4 shared gates and verdict precedence.

Module-level canaries catch dimension math regressions. These canaries
exercise the shared path every product goes through:

router -> safety gate -> completeness gate -> module dispatch -> confidence.

The chosen rows are real enriched catalog products discovered by a
2026-05-20 full-catalog v4 sweep. They intentionally cover verdict
precedence and confidence bands rather than exact per-dimension math.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


V4_CANARIES = {
    # Safety short-circuit: no module block, confidence uses gate string.
    "246324": {
        "label": "vitafusion CBD Mixed Berry",
        "module": "generic",
        "verdict": "BLOCKED",
        "confidence": "blocked_by_safety_gate",
        "score": None,
        "safety_short_circuit": True,
    },
    # CAUTION carries forward and wins over SAFE/POOR score band.
    "241706": {
        "label": "HUM Ripped Rooster",
        "module": "generic",
        "verdict": "CAUTION",
        "confidence": "moderate",
        # Phase 4 (trust→verification bonus): 58 → 56.3.
        # Phase 6 (botanical profile): green tea (primary botanical, 100 mg, and
        # absent from rda_therapeutic_dosing.json so dose band is
        # disclosed_no_reference) now scores on its real botanical formulation
        # + clinical dose instead of an inflated vitamin proxy → 49.9. The
        # canary's point is unchanged: CAUTION carries forward and wins over the
        # SAFE/POOR score band regardless of where the band lands.
        # Phase 8 (primary-ingredient evidence floor): green tea (mass-primary) has
        # a strong study but positive_weak effect -> floor 14*0.85=11.9 -> 52.5.
        # Verdict stays CAUTION (the canary's invariant: CAUTION wins over band).
        "score_range": (41.9, 43.3),
        "safety_verdict": "CAUTION",
    },
    # Conservative blend evidence is audit-visible, but does not force a
    # CAUTION ceiling. Phase 9 makes production score equal raw.
    "241684": {
        "label": "HUM Flatter Me",
        "module": "generic",
        # Re-baseline 2026-06-08: real clinical-evidence-pipeline credit for
        # bromelain + digestive proteases (content-verified as genuinely earned,
        # NOT the essential-nutrient floor) lifted raw ~36 -> 46.1, crossing the
        # 40 SAFE cutoff. SAFE = no safety concern; the weak quality is conveyed
        # by the score (46 = Weak six-pillar tier), not the verdict. Blend
        # visibility still does NOT force CAUTION (transparency dim = 0, correctly
        # penalized). Mirrors the 241707 re-baseline precedent.
        "verdict": "SAFE",
        "confidence": "low",
        "score_range": (45.4, 46.8),
    },
    # Probiotic with named strains but no total CFU: scoreable with low
    # confidence; dose/transparency dimensions keep it weak without a forced
    # CAUTION ceiling.
    "241707": {
        "label": "HUM Skin Squad Pre + Probiotic",
        "module": "probiotic",
        # re-baseline 2026-06-06: native clinical-strain credit lifted score
        # 30.7 -> 47.2, crossing the 40 SAFE cutoff. SAFE = no safety concern
        # (low quality is conveyed by the score, not the verdict).
        "verdict": "SAFE",
        "confidence": "low",
        "score_range": (46.5, 47.9),
    },
    # Fish-oil parent mass with no EPA/DHA breakdown: scoreable as aggregate
    # evidence with moderate uncertainty, no score cap, and no CAUTION ceiling.
    # Re-baseline 2026-06-09: stricter cert brand matching rejected a stale
    # cross-brand NSF registry false positive (CVS Health product matched to
    # LTH GLOW Omega-3), removing unearned verification credit.
    "239467": {
        "label": "CVS Health Fish Oil 1000 mg",
        "module": "omega",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_range": (58.3, 59.7),
    },
    # Typed confidence moderate: strong evidence/label/verification, but
    # taxonomy-first identity confidence correctly surfaces that this is a
    # mixed targeted creatine/HMB sports product rather than a clean class hit.
    "325587": {
        "label": "Transparent Labs Creatine HMB",
        "module": "sports",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_range": (82.3, 83.7),  # Phase 4: 88 → 84.6; cert→GMP: +2.2 (Informed Choice sku implies GMP)
    },
    # Boundary case: a well-labeled fiber gummy with no clinical evidence.
    # Re-baseline 2026-06-08: dose + transparency credit lifted raw ~31 -> 40.0,
    # landing exactly on the POOR/SAFE cutoff (POOR if raw < 40 else SAFE → SAFE).
    # SAFE = not dangerous; weak quality is the score (40 = Poor six-pillar tier).
    # Intentional sensitive tripwire at the 40-line: if a change pushes it back
    # under 40 the verdict assertion flags it. The robust POOR diversity anchor is
    # held by 2266 below, not this knife-edge product.
    "12932": {
        "label": "vitafusion Fiber Gummies",
        "module": "generic",
        # Re-baseline 2026-06-15: commit 2d6b841a rebalanced the V4 dietary-sugar
        # penalty bands (gummies take B1_dietary_sugar -2.0), dropping raw 40.0 -> 38.0,
        # crossing the 40-line into POOR. Legit corpus-wide scoring fix, not a regression.
        "verdict": "POOR",
        "confidence": "low",
        "score_range": (37.4, 38.6),
    },
    # Stable POOR diversity anchor (added 2026-06-08 when 241684 + 12932 both
    # legitimately crossed the 40 line into SAFE). Single-ingredient chlorophyll
    # commodity: no clinical evidence, minimal formulation → raw 26.4, ~14 pts
    # below the cutoff so it will not drift across it. Clean SAFE gate (not
    # dangerous); POOR comes purely from the score band. Also a documented weak/
    # junk control in the display-calibration tests. Re-baseline 2026-06-09:
    # product-label USP claim gets the intentional small provisional +2 trust
    # credit, while still staying POOR.
    "2266": {
        "label": "Triple Chlorophyll (GNC)",
        "module": "generic",
        "verdict": "POOR",
        "confidence": "low",
        # Re-baseline 2026-06-15: the product's USP strings are monograph refs
        # ("Conforms to USP"), not named cert programs -> B4a_verified_certifications=0,
        # so the prior provisional +2 USP trust credit does not apply; raw 26.4.
        "score_range": (25.7, 27.1),
    },
    # Typed confidence high on the probiotic module.
    "230149": {
        "label": "OLLY Extra Strength Probiotic",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "high",
        "score_range": (72.6, 74.0),  # Re-baseline 2026-06-15: 2d6b841a sugar/additive penalties -> raw 73.3
    },
}


_CACHE: dict[str, dict] | None = None


def _load_canaries() -> dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    found: dict[str, dict] = {}
    target_ids = set(V4_CANARIES)
    products_root = SCRIPTS_ROOT / "products"
    if not products_root.exists():
        _CACHE = {}
        pytest.skip("no enriched products directory in this checkout")

    for path in products_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.get("products") or data.get("items") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            dsld_id = str(row.get("dsld_id") or row.get("id") or "")
            if dsld_id in target_ids:
                found[dsld_id] = row
        if len(found) == len(target_ids):
            break

    _CACHE = found
    return found


@pytest.mark.parametrize("dsld_id,expected", list(V4_CANARIES.items()))
def test_v4_real_catalog_gate_and_confidence_canary(dsld_id: str, expected: dict) -> None:
    from score_supplements_v4 import score_product_v4

    product = _load_canaries().get(dsld_id)
    if product is None:
        pytest.skip(f"v4 canary {dsld_id} not found: {expected['label']}")
    if expected["verdict"] not in {"BLOCKED", "UNSAFE"}:
        from scoring_input_contract import get_scoring_ingredients
        scoring_input = get_scoring_ingredients(product, strict=True)
        if not scoring_input.rows and expected["verdict"] != "NOT_SCORED":
            pytest.skip(
                f"{expected['label']} enriched artifact lacks strict v4 scoring inputs; "
                "rerun enrichment before using as canary"
            )

    out = score_product_v4(product)
    assert out["v4_module"] == expected["module"]
    assert out["v4_verdict"] == expected["verdict"]
    assert out["v4_confidence"] == expected["confidence"]

    if "score" in expected:
        assert out["raw_score_v4_100"] == expected["score"]
    if "score_range" in expected:
        lo, hi = expected["score_range"]
        assert lo <= out["raw_score_v4_100"] <= hi

    breakdown = out["v4_breakdown"]
    if expected.get("safety_short_circuit"):
        assert breakdown["safety_gate"]["short_circuits_scoring"] is True
        assert "module" not in breakdown
    if "safety_verdict" in expected:
        assert breakdown["safety_gate"]["verdict"] == expected["safety_verdict"]
        assert breakdown["safety_gate"]["short_circuits_scoring"] is False
        assert "module" in breakdown
    if "missing" in expected:
        missing = set(breakdown["completeness_gate"]["missing_fields"])
        assert expected["missing"].issubset(missing)
        assert "module" not in breakdown


def test_v4_canaries_cover_gate_and_confidence_bands() -> None:
    verdicts = {c["verdict"] for c in V4_CANARIES.values()}
    confidences = {c["confidence"] for c in V4_CANARIES.values()}

    assert {"BLOCKED", "CAUTION", "POOR", "SAFE"}.issubset(verdicts)
    assert {
        "blocked_by_safety_gate",
        "high",
        "moderate",
        "low",
    }.issubset(confidences)
