#!/usr/bin/env python3
"""Percentile category data-file schema tests.

The inference tests that lived here were RETIRED in consolidation Phase 0b
(SUPP_TYPE_CONSOLIDATION_PLAN.md §9). They exercised
`SupplementEnricherV3._infer_percentile_category`, an independent decision
engine that scored product-name tokens, canonical ingredients and form factor
against this file's `classification_rules` — in parallel with, and disagreeing
with, `classify_supplement` on 56.2% of the corpus. The enricher now projects
the canonical taxonomy instead (`_decorate_percentile_category`), so the engine
those tests covered no longer exists.

Their clinical intent was PORTED, not dropped: "a green tea capsule is not a
greens powder", "whey is a protein powder", and the greens-superfood positive
are now asserted end to end against the canonical taxonomy in
`test_percentile_category_decorator.py::test_cohort_intent_survives_under_one_brain`.

What remains here guards the DATA FILE's shape. The file is still loaded and is
still checked by db_integrity_sanity_check, but its `classification_rules` and
its 9 curated `categories` labels are now unread by production —
see the Phase 5 dead-data note in the plan.
"""

import json
from pathlib import Path


class TestPercentileCategorySchema:
    def test_percentile_categories_schema_shape(self):
        path = Path(__file__).parent.parent / "data" / "percentile_categories.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert isinstance(data.get("_metadata"), dict)
        assert data["_metadata"].get("schema_version") == "5.0.0"
        assert isinstance(data.get("categories"), dict)
        assert isinstance(data.get("classification_rules"), dict)

        fallback_ids = [
            category_id
            for category_id, category_def in data["categories"].items()
            if isinstance(category_def, dict) and category_def.get("is_fallback")
        ]
        assert len(fallback_ids) == 1

