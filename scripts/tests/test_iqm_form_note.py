#!/usr/bin/env python3
"""Consumer form notes — allowlist gate, single-form guard, export contract.

The IQM `notes` field is a curation workspace: 71% of entries carry audit prose
(PMIDs, "Clinician recalibration 2026-06-02", repo paths). Only a reviewed
`consumer_note` may reach a user.

Two properties these tests exist to protect:

1. **Automatic splitting of `notes` is not safe.** For 21% of forms the head
   sentences are marketing prose or claims the audit trailer later corrected.
   `coenzymated_complex` is the canonical counterexample and is asserted below.

2. **`bio_score` is a blend.** It is `percent_share`-weighted across
   `matched_forms`; `matched_form` (singular) is only the first entry. A real
   calcium row blends carbonate (8) + citrate (14) + bis-glycinate (14) to 12.0
   ("Excellent form") while naming only carbonate. Attaching carbonate's note
   there would contradict the badge.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import build_final_db  # noqa: E402
from build_final_db import (  # noqa: E402
    FormNoteProvenanceError,
    _derive_form_note,
    build_detail_blob,
    validate_iqm_consumer_notes,
)

REVIEW = {"by": "Dr Pham", "date": "2026-08-08"}
NOTE = (
    "The active coenzyme form of B2, also called FMN. Taken by mouth it is "
    "converted back to plain riboflavin before your body absorbs it, so it is "
    "taken up about as well as standard riboflavin."
)
PREVIEW = "The active coenzyme form of B2, also called FMN."


def _iqm(**form_overrides):
    form = {"bio_score": 10, "notes": "Workspace prose. Cited evidence: PMID:8604671."}
    form.update(form_overrides)
    return {"vitamin_b2_riboflavin": {"forms": {"riboflavin-5-phosphate": form}}}


def _match(**overrides):
    m = {
        "canonical_id": "vitamin_b2_riboflavin",
        "matched_form": "riboflavin-5-phosphate",
        "bio_score": 10.0,
        "matched_forms": [],
    }
    m.update(overrides)
    return m


# --- allowlist -----------------------------------------------------------

def test_no_consumer_note_emits_nothing():
    """The default for every uncurated form: fail closed, never split `notes`."""
    assert _derive_form_note(_match(), _iqm()) == (None, None)


def test_raw_notes_are_never_used_as_the_consumer_note():
    iqm = _iqm(notes="Perfectly clean looking sentence with no audit markers.")
    assert _derive_form_note(_match(), iqm) == (None, None)


def test_reviewed_consumer_note_is_emitted_with_preview():
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    assert _derive_form_note(_match(), iqm) == (NOTE, PREVIEW)


def test_preview_is_the_first_sentence_split_pipeline_side():
    """The app must never make a sentence-boundary decision."""
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    _, preview = _derive_form_note(_match(), iqm)
    assert preview == PREVIEW
    assert NOTE.startswith(preview)


def test_coenzymated_marketing_head_is_rejected():
    """Regression for the counterexample that forced the allowlist design.

    These two sentences precede the first audit marker, so any split-based
    approach would ship them — under an "Excellent form" badge, asserting the
    exact premise the audit trailer corrects.
    """
    head = (
        "Active coenzyme forms of B-vitamins for enhanced bioavailability and "
        "cellular utilization. Pre-converted forms ready for immediate use."
    )
    iqm = _iqm(consumer_note=head, consumer_note_review=REVIEW)
    with pytest.raises(FormNoteProvenanceError, match="marketing language"):
        validate_iqm_consumer_notes(iqm)
    assert _derive_form_note(_match(), iqm) == (None, None)


# --- Gate A: provenance --------------------------------------------------

@pytest.mark.parametrize(
    "review, expected",
    [
        (None, "without consumer_note_review"),
        ({"date": "2026-08-08"}, "by is missing or empty"),
        ({"by": "   ", "date": "2026-08-08"}, "by is missing or empty"),
        ({"by": "Dr Pham"}, "not an ISO date"),
        ({"by": "Dr Pham", "date": "08/08/2026"}, "not an ISO date"),
    ],
)
def test_gate_a_rejects_incomplete_provenance(review, expected):
    form = {"consumer_note": "A clean reviewed consumer sentence about this form."}
    if review is not None:
        form["consumer_note_review"] = review
    with pytest.raises(FormNoteProvenanceError, match=expected):
        validate_iqm_consumer_notes(_iqm(**form))


@pytest.mark.parametrize(
    "note, expected",
    [
        ("Clean enough. Cited evidence: PMID:123.", "internal audit text"),
        ("See scripts/audits/mineral_forms/api_verification.json.", "internal audit text"),
        ("Clinician recalibration 2026-06-02 lowered this.", "internal audit text"),
        ("Avoid this form if you take blood thinners.", "safety language"),
        ("Pre-converted forms ready for immediate use.", "marketing language"),
        ("x" * 601, "exceeds 600 chars"),
    ],
)
def test_gate_a_rejects_unsafe_content(note, expected):
    iqm = _iqm(consumer_note=note, consumer_note_review=REVIEW)
    with pytest.raises(FormNoteProvenanceError, match=expected):
        validate_iqm_consumer_notes(iqm)


@pytest.mark.parametrize("variant", ["contraindicated", "contraindication"])
def test_gate_a_rejects_contraindication_word_family(variant):
    """Safety terms must not leak through a stem-only word-boundary regex."""
    iqm = _iqm(
        consumer_note=f"This neutral test sentence mentions {variant}.",
        consumer_note_review=REVIEW,
    )
    with pytest.raises(FormNoteProvenanceError, match="safety language"):
        validate_iqm_consumer_notes(iqm)


def test_gate_a_reports_every_defect_not_just_the_first():
    """A curator should see the whole queue in one run."""
    iqm = {
        "p": {
            "forms": {
                "a": {"bio_score": 1, "consumer_note": "Missing its review block."},
                "b": {
                    "bio_score": 1,
                    "consumer_note": "Avoid this one.",
                    "consumer_note_review": REVIEW,
                },
                "ok": {
                    "bio_score": 1,
                    "consumer_note": "A clean sentence.",
                    "consumer_note_review": REVIEW,
                },
            }
        }
    }
    with pytest.raises(FormNoteProvenanceError) as excinfo:
        validate_iqm_consumer_notes(iqm)
    message = str(excinfo.value)
    assert "p/a" in message and "p/b" in message
    assert "p/ok" not in message


def test_derive_never_raises_on_a_defective_note():
    """Gate A is the loud gate; derive is the belt that must not leak.

    The export loop quarantines a product on any exception, so raising here
    would silently drop products instead of failing the build.
    """
    iqm = _iqm(consumer_note="Leaky. PMID:123.", consumer_note_review=REVIEW)
    assert _derive_form_note(_match(), iqm) == (None, None)


def test_real_ingredient_quality_map_passes_gate_a():
    build_final_db.IQM_REFERENCE_INDEX = None
    try:
        assert build_final_db.load_iqm_reference_index()
    finally:
        build_final_db.IQM_REFERENCE_INDEX = None


# --- single-form guard ---------------------------------------------------

def test_blend_of_distinct_forms_suppresses_the_note():
    """The real calcium case: no single form supplied the blended bio_score."""
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    blended = _match(
        matched_forms=[
            {"form_key": "calcium carbonate", "bio_score": 8.0, "percent_share": 1 / 3},
            {"form_key": "calcium citrate", "bio_score": 14.0, "percent_share": 1 / 3},
            {"form_key": "calcium bis-glycinate", "bio_score": 14.0, "percent_share": 1 / 3},
        ]
    )
    assert _derive_form_note(blended, iqm) == (None, None)


def test_score_adjusted_away_from_the_iqm_form_suppresses_the_note():
    """Share-scaled rows (row 5.9 vs IQM 6) must not borrow the form's note."""
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    assert _derive_form_note(_match(bio_score=12.0), iqm) == (None, None)


