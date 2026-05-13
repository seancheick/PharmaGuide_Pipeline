"""Metadata contract for `percentile_categories.json`.

This file is the canonical category-cohort definition used by the scorer's
percentile-ranking step. Two top-level dicts:

* ``categories`` — PRIMARY entry catalog (9 cohort definitions:
  greens_powder, protein_powder, pre_workout, collagen_powder, …) each
  carrying inference signals (DSLD-category, ingredient-signature,
  keyword anchors).
* ``classification_rules`` — static rule config (4 keys:
  ``confidence_threshold``, ``margin_threshold``, ``score_normalizer``,
  ``tie_break_by``) consumed by the classifier alongside.

The file intentionally does NOT carry ``_metadata.total_entries`` —
authors chose to omit it rather than ambiguously claim 9 (entries) or 13
(entries + rules). This test pins the meaningful count: the 9 category
cohorts. If you add a cohort, this test catches a stale documentation
state.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "percentile_categories.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_categories_dict_is_non_empty(blob):
    """Defensive: the scorer depends on at least one category cohort.
    If categories is empty or missing, percentile ranking degrades to
    no-cohort behavior silently."""
    assert "categories" in blob, "missing required `categories` dict"
    assert isinstance(blob["categories"], dict)
    assert blob["categories"], "`categories` cannot be empty — percentile ranking would have no cohorts"


def test_total_entries_tracks_categories_count(blob):
    """File-specific drift gate: total_entries pins len(categories) — the
    canonical cohort count. classification_rules is auxiliary config and
    not counted. If you add a cohort, bump total_entries to match."""
    expected = len(blob["categories"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but categories has {expected} "
        f"cohorts. Bump total_entries to {expected}."
    )


def test_classification_rules_present(blob):
    """Defensive: the classifier reads each of these by name."""
    required_rules = {"confidence_threshold", "margin_threshold",
                      "score_normalizer", "tie_break_by"}
    rules = blob.get("classification_rules", {})
    missing = required_rules - set(rules)
    assert not missing, f"classification_rules missing required keys: {missing}"


def test_each_category_carries_inference_signals(blob):
    """Defensive: every NON-fallback cohort must declare inference signals
    inside `evidence` (e.g. `canonical_ingredients`, `name_tokens`) so the
    classifier can route products to it. Cohorts also need a `label`,
    `priority`, and `min_evidence_score`. The fallback cohort
    (``is_fallback: true``) intentionally has ``evidence: null`` — it
    catches anything no other cohort routes to."""
    bad = []
    required_top_keys = {"label", "priority", "evidence", "min_evidence_score"}
    for cohort_id, cohort in blob["categories"].items():
        if not isinstance(cohort, dict):
            bad.append((cohort_id, "not a dict"))
            continue
        missing = required_top_keys - set(cohort)
        if missing:
            bad.append((cohort_id, f"missing required keys: {missing}"))
            continue
        if cohort.get("is_fallback") is True:
            continue  # fallback cohort intentionally has empty evidence
        evidence = cohort.get("evidence")
        if not isinstance(evidence, dict) or not evidence:
            bad.append((cohort_id, "non-fallback cohort needs non-empty evidence dict"))
    assert not bad, f"cohorts with schema issues: {bad[:5]}"
