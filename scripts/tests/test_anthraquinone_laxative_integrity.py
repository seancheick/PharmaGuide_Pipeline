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
     "Aloe ferox leaf juice powder", "Aloe vera latex", "Aloe barbadensis latex",
     "Non-decolorized aloe vera whole leaf extract"],  # known processing: anthraquinones retained (NCCIH)
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
        "Decolorized aloe vera whole leaf extract",  # a substring of a latex alias; carbon-treated
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
    matching = [r for r in rules if r.get("subject_ref", {}).get("canonical_id") == "RISK_ALOE_LATEX"]
    assert len(matching) == 1  # one rule per preparation
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


# --- Aloe latex preparation identity (Dr. Pham, signed answers 2026-11-12, section 2) ---
# The EU monograph EMA/HMPC/625788/2015 covers the dried leaf juice (latex) of Aloe barbadensis
# (Barbados aloes) and of Aloe ferox (Cape aloes). The rule was authored on the IQM species
# identity aloe_ferox, so Aloe vera latex, flagged RISK_ALOE_LATEX, met no digoxin finding while
# "Aloe ferox gel", an IQM aloe_ferox alias, met it. The rule now sits on the latex identity, whose
# negative terms keep inner-leaf gel out; whole leaf of unknown processing stays unasserted.

ALOE_LATEX_RULE = "RULE_IQM_ALOE_FEROX"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _aloe_rule() -> dict:
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    return next(r for r in rules if r["id"] == ALOE_LATEX_RULE)


