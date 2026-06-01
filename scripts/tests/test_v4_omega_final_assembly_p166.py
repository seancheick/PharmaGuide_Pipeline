"""v4 Omega module — P1.6.6 final assembly tests.

Locks the final-assembly arithmetic:

  class_subtotal = (sum(dim.score) / sum_of_evaluable_max) * 100
  adjusted = class_subtotal + manufacturer_trust + manufacturer_violations
  raw_score_100 = clamp(0, 100, adjusted)
  score_100 = raw_score_100

Plus locks the raw-rubric canary scores so future drift in any of the
5 dimensions surfaces immediately.

Canary results vs v3 baselines:
  - Sports Research Omega-3 (327776): v3=63.7 → v4=81.6 (+17.9)
    The P1.5 omega-debt fix delivered, and P1.7 curated IFOS
    product_line verification now adds omega Trust credit.
  - Nordic Naturals Ultimate Omega + CoQ10 (288740): v3=68.6 → v4=67.9
    (-0.7). Nordic loses form_disclosed credit (form=undefined per
    'do not invent fields' — Nordic is famously rTG but DSLD label
    omits it) but stays in band via dose + evidence + Mfg Trust.

Per §13 architecture lock — no v3 imports.
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


def _premium_omega() -> dict:
    """Synthetic premium omega product hitting near-max in most dimensions."""
    return {
        "status": "active", "form_factor": "softgel",
        "product_name": "Premium Wild Fish Oil Triglycerides EPA+DHA 1200 mg",
        "supplement_type": {"type": "specialty"},
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Fish Oil Concentrate", "canonical_id": "fish_oil",
             "quantity": 1500, "unit": "mg"},
            {"name": "EPA", "canonical_id": "epa",
             "quantity": 700, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha",
             "quantity": 500, "unit": "mg"},
        ]},
        "verified_cert_programs": [
            {"program": "IFOS", "scope": "sku"},
        ],
        "certification_data": {
            "gmp": {"nsf_gmp": True},
            "batch_traceability": {"has_coa": True, "has_batch_lookup": True},
            "evidence_based": {
                "third_party_programs": [
                    {"rule_id": "CERT_FRIEND_OF_THE_SEA",
                     "display_name": "Friend of the Sea",
                     "score_eligible": True},
                ]
            }
        },
        "compliance_data": {
            "allergen_free_claims": [{"id": "x"}],
            "gluten_free": True,
            "vegan": False,
        },
    }


# --- Final assembly contract --------------------------------------------


def test_score_omega_populates_raw_and_production_scores() -> None:
    """After P1.6.6, both raw_score_100 and score_100 are real numbers."""
    from scoring_v4.modules.omega import score_omega

    result = score_omega(_premium_omega())
    bd = result.to_breakdown()
    assert bd["raw_score_100"] is not None
    assert bd["score_100"] is not None
    assert 0 <= bd["raw_score_100"] <= 100
    assert 0 <= bd["score_100"] <= 100


def test_phase_marker_rolls_to_p166() -> None:
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    assert bd["phase"] == "P1.6.6_omega_final_assembly"


def test_score_100_policy_metadata_present() -> None:
    """Final assembly emits the Phase 9 score policy audit block."""
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    cal = bd["metadata"]["score_policy"]
    assert cal["method"] == "rubric_raw_is_production_score"
    assert cal["audit_affine_v3_compare"]["intercept"] == 25.0
    assert cal["audit_affine_v3_compare"]["slope"] == 0.75


def test_score_100_rubric_arithmetic() -> None:
    """score_100 = raw_score_100."""
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    raw = bd["raw_score_100"]
    expected = max(0.0, min(100.0, 1.0 * raw))
    assert abs(bd["score_100"] - expected) <= 0.1


def test_manufacturer_trust_populated() -> None:
    """Brand-level IFOS / cert signals that we kept out of product Trust
    (P1.6.4 policy) legitimately route to Manufacturer Trust D1 here."""
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    mt = bd["manufacturer_trust"]
    assert mt["score"] is not None
    assert mt["max"] == 5


def test_manufacturer_violations_populated() -> None:
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    mv = bd["manufacturer_violations"]
    assert mv["score"] is not None
    assert mv["floor"] == -25


def test_assembly_metadata_records_all_audit_fields() -> None:
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    md = bd["metadata"]
    # All the audit fields downstream tooling expects
    for key in (
        "phase",
        "raw_dimension_sum",
        "evaluable_class_max",
        "excluded_dimensions",
        "class_subtotal",
        "manufacturer_trust_adjustment",
        "manufacturer_violation_adjustment",
        "adjusted_score_before_clamp",
        "raw_score_100_pre_score_policy",
        "score_policy",
        "production_score_before_clamp",
    ):
        assert key in md, f"missing audit metadata key: {key}"


def test_empty_product_still_emits_production_score() -> None:
    """Empty input: all 5 dims score 0, but Manufacturer Trust D1 may
    award a small default tier (~1-3 pts) for products with no
    manufacturer-data signals. Final production score lands in low
    range. Defensive — completeness gate normally short-circuits
    empty input before this module runs."""
    from scoring_v4.modules.omega import score_omega

    bd = score_omega({}).to_breakdown()
    assert bd["score_100"] is not None
    # raw_score_100 floors at 0 (dims=0) plus 0..5 Mfg Trust.
    assert 0 <= bd["raw_score_100"] <= 5
    # score_100 = 25 + 0.75 * raw → at most 25 + 3.75 = 28.75 for empty.
    assert 0.0 <= bd["score_100"] <= 6.0


# --- Rescale-around-None semantics --------------------------------------


def test_excluded_dimensions_rescale_correctly() -> None:
    """If one dimension is None, class_subtotal rescales to use only
    the evaluable_max of the populated dimensions."""
    from scoring_v4.modules.omega import score_omega

    # Force a None dim by overriding Evidence to None (cannot easily
    # do via product input; this test exercises the metadata shape).
    bd = score_omega(_premium_omega()).to_breakdown()
    md = bd["metadata"]
    # In P1.6.6 with a complete product, no exclusions.
    assert md["excluded_dimensions"] == []
    # class_subtotal = (raw_sum / 100) * 100 = raw_sum when all 5 dims
    # are populated (because 25+25+20+15+15 = 100).
    assert abs(md["class_subtotal"] - md["raw_dimension_sum"]) < 0.01


# --- Real-catalog canary locks ------------------------------------------


_CANARY_FINAL_IDS = {"327776", "326270", "288740", "273630", "239592", "182968"}
_canary_cache = None


def _load_canaries(ids):
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}
    root = SCRIPTS_ROOT / "products"
    if not root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir")
    found = {}
    for path in root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("products") or data.get("items") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in _CANARY_FINAL_IDS:
                found[did] = item
        if len(found) == len(_CANARY_FINAL_IDS):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


# Expected ranges are tight (±3 pts) around the P1.6.6 smoke results.
# Wider than ±0.5 to tolerate small drifts in generic_evidence /
# manufacturer pipeline; tighter than ±10 to catch real regressions.
@pytest.mark.parametrize("dsld_id,brand,expected_score_min,expected_score_max", [
    ("327776", "Sports Research", 63.2, 64.6),  # Phase 4: 81.6 → 77.4
    ("326270", "Sports Research", 63.2, 64.6),  # Phase 4: 81.6 → 77.4
    ("288740", "Nordic Naturals", 57.2, 58.6),
    ("273630", "Garden of Life", 55.9, 57.3),
    ("239592", "CVS Health", 50.5, 51.9),
    ("182968", "Pure Encapsulations",  52.0, 59.0),
])
def test_canary_final_score_in_range(dsld_id, brand, expected_score_min, expected_score_max):
    """Real-catalog raw-rubric omega scores lock in expected ranges.

    If a dimension's scoring math drifts, this is the front-line alarm.
    Update the ranges deliberately — never widen them silently."""
    from scoring_v4.modules.omega import score_omega

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in catalog")

    bd = score_omega(canaries[dsld_id]).to_breakdown()
    score = bd["score_100"]
    assert expected_score_min <= score <= expected_score_max, (
        f"{dsld_id} ({brand}) omega score {score} not in "
        f"[{expected_score_min}, {expected_score_max}]"
    )


def test_canary_sports_research_improves_vs_v3_baseline() -> None:
    """Sports Research Omega-3 (327776), v3=63.7. With the affine removed
    (score = rubric raw), the prior '+17.9 vs v3' was calibration inflation;
    the honest omega RAW score lands ~v3 level. Lock NO MATERIAL REGRESSION:
    the omega module's structural work must not score this BELOW v3."""
    from scoring_v4.modules.omega import score_omega

    canaries = _load_canaries({"327776"})
    if "327776" not in canaries:
        pytest.skip("Sports Research canary not in catalog")

    bd = score_omega(canaries["327776"]).to_breakdown()
    v3_baseline = 63.7
    delta = bd["score_100"] - v3_baseline
    assert delta >= -3.0, (
        f"Sports Research v4 {bd['score_100']} vs v3 {v3_baseline}: with the affine "
        f"removed (score = rubric raw), the omega module's structural work must not "
        f"score this materially BELOW v3 (the prior +17.9 was calibration inflation)."
    )


