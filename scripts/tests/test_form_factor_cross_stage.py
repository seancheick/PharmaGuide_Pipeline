"""SP-3 C4 — form_factor_canonical contract across pipeline stages.

End-to-end contract: a product enters cleaning with `physicalState`,
the enricher writes `form_factor_canonical`, and every downstream
consumer (v4 router, completeness gate, multi/prenatal formulation,
build_final_db) reads the canonical id. Old enriched batches that
predate the field keep working via legacy fallback paths.

Synthetic raw → enriched-blob test (no need for shipped enriched
batches in the checkout). Verifies that:
  1. The enricher's `_collect_serving_basis_data` writes the canonical id.
  2. The completeness gate uses the canonical id.
  3. The multi/prenatal formulation gummy detector uses the canonical id.
  4. build_final_db._derive_serving_verb_and_noun uses the canonical id.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.gate_completeness import _form_factor as gate_form_factor
from scoring_v4.modules.multi_prenatal_formulation import _form_factor_text
from build_final_db import _derive_serving_verb_and_noun


@pytest.fixture(scope="module")
def enricher():
    """SupplementEnricherV3 instance for the helper-level cross-stage test.
    Bypasses __init__ to avoid loading 40 reference databases."""
    inst = SupplementEnricherV3.__new__(SupplementEnricherV3)
    inst._last_delivery_data = None
    inst.config = {"processing_config": {}}
    import logging
    inst.logger = logging.getLogger("test")
    return inst


# --- Canary 1: Softgel (the most-affected DSLD code, e0161) ---

def test_softgel_survives_clean_enrich_consumer_chain(enricher):
    """A softgel product enters the enricher with DSLD e0161 and the
    canonical id 'softgel' must survive to every downstream consumer."""
    # Stage 1: cleaned product (post-clean_dsld_data, pre-enrich)
    cleaned = {
        "physicalState": {
            "langualCode": "e0161",
            "langualCodeDescription": "Softgel Capsule",
        },
        "servingSizes": [{"servingSizeQuantity": 1, "servingSizeUnitOfMeasure": "softgel(s)"}],
        "statements": [],
        "userGroups": [],
    }

    # Stage 2: enrich writes form_factor_canonical
    enriched_serving = enricher._collect_serving_basis_data(cleaned)
    assert enriched_serving["form_factor_canonical"] == "softgel"
    assert enriched_serving["form_factor"] is not None  # legacy preserved
    enriched_blob = {
        "form_factor": enriched_serving["form_factor"],
        "form_factor_canonical": enriched_serving["form_factor_canonical"],
    }

    # Stage 3a: completeness gate consumes canonical
    assert gate_form_factor(enriched_blob) == "softgel"

    # Stage 3b: multi/prenatal formulation text includes canonical
    text = _form_factor_text(enriched_blob)
    assert "softgel" in text

    # Stage 4: build_final_db serving-verb derivation uses canonical
    verb, sing, plural = _derive_serving_verb_and_noun("ct", "softgel")
    assert verb, "must produce a serving verb"
    assert "softgel" in (sing + plural).lower(), (
        f"softgel verb derivation must mention softgel, got {sing!r}/{plural!r}"
    )


# --- Canary 2: Gummy (drives the multi/prenatal formulation penalty) ---

def test_gummy_survives_clean_enrich_consumer_chain(enricher):
    cleaned = {
        "physicalState": {
            "langualCode": "e0176",
            "langualCodeDescription": "Gummy or Jelly",
        },
        "servingSizes": [{"servingSizeQuantity": 2, "servingSizeUnitOfMeasure": "gummies"}],
        "statements": [],
        "userGroups": [],
    }
    enriched_serving = enricher._collect_serving_basis_data(cleaned)
    assert enriched_serving["form_factor_canonical"] == "gummy"

    blob = {
        "form_factor": enriched_serving["form_factor"],
        "form_factor_canonical": enriched_serving["form_factor_canonical"],
    }
    assert gate_form_factor(blob) == "gummy"
    assert "gummy" in _form_factor_text(blob)

    # Critical for multi/prenatal scoring: the gummy regex must fire on the
    # text blob since canonical id is alone enough to trigger the penalty.
    import re
    GUMMY_RE = re.compile(r"\b(gummy|gummies|chewable)\b")
    assert GUMMY_RE.search(_form_factor_text(blob))


# --- Canary 3: Backward-compat — old enriched blob without canonical field ---

def test_legacy_blob_without_canonical_still_works():
    """Pre-2026-05-21 enriched blob has only `form_factor`, not the
    canonical field. Every consumer falls back gracefully."""
    legacy_blob = {"form_factor": "capsule"}

    # Completeness gate: legacy fallback wins
    assert gate_form_factor(legacy_blob) == "capsule"

    # Formulation text blob still picks it up
    assert "capsule" in _form_factor_text(legacy_blob)

    # build_final_db: legacy text drives the serving verb
    verb, sing, plural = _derive_serving_verb_and_noun("ct", "capsule")
    assert verb
    assert "capsule" in (sing + plural).lower()


# --- Canary 4: Mixed disagreement — canonical disagrees with legacy ---

def test_canonical_wins_when_legacy_disagrees():
    """The pre-SP-3 enricher collapsed `Softgel Capsule` into legacy
    `form_factor: capsule`. After SP-3, the canonical is `softgel` and
    legacy is still `capsule`. The consumers must trust the canonical."""
    blob = {
        "form_factor": "capsule",          # legacy (pre-SP-3 enricher)
        "form_factor_canonical": "softgel", # new SP-3 canonical
    }
    # Completeness gate picks softgel
    assert gate_form_factor(blob) == "softgel"
    # Formulation text includes both — softgel is what matters for scoring
    text = _form_factor_text(blob)
    assert "softgel" in text


# --- Canary 5: Tea bag (text-driven canonical, no langual_code) ---

def test_tea_bag_text_only_canonicalizes(enricher):
    """DSLD `e0172` is 'Other (e.g. tea bag)' — that's the catch-all bucket.
    A product where the label text explicitly says 'Tea Bag' without the
    e0172 code should canonicalize to tea_bag via the text alias path."""
    cleaned = {
        "physicalState": {
            "langualCode": "",  # no DSLD code
            "langualCodeDescription": "Tea Bag",
        },
        "servingSizes": [],
        "statements": [],
        "userGroups": [],
    }
    result = enricher._collect_serving_basis_data(cleaned)
    assert result["form_factor_canonical"] == "tea_bag"
