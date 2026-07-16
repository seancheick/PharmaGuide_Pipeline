"""Determinism guard for supplement_taxonomy.classify_supplement.

supplement_taxonomy.py's module docstring promises "Classification is
deterministic and auditable". It was not: several `classification_reasons`
render a *set* intersection through `list(...)`, and CPython randomizes string
hashing per process (PYTHONHASHSEED), so the same product classified in two
different runs produced reason strings whose id lists were ordered differently.

    embedded  : "vitamin combo: ['vitamin_d', 'vitamin_e', 'vitamin_a', 'vitamin_c']"
    recomputed: "vitamin combo: ['vitamin_c', 'vitamin_e', 'vitamin_a', 'vitamin_d']"

Found by the supp-type consolidation harness's baseline-parity gate on real
product dsld 18141 (CVS "Omega-3 100 mg"): current code could not reproduce the
taxonomy embedded in the artifact it had itself written.

Why it matters beyond tidiness:
  * enriched artifacts are not byte-reproducible run to run, so any
    artifact-vs-artifact diff carries permanent false positives;
  * `audit_source_of_truth_contract.py` greps these reason strings as a
    release gate, which makes a randomly-ordered string a release input;
  * `primary_type` is unaffected, so the defect is invisible to any check
    that only compares the type name.

These tests run the classifier under two different hash seeds in subprocesses,
because within a single process the ordering is stable and the bug hides.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name, canonical_id, category, qty=100.0):
    return {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "category": category,
        "quantity": qty,
        "unit": "mg",
        "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }


# A vitamin panel wide enough to render the `vitamin combo: [...]` reason.
VITAMIN_COMBO_PRODUCT = {
    "dsld_id": 990001,
    "product_name": "Test Vitamin Combo",
    "fullName": "Test Vitamin Combo",
    "ingredient_quality_data": {
        "ingredients_scorable": [
            _row("Vitamin A", "vitamin_a", "vitamin"),
            _row("Vitamin C", "vitamin_c", "vitamin"),
            _row("Vitamin D", "vitamin_d", "vitamin"),
            _row("Vitamin E", "vitamin_e", "vitamin"),
        ],
    },
    "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
}

_CHILD = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, {scripts!r})
    from supplement_taxonomy import classify_supplement
    product = json.loads(sys.argv[1])
    print(json.dumps(classify_supplement(product), sort_keys=True, default=str))
    """
)


def _classify_with_hash_seed(product: dict, seed: str) -> dict:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD.format(scripts=str(SCRIPTS_DIR)),
         json.dumps(product)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(SCRIPTS_DIR),
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("seeds", [("0", "1"), ("1", "12345")])
def test_classification_is_reproducible_across_hash_seeds(seeds):
    """The same product must classify identically in two independent runs."""
    first = _classify_with_hash_seed(VITAMIN_COMBO_PRODUCT, seeds[0])
    second = _classify_with_hash_seed(VITAMIN_COMBO_PRODUCT, seeds[1])

    assert first == second, (
        "classify_supplement is not reproducible across processes; the enriched "
        "artifact cannot be trusted as a diff baseline"
    )


def test_reason_id_lists_are_ordered_deterministically():
    """The rendered id lists must be sorted, not set-iteration order."""
    taxonomy = classify_supplement(dict(VITAMIN_COMBO_PRODUCT))
    combo = [r for r in taxonomy["classification_reasons"] if "combo:" in r]
    assert combo, f"expected a combo reason, got {taxonomy['classification_reasons']}"

    for reason in combo:
        rendered = reason.split(":", 1)[1].strip()
        ids = json.loads(rendered.replace("'", '"'))
        assert ids == sorted(ids), (
            f"reason renders ids in unstable set order: {reason!r}"
        )


def test_no_set_is_rendered_through_bare_list_in_reasons():
    """Source guard: `list(<set>)` in a reason re-introduces the defect.

    Cheap and blunt on purpose — the subprocess test above only catches the
    sites a fixture happens to reach, and a new branch would slip through.
    """
    source = (SCRIPTS_DIR / "supplement_taxonomy.py").read_text()
    offenders = [
        line.strip()
        for line in source.splitlines()
        if "reasons.append" in line and "list(" in line
    ]
    assert not offenders, (
        "reasons must render id sets via sorted(...) so the classification is "
        "reproducible:\n  " + "\n  ".join(offenders)
    )