def test_aloe_latex_rule_is_authored_on_the_latex_preparation_identity():
    rules = json.loads((DATA / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
    assert _aloe_rule()["subject_ref"] == {"db": "banned_recalled_ingredients", "canonical_id": "RISK_ALOE_LATEX"}
    # No second owner on the species identity: gel and latex of A. ferox share it.
    assert not [r["id"] for r in rules if r["subject_ref"].get("canonical_id") == "aloe_ferox"]


def test_every_cape_aloe_identity_name_except_gel_meets_the_latex_identity(enricher):
    """Moving the rule off the species identity must lose no latex row: every Aloe ferox name the
    ingredient map resolves, other than a gel, is a latex match."""
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())["aloe_ferox"]
    names = [name for form, entry in iqm["forms"].items() for name in [form, *(entry.get("aliases") or [])]]
    assert names
    for name in names:
        assert bool(_matches(enricher, name, "RISK_ALOE_LATEX")) is ("gel" not in name.lower()), name


@pytest.mark.parametrize(
    "name,group,reaches",
    [
        ("Aloe ferox", "Cape Aloe", True),  # the label as sold (267819, Aloe Latex 140 mg)
        ("Aloe vera latex", "Aloe", True),  # Barbados aloes: same monograph, flagged, met nothing
        ("Aloe barbadensis latex", "Aloe", True),
        ("Non-decolorized aloe vera whole leaf extract", "Aloe", True),  # processing known: latex retained
        ("Decolorized aloe vera whole leaf extract", "Aloe", False),
        # Held for Dr. Pham: a Cape aloe gel now meets no aloe rule (no corpus label names one).
        ("Aloe ferox gel", "Cape Aloe", False),  # inner-leaf gel is not the latex
        ("Aloe ferox inner leaf gel", "Cape Aloe", False),
        ("Aloe vera inner leaf gel", "Aloe", False),
        ("88% organic whole leaf Aloe vera", "Aloe", False),  # processing unknown: not asserted
    ],
)
def test_aloe_digoxin_finding_follows_the_preparation(enricher, name, group, reaches):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((FIXTURES / "aloe_latex_267819_raw.json").read_text())
    raw["ingredientRows"][0].update(name=name, ingredientGroup=group)
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    profile = enriched["interaction_profile"]
    fired = {alert["rule_id"] for alert in profile["ingredient_alerts"]}
    assert (ALOE_LATEX_RULE in fired) is reaches, (name, fired)
    assert ("cardiac_glycosides" in profile["drug_class_summary"]) is reaches, name


def test_aloe_digoxin_row_keeps_avoid_unsupervised_use_with_preparation_context():
    """Section 2: keep "avoid unsupervised use" with potassium-loss and preparation context. The
    monograph requires medical consultation and sets no dose or duration cutoff; the laxative
    itself is not said to make digoxin toxic."""
    rule = _aloe_rule()
    [digoxin] = [d for d in rule["drug_class_rules"] if d["drug_class_id"] == "cardiac_glycosides"]
    assert digoxin["severity"] == "avoid"
    assert digoxin["alert_headline"] == "Avoid unsupervised use with digoxin"
    body = digoxin["alert_body"]
    assert "potassium" in body and "without your prescriber's advice" in body
    assert "unsupervised prolonged" not in body
    assert "this laxative" not in body  # a whole-leaf extract need not be sold as a laxative
    action = digoxin["action"].lower()
    assert "do not use aloe latex products without your prescriber's advice" in action
    assert "which laxative suits you" not in action  # no source; assumes laxative use
    assert "have to consult a doctor before taking aloes concomitantly (4.4)" in digoxin["mechanism"]
    assert "no dose or duration that clears the combination" in digoxin["mechanism"]
    assert "inner-leaf gel" in digoxin["mechanism"]  # preparation context
    review = digoxin["clinical_review"]
    assert review["reviewer"] == "Dr. Pham"
    # Her words quoted, not paraphrased; the implementation is labelled agent work.
    assert "should not inherit it indiscriminately" in review["notes"]
    assert "should remain uncertain" in review["notes"]
    assert "Agent implementation, not reviewed by Dr. Pham" in review["notes"]
    assert "prepared by agent, not reviewed by Dr. Pham" in review["notes"]
    # The pregnancy row now reaches Barbados aloe latex too; its text must not name Cape aloe only.
    [pregnancy] = [c for c in rule["condition_rules"] if c["condition_id"] == "pregnancy"]
    assert pregnancy["mechanism"].startswith("Aloe latex (Cape or Barbados aloes)")
    assert rule["review_owner"].startswith(
        "Dr. Pham (signed answers 2026-11-12, section 2: keep 'avoid unsupervised use' on the cardiac-glycoside row"
    )
    assert rule["last_reviewed"] == "2026-11-12"


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


# --- Rhubarb root, Rheum palmatum / officinale (EU Annex III Part C; EFSA 2024) ---

def test_rhubarb_root_is_a_watchlist_entry_with_verified_identity():
    entry = BANNED["WATCH_RHUBARB_ROOT"]
    assert entry["status"] == "watchlist"
    assert entry["external_ids"]["unii"] == "G025DAL7CE"  # GSRS CHINESE RHUBARB ROOT (RHEUM PALMATUM)
    assert entry["cui"] == "C1090801"  # UMLS Rheum palmatum
    # 21 CFR 172.510 lists rhubarb root (R. officinale, R. palmatum) as a natural flavoring.
    assert entry["inactive_policy"] == "excipient_acceptable"


@pytest.mark.parametrize(
    "label",
    ["Turkey Rhubarb", "Turkey Rhubarb extract", "Turkey Rhubarb Root Extract", "Rhubarb Root Extract",
     "Rheum palmatum root", "Chinese rhubarb root", "Da huang"],
)
def test_rhubarb_root_labels_match_exactly(enricher, label):
    hits = _matches(enricher, label, "WATCH_RHUBARB_ROOT")
    assert hits, f"{label!r} should match WATCH_RHUBARB_ROOT"
    assert hits[0]["match_type"] in {"exact", "alias"}


@pytest.mark.parametrize(
    "label",
    # Rheum rhaponticum (ERr 731) is outside the EU Part C entry; bare "rhubarb"
    # can be the food stalk.
    ["ERr 731 Siberian Rhubarb (Rheum rhaponticum L.) extract", "Siberian rhubarb", "organic Rhubarb",
     "Rhubarb", "Rhubarb leaf"],
)
def test_other_rhubarb_labels_do_not_match(enricher, label):
    assert not _matches(enricher, label, "WATCH_RHUBARB_ROOT"), label
