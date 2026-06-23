"""Safety-lane recognition (2026-06, unmapped-triage safety pass).

Five unmapped DSLD safety labels routed to banned_recalled_ingredients.json with
LIVE-API-VERIFIED identifiers (PubChem CID/CAS, UMLS CUI, FDA UNII). Two are
reconciliations with EXISTING entries (the recognition probe showed germanium is
already high_risk and must NOT be upgraded to banned; the CBD drug-exclusion entry
already exists), three are net-new:

  - Germanium Ge-132 (organic)  -> alias-extend RISK_GERMANIUM (KEEP high_risk;
    the existing entry deliberately chose high_risk over banned despite the FDA
    import alert / fatal nephrotoxicity). Closes the "Ge-132" label gap.
  - Broad Spectrum Phytocannabinoids -> alias-add to BANNED_CBD_US (banned, FDA
    drug-exclusion). REAL safety gap: the bare label was slipping through unflagged.
  - Miroestrol      -> NEW high_risk (potent dual-ER phytoestrogen, Pueraria mirifica)
  - Ginkgolic Acid  -> NEW contaminant/watchlist (allergenic ginkgo impurity, <5 ppm spec)
  - Withaferin A    -> NEW watchlist (normal ashwagandha constituent; cytotoxic only
    in concentrated extracts — NOT high_risk, evidence does not support it)
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3

BANNED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json")


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def banned_by_id():
    with open(BANNED_PATH, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["ingredients"]}


def _safety_ids(enricher, label):
    """A dangerous label must surface a banned_recalled signal via EITHER path:
    the _check_banned_substances gate or the non-scorable recognition index."""
    ids = set()
    r = enricher._check_banned_substances([{"name": label, "standardName": label}])
    if r.get("found"):
        ids |= {s.get("banned_id") for s in r.get("substances", [])}
    rec = enricher._is_recognized_non_scorable(label, label)
    if rec and rec.get("recognition_source") == "banned_recalled_ingredients":
        ids.add(rec.get("matched_entry_id"))
    return ids


@pytest.mark.parametrize(
    "label,expected_id",
    [
        ("Bis-Beta Carboxyethyl Germanium Sesquioxide", "RISK_GERMANIUM"),
        ("Ge-132", "RISK_GERMANIUM"),
        ("Organic Germanium", "RISK_GERMANIUM"),
        ("Broad Spectrum Phytocannabinoids", "BANNED_CBD_US"),
        ("Miroestrol", "RISK_MIROESTROL"),
        ("Ginkgolic Acid", "CONTAM_GINKGOLIC_ACID"),
        ("Withaferin A", "WATCH_WITHAFERIN_A"),
    ],
)
def test_safety_label_is_flagged(enricher, label, expected_id):
    assert expected_id in _safety_ids(enricher, label), (
        f"{label!r} must surface safety entry {expected_id!r}; got {_safety_ids(enricher, label)}"
    )


def test_germanium_stays_high_risk_not_banned(banned_by_id):
    """Reconciliation guard: germanium is high_risk by deliberate precedent, NOT banned."""
    assert banned_by_id["RISK_GERMANIUM"]["status"] == "high_risk"


def test_miroestrol_entry_verified(banned_by_id):
    e = banned_by_id["RISK_MIROESTROL"]
    assert e["status"] == "high_risk" and e["entity_type"] == "ingredient"
    assert e["cui"] == "C3491692"                       # UMLS-verified miroestrol
    assert e["external_ids"]["cas"] == "2618-41-9"      # PubChem-verified
    assert e["external_ids"]["pubchem_cid"] == 165001
    assert "unii" not in e["external_ids"]              # governed null (no GSRS record)


def test_ginkgolic_acid_entry_verified(banned_by_id):
    e = banned_by_id["CONTAM_GINKGOLIC_ACID"]
    assert e["entity_type"] == "contaminant"            # impurity, not an intended ingredient
    assert e["cui"] == "C0675409"                       # UMLS-verified ginkgolic acid
    assert e["external_ids"]["cas"] == "22910-60-7"
    assert e["external_ids"]["pubchem_cid"] == 5281858


def test_withaferin_a_entry_verified(banned_by_id):
    e = banned_by_id["WATCH_WITHAFERIN_A"]
    assert e["status"] == "watchlist"                   # NOT high_risk — normal constituent
    assert e["cui"] == "C0078503"                       # UMLS-verified withaferin A
    assert e["external_ids"]["unii"] == "L6DO3QW4K5"    # GSRS-verified
    assert e["external_ids"]["cas"] == "5119-48-2"
    assert e["external_ids"]["pubchem_cid"] == 265237