def test_repeated_entries_of_one_form_still_emit():
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    repeated = _match(
        matched_forms=[
            {"form_key": "riboflavin-5-phosphate", "bio_score": 10.0},
            {"form_key": "riboflavin-5-phosphate", "bio_score": 10.0},
        ]
    )
    assert _derive_form_note(repeated, iqm) == (NOTE, PREVIEW)


def test_note_follows_the_scoring_form_not_the_label_prose():
    """`display_form_label` is display copy and may name something else.

    Here the label reads "Vitamin B2 (as Riboflavin 5' Phosphate); Vitamin B2"
    while the resolved scoring form is `riboflavin-5-phosphate`. The note must
    track the resolved form, and must not vary with the label text.
    """
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    label_heavy = _match(
        display_form_label="Vitamin B2 (as Riboflavin 5' Phosphate); Vitamin B2",
        raw_source_text="Vitamin B-2 Complex",
    )
    assert _derive_form_note(label_heavy, iqm) == (NOTE, PREVIEW)


def test_unresolvable_identity_emits_nothing():
    iqm = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    assert _derive_form_note(_match(canonical_id=""), iqm) == (None, None)
    assert _derive_form_note(_match(matched_form=""), iqm) == (None, None)
    assert _derive_form_note(_match(canonical_id="nope"), iqm) == (None, None)
    assert _derive_form_note(_match(bio_score=None), iqm) == (None, None)


