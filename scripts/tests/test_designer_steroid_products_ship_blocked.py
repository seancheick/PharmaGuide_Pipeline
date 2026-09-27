"""A product carrying a verified unlawful designer steroid ships with its reason.

The Iron Legion labels (DSLD 33358, 33360, 33361) declare methyldiazinol,
2,17alpha-dimethyl-5alpha-androst-2-en-17beta-ol and 17alpha-ethyl-estr-5-ene-
3beta,17beta-diol. They matched only the steroid watchlist class record, whose
match needs individual review, so each scored as NOT_SCORED/CAUTION with an
unresolved active row and the export withheld the product: a scan found
nothing. Sean, 2026-09-27: verify each; a banned ingredient ships the product
blocked with the reason. Each compound is a synthetic steroid, not a lawful
dietary ingredient (FDA: bodybuilding products labelled as supplements
"illegally contain steroids"), with a Schedule III structural parent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


@pytest.mark.parametrize(
    "pid,banned_id",
    [
        (33358, "BANNED_METHYLDIAZINOL"),
        (33360, "BANNED_DIMETHANDROSTENOL"),
        (33361, "BANNED_NORETHANDRIOL"),
    ],
)
def test_the_designer_steroid_product_ships_blocked_with_its_reason(pipeline, pid, banned_id):
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"designer_steroid_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    scored = build_scored_artifact(enriched)
    assert scored["verdict"] == "BLOCKED"
    blob = build_detail_blob(enriched, scored)
    reasons = [w for w in blob["warnings"] if banned_id in json.dumps(w)]
    assert reasons and all(w.get("safety_warning_one_liner") or w.get("alert_headline") for w in reasons)
