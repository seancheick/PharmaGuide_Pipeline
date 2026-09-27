"""A product whose active has only a non-banned safety match is scored and ships.

These labels were withheld from the catalog: the active row matched only a
high-risk, watchlist or additive safety record, which cannot supply a primary
identity, so the row stayed an unresolved score-active and the export refused
the product (a scan found nothing). Sean, 2026-09-27: anything that is not
banned or recalled must be scored to ship, keeping its safety warning. Each
row now reaches a verified identity; Life Extension Mix's salts were curated on
2026-09-27 so it scores. ALCAR arginate keeps its identity-only owner (no ALCAR form or dose credit).
They ship instead of being withheld.

Excipient substances (mannitol, polydextrose, calcium silicate) get no IQM
identity: the IQM has no section-scoped matching, so an IQM alias also claims
the inactive filler row and drops its additive record (13 Nutricost
electrolyte labels lost ADD_CALCIUM_SILICATE when tried).
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
    "pid,canonical_id,safety_id,status",
    [
        (241706, "7_keto_dhea", "BANNED_7_KETO_DHEA", "scored"),  # HUM Ripped Rooster "7-Keto"
        (307546, "7_keto_dhea", "BANNED_7_KETO_DHEA", "scored"),  # Jarrow 7-oxo-DHEA 3-acetate
        (182627, "citrus_bioflavonoids", "RISK_BITTER_ORANGE", "scored"),  # Life Extension Mix
        # ALCAR arginate keeps its identity-only owner: no ALCAR form or dose credit
        (328274, "OI_ACETYL_L_CARNITINE_ARGINATE", None, "scored"),
        (200891, "germanium", "RISK_GERMANIUM", "scored"),  # Jarrow Ge-132
        (241744, "silver", "ADD_COLLOIDAL_SILVER", "scored"),  # Double Wood colloidal silver
    ],
)
def test_the_product_ships_scored_and_keeps_its_safety_warning(pipeline, pid, canonical_id, safety_id, status):
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"safety_only_row_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    rows = enriched["ingredient_quality_data"]["ingredients"]
    assert canonical_id in {row.get("canonical_id") for row in rows}
    assert not [row["name"] for row in rows if row.get("identity_disposition") == "identity_conflict"]
    scored = build_scored_artifact(enriched)
    assert scored["quality_score_status"] == status
    blob = build_detail_blob(enriched, scored)
    if safety_id:
        assert safety_id in json.dumps(blob["warnings"] + blob.get("warnings_profile_gated", []))


def test_an_inactive_excipient_keeps_its_additive_record(pipeline):
    """Nutricost Electrolytes (306215) lists calcium silicate as an anti-caking
    agent; it must stay ADD_CALCIUM_SILICATE, never a calcium nutrient row."""
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / "inactive_additive_306215_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    hits = enriched["contaminant_data"]["harmful_additives"]["additives"]
    assert "ADD_CALCIUM_SILICATE" in {hit["additive_id"] for hit in hits}


@pytest.mark.parametrize(
    "pid,rule_id",
    [
        (241706, "RULE_BANNED_7KETO_DHEA_PREGNANCY"),
        (307546, "RULE_BANNED_7KETO_DHEA_PREGNANCY"),
        (182627, "RULE_BANNED_BITTER_ORANGE_HYPERTENSION"),
    ],
)
def test_a_row_answers_to_the_rules_of_its_safety_match(pipeline, pid, rule_id):
    """A row with an IQM identity and a safety match meets the interaction
    rules authored on the safety record, not only those on its IQM identity."""
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"safety_only_row_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    fired = {alert["rule_id"] for alert in enriched["interaction_profile"]["ingredient_alerts"]}
    assert rule_id in fired
