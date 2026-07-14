"""_merge_blend_evidence must collapse the SAME proprietary blend that the
single-pass cleaning extractor emits twice — once as a 0-child header row and
once as the aggregated nested-children group.

Regression for Paradise Earth "Vitamin D3 + K2" (dsld 336897): the 0-child
header and 17-child body of "Nature's C Veggie Berry Blend" have distinct merge
dedupe keys (different nested_count), so both survived and B5 double-penalized
the blend. Fix: a post-merge consolidation pass groups by (name, mg_bucket) and
drops the 0-child header when a disclosed body exists, while keeping
genuinely-distinct same-name DISCLOSED blends separate (the both-children
B4-parity case in test_blend_merge_pipeline).
"""
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _blend(name, weight, children, source="cleaning"):
    return {
        "name": name,
        "total_weight": weight,
        "nested_count": len(children),
        "child_ingredients": [{"name": c} for c in children],
        "disclosure_level": "partial" if children else "none",
        "sources": [source],
        "hidden_count": 0,
    }


def test_same_name_weight_header_and_body_merge_keeping_children(enricher):
    header = _blend("Nature's C Veggie Berry Blend", 73, [])
    body = _blend("Nature's C Veggie Berry Blend", 73, [f"c{i}" for i in range(17)])
    merged = enricher._merge_blend_evidence([], [header, body])
    assert len(merged) == 1, f"same blend must collapse to one; got {[b['name'] for b in merged]}"
    assert len(merged[0].get("child_ingredients") or []) == 17, "survivor keeps the 17 children"


def test_detector_header_and_cleaning_body_merge(enricher):
    det = _blend("Green Juice Blend", 50, [], source="detector")
    clean = _blend("Green Juice Blend", 50, ["a", "b", "c"])
    merged = enricher._merge_blend_evidence([det], [clean])
    assert len(merged) == 1, "detector 0-child + cleaning rich-child = one blend"
    assert len(merged[0].get("child_ingredients") or []) == 3


def test_detector_category_name_uses_matched_label_for_header_body_merge(enricher):
    detector = _blend("General Proprietary Blends", None, [], source="detector")
    detector["evidence"] = {"matched_text": "Proprietary Blend"}
    cleaning = _blend(
        "Proprietary Blend",
        None,
        ["Lactobacillus gasseri KS-13", "Bifidobacterium longum MM-2"],
    )

    merged = enricher._merge_blend_evidence([detector], [cleaning])

    assert len(merged) == 1
    assert merged[0]["name"] == "Proprietary Blend"
    assert len(merged[0].get("child_ingredients") or []) == 2


def test_distinct_blends_stay_separate(enricher):
    a = _blend("Adaptogen Blend", 100, ["x"])
    b = _blend("Antioxidant Blend", 100, ["y"])
    merged = enricher._merge_blend_evidence([], [a, b])
    assert len(merged) == 2, "genuinely different blends must not merge"
