"""IQM batch — Tracks B + E + F (small IQM batch from the NOT_SCORED triage slice).

Plan: reports/not_scored_triage/track_BEF_iqm_batch_plan.md

This file pins the IQM alias / form additions that close NOT_SCORED gaps
identified by Tracks E (form_unmapped) and F (no_quality_map_match) in the
NOT_SCORED triage. The additions are STRICTLY alias-only or form-only — no
new IQM parents, no invented bio_scores, no broadened semantic coverage.

Per dev review v2 (2026-05-23), the first three approved commits are:

  1. citrus_bergamot — add 'Citrus bergamia Risso fruit extract' +
     'Citrus bergamia Risso' to the 'bergamot (unspecified)' form aliases.
     Chemistry: 'Risso' is the botanical-authority designation for Antoine
     Risso (1813), same species as the existing 'citrus bergamia' alias.
     Affects Jarrow 211933 / 264734.

  2. isoflavones — add EXACT 'total Soy Isoflavones' + 'Soy Isoflavones' to
     existing 'soy isoflavones (genistein, daidzein)' form aliases (or
     create the form if it doesn't exist). Do NOT broaden beyond soy-specific
     terms — per dev review, no generic 'isoflavone' alias.
     Affects Solgar 201361.

  3. rna_dna — add 'Ribonucleic Acid' alias to existing rna_dna parent.
     Low bio_score preserved (oral RNA has limited clinical evidence).
     Affects Life Extension 231631.

Each commit is atomic per dev review cadence. Tests below are the data-layer
contract — the live-corpus delta is verified separately after the IQM edit.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: F401


IQM_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


# ---------------------------------------------------------------------------
# Commit #1: citrus_bergamot form alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_alias",
    [
        "Citrus bergamia Risso fruit extract",
        "Citrus bergamia Risso",
    ],
)
def test_citrus_bergamot_unspecified_form_includes_risso_aliases(iqm, expected_alias):
    """Jarrow Citrus Bergamot 500 mg (211933 / 264734) row.std_name is
    'Citrus bergamia Risso fruit extract' — must alias to the existing
    bergamot (unspecified) form. Risso is the botanical-authority
    designation for Antoine Risso, same Citrus bergamia species as the
    existing 'citrus bergamia' alias."""
    assert "citrus_bergamot" in iqm, "citrus_bergamot parent missing from IQM"
    forms = iqm["citrus_bergamot"].get("forms", {})
    assert "bergamot (unspecified)" in forms, (
        "Expected 'bergamot (unspecified)' form to exist on citrus_bergamot. "
        f"Available forms: {list(forms.keys())}"
    )
    aliases_lower = [a.lower() for a in forms["bergamot (unspecified)"].get("aliases", [])]
    assert expected_alias.lower() in aliases_lower, (
        f"alias {expected_alias!r} missing from citrus_bergamot."
        f"forms['bergamot (unspecified)'].aliases. "
        f"Jarrow Citrus Bergamot products will fall out of scored catalog."
    )


def test_citrus_bergamot_unspecified_form_bio_score_pinned(iqm):
    """Pin the conservative bio_score on the unspecified form. Adding the
    Risso alias must NOT touch the existing 12 bio_score (unspecified extract
    is intentionally lower than BPF=14 / standardized extract=12)."""
    form = iqm["citrus_bergamot"]["forms"]["bergamot (unspecified)"]
    assert form["bio_score"] == 12, (
        f"bergamot (unspecified) bio_score changed from 12 to {form['bio_score']} — "
        f"alias-add must not modify bio_score."
    )


# ---------------------------------------------------------------------------
# Commit #2: isoflavones soy-specific alias
# ---------------------------------------------------------------------------


def test_isoflavones_unspecified_form_includes_total_soy_isoflavones_alias(iqm):
    """Solgar Super Concentrated Isoflavones (201361) row.std_name is
    'total Soy Isoflavones' — must alias to the existing isoflavones parent.
    Per dev review: ONLY this exact label string. Do NOT broaden beyond
    soy/isoflavone terms (no generic 'isoflavone' alias added)."""
    assert "isoflavones" in iqm, "isoflavones parent missing from IQM"
    forms = iqm["isoflavones"].get("forms", {})
    assert "isoflavones (unspecified)" in forms
    aliases_lower = [a.lower() for a in forms["isoflavones (unspecified)"].get("aliases", [])]
    assert "total soy isoflavones" in aliases_lower, (
        "alias 'total Soy Isoflavones' missing from isoflavones."
        "forms['isoflavones (unspecified)'].aliases. "
        "Solgar Super Concentrated Isoflavones (201361) will stay NOT_SCORED."
    )


def test_isoflavones_unspecified_form_bio_score_pinned(iqm):
    """Pin the conservative bio_score = 8 on the unspecified isoflavones form.
    Isoflavones (unspecified) is intentionally low — class-level signal without
    specific genistein/daidzein standardization."""
    form = iqm["isoflavones"]["forms"]["isoflavones (unspecified)"]
    assert form["bio_score"] == 8, (
        f"isoflavones (unspecified) bio_score changed from 8 to {form['bio_score']} — "
        f"alias-add must not modify bio_score."
    )


def test_isoflavones_no_generic_isoflavone_alias_added(iqm):
    """Negative-scope guard: per dev review v2, the alias-add must NOT include
    a generic 'isoflavone' (singular) or any non-soy-specific term that would
    expand semantic coverage. Existing aliases are all soy-specific."""
    form = iqm["isoflavones"]["forms"]["isoflavones (unspecified)"]
    aliases_lower = {a.lower() for a in form.get("aliases", [])}
    # forbidden expansions
    assert "isoflavone" not in aliases_lower, (
        "Generic 'isoflavone' (singular) alias added — this broadens coverage "
        "beyond soy and is out of scope for this slice."
    )
