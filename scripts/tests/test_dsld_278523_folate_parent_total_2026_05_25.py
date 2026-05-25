"""Lock current correct behavior for CVS B-100 Complex (DSLD 278523).

DSLD encodes nutrient/form pairs as parent + nested child:
    Folate         680 mcg DFE  (label-equivalent total)
      Folic Acid   400 mcg      (actual delivered form)

Both rows share canonical_id='vitamin_b9_folate'. Both appear in
ingredients_scorable for audit/lineage. The enricher's
_mark_parent_total_rows (enrich_supplements_v3.py:5647) MUST mark the
top-level parent is_parent_total=True so the scorer skips it in
A1/A2/A5e/EPA-DHA paths and only the form-specific child contributes
its bio_score.

Failure modes this test catches:
- _mark_parent_total_rows stops firing for nutrient/form pairs and
  Folate parent is no longer skipped in A1 (double-count risk).
- A cleaner change drops one row from ingredients_scorable.
- The child row erroneously gets is_parent_total=True, causing the
  scorer to skip ALL folate contributions (folate falls to 0).
"""

import glob
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DSLD_ID = "278523"


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


def _folate_rows(prod):
    scor = (prod.get("ingredient_quality_data") or {}).get("ingredients_scorable") or []
    return [r for r in scor if r.get("canonical_id") == "vitamin_b9_folate"]


@pytest.fixture(scope="module")
def prod():
    """Locate DSLD 278523 once per module; fail fast if missing."""
    p = _find_enriched(DSLD_ID)
    if p is None:
        pytest.fail(f"DSLD {DSLD_ID} not found in any enriched batch")
    return p


def test_dsld_278523_two_folate_rows_in_scorable(prod):
    folate = _folate_rows(prod)
    assert len(folate) == 2, (
        f"DSLD {DSLD_ID}: expected 2 folate rows (Folate parent + Folic Acid child) "
        f"in ingredients_scorable, got {len(folate)}: "
        f"{[r.get('name') for r in folate]}"
    )


def test_dsld_278523_parent_folate_marked_is_parent_total(prod):
    folate = _folate_rows(prod)
    parents = [r for r in folate if not r.get("is_nested_ingredient")]
    assert len(parents) == 1, (
        f"DSLD {DSLD_ID}: expected exactly 1 top-level Folate row, got {len(parents)}"
    )
    assert parents[0].get("is_parent_total") is True, (
        f"DSLD {DSLD_ID}: parent 'Folate' (680 mcg DFE) must have "
        f"is_parent_total=True so the scorer skips it in A1 and does not "
        f"double-count with the nested Folic Acid form; got "
        f"is_parent_total={parents[0].get('is_parent_total')}"
    )


def test_dsld_278523_nested_folic_acid_is_not_parent_total(prod):
    folate = _folate_rows(prod)
    children = [r for r in folate if r.get("is_nested_ingredient")]
    assert len(children) == 1, (
        f"DSLD {DSLD_ID}: expected exactly 1 nested Folic Acid row, got {len(children)}"
    )
    assert children[0].get("is_parent_total") is False, (
        f"DSLD {DSLD_ID}: nested 'Folic Acid' (400 mcg) must have "
        f"is_parent_total=False so the scorer scores its form-specific "
        f"bio_score; got is_parent_total={children[0].get('is_parent_total')} "
        f"(setting True would zero out folate scoring for this product)"
    )
