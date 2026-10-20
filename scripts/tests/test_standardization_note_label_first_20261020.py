"""A standardization note shows only what the label declares.

build_final_db._compute_standardization_note read the matched IQM form name and
the IQM form notes (curation text) before the label's own row notes. A mapped
row therefore showed IQM text as if the label had said it ("organic Turmeric"
showed "3% curcuminoids"; a 93% curcuminoid label showed 3%), and a label's own
"45% EGCG" vanished once its green tea row mapped. The note now reads the label
row's notes and its label name only.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _blob_row(pipeline, pid, name, enricher_patch=None):
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"std_note_{pid}_raw.json").read_text())
    if enricher_patch:
        enricher = copy.copy(enricher)
        enricher.databases = copy.deepcopy(enricher.databases)
        enricher._match_quality_cache = {}
        enricher_patch(enricher.databases)
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    blob = build_detail_blob(copy.deepcopy(enriched), build_scored_artifact(copy.deepcopy(enriched)))
    return next(r for r in blob["ingredients"] if r["name"] == name)


@pytest.mark.parametrize("pid, name, note", [
    ("177145", "organic Turmeric", None),                               # label states no %; IQM notes said 3%
    ("178319", "Rhodiola rosea root extract", None),                    # mapped to the 3% rosavins form; label states no %
    ("201577", "standardized Turmeric extract", "93% curcuminoids"),    # label 93%; IQM notes said 3%
    ("239074", "Panax ginseng extract", "2% ginsenosides"),             # label 2%; form name "(4–7% ginsenosides)"
    ("1627", "American Ginseng root extract", "3% ginsenosides"),       # label 3%, previously hidden
])
def test_the_note_is_the_labels_own_standardization(pipeline, pid, name, note):
    assert _blob_row(pipeline, pid, name)["standardization_note"] == note


@pytest.mark.parametrize("pid, name, note", [
    # The 11 products #198 releases: each label's own EGCG standard.
    ("231721", "Green Tea extract", "45% EGCG"),
    ("231722", "Green Tea decaffeinated extract", "45% EGCG"),
    ("59208", "Green Tea decaffeinated extract", "45% EGCG"),
    ("59553", "Green Tea decaffeinated extract", "45% EGCG"),
    ("278368", "Green Tea Leaf Extract", "94% EGCG"),
    ("33233", "Green Tea extract", "94% EGCG"),
    ("33246", "Green Tea extract", "94% EGCG"),
    ("37250", "Green Tea extract", "94% EGCG"),
    ("294047", "Green Tea Leaf Extract", "23% EGCG"),
    ("309484", "Green Tea Leaf Extract", "70% EGCG"),
    ("330014", "Green Tea Leaf Extract", "50% EGCG"),
])
def test_a_mapped_green_tea_row_keeps_its_labels_egcg(pipeline, pid, name, note):
    def contains_egcg(databases):
        databases["ingredient_quality_map"]["green_tea_extract"]["relationships"] = [
            {"type": "contains", "target_id": "egcg"}]
    row = _blob_row(pipeline, pid, name, contains_egcg)
    assert row["form_match_status"] != "unmapped"
    assert row["standardization_note"] == note


@pytest.mark.parametrize("text", [
    "standardized to 4–7% ginsenosides",    # en dash range
    "standardized to 4—7% ginsenosides",    # em dash range
    "standardized to 4-7% ginsenosides",    # hyphen range
])
def test_a_range_is_never_a_standardization_claim(text):
    from build_final_db import _compute_standardization_note
    assert _compute_standardization_note({"notes": text}) is None


@pytest.mark.parametrize("text, note", [
    # Label wordings of the same claims (rows 287462, 305203, 241706).
    ("standardized to contain 3% total rosavins and 1% salidroside", "3% rosavins"),
    ("min. 5% total withanolides", "5% withanolides"),
    ("standardized to (50 mg) 50% Epigallocatechin Gallate", "50% EGCG"),
    # Another compound keeps its own name, never the neighbouring marker
    # (curcumin is not curcuminoids; salidrosides are not rosavins).
    ("95% Curcumin = 150 mg", "95% curcumin"),
    ("3% Salidrosides", "3% salidrosides"),
])
def test_label_wordings_of_a_recognized_claim(text, note):
    from build_final_db import _compute_standardization_note
    assert _compute_standardization_note({"notes": text}) == note
