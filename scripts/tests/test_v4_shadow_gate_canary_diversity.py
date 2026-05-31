"""Real-catalog canaries for v4 shared gates and shadow precedence.

Module-level canaries catch dimension math regressions. These canaries
exercise the shared path every product goes through:

router -> safety gate -> completeness gate -> module dispatch -> confidence.

The chosen rows are real enriched catalog products discovered by a
2026-05-20 full-catalog shadow sweep. They intentionally cover verdict
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


SHADOW_CANARIES = {
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
        "score_range": (55.5, 57.5),  # Phase 4 (trust→verification bonus): 58 → 56.3
        "safety_verdict": "CAUTION",
    },
    # Conservative blend evidence is audit-visible, but does not force a
    # CAUTION ceiling. Phase 4+5 lowered raw below the raw-40 floor (calibrated
    # 52.1, raw 36.1) -> POOR via the raw floor, not CAUTION. Expected interim;
    # Phase 9 recalibrates the raw scale/floor.
    "241684": {
        "label": "HUM Flatter Me",
        "module": "generic",
        "verdict": "POOR",
        "confidence": "low",
        "score_range": (51.1, 53.1),
    },
    # Probiotic with named strains but no total CFU: scoreable, but cannot be
    # SAFE because the primary probiotic dose is undisclosed.
    "241707": {
        "label": "HUM Skin Squad Pre + Probiotic",
        "module": "probiotic",
        "verdict": "CAUTION",
        "confidence": "moderate",
        "score_range": (47.6, 49.6),  # Phase 4: 55 → 53.1
    },
    # Fish-oil parent mass with no EPA/DHA breakdown: scoreable as low-
    # confidence aggregate evidence with a score cap, but not an automatic
    # CAUTION ceiling.
    "239467": {
        "label": "CVS Health Fish Oil 1000 mg",
        "module": "omega",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_range": (58.9, 60.9),
    },
    # Typed confidence moderate: strong evidence/label/verification, but
    # taxonomy-first identity confidence correctly surfaces that this is a
    # mixed targeted creatine/HMB sports product rather than a clean class hit.
    "325587": {
        "label": "Transparent Labs Creatine HMB",
        "module": "sports",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_range": (79.1, 81.1),  # Phase 4: 88 → 84.6
    },
    # Typed confidence low + POOR verdict.
    "12932": {
        "label": "vitafusion Fiber Gummies",
        "module": "generic",
        "verdict": "POOR",
        "confidence": "low",
        "score_range": (44.2, 46.2),
    },
    # Typed confidence high on the probiotic module.
    "230149": {
        "label": "OLLY Extra Strength Probiotic",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "high",
        "score_range": (71.6, 73.6),  # Phase 4: 80.5 → 77.1
    },
}


_CACHE: dict[str, dict] | None = None


def _load_canaries() -> dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    found: dict[str, dict] = {}
    target_ids = set(SHADOW_CANARIES)
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


@pytest.mark.parametrize("dsld_id,expected", list(SHADOW_CANARIES.items()))
def test_shadow_real_catalog_gate_and_confidence_canary(dsld_id: str, expected: dict) -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _load_canaries().get(dsld_id)
    if product is None:
        pytest.skip(f"shadow canary {dsld_id} not found: {expected['label']}")
    if expected["verdict"] not in {"BLOCKED", "UNSAFE"}:
        from scoring_input_contract import get_scoring_ingredients
        scoring_input = get_scoring_ingredients(product, strict=True)
        if not scoring_input.rows and expected["verdict"] != "NOT_SCORED":
            pytest.skip(
                f"{expected['label']} enriched artifact lacks strict v4 scoring inputs; "
                "rerun enrichment before using as canary"
            )

    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_module"] == expected["module"]
    assert out["shadow_score_v4_verdict"] == expected["verdict"]
    assert out["shadow_score_v4_confidence"] == expected["confidence"]

    if "score" in expected:
        assert out["shadow_score_v4_100"] == expected["score"]
    if "score_range" in expected:
        lo, hi = expected["score_range"]
        assert lo <= out["shadow_score_v4_100"] <= hi

    breakdown = out["shadow_score_v4_breakdown"]
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


def test_shadow_canaries_cover_gate_and_confidence_bands() -> None:
    verdicts = {c["verdict"] for c in SHADOW_CANARIES.values()}
    confidences = {c["confidence"] for c in SHADOW_CANARIES.values()}

    assert {"BLOCKED", "CAUTION", "POOR", "SAFE"}.issubset(verdicts)
    assert {
        "blocked_by_safety_gate",
        "high",
        "moderate",
        "low",
    }.issubset(confidences)