# --- export contract (end to end) ----------------------------------------

def _enriched():
    return {
        "dsld_id": "TEST_FORM_NOTE",
        "product_name": "Test B-Complex",
        "brandName": "Test Brand",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": False,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": True,
        "compliance_data": {},
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [
            {
                "name": "Riboflavin",
                "raw_source_text": "Riboflavin",
                "raw_source_path": "activeIngredients[0]",
                "normalized_key": "riboflavin",
                "quantity": 10,
                "unit": "mg",
                "forms": [],
            }
        ],
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "Riboflavin",
                    "raw_source_text": "Riboflavin",
                    "raw_source_path": "activeIngredients[0]",
                    "standard_name": "Vitamin B2 (Riboflavin)",
                    "canonical_id": "vitamin_b2_riboflavin",
                    "matched_form": "riboflavin-5-phosphate",
                    "matched_forms": [],
                    "bio_score": 10.0,
                    "score": 10.0,
                    "natural": False,
                    "notes": "Workspace prose. Cited evidence: PMID:8604671.",
                    "category": "vitamins",
                    "mapped": True,
                    "quantity": 10,
                    "unit": "mg",
                    "safety_hits": [],
                }
            ]
        },
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [],
        "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {
            "basis_count": 1,
            "basis_unit": "capsule",
            "min_servings_per_day": 1,
            "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {
            "match_count": 0,
            "clinical_matches": [],
            "unsubstantiated_claims": [],
        },
        "rda_ul_data": {
            "collection_enabled": True,
            "ingredients_with_rda": 0,
            "analyzed_ingredients": [],
            "count": 0,
            "adequacy_results": [],
            "conversion_evidence": [],
            "safety_flags": [],
            "has_over_ul": False,
        },
    }


def _scored():
    return {
        "score_80": 50.0,
        "display": "50/80",
        "display_100": "62/100",
        "score_100_equivalent": 62.0,
        "grade": "Fair",
        "verdict": "SAFE",
        "safety_verdict": "SAFE",
        "mapped_coverage": 1.0,
        "badges": [],
        "flags": [],
        "section_scores": {},
        "summary": {},
        "supp_type": "specialty",
        "unmapped_actives": [],
        "breakdown": {},
    }


@pytest.fixture
def curated_iqm(monkeypatch):
    """Install a curated IQM without touching the real map on disk."""
    index = _iqm(consumer_note=NOTE, consumer_note_review=REVIEW)
    monkeypatch.setattr(build_final_db, "IQM_REFERENCE_INDEX", index)
    monkeypatch.setattr(build_final_db, "load_iqm_reference_index", lambda: index)
    return index


def _riboflavin_row(blob):
    for row in blob.get("display_ingredients") or []:
        analysis = row.get("analysis") or {}
        if analysis.get("canonical_id") == "vitamin_b2_riboflavin":
            return row
    raise AssertionError("riboflavin row missing from display_ingredients")


def test_note_reaches_the_canonical_analysis_payload(curated_iqm):
    """The app reads `display_ingredients[].analysis`; the legacy array is not
    enough. This asserts the final emitted payload, not the helper."""
    blob = build_detail_blob(_enriched(), _scored())
    analysis = _riboflavin_row(blob)["analysis"]
    assert analysis["form_note"] == NOTE
    assert analysis["form_note_preview"] == PREVIEW
    assert analysis["bio_score"] == 10.0


def test_legacy_notes_field_still_carries_the_workspace_prose(curated_iqm):
    """Contract-required and read by other consumers — must not be scrubbed."""
    blob = build_detail_blob(_enriched(), _scored())
    legacy = blob["ingredients"][0]
    assert "PMID" in legacy["notes"]
    assert legacy["form_note"] == NOTE


def test_uncurated_form_emits_null_on_the_canonical_path(monkeypatch):
    index = _iqm()
    monkeypatch.setattr(build_final_db, "IQM_REFERENCE_INDEX", index)
    monkeypatch.setattr(build_final_db, "load_iqm_reference_index", lambda: index)
    blob = build_detail_blob(_enriched(), _scored())
    analysis = _riboflavin_row(blob)["analysis"]
    assert analysis["form_note"] is None
    assert analysis["form_note_preview"] is None
