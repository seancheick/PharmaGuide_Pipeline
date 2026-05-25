"""Lock current safe behavior for DSLD 317006 (Sports Research Turmeric Curcumin C3 Complex).

Investigation 2026-05-25 confirmed: the cleaner emits two top-level
activeIngredients rows that both carry canonical_id='piperine'
(Bioperine parent at 5 mg, isNested=False; Piperine child at 4.75 mg,
isNested=True, parentBlend='Bioperine'). This is the standard
branded-extract + standardized-active-constituent lineage shape from
DSLD and is allowed in the cleaner contract.

The enricher MUST route both rows through the absorption-enhancer
demotion path (sub-threshold piperine paired with curcumin) so
NEITHER row contributes to Section A scoring. Without that routing
the same identity would be double-scored.

Failure modes this test catches:
- The absorption-enhancer threshold (10 mg) is changed in a way that
  re-promotes Bioperine 5 mg / Piperine 4.75 mg into scorable rows.
- A cleaner-side contract tightening removes the nested row and the
  enricher's grouping breaks.
- A canonical_id change breaks the piperine identity recognition.
"""

import glob
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DSLD_ID = "317006"


def _find_enriched(dsld_id):
    for p in sorted(glob.glob(str(REPO_ROOT / "scripts/products/output_*_enriched/enriched/*.json"))):
        try:
            with open(p) as f:
                data = json.load(f)
        except Exception:
            continue
        prods = data.get("products", data) if isinstance(data, dict) else data
        if not isinstance(prods, list):
            continue
        for prod in prods:
            if str(prod.get("dsld_id") or prod.get("id") or "") == str(dsld_id):
                return prod
    return None


@pytest.fixture(scope="module")
def prod():
    """Locate DSLD 317006 once per module; fail fast if missing."""
    p = _find_enriched(DSLD_ID)
    if p is None:
        pytest.fail(f"DSLD {DSLD_ID} not found in any enriched batch")
    return p


def test_dsld_317006_no_piperine_in_ingredients_scorable(prod):
    scor = (prod.get("ingredient_quality_data") or {}).get("ingredients_scorable") or []
    leaked = [r for r in scor if r.get("canonical_id") == "piperine"]
    assert leaked == [], (
        f"DSLD {DSLD_ID}: piperine rows leaked into ingredients_scorable "
        f"(double-scoring risk against curcumin in same product): "
        f"{[(r.get('name'), r.get('quantity'), r.get('unit')) for r in leaked]}"
    )


def test_dsld_317006_bioperine_and_piperine_both_in_demoted_absorption_enhancers(prod):
    dae = (prod.get("ingredient_quality_data") or {}).get("demoted_absorption_enhancers") or []
    names = {(r.get("name") or "").strip().lower() for r in dae if isinstance(r, dict)}
    assert "bioperine" in names, (
        f"DSLD {DSLD_ID}: top-level 'Bioperine' missing from "
        f"demoted_absorption_enhancers; got {sorted(names)}"
    )
    assert "piperine" in names, (
        f"DSLD {DSLD_ID}: nested 'Piperine' missing from "
        f"demoted_absorption_enhancers; got {sorted(names)}"
    )


def test_dsld_317006_both_piperine_rows_recognized_non_scorable_sub_threshold(prod):
    rns = (prod.get("ingredient_quality_data") or {}).get("ingredients_recognized_non_scorable") or []
    piperine = [r for r in rns if r.get("canonical_id") == "piperine"]
    assert len(piperine) == 2, (
        f"DSLD {DSLD_ID}: expected 2 piperine rows in "
        f"ingredients_recognized_non_scorable (Bioperine + nested Piperine), "
        f"got {len(piperine)}"
    )
    reasons = {r.get("recognition_reason") for r in piperine}
    assert reasons == {"absorption_enhancer_sub_threshold"}, (
        f"DSLD {DSLD_ID}: expected recognition_reason="
        f"'absorption_enhancer_sub_threshold' for both piperine rows, got {reasons}"
    )
