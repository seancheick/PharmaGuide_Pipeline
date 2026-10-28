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


# V4.1 Step 4 (2026-10-15) re-pinned the internal raw_score_v4_100 values below
# without any module, verdict, confidence or readiness change: formula checks
# own additive/sugar findings; count, disclosure, focus and route-base credits
# are retired; unbenchmarked amounts take the shared 11.4-public neutral; and
# probiotic Formulation/Dose are canonical form quality and measured adequacy.
# The raw module score still divides by unchanged module caps (fiber 30), so a
# route whose retired components were large (12932 fiber gummies) moves most.
# Probiotic form quality is the strains' own (241707, 206362: a rated
# co-ingredient no longer supplies it).
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
    # Reviewed identity resolution makes the current label assessable; its
    # separate substance warning must remain CAUTION rather than become SAFE.
    "241706": {
        "label": "HUM Ripped Rooster", "module": "generic", "verdict": "CAUTION",
        "confidence": "moderate", "score_unavailable_reason": None, "score": 45.2,
        "safety_verdict": "CAUTION", "completeness_ready": True,
        # Two independent repairs: retain the explicitly printed50%-EGCG form,
        # and read Contains No: as a negative list. Existing enriched corpus is
        # stale for both; run its original NIH fixture through the real owners.
        "raw_fixture": "safety_only_row_241706_raw.json", "source_allergen_form_checks": True,
    },
    # The dedicated digestive route remains correct. Both the activity rows and
    # proprietary-blend anchor are module-owned product projections.
    "241684": {
        "label": "HUM Flatter Me",
        "module": "fiber_digestive",
        "verdict": "SAFE",
        "confidence": "low",
        "score_unavailable_reason": None,
        # Already 40.0 on the stored corpus at 5fb2be1ca (stale pin, not V4.1).
        "score": 40.0,
        "unevaluated_canonicals": set(),
    },
    # No total CFU and no demonstrated dose applicability: dose remains zero.
    # Contextual strain evidence alone does not force a SAFE score band.
    "241707": {
        "label": "HUM Skin Squad Pre + Probiotic",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "low",
        # Dose V4.1: hidden per-strain amounts take the neutral (Dose 0 -> 8.55).
        "score_range": (40.6, 40.6),
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
        "confidence": "low",
        # Schema 2.4's canonical EPA/DHA projection proves the parent fish-oil
        # row is not an undisclosed active, restoring the 1-point disclosure
        # component without changing any omega pillar.
        "score_range": (13.6, 13.6),
    },
    # Typed confidence moderate: strong evidence/label/verification, but
    # taxonomy-first identity confidence correctly surfaces that this is a
    # mixed targeted creatine/HMB sports product rather than a clean class hit.
    "325587": {
        "label": "Transparent Labs Creatine HMB",
        "module": "sports",
        "verdict": "SAFE",
        "confidence": "moderate",
        # Printed creatine5g and HMB1.5g: current shared contribution targets
        # award20 and10 raw Dose points; their co-primary average is15.
        # Evidence 14 raw (1.31.0): creatine left the retired ingredient
        # allowlist; no automatic floor exceeds the strong base.
        "score_range": (69.2, 69.2),
        "raw_fixture": "evidence_readiness_325587_raw.json",
        "dose_raw": 15.0,
    },
    # Assessment coverage is separate from quality. This disclosed fiber total
    # remains module-owned; completed limited/negative evidence stays explicit.
    "12932": {
        "label": "vitafusion Fiber Gummies",
        "module": "fiber_digestive",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_unavailable_reason": None,
        "score": 35.5,
        "raw_fixture": "evidence_readiness_12932_raw.json",
        "evidence_raw": 0.0,
        "evidence_driver": "evidence_review_complete_limited_or_negative",
        "unevaluated_canonicals": set(),
    },
    # The chlorophyll blend anchor reconciles and maps as a module-owned product
    # projection; the structural blend header is not a second label active.
    "2266": {
        "label": "Triple Chlorophyll (GNC)",
        "module": "generic",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_unavailable_reason": None,
        "score": 34.7,
        "no_primary_evidence_floor": True,
        "evidence_driver": "evidence_review_complete_limited_or_negative",
        "unevaluated_canonicals": set(),
    },
    # Real-catalog guard for the four-micronutrient taxonomy false positive: the
    # targeted hair formula remains generic. Reviewed PABA/Fo-Ti literature
    # has no established applicability; zinc lozenge evidence cannot transfer to gummies.
    "241692": {
        "label": "HUM Hair Sweet Hair Berry",
        "module": "generic",
        "verdict": "SAFE",
        "confidence": "moderate",
        "score_unavailable_reason": None,
        # Already 55.0 on the stored corpus at 5fb2be1ca (stale pin, not V4.1).
        "score": 55.0,
        "limited_canonicals": {"paba", "fo_ti"},
    },
    # Typed confidence high on the probiotic module.
    "230149": {
        "label": "OLLY Extra Strength Probiotic",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "high",
        # Freeze the actual label instead of a changing stored enriched batch.
        # Its native strain assessment and hidden-amount Dose remain separate.
        # 49b61f37d (2026-10-23, exact claimed purpose for native treatment
        # research credit): applicability 6 -> 3 (broad alignment), so
        # Evidence 16 -> 13 and 68.5 -> 65.5. This slow-profile pin was stale
        # since that commit (bisected 2026-10-28; passes at 35c306e85).
        "score_range": (65.5, 65.5),
        "raw_fixture": "evidence_readiness_230149_raw.json",
        "dose_raw": 8.55,
        "evidence_raw": 13.0,
        "no_independent_delivery": True,
    },
    # Fully ready verdict-diversity anchors. These replace products that are now
    # correctly quarantined for material evidence that has not been reviewed.
    "240870": {
        "label": "Nature Made Extra Strength D3 5000 IU",
        "module": "generic",
        "verdict": "CAUTION",
        "confidence": "moderate",
        # Dose V4.1: raw Dose is adequacy only (11 -> 22) and the public
        # Dose ceiling caps it once (public Dose 10 unchanged).
        # 1.31.0: the vitamin D ingredient allowlist is retired, so Evidence
        # takes the strong floor (18 -> 14 raw): 78.3 -> 74.3.
        "score_range": (74.3, 74.3),
        "safety_verdict": "CAUTION",
    },
    "206362": {
        "label": "GNC Kids Probiotic Fast Stix",
        "module": "probiotic",
        "verdict": "SAFE",
        "confidence": "moderate",
        # V4.1 (Oct 15, 2026): its strain research does not apply to this
        # product, so the former 10 certainty points are gated to 0.
        # Dose V4.1: hidden per-strain amounts take the neutral (0 -> 8.55).
        "score_range": (37.6, 37.6),
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

    if expected.get("raw_fixture"):
        from enhanced_normalizer import EnhancedDSLDNormalizer
        from enrich_supplements_v3 import SupplementEnricherV3

        raw = json.loads((Path(__file__).parent / "fixtures" / expected["raw_fixture"]).read_text())
        product, _ = SupplementEnricherV3().enrich_product(
            EnhancedDSLDNormalizer().normalize_product(raw)
        )
    else:
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
    for pillar in ("dose", "evidence"):
        if pillar + "_raw" in expected:
            assert breakdown["module"]["dimensions"][pillar]["score"] == expected[pillar + "_raw"]
    if expected.get("source_allergen_form_checks"):
        assert product["allergen_hits"] == []
        assert breakdown["module"]["dimensions"]["transparency"]["penalties"]["B2_false_allergen_free_claim"] == 0.0
        assert "B0_HIGH_RISK_SUBSTANCE" in breakdown["safety_gate"]["safety_signals"]
        tea = next(row for row in product["ingredient_quality_data"]["ingredients"]
                   if row.get("canonical_id") == "green_tea_extract")
        assert tea["matched_form"] == "green tea extract (50% EGCG)"
        assert tea["bio_score"] == 9.0
    if expected.get("no_independent_delivery"):
        assert breakdown["module"]["dimensions"]["formulation"]["components"]["A3_delivery_system"] == 0.0
    if expected.get("no_primary_evidence_floor"):
        evidence_dimension = breakdown["module"]["dimensions"]["evidence"]
        assert evidence_dimension["score"] == 0.0
        assert evidence_dimension["metadata"]["primary_evidence_floor"] == 0.0
        assert "chlorophyll_complex" not in evidence_dimension["metadata"]["evidence_owner_canonicals"]
    if expected.get("completeness_ready"):
        assert breakdown["completeness_gate"]["is_live_eligible"] is True
        assert breakdown["completeness_gate"]["missing_fields"] == []
        assert breakdown["completeness_gate"]["mapped_coverage"] == 1.0
        assert "module" in breakdown
    if "evidence_driver" in expected:
        assert expected["evidence_driver"] in breakdown["confidence"]["evidence"]["drivers"]
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
    if "limited_canonicals" in expected:
        evidence = breakdown["assessment_readiness"]["evidence"]
        observed = {
            row.get("canonical_id") for row in evidence["ingredient_assessments"]
            if row.get("material") is True
            and row.get("state") == "evaluated_limited_or_negative"
            and row.get("reason_code") == "literature_applicability_unestablished"
            and row.get("evidence_ids") == []
        }
        assert expected["limited_canonicals"].issubset(observed)
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

    assert {"BLOCKED", "CAUTION", "SAFE"}.issubset(verdicts)
    assert "POOR" not in verdicts
    assert {None, "high", "moderate", "low"}.issubset(confidences)
