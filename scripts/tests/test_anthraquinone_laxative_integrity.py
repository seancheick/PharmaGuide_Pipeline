"""Anthraquinone (hydroxyanthracene) stimulant laxatives live in banned_recalled.

Sean's rule (2026-09-25): a high-risk ingredient belongs only in
banned_recalled_ingredients.json, where its status drives the verdict and the
B0 penalty. Before this, Cape aloe (Aloe ferox) matched nothing and shipped
SAFE with a full safety pillar (dsld 267819), while cascara, removed from OTC
laxative use by the same FDA rule (67 FR 31125), shipped CAUTION.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3

DATA = Path(__file__).resolve().parents[1] / "data"
BANNED = {
    e["id"]: e
    for e in json.loads((DATA / "banned_recalled_ingredients.json").read_text())["ingredients"]
}


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _matches(enricher, name, banned_id, section="active"):
    row = {"name": name, "standardName": name, "_source_section": section}
    result = enricher._check_banned_substances([row])
    return [s for s in result.get("substances", []) if s.get("banned_id") == banned_id]


def test_aloe_latex_entry_is_high_risk_with_verified_identity():
    entry = BANNED["RISK_ALOE_LATEX"]
    assert entry["status"] == "high_risk"
    assert entry["match_mode"] == "active"
    assert entry["external_ids"]["unii"] == "V5VD430YW9"  # GSRS "ALOE" [USP], latex of A. vera or A. ferox
    assert entry["cui"] == "C4760748"  # UMLS "Cape Aloes"; the corpus matches are all Aloe ferox
    urls = {r.get("url") for r in entry["references_structured"]}
    assert "https://doi.org/10.2903/j.efsa.2018.5090" in urls
    assert any("02-11510" in (u or "") for u in urls)  # 67 FR 31125
    # The EU General Court annulled the Aloe-leaf listing of Reg 2021/468 on
    # 2024-11-13 (T-189/21); the Commission's appeal C-38/25 P is pending, so the
    # EU position is contested, not a settled ban. Consumer copy must not claim one.
    eu = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "EU"]
    assert eu and eu[0]["status"] == "under_review"
    assert "T-189/21" in eu[0]["notes"] and "C-38/25" in eu[0]["notes"]
    for field in ("safety_warning", "safety_warning_one_liner"):
        assert "EU" not in entry[field], field


@pytest.mark.parametrize(
    "label",
    ["Aloe ferox", "Cape aloe", "Cape aloes", "Aloe latex", "Aloe capensis", "Bitter aloe",
     "Aloe ferox leaf juice powder"],
)
def test_cape_aloe_and_aloe_latex_labels_match_exactly(enricher, label):
    hits = _matches(enricher, label, "RISK_ALOE_LATEX")
    assert hits, f"{label!r} should match RISK_ALOE_LATEX"
    assert hits[0]["match_type"] in {"exact", "alias"}  # B0 scores exact/alias only
    assert hits[0]["status"] == "high_risk"


@pytest.mark.parametrize(
    "label",
    [
        "Aloe vera",
        "Aloe vera gel",
        "Organic Aloe Vera Inner Leaf Gel 200:1 Concentrate",
        "Aloe vera inner leaf juice",
        "Aloe vera (Aloe barbadensis) extract",
        "88% organic whole leaf aloe vera",
        "Aloe polysaccharides",
        "Aloe Polymax+",
        "Aloe ferox gel",
        "Aloe ferox inner leaf gel",
    ],
)
def test_aloe_gel_and_unspecified_aloe_vera_do_not_match(enricher, label):
    assert not _matches(enricher, label, "RISK_ALOE_LATEX"), label


def test_cape_aloe_gets_us_caution_not_block_or_quarantine():
    from scoring_v4.gate_safety import evaluate_safety_gate

    entry = BANNED["RISK_ALOE_LATEX"]
    assert entry["policy_verification_status"] == "verified"
    assert any(j.get("jurisdiction_code") == "US" for j in entry["jurisdictions"])
    result = evaluate_safety_gate({
        "dsld_id": "clinical-RISK_ALOE_LATEX",
        "activeIngredients": [{"name": "Aloe ferox", "standardName": "Aloe ferox"}],
    })
    assert result.verdict == "CAUTION"  # the EU prohibition is advisory for the US catalog
    assert result.quarantine_required is False


def test_aloe_as_trace_flavoring_inactive_is_not_penalized(enricher):
    # 21 CFR 172.510 lists aloe (A. barbadensis, A. ferox) as a natural flavoring substance.
    assert BANNED["RISK_ALOE_LATEX"]["inactive_policy"] == "excipient_acceptable"
    assert not _matches(enricher, "Cape aloe", "RISK_ALOE_LATEX", section="inactive")


# --- Senna (Sean 2026-09-25: one owner; ADD_SENNA leaves harmful_additives) ---

HARMFUL_IDS = {
    e["id"]
    for e in json.loads((DATA / "harmful_additives.json").read_text())["harmful_additives"]
}


def test_senna_is_a_watchlist_entry_with_one_owner():
    entry = BANNED["WATCH_SENNA"]
    assert entry["status"] == "watchlist"
    assert entry["external_ids"]["unii"] == "AK7JF626KX"  # GSRS SENNA ALEXANDRINA LEAF
    assert entry["cui"] == "C0330722"  # UMLS Senna alexandrina
    assert entry.get("rxcui") is None  # RxNav 237929 returns an empty record
    urls = {r.get("url") for r in entry["references_structured"]}
    assert "https://doi.org/10.2903/j.efsa.2024.8766" in urls
    codes = {j.get("jurisdiction_code") for j in entry["jurisdictions"]}
    assert {"US", "EU"} <= codes
    assert "ADD_SENNA" not in HARMFUL_IDS


@pytest.mark.parametrize(
    "label",
    ["Senna", "Senna leaf extract", "Senna Leaf", "Sennosides", "Senna alexandrina leaf",
     "Cassia angustifolia"],
)
def test_senna_labels_match_exactly(enricher, label):
    hits = _matches(enricher, label, "WATCH_SENNA")
    assert hits, f"{label!r} should match WATCH_SENNA"
    assert hits[0]["match_type"] in {"exact", "alias"}
    assert hits[0]["status"] == "watchlist"


@pytest.mark.parametrize(
    "label",
    ["Coffee senna", "Senna occidentalis", "Cassia occidentalis", "Cassia bark", "Cassia cinnamon"],
)
def test_other_cassia_species_do_not_match_senna(enricher, label):
    assert not _matches(enricher, label, "WATCH_SENNA"), label


def test_senna_gets_us_caution_and_trace_flavoring_is_not_penalized(enricher):
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate({
        "dsld_id": "clinical-WATCH_SENNA",
        "activeIngredients": [{"name": "Senna leaf extract", "standardName": "Senna leaf extract"}],
    })
    assert result.verdict == "CAUTION"
    assert result.quarantine_required is False
    # 21 CFR 172.510 lists Senna, Alexandria (Cassia acutifolia) as a natural flavoring substance.
    assert BANNED["WATCH_SENNA"]["inactive_policy"] == "excipient_acceptable"
    assert not _matches(enricher, "Senna", "WATCH_SENNA", section="inactive")


# --- Cape aloe interaction rule (EMA/HMPC/625788/2015 sections 4.3-4.6; NCCIH) ---

EMA_ALOE = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-"
    "aloe-barbadensis-mill-and-aloe-various-species-mainly-aloe-ferox-mill-and-its-hybrids-folii-succus-siccatus_en.pdf"
)
# Wrong-topic PMIDs found on sibling laxative rules: a cascaroside chromatography
# paper and a Cassiae Semen (cassia seed) review. They must not spread.
GHOST_PMID_URLS = {
    "https://pubmed.ncbi.nlm.nih.gov/32876395/",
    "https://pubmed.ncbi.nlm.nih.gov/36702448/",
}


def test_cape_aloe_interaction_rule_follows_the_ema_monograph():
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    matching = [r for r in rules if r.get("subject_ref", {}).get("canonical_id") == "aloe_ferox"]
    assert len(matching) == 1  # one rule per ingredient
    rule = matching[0]
    conditions = {c["condition_id"]: c for c in rule["condition_rules"]}
    drugs = {d["drug_class_id"]: d for d in rule["drug_class_rules"]}
    assert set(conditions) == {"pregnancy", "kidney_disease", "liver_disease"}
    assert set(drugs) == {"cardiac_glycosides", "antiarrhythmics", "thiazide_diuretics"}
    assert conditions["pregnancy"]["severity"] == "contraindicated"
    assert drugs["cardiac_glycosides"]["severity"] == "avoid"
    preg = rule["pregnancy_lactation"]
    assert preg["pregnancy_category"] == "contraindicated"
    assert preg["lactation_category"] == "contraindicated"
    subs = [*rule["condition_rules"], *rule["drug_class_rules"], preg]
    for sub in subs:
        assert sub["sources"], sub
        assert not GHOST_PMID_URLS & set(sub["sources"])
    assert EMA_ALOE in drugs["cardiac_glycosides"]["sources"]
    assert EMA_ALOE in preg["sources"]


# --- Frangula bark (EU Annex III Part C; EFSA 2024 e8766) ---

def test_frangula_is_a_watchlist_entry_with_verified_identity():
    entry = BANNED["WATCH_FRANGULA"]
    assert entry["status"] == "watchlist"
    assert entry["external_ids"]["unii"] == "S2D77IH61R"  # GSRS FRANGULA ALNUS BARK
    assert entry["cui"] == "C0080354"  # UMLS Frangula
    urls = {r.get("url") for r in entry["references_structured"]}
    assert "https://doi.org/10.2903/j.efsa.2024.8766" in urls
    eu = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "EU"]
    assert eu and eu[0]["status"] == "under_review"


@pytest.mark.parametrize(
    "label",
    ["Frangula", "Frangula bark", "Frangula bark extract", "Rhamnus frangula", "Frangula alnus",
     "Alder buckthorn bark"],
)
def test_frangula_labels_match_exactly(enricher, label):
    hits = _matches(enricher, label, "WATCH_FRANGULA")
    assert hits, f"{label!r} should match WATCH_FRANGULA"
    assert hits[0]["match_type"] in {"exact", "alias"}


@pytest.mark.parametrize(
    "label",
    # Bare "buckthorn" is ambiguous (Frangula alnus, Rhamnus cathartica, or sea
    # buckthorn berry), so it stays unmatched until the label names the species.
    ["Buckthorn", "Buckthorn bark extract", "wild crafted Buckthorn", "Sea Buckthorn",
     "Sea Buckthorn Berry Fruit Powder"],
)
def test_ambiguous_buckthorn_labels_do_not_match_frangula(enricher, label):
    assert not _matches(enricher, label, "WATCH_FRANGULA"), label
