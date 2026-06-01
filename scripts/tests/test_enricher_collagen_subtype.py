"""Phase 7.5 — enricher emits an authoritative collagen_subtype on collagen rows.

Release gate: every collagen row (canonical_id == "collagen") must carry a
collagen_subtype field so the scorer / Flutter / audits read it instead of
re-deriving from text. Generic rows are 'unspecified' (scorer resolves with
product context); rows the row text proves get a concrete subtype.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pytest  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _match(form, canonical_id="collagen", bio_score=11):
    return {
        "canonical_id": canonical_id,
        "bio_score": bio_score,
        "natural": False,
        "form_name": form,
        "matched_form": form,
        "match_status": "MATCHED",
        "match_tier": "exact",
    }


def _ingredient(name, quantity=10, unit="Gram(s)"):
    return {"name": name, "standardName": "Collagen", "quantity": quantity, "unit": unit,
            "raw_source_text": name}


def _subtype(enricher, name, form):
    entry = enricher._build_quality_entry(_ingredient(name), _match(form), hierarchy_type=None)
    return entry


def test_collagen_row_always_carries_subtype(enricher):
    entry = _subtype(enricher, "Hydrolyzed Collagen Peptides", "hydrolyzed collagen peptides")
    assert "collagen_subtype" in entry
    assert entry["collagen_subtype"] == "peptides_i_iii"


def test_ucii_row_stamped_undenatured(enricher):
    entry = _subtype(enricher, "UC-II standardized Cartilage", "undenatured collagen")
    assert entry["collagen_subtype"] == "undenatured_type_ii"


def test_biocell_sternum_row_stamped_hydrolyzed_type2(enricher):
    entry = _subtype(enricher, "BioCell Collagen", "hydrolyzed collagen peptides")
    assert entry["collagen_subtype"] == "hydrolyzed_type_ii"


def test_generic_collagen_row_unspecified(enricher):
    # bare "Collagen" with no distinguishing row signal -> unspecified (scorer
    # resolves with product context), but the FIELD is always present.
    entry = enricher._build_quality_entry(
        {"name": "Collagen", "standardName": "Collagen", "quantity": 5, "unit": "Gram(s)",
         "raw_source_text": "Collagen"},
        {"canonical_id": "collagen", "bio_score": 5, "natural": False,
         "form_name": "collagen", "matched_form": "collagen", "match_status": "MATCHED"},
        hierarchy_type=None,
    )
    assert entry["collagen_subtype"] == "unspecified"


def test_non_collagen_row_has_no_subtype(enricher):
    entry = enricher._build_quality_entry(
        {"name": "Magnesium Glycinate", "standardName": "Magnesium", "quantity": 200, "unit": "mg",
         "raw_source_text": "Magnesium Glycinate"},
        {"canonical_id": "magnesium", "bio_score": 14, "natural": False,
         "form_name": "magnesium glycinate", "matched_form": "magnesium glycinate",
         "match_status": "MATCHED"},
        hierarchy_type=None,
    )
    assert "collagen_subtype" not in entry
