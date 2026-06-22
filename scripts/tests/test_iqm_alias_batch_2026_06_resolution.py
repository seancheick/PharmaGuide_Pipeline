"""Enricher-level resolution locks for the 2026-06 IQM alias batch.

Closes a test-coverage gap: the staged batch added aliases to 9 IQM parents but
only 4 (ecdysterone/gypenosides/turkey-tail/aloe) had regression cases in
``test_clean_unmapped_alias_regressions.py``. These assert the *end-to-end*
identity AND form-level bio_score for the remaining parents, so a future
prefix-strip or form-collapse regression is caught.

The high-value lock is N-Acetyl-L-Glutamine: it is an alias on the *acetylated*
form (bio_score 8, poor absorption), which is a form under the ``l_glutamine``
parent. A naive "strip the N-Acetyl prefix" path would mis-resolve it to the
free-glutamine powder form (bio_score 11) and silently upgrade a
poor-bioavailability compound. Verified live via the enricher 2026-06-22.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _resolve(enricher, label):
    """Return (standard_name, bio_score, matched_form) for a single-active product."""
    product = {
        "activeIngredients": [{"name": label, "quantity": 500, "unit": "mg"}],
        "inactiveIngredients": [],
    }
    data = enricher._collect_ingredient_quality_data(product)
    scorable = data.get("ingredients_scorable") or []
    assert scorable, f"{label!r} did not resolve to any scorable ingredient"
    row = scorable[0]
    return row.get("standard_name"), row.get("bio_score"), row.get("matched_form")


@pytest.mark.parametrize(
    "label,std,bio,form",
    [
        # Acetylated glutamine MUST keep the poor-absorption form (bio 8),
        # NOT collapse to the free-glutamine powder form (bio 11).
        ("N-Acetyl L-Glutamine", "L-Glutamine", 8.0, "n-acetyl-l-glutamine"),
        ("N-Acetyl Glutamine", "L-Glutamine", 8.0, "n-acetyl-l-glutamine"),
        ("Soy Bean Isoflavones", "Isoflavones", 8.0, "isoflavones (unspecified)"),
        ("Soybean Isoflavone", "Isoflavones", 8.0, "isoflavones (unspecified)"),
        ("Wolfberry Fruit Extract", "Goji Berry", 5.0, "goji berry (unspecified)"),
        ("Phenylethylamine Hydrochloride", "Phenylethylamine", 5.0, "phenylethylamine (unspecified)"),
        ("Mucuna pruriens Fruit Extract", "Mucuna Pruriens (Velvet Bean)", 7.0, "mucuna pruriens standardized extract"),
        ("Mucuna pruriens Fruit Extract, Powder", "Mucuna Pruriens (Velvet Bean)", 7.0, "mucuna pruriens standardized extract"),
    ],
)
def test_alias_batch_resolves_to_correct_identity_and_form(enricher, label, std, bio, form):
    got_std, got_bio, got_form = _resolve(enricher, label)
    assert got_std == std
    assert got_bio == bio
    assert got_form == form


def test_glutamine_forms_stay_distinct(enricher):
    """The NAG aliases sit on the acetylated form; collapsing the form axis would
    mis-score the others. Lock the three distinct glutamine forms."""
    assert _resolve(enricher, "L-Glutamine")[1] == 11.0          # free-form powder
    assert _resolve(enricher, "Sustamine")[1] == 15.0            # alanyl dipeptide
    assert _resolve(enricher, "N-Acetyl L-Glutamine")[1] == 8.0  # acetylated
