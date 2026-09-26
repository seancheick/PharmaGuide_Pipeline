"""The enricher's banned check and the v4 safety gate must read one label alike.

Regression for DSLD 311187 (BulkSupplements "Buckthorn Bark Extract"). The raw
row is named "Buckthorn Bark Extract" and declares its form as
"Frangula alnus Bark Extract". The cleaner maps it to Frangula; enrichment's
identity repair (``_project_repaired_identity_to_active_row``) then rewrites
the row to "Buckthorn Bark" before ``_collect_contaminant_data`` runs. The
enricher's banned check read only ``name`` / ``standardName``, so
``contaminant_data`` lost WATCH_FRANGULA, while the gate's resolver pass also
reads ``raw_source_text`` and ``forms[]`` and still matched it. The product
shipped verdict CAUTION with no B0 penalty and a 10/10 safety pillar that said
"No banned, recalled, or watchlisted ingredients".

The invariant pinned here is identity-independent: label evidence the gate
treats as a banned/recalled match is also a match in ``contaminant_data``,
which the safety pillar and the B0 penalty read. Which botanical "Buckthorn"
names is a separate curation decision and is deliberately not pinned.
"""

from __future__ import annotations

import copy
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

logging.disable(logging.CRITICAL)

# Minimal copy of the raw DSLD label 311187 (staging/brands/BulkSupplements).
BUCKTHORN_FRANGULA_FORM_RAW = {
    "id": 311187,
    "fullName": "Buckthorn Bark Extract",
    "brandName": "BulkSupplements.com",
    "servingSizes": [
        {
            "order": 1,
            "minQuantity": 750,
            "maxQuantity": 750,
            "minDailyServings": 1,
            "maxDailyServings": 3,
            "unit": "mg",
            "inSFB": True,
        }
    ],
    "productType": {"langualCode": "A1306", "langualCodeDescription": "Botanical"},
    "physicalState": {"langualCode": "E0162", "langualCodeDescription": "Powder"},
    "ingredientRows": [
        {
            "order": 1,
            "ingredientId": 332067,
            "name": "Buckthorn Bark Extract",
            "category": "botanical",
            "ingredientGroup": "Buckthorn",
            "uniiCode": None,
            "quantity": [
                {
                    "servingSizeOrder": 1,
                    "servingSizeQuantity": 750,
                    "operator": "=",
                    "quantity": 750,
                    "unit": "mg",
                    "servingSizeUnit": "mg",
                }
            ],
            "nestedRows": [],
            "alternateNames": [],
            "forms": [
                {
                    "order": 1,
                    "ingredientId": 332068,
                    "prefix": None,
                    "percent": None,
                    "name": "Frangula alnus Bark Extract",
                    "category": "botanical",
                    "ingredientGroup": "Buckthorn",
                    "uniiCode": None,
                }
            ],
        }
    ],
    "otheringredients": {"text": None, "ingredients": None},
}


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def pipeline(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4

    cleaned = EnhancedDSLDNormalizer().normalize_product(
        copy.deepcopy(BUCKTHORN_FRANGULA_FORM_RAW)
    )
    enriched, _issues = enricher.enrich_product(cleaned)
    return enriched, score_product_v4(enriched)


def _active_hits(enricher, row: dict) -> list:
    tagged = [{**row, "_source_section": "active", "_source_index": 0}]
    return enricher._check_banned_substances(tagged)["substances"]


def _contaminant_ids(enriched: dict) -> set:
    substances = (
        (enriched.get("contaminant_data") or {}).get("banned_substances") or {}
    ).get("substances") or []
    return {s.get("banned_id") for s in substances if isinstance(s, dict)}


def test_form_evidence_reaches_contaminant_data(pipeline) -> None:
    enriched, _scored = pipeline
    substances = enriched["contaminant_data"]["banned_substances"]["substances"]
    hits = [s for s in substances if s.get("banned_id") == "WATCH_FRANGULA"]
    assert hits, f"WATCH_FRANGULA missing from contaminant_data: {substances}"
    assert hits[0]["source_section"] == "active"
    # A strict exact/alias match: the B0 penalty only scores these.
    assert hits[0]["match_type"] in {"exact", "alias"}


def test_every_gate_resolver_hit_is_in_contaminant_data(pipeline) -> None:
    from scoring_v4.gate_safety import _iter_resolver_safety_hits

    enriched, _scored = pipeline
    gate_ids = {hit["matched_rule_id"] for hit in _iter_resolver_safety_hits(enriched)}
    assert gate_ids, "fixture no longer exercises the gate's label-evidence pass"
    assert gate_ids <= _contaminant_ids(enriched)


def test_safety_pillar_and_b0_agree_with_the_verdict(pipeline) -> None:
    _enriched, scored = pipeline
    assert scored["v4_verdict"] == "CAUTION"
    pillar = scored["quality_pillars_v4"]["safety_hygiene"]
    assert pillar["score"] == 0, pillar
    assert "watchlisted ingredient" in pillar["reason"], pillar["reason"]
    penalties = scored["v4_breakdown"]["module"]["dimensions"]["formulation"]["penalties"]
    assert penalties["B0_moderate_watchlist"] < 0, penalties


def test_rule_retired_for_the_role_is_not_a_hit(enricher) -> None:
    """ADD_SODIUM_TETRABORATE is retired for declared boron source forms; the
    gate ignores it (B0_RETIRED_POLICY_SIGNAL_IGNORED), so B0 must not see it."""
    row = {
        "name": "Boron",
        "standardName": "Boron",
        "raw_source_text": "Boron",
        "forms": [{"prefix": None, "name": "Sodium Tetraborate"}],
    }
    resolution = enricher._inactive_ingredient_resolver.resolve(
        raw_name="Sodium Tetraborate", role="active"
    )
    assert resolution.matched_rule_id == "ADD_SODIUM_TETRABORATE"
    assert "ADD_SODIUM_TETRABORATE" not in {
        s["banned_id"] for s in _active_hits(enricher, row)
    }


def test_regional_rule_in_a_form_is_not_a_b0_hit(enricher) -> None:
    """DSLD 59204: CONTAM_GINKGOLIC_ACID is EU-only, so the gate records a
    regional advisory, not CAUTION, and the pillar ignores it; B0 has no
    jurisdiction filter, so form evidence must not hand it one."""
    row = {
        "name": "Ginkgo biloba extract",
        "standardName": "Ginkgo Biloba",
        "raw_source_text": "Ginkgo biloba extract",
        "forms": [
            {"prefix": "std. to", "name": "Ginkgo Flavone Glycosides"},
            {"prefix": None, "name": "Ginkgolic Acid"},
        ],
    }
    resolution = enricher._inactive_ingredient_resolver.resolve(
        raw_name="Ginkgolic Acid", role="active"
    )
    assert resolution.matched_rule_id == "CONTAM_GINKGOLIC_ACID"
    assert "CONTAM_GINKGOLIC_ACID" not in {
        s["banned_id"] for s in _active_hits(enricher, row)
    }


def test_one_form_term_scores_one_entry(enricher) -> None:
    """DSLD 47815: a bitter-orange source form resolves to one rule, as in the
    gate, so two overlapping entries cannot double the B0 penalty."""
    row = {
        "name": "Citrus Bioflavonoid Complex",
        "standardName": "Citrus Bioflavonoids",
        "raw_source_text": "Citrus Bioflavonoid Complex",
        "forms": [{"prefix": None, "name": "Bitter Orange"}],
    }
    scored = [
        s["banned_id"] for s in _active_hits(enricher, row)
        if s["match_type"] in {"exact", "alias"}
    ]
    assert len(scored) == 1, scored
