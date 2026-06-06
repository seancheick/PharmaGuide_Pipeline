"""Phase 0 — every v4 scored artifact carries a provenance stamp.

So an audit or a future score dispute can reconstruct exactly what produced a
score: engine version, classification-schema version, and the version+fingerprint
of every config rubric consumed. Must be present even on BLOCKED/NOT_SCORED rows.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "scoring_v4"))

_REQUIRED = {
    "scoring_engine_version",
    "classification_schema_version",
    "config_versions",
    "module_route",
    "mode",
}


def _provenance(product):
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(product)
    return out["shadow_score_v4_breakdown"]["provenance"]


def test_scored_product_has_provenance_block():
    product = {
        "product_name": "Fish Oil",
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 800, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 600, "unit": "mg"},
        ]},
    }
    prov = _provenance(product)
    assert _REQUIRED <= set(prov.keys())
    assert prov["mode"] == "shadow"
    assert prov["scoring_engine_version"]
    assert prov["classification_schema_version"]
    # config fingerprint present + 16-hex
    omega = prov["config_versions"]["omega"]
    assert len(omega["fingerprint"]) == 16
    assert omega["schema_version"]


def test_empty_product_still_carries_provenance():
    """A malformed/empty product (NOT_SCORED path) must still be auditable."""
    prov = _provenance({})
    assert _REQUIRED <= set(prov.keys())
    assert prov["mode"] == "shadow"


def test_blocked_product_still_carries_provenance():
    """A safety-gate short-circuit must still be reproducible/auditable."""
    product = {
        "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                ]
            }
        },
    }
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    prov = out["shadow_score_v4_breakdown"]["provenance"]
    assert _REQUIRED <= set(prov.keys())
    assert prov["mode"] == "shadow"


def test_module_route_recorded_in_provenance():
    product = {
        "product_name": "Creatine Monohydrate 5 g",
        "primary_type": "amino_acid",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Creatine Monohydrate", "canonical_id": "creatine_monohydrate",
             "quantity": 5, "unit": "Gram(s)", "bio_score": 14},
        ]},
    }
    prov = _provenance(product)
    assert prov["module_route"] in {"generic", "probiotic", "omega", "multi_or_prenatal", "sports"}
