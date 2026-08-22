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
    # Safety short-circuit: no module block; gate state is not confidence.
    "246324": {
        "label": "vitafusion CBD Mixed Berry",
        "module": "generic",
        "verdict": "BLOCKED",
        "confidence": None,
        "score_unavailable_reason": "blocked_by_safety_gate",
        "score": None,
        "safety_short_circuit": True,
    },
    # The safety decision remains audit-visible while scoring continues.
    # 7-keto-DHEA reaches scoring through a product-level dose projection, so
    # it is owned by the module rather than counted as a second label-active
    # evidence question.
    "241706": {
        "label": "HUM Ripped Rooster",
        "module": "generic",
        "verdict": "CAUTION",
        "confidence": "moderate",
        "score_unavailable_reason": None,
        "score": 43.1,
        "unevaluated_canonicals": set(),
        "safety_verdict": "CAUTION",
    },
    # The dedicated digestive route remains correct. Both the activity rows and
    # proprietary-blend anchor are module-owned product projections.
    "241684": {
        "label": "HUM Flatter Me",
        "module": "fiber_digestive",
        "verdict": "POOR",
        "confidence": "low",
        "score_unavailable_reason": None,
        "score": 36.2,
        "unevaluated_canonicals": set(),
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
        # 2026-07-19: current raw is 47.2 (matches the documented value above);
        # the old hi=47.1 was an off-by-0.1 window set below the real score.
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
        # Schema 2.4's canonical EPA/DHA projection proves the parent fish-oil
        # row is not an undisclosed active, restoring the 1-point disclosure
        # component without changing any omega pillar.
        "score_range": (59.3, 60.7),
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
    # A disclosed fiber dose is not a substitute for a reviewed fiber-evidence
    # assessment; the route and dose remain testable on the QA record.
    # `fiber` names the product-level total, which the fiber module assesses,
    # so this product has no individual evidence question left open.
    "12932": {
        "label": "vitafusion Fiber Gummies",
        "module": "fiber_digestive",
        "verdict": "SAFE",
        "confidence": "low",
        "score_unavailable_reason": None,
        "score": 50.0,
        "unevaluated_canonicals": set(),
    },
    # The chlorophyll blend anchor reconciles and maps as a module-owned product
    # projection; the structural blend header is not a second label active.
    "2266": {
        "label": "Triple Chlorophyll (GNC)",
        "module": "generic",
        "verdict": "SAFE",
        "confidence": "low",
        "score_unavailable_reason": None,
        "score": 48.2,
        "unevaluated_canonicals": set(),
    },
    # Real-catalog guard for the four-micronutrient taxonomy false positive: the
    # targeted hair formula remains generic, while PABA and Fo-Ti evidence debt
    # keeps it out of the live catalog.
    "241692": {
        "label": "HUM Hair Sweet Hair Berry",
        "module": "generic",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_unavailable_reason": None,
        "score": 65.5,
        "unevaluated_canonicals": {"paba", "fo_ti"},
    },
    # Typed confidence high on the probiotic module.
    "230149": {
        "label": "OLLY Extra Strength Probiotic",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "high",
        "score_range": (72.6, 74.0),  # Re-baseline 2026-06-15: 2d6b841a sugar/additive penalties -> raw 73.3
    },
    # Fully ready verdict-diversity anchors. These replace products that are now
    # correctly quarantined for material evidence that has not been reviewed.
    "240870": {
        "label": "Nature Made Extra Strength D3 5000 IU",
        "module": "generic",
        "verdict": "CAUTION",
        "confidence": "moderate",
        "score_range": (75.8, 77.2),
        "safety_verdict": "CAUTION",
    },
    "206362": {
        "label": "GNC Kids Probiotic Fast Stix",
        "module": "probiotic",
        "verdict": "POOR",
        "confidence": "moderate",
        "score_range": (39.1, 40.0),
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
    assert out["quality_score_confidence"] == expected["confidence"]
    assert out["score_unavailable_reason"] == expected.get(
        "score_unavailable_reason"
    )

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
        if "missing" not in expected:
            assert "module" in breakdown
    if "missing" in expected:
        missing = set(breakdown["completeness_gate"]["missing_fields"])
        assert expected["missing"].issubset(missing)
        assert "module" not in breakdown
    if "unevaluated_canonicals" in expected:
        evidence = breakdown["assessment_readiness"]["evidence"]
        observed = {
            row.get("canonical_id")
            for row in evidence["ingredient_assessments"]
            if row.get("material") is True
            and row.get("state") == "not_yet_evaluated"
            and row.get("reason_code") == "no_reviewed_evidence_assessment"
        }
        assert expected["unevaluated_canonicals"].issubset(observed)


def test_v4_canaries_cover_gate_and_confidence_bands() -> None:
    verdicts = {c["verdict"] for c in V4_CANARIES.values()}
    confidences = {c["confidence"] for c in V4_CANARIES.values()}

    assert {"BLOCKED", "CAUTION", "POOR", "SAFE"}.issubset(verdicts)
    assert {None, "high", "moderate", "low"}.issubset(confidences)
