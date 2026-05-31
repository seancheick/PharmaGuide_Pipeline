from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SCRIPTS_ROOT / "api_audit") not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT / "api_audit"))

from api_audit.v4_side_by_side_review import flatten_row, select_review_sample  # noqa: E402


def _row(dsld_id: int, module: str, **overrides):
    base = {
        "dsld_id": str(dsld_id),
        "brand_name": "Brand",
        "product_name": f"Product {dsld_id}",
        "primary_class": module,
        "v4_module": module,
        "in_shipped_universe": True,
        "v3_shipped_score": 60.0,
        "v3_verdict": "SAFE",
        "v3_safety_verdict": "SAFE",
        "v3_sections": {"A": 12, "B": 30, "C": 10, "D": 4, "E": 0},
        "v4_score": 60.0,
        "v4_raw_score": 50.0,
        "v4_verdict": "SAFE",
        "v4_dimensions": {"formulation": 10, "dose": 12, "evidence": 8},
        "v4_dimension_metadata": {"dose": {"reason": "fixture"}},
        "v4_confidence_detail": {"band": "moderate"},
        "score_delta_vs_v3": 0.0,
        "raw_score_delta_vs_v3": -10.0,
        "v4_completeness_missing": [],
        "v4_completeness_soft_missing": [],
        "v4_completeness_score_cap": None,
        "v4_completeness_verdict_ceiling": None,
        "compression_flags": [],
    }
    base.update(overrides)
    return base


def test_select_review_sample_balances_v4_modules_when_available():
    modules = ["generic", "multi_or_prenatal", "omega", "probiotic", "sports"]
    rows = []
    dsld_id = 1000
    for module in modules:
        for idx in range(25):
            rows.append(_row(dsld_id, module, raw_score_delta_vs_v3=idx - 12))
            dsld_id += 1

    sample = select_review_sample(rows, sample_size=100)

    counts = {}
    for row in sample:
        counts[row["v4_module"]] = counts.get(row["v4_module"], 0) + 1
    assert counts == {module: 20 for module in modules}


def test_flatten_row_includes_v3_sections_and_v4_dimension_metadata():
    row = _row(
        42,
        "generic",
        v4_completeness_soft_missing=["conservative_blend_anchor_mass"],
        compression_flags=["low_evidence_dimension"],
    )

    flat = flatten_row(row)

    assert flat["v3_A_ingredient_quality"] == 12
    assert flat["v4_formulation"] == 10
    assert flat["v4_completeness_soft_missing"] == "conservative_blend_anchor_mass"
    assert flat["compression_flags"] == "low_evidence_dimension"
    assert '"dose"' in flat["v4_dimension_metadata_json"]