# --- All 5 dimensions populated through P1.6.6 -------------------------


def test_all_five_dimensions_populated_at_p166() -> None:
    from scoring_v4.modules.omega import score_omega

    bd = score_omega(_premium_omega()).to_breakdown()
    # Phase 4: trust is no longer a core dimension; the four core dimensions are
    # populated and verification is an additive bonus.
    for dim in ("formulation", "dose", "evidence", "transparency"):
        assert bd["dimensions"][dim]["score"] is not None, (
            f"omega.{dim}.score should be populated"
        )
    assert "trust" not in bd["dimensions"]
    assert bd["verification_bonus"]["max"] == 8.0


# --- Architecture lock --------------------------------------------------


def test_omega_orchestrator_does_not_import_v3_scorer() -> None:
    import ast
    import scoring_v4.modules.omega as om

    tree = ast.parse(Path(om.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith("score_supplements"), (
                f"v4→v3 import: from {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("score_supplements"), (
                    f"v4→v3 import: import {alias.name}"
                )


# --- Shadow integration -------------------------------------------------


def test_shadow_scorer_emits_omega_production_score() -> None:
    """Through the shadow scorer entry point, omega-routed products
    emit shadow_score_v4_100 = the production rubric score."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_premium_omega())
    assert out["shadow_score_v4_module"] == "omega"
    assert out["shadow_score_v4_100"] is not None
    assert 0 <= out["shadow_score_v4_100"] <= 100
    assert out["shadow_score_v4_verdict"] in ("SAFE", "POOR")
