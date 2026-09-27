"""A product whose active has only a non-banned safety match is scored and ships.

These labels were withheld from the catalog: the active row matched only a
high-risk, watchlist or additive safety record, which cannot supply a primary
identity, so the row stayed an unresolved score-active and the export refused
the product (a scan found nothing). Sean, 2026-09-27: anything that is not
banned or recalled must be scored to ship, keeping its safety warning. Each
row now reaches a verified IQM identity. Three labels stay NOT_SCORED only
because other rows declare forms the IQM does not map yet
(disclosed_form_unmapped: Life Extension Mix salts, BHB salts, Seneactiv);
they now ship with their warnings instead of being withheld.
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
        (182627, "citrus_bioflavonoids", "RISK_BITTER_ORANGE", "not_scored"),  # Life Extension Mix
        (233404, "prebiotics", None, "not_scored"),  # Keto Brain: FiberSmart resistant starch
        (328274, "l_carnitine", None, "scored"),  # ALCAR arginate dihydrochloride (ALCAR form)
        (213508, "fiber", None, "scored"),  # GNC Hunger Support: Litesse polydextrose
        (295773, "calcium", None, "not_scored"),  # Transparent Labs Bulk: calcium silicate
        (252699, "mannitol", None, "scored"),  # BulkSupplements Mannitol
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
    if status != "scored":
        assert scored["strict_scoring_contract"]["findings"] == ["disclosed_form_unmapped"]
    blob = build_detail_blob(enriched, scored)
    if safety_id:
        assert safety_id in json.dumps(blob["warnings"] + blob.get("warnings_profile_gated", []))
