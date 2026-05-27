"""v4 cross-module canary diversity for completed scoring modules.

Omega has its own P1.6 canary file. This file covers the completed
generic and probiotic modules against real enriched catalog rows so we
catch class-specific regressions that synthetic unit fixtures miss:

- generic mid / low score bands
- generic non-evaluable Dose rescaling
- generic high Trust and zero Trust cases
- sports high score band
- probiotic high / mid / low score bands
- probiotic per-strain CFU disclosed vs aggregate-CFU-only Dose=0
- probiotic Trust positive vs Trust zero
- prenatal probiotic routing stays probiotic, not multi_or_prenatal

Tests scan the enriched catalog once and cache the selected rows.
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


GENERIC_CANARIES = {
    # Recent cert override / high Trust path.
    "328825": {
        "label": "Thorne Curcumin Phytosome 1000 mg",
        "score_range": (65.0, 70.0),
        "traits": {"trust_high": True},
    },
    # Dose-not-evaluable low scorer; locks botanical/fiber rescaling path.
    "12932": {
        "label": "vitafusion Fiber Gummies",
        "score_range": (28.0, 34.0),
        "traits": {"dose_none": True, "trust_zero": True},
    },
    # False-positive guard from omega routing: liposomal delivery/lecithin
    # stays generic even though fatty-acid-like carrier signals exist.
    "184661": {
        "label": "Pure Encapsulations Liposomal Glutathione",
        "score_range": (54.0, 60.0),
        "traits": {"transparency_low": True},
    },
}


SPORTS_CANARIES = {
    # High sports scorer after the P1.7 sports module split.
    "325587": {
        "label": "Transparent Labs Creatine HMB",
        "score_range": (78.0, 80.5),
        "traits": {"trust_positive": True, "dose_max": True},
    },
}


PROBIOTIC_CANARIES = {
    # Highest real probiotic scorer from the catalog sweep.
    "306247": {
        "label": "Thorne FloraSport 20B",
        "score_range": (72.0, 77.0),
        "traits": {"trust_positive": True},
    },
    # Low end of current probiotic score distribution.
    "201158": {
        "label": "OLLY Kids Quick Melt Probiotic Sticks",
        "score_range": (42.0, 45.2),
        "traits": {"trust_positive": True},
    },
    # Aggregate-CFU-only canary: gets Formulation credit but Dose=0.
    "178346": {
        "label": "Spring Valley Advanced Strength Probiotic 50B",
        "score_range": (57.0, 61.0),
        "traits": {"form_max": True, "dose_zero": True, "trust_zero": True},
    },
    # Per-strain CFU disclosed path; Dose > 0 with no Trust credit.
    "286725": {
        "label": "vitafusion Probiotic 5B",
        "score_range": (64.0, 68.0),
        "traits": {"dose_positive": True, "trust_zero": True},
    },
    # Per-strain CFU + positive Trust path.
    "184730": {
        "label": "Pure Encapsulations Probiotic 123",
        "score_range": (56.0, 60.0),
        "traits": {"dose_positive": True, "trust_positive": True},
    },
    # Prenatal name must stay probiotic because supplement_type wins.
    "76803": {
        "label": "GNC Probiotic Solutions Prenatal 20B",
        "score_range": (47.0, 50.1),
        "traits": {"prenatal_name_routes_probiotic": True, "trust_positive": True},
    },
}


ALL_CANARY_IDS = set(GENERIC_CANARIES) | set(SPORTS_CANARIES) | set(PROBIOTIC_CANARIES)
_CANARY_CACHE: dict[str, dict] | None = None


def _load_canaries() -> dict[str, dict]:
    global _CANARY_CACHE
    if _CANARY_CACHE is not None:
        return _CANARY_CACHE

    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        _CANARY_CACHE = {}
        pytest.skip("no enriched products directory in this checkout")

    found: dict[str, dict] = {}
    for path in enriched_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("products") or data.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            dsld_id = str(item.get("dsld_id") or item.get("id") or "")
            if dsld_id in ALL_CANARY_IDS:
                found[dsld_id] = item
        if len(found) == len(ALL_CANARY_IDS):
            break

    _CANARY_CACHE = found
    return found


def _dimension_score(breakdown: dict, dimension: str):
    return breakdown["dimensions"][dimension]["score"]


def _require_strict_v4_contract(product: dict, label: str) -> None:
    from scoring_input_contract import get_scoring_ingredients

    scoring_input = get_scoring_ingredients(product, strict=True)
    if not scoring_input.rows:
        pytest.skip(
            f"{label} enriched artifact lacks strict v4 scoring inputs "
            f"({scoring_input.zero_scorable_reason}); rerun enrichment before using as canary"
        )


@pytest.mark.parametrize("dsld_id,expected", list(GENERIC_CANARIES.items()))
def test_generic_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.generic import score_generic
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"generic canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "generic"
    gate = evaluate_completeness_gate(product, "generic")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_generic(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    if traits.get("dose_none"):
        assert _dimension_score(breakdown, "dose") is None
    if traits.get("trust_zero"):
        assert _dimension_score(breakdown, "trust") == 0
    if traits.get("trust_positive"):
        assert _dimension_score(breakdown, "trust") > 0
    if traits.get("trust_high"):
        assert _dimension_score(breakdown, "trust") >= 10
    if traits.get("transparency_low"):
        assert _dimension_score(breakdown, "transparency") <= 2


@pytest.mark.parametrize("dsld_id,expected", list(SPORTS_CANARIES.items()))
def test_sports_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.sports import score_sports
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"sports canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "sports"
    gate = evaluate_completeness_gate(product, "sports")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_sports(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    if traits.get("dose_max"):
        assert _dimension_score(breakdown, "dose") == 20
    if traits.get("trust_positive"):
        assert _dimension_score(breakdown, "trust") > 0


@pytest.mark.parametrize("dsld_id,expected", list(PROBIOTIC_CANARIES.items()))
def test_probiotic_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.probiotic import score_probiotic
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"probiotic canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "probiotic"
    gate = evaluate_completeness_gate(product, "probiotic")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_probiotic(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    if traits.get("form_max"):
        assert _dimension_score(breakdown, "formulation") == 25
    if traits.get("dose_zero"):
        assert _dimension_score(breakdown, "dose") == 0
    if traits.get("dose_positive"):
        assert _dimension_score(breakdown, "dose") > 0
    if traits.get("trust_zero"):
        assert _dimension_score(breakdown, "trust") == 0
    if traits.get("trust_positive"):
        assert _dimension_score(breakdown, "trust") > 0


def test_cross_module_canary_count_floor() -> None:
    assert len(GENERIC_CANARIES) >= 3
    assert len(SPORTS_CANARIES) >= 1
    assert len(PROBIOTIC_CANARIES) >= 6


def test_cross_module_canaries_cover_expected_score_bands() -> None:
    generic_ranges = [v["score_range"] for v in GENERIC_CANARIES.values()]
    sports_ranges = [v["score_range"] for v in SPORTS_CANARIES.values()]
    probiotic_ranges = [v["score_range"] for v in PROBIOTIC_CANARIES.values()]

    assert any(hi <= 45 for _lo, hi in generic_ranges), "missing low generic canary"
    assert any(lo >= 70 for lo, _hi in sports_ranges), "missing high sports canary"
    assert any(hi <= 46 for _lo, hi in probiotic_ranges), "missing low probiotic canary"
    assert any(lo >= 70 for lo, _hi in probiotic_ranges), "missing high probiotic canary"
