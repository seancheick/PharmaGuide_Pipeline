"""Japanese star anise is a toxic plant with its own high-risk entry.

Illicium anisatum (GSRS UNII 96MVO223I9 "ILLICIUM ANISATUM WHOLE", UMLS C0949938)
contains the neurotoxin anisatin (PMID 22484123). FDA advisory P03-67 (2003)
calls it long recognized as toxic, not GRAS and fit for decorative use only.
No current prohibition was found (EU Decision 2002/75/EC ended 2003-08-11), so it is
high_risk, not banned. A row naming it used to stay unmapped with no warning.

Chinese star anise (Illicium verum, botanical star_anise) is a different,
GRAS species and must never match. GSRS returns the STAR ANISE record for a
"Japanese star anise" name search, so identity is pinned here, not looked up.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"
ENTRY_ID = "HIGH_RISK_JAPANESE_STAR_ANISE"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(name, group="Star Anise") -> dict:
        # Real label 252910 (BulkSupplements Star Anise Extract 500 mg, DSLD group "Star Anise")
        # with its one row renamed.
        raw = copy.deepcopy(json.loads((FIXTURES / "star_anise_252910_raw.json").read_text()))
        if name is not None:
            raw["ingredientRows"][0].update(name=name, ingredientGroup=group)
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        from scoring_v4.scored_artifact import build_scored_artifact
        return {"enriched": enriched, "scored": build_scored_artifact(copy.deepcopy(enriched))}

    return run


def _entry():
    rows = json.loads((DATA / "banned_recalled_ingredients.json").read_text())["ingredients"]
    return next(r for r in rows if r["id"] == ENTRY_ID)


def _banned_ids(enriched):
    return {s.get("banned_id") for s in enriched["contaminant_data"]["banned_substances"]["substances"]}


def test_entry_identity_and_status():
    entry = _entry()
    assert entry["status"] == "high_risk" and entry["ban_context"] == "substance"
    assert entry["external_ids"] == {"unii": "96MVO223I9"}
    assert entry["cui"] == "C0949938"
    assert entry["gsrs"]["substance_name"] == "ILLICIUM ANISATUM WHOLE"
    names = {a.lower() for a in entry["aliases"]}
    assert "illicium anisatum" in names and "japanese star anise" in names
    # Agent source-content review; no clinician reviewed this entry.
    assert entry["review"]["reviewed_by"] == "claude-audit (not clinician-reviewed)"
    # The edible species and its bare name never name this entry.
    assert not names & {"star anise", "chinese star anise", "illicium verum", "badian"}


@pytest.mark.parametrize("group", ["Star Anise", None])
@pytest.mark.parametrize("name", ["Japanese Star Anise", "Illicium anisatum", "Illicium religiosum"])
def test_a_row_naming_japanese_star_anise_is_flagged_high_risk(pipeline, name, group):
    # DSLD may file the toxic species under the edible species' group; the name still decides.
    out = pipeline(name, group or name)
    assert ENTRY_ID in _banned_ids(out["enriched"])
    rows = out["enriched"]["ingredient_quality_data"]["ingredients"]
    assert all(r.get("canonical_id") != "star_anise" for r in rows)
    # A single-ingredient label has no scorable active, so quality is not scored; safety still is.
    assert out["scored"]["product_safety_status"] == "caution"


@pytest.mark.parametrize("name", [None, "Chinese Star Anise", "Illicium verum fruit extract"])
def test_chinese_star_anise_is_never_flagged(pipeline, name):
    out = pipeline(name)
    assert ENTRY_ID not in _banned_ids(out["enriched"])
    rows = out["enriched"]["ingredient_quality_data"]["ingredients"]
    assert [r["canonical_id"] for r in rows] == ["star_anise"]
    assert out["scored"]["product_safety_status"] == "no_known_catalog_concern"
