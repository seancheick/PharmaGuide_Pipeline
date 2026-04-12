"""
Codex Bug #2: parent_fallback_report captures transient intermediate matching
attempts that are later overridden by a better match. Demonstrated with
Pure Encapsulations Devil's Claw products that use a curly apostrophe
(U+2019) in their ingredient label.

Expected final state:
    matched_form = "devil's claw standardized (harpagoside)"  (bio_score 9, score 12)

Observed bug BEFORE fix:
    matched_form correctly resolves to the harpagoside form (score 12), BUT
    `_parent_fallback_details` still contains a spurious row:
        canonical_id = devils_claw
        fallback_form_name = "devil's claw (unspecified)"
    because an inner matching attempt inside `_match_quality_map` emitted the
    telemetry row before the outer multi-form / form-extraction path overrode
    the result.

Fix: the telemetry append must be gated on the FINAL enriched outcome, not on
an intermediate `best` candidate inside `_match_quality_map`. Specifically,
emit a parent_fallback_details row only when the per-ingredient quality_entry
actually lands on the fallback form name — i.e., when the enricher could not
upgrade the match to a real form via any subsequent path.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
BATCH_PATH = (
    SCRIPTS_DIR
    / "products"
    / "output_Pure_Encapsulations"
    / "cleaned"
    / "cleaned_batch_2.json"
)


def _load_curly_devils_claw_product(product_id: str) -> dict:
    """Load the exact Pure Encapsulations curly-apostrophe Devil's Claw product."""
    if not BATCH_PATH.exists():
        pytest.skip(f"Fixture batch not available at {BATCH_PATH}")
    with open(BATCH_PATH) as f:
        data = json.load(f)
    products = data if isinstance(data, list) else [data]
    for p in products:
        if str(p.get("id")) == product_id:
            return p
    pytest.skip(f"Product {product_id} not found in {BATCH_PATH}")


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


class TestParentFallbackFinalStateGuard:
    @pytest.mark.parametrize("product_id", ["185102", "185106"])
    def test_curly_apostrophe_devils_claw_final_state_is_harpagoside(
        self, enricher, product_id
    ):
        """
        Devil's Claw with a curly apostrophe and Harpagosides analyte must
        finalize on the harpagoside-standardized form (not the fallback).
        """
        enricher._parent_fallback_details = []
        enricher._form_fallback_details = []

        product = _load_curly_devils_claw_product(product_id)
        enriched, errors = enricher.enrich_product(product)

        scorable = (
            enriched.get("ingredient_quality_data") or {}
        ).get("ingredients_scorable") or []
        dc_rows = [
            row
            for row in scorable
            if "devil" in (row.get("name") or "").lower()
            or "harpago" in (row.get("name") or "").lower()
        ]
        assert dc_rows, (
            f"Expected a scorable Devil's Claw row in product {product_id}"
        )
        for row in dc_rows:
            assert row.get("matched_form") == "devil's claw standardized (harpagoside)"
            assert row.get("bio_score") == 9.0
            assert row.get("score") == 12.0

    @pytest.mark.parametrize("product_id", ["185102", "185106"])
    def test_no_transient_parent_fallback_telemetry_emitted(
        self, enricher, product_id
    ):
        """
        Regression guard for Codex Bug #2: when the final enriched row lands
        on a real form (not the fallback form name), NO parent_fallback_details
        entry should be appended — the earlier intermediate append was transient
        and must not leak into the report.
        """
        enricher._parent_fallback_details = []
        enricher._form_fallback_details = []
        # Reset the counter so we can assert both the list and the counter
        enricher.match_counters["parent_fallback_count"] = 0

        product = _load_curly_devils_claw_product(product_id)
        enricher.enrich_product(product)

        dc_parent_rows = [
            p
            for p in enricher._parent_fallback_details
            if p.get("canonical_id") == "devils_claw"
        ]
        assert len(dc_parent_rows) == 0, (
            f"Expected 0 transient devils_claw parent_fallback rows for product "
            f"{product_id}; got {dc_parent_rows}"
        )
