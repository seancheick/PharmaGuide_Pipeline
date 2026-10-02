"""Per-entry identifier integrity tests for banned_recalled_ingredients.json.

Pattern mirrors scripts/tests/test_iqm_identifier_integrity.py: one assertion
per Wave 9.C correction, content-verified against UMLS / RxNav / PubChem
before the entry is written.

Each test locks the entry's stored identifier to the clinician-authorized
value (here: agent-authorized per the user's 2026-05-28 direction to
"use api tools and deep research to validate and advance until we
complete" on banned_recalled_ingredients.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BR_PATH = REPO_ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"


@pytest.fixture(scope="module")
def banned_recalled() -> list[dict]:
    payload = json.loads(BR_PATH.read_text())
    return payload["ingredients"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"banned_recalled_ingredients.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.C.3 — HIGH-severity CUI/RxCUI corrections (3 entries)
# --------------------------------------------------------------------------- #


def test_banned_igf1_cui_is_canonical_substance(banned_recalled):
    """BANNED_IGF1 must use C0021665 ('Insulin-Like Growth Factor I',
    semantic types Amino Acid/Peptide/Protein, Biologically Active Substance).
    C5674892 resolved to 'primary insulin-like growth factor-1 (IGF-1)
    deficiency' (Disease or Syndrome) — the disease state, not the protein.
    Caught by the strict-mode Disease guard 2026-05-28."""
    entry = _find(banned_recalled, "BANNED_IGF1")
    assert entry["cui"] == "C0021665", (
        "BANNED_IGF1.cui must be C0021665 (the IGF-1 protein substance), "
        "not C5674892 (primary IGF-1 deficiency, a disease state)."
    )


def test_banned_dhea_cui_is_canonical_prasterone(banned_recalled):
    """BANNED_DHEA must use C0011185 ('prasterone' — the UMLS preferred
    name for Dehydroepiandrosterone, semantic types Steroid /
    Pharmacologic Substance). C0011260 was not found in UMLS at all
    (deprecated or never-issued CUI; live API returned no record on
    2026-05-28). Caught by strict-mode unresolvable guard."""
    entry = _find(banned_recalled, "BANNED_DHEA")
    assert entry["cui"] == "C0011185", (
        "BANNED_DHEA.cui must be C0011185 (prasterone / DHEA), not "
        "C0011260 (which UMLS does not resolve to any concept)."
    )


def test_add_colloidal_silver_rxcui_cleared_to_null(banned_recalled):
    """ADD_COLLOIDAL_SILVER must NOT carry rxcui '9785' — that RxCUI is
    deprecated in RxNav (/REST/rxcui/9785/properties.json returned 404
    on 2026-05-28; live RxNav name-search for 'colloidal silver' returns
    no current RxCUI). Cleared to null with rxcui_note documenting the
    verification, same pattern as the IQM Batch 3 bilberry/goldenseal/
    cryptoxanthin/sulforaphane clearances. The cui (C0772313) and unii
    (3M4G523W1G) remain untouched — they are still valid identifiers."""
    entry = _find(banned_recalled, "ADD_COLLOIDAL_SILVER")
    assert entry.get("rxcui") is None, (
        "ADD_COLLOIDAL_SILVER.rxcui must be null (RxNav 404 on 9785 + no "
        "name-search match for colloidal silver). cui and unii remain valid."
    )
    assert entry.get("rxcui_note"), (
        "ADD_COLLOIDAL_SILVER must have an rxcui_note explaining the "
        "deprecation."
    )


def test_hm_cadmium_cui_is_canonical_substance(banned_recalled):
    """HM_CADMIUM must use C0006632 ('cadmium' — Hazardous or Poisonous
    Substance / Element, Ion, or Isotope). C0373557 was 'Cadmium
    measurement' (Laboratory Procedure) — the lab assay concept, not the
    element being banned/restricted. Caught by strict-mode 'resolved
    concept lacks substance semantic type' guard 2026-05-28."""
    entry = _find(banned_recalled, "HM_CADMIUM")
    assert entry["cui"] == "C0006632", (
        "HM_CADMIUM.cui must be C0006632 (the cadmium element/hazardous "
        "substance), not C0373557 (Cadmium measurement, a Laboratory "
        "Procedure concept)."
    )


def test_add_5a_hydroxy_laxogenin_unii_is_not_plain_laxogenin(banned_recalled):
    """ADD_5A_HYDROXY_LAXOGENIN names 5alpha-hydroxy-laxogenin, so it carries
    GSRS 844KE20WT5 (5.ALPHA.-HYDROXY LAXOGENIN; LAXOSTERONE; C27H42O5; CAS
    56786-63-1; InChIKey HCRGPOQBVFMZFY-PPCFKNSFSA-N = PubChem CID 69906537).
    HT7W184YG4 is plain LAXOGENIN (C27H42O4; CAS 1177-71-5; CID 10950057),
    which lacks the 5alpha-hydroxyl. It passed verify_unii only through the
    "laxogenin" alias. The gsrs block must describe the same record.
    Verified in GSRS and PubChem 2026-09-26."""
    entry = _find(banned_recalled, "ADD_5A_HYDROXY_LAXOGENIN")
    assert entry["external_ids"]["unii"] == "844KE20WT5"
    assert entry["gsrs"]["substance_name"] == "5.ALPHA.-HYDROXY LAXOGENIN"
    # The LAXOGENIN record's DSLD code (3987, 5 products) must not survive.
    assert entry["gsrs"]["dsld_count"] is None
    assert entry["gsrs"]["dsld_info_raw"] is None
    assert "HT7W184YG4" in json.dumps(entry["review"]["change_log"])


def test_add_n_phenethyl_dimethylamine_unii_is_the_amine_not_the_ketone(banned_recalled):
    """ADD_N_PHENETHYL_DIMETHYLAMINE is N,N-dimethylphenethylamine, so it
    carries GSRS I4C10U12C8 (N,N-DIMETHYL-2-PHENETHYLAMINE; N-PHENETHYL
    DIMETHYLAMINE; C10H15N; CAS 1126-71-2; InChIKey
    TXOFSCODFRHERQ-UHFFFAOYSA-N = PubChem CID 25125). G8WX4UG544 is
    2-(dimethylamino)-1-phenylethanone (C10H13NO; CAS 3319-03-7; CID 137890),
    a beta-keto compound. That name was also an alias here, which is how the
    wrong UNII passed verify_unii. Verified in GSRS and PubChem 2026-09-26."""
    entry = _find(banned_recalled, "ADD_N_PHENETHYL_DIMETHYLAMINE")
    assert entry["external_ids"]["unii"] == "I4C10U12C8"
    aliases = {a.lower() for a in entry["aliases"]}
    assert "2-(dimethylamino)-1-phenylethanone" not in aliases
    assert "G8WX4UG544" in json.dumps(entry["review"]["change_log"])


def test_add_cascara_sagrada_unii_is_the_bark_not_casanthranol(banned_recalled):
    """ADD_CASCARA_SAGRADA is cascara sagrada bark, so it carries GSRS
    4VBP01X99F (FRANGULA PURSHIANA BARK; CASCARA SAGRADA [MI]; CAS
    8015-89-2), the same UNII as IQM cascara_sagrada. 3SJ3U7J6V2 is
    Casanthranol, a purified anthranol-glycoside fraction of the bark
    (CAS 8024-48-4), a different material. Verified in GSRS 2026-09-25."""
    entry = _find(banned_recalled, "ADD_CASCARA_SAGRADA")
    iqm = json.loads(
        (REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json").read_text()
    )
    assert entry["external_ids"]["unii"] == "4VBP01X99F"
    assert iqm["cascara_sagrada"]["external_ids"]["unii"] == "4VBP01X99F"
    assert "3SJ3U7J6V2" in json.dumps(entry["review"]["change_log"])


def test_banned_tansy_cui_is_the_plant_not_a_flower_essence(banned_recalled):
    """BANNED_TANSY covers tansy herb and oil (Tanacetum vulgare), so its CUI
    is C0331409 'Tanacetum vulgare' (Plant; NCBI, MSH, SNOMEDCT_US; common
    name tansy). C1256219 is 'Tanacetum vulgare, flower essence'
    (Pharmacologic Substance; MTH/CHV/ALT atoms only), a flower-remedy
    preparation. Botanical siblings anchor to the Plant concept (e.g.
    BANNED_CALAMUS_ACORUS_CALAMUS, RISK_KRATOM_NATURAL). Verified in UMLS
    2026-09-26."""
    entry = _find(banned_recalled, "BANNED_TANSY")
    assert entry["cui"] == "C0331409"
    assert "C1256219" in json.dumps(entry["review"]["change_log"])


def test_add_5a_hydroxy_laxogenin_has_its_rxnorm_and_umls_anchors(banned_recalled):
    """5alpha-hydroxy-laxogenin has an RxNorm ingredient and a UMLS concept.
    RxNav 1801703 is an active IN named "5.alpha.-hydroxy laxogenin"; GSRS
    844KE20WT5 (this entry's UNII) lists RXCUI 1801703 as its PRIMARY code.
    UMLS C4276029 "5.alpha.-hydroxy laxogenin" (Organic Chemical,
    Pharmacologic Substance) holds that RXNORM atom. Searches for
    "5alpha-hydroxy laxogenin" missed it because UMLS spells the name with
    dotted ".alpha.". Plain laxogenin is a different concept (C0915797).
    The annotated null and its curated override were wrong. Verified in
    RxNav, GSRS and UMLS 2026-09-26."""
    entry = _find(banned_recalled, "ADD_5A_HYDROXY_LAXOGENIN")
    assert entry.get("rxcui") == "1801703"
    assert entry.get("cui") == "C4276029"
    assert "cui_status" not in entry and "cui_note" not in entry
    overrides = json.loads(
        (REPO_ROOT / "scripts" / "data" / "curated_overrides" / "cui_overrides.json").read_text()
    )
    assert overrides["5a-hydroxy laxogenin"]["cui"] == "C4276029"


def test_add_5a_hydroxy_laxogenin_cites_live_fda_sources(banned_recalled):
    """The entry cited "FDA Warning Letter 607248 (Andro Pharma LLC, 2020)"
    and a generic constituent-updates index. Both URLs returned HTTP 404 on
    2026-09-26; the Wayback Machine has no capture of any andro-pharma
    warning-letter URL, and no search found the letter. FDA's May 4, 2022
    letter to Performax Labs (622337) names "5a-Hydroxy-Laxogenin" and
    states 5-alpha-hydroxy-laxogenin is not a dietary ingredient; the May 9,
    2022 constituent update lists it among the cited ingredients."""
    entry = _find(banned_recalled, "ADD_5A_HYDROXY_LAXOGENIN")
    urls = [r.get("url") or "" for r in entry["references_structured"]]
    blob = json.dumps(entry["references_structured"])
    assert "andro-pharma" not in blob and "607248" not in blob
    assert "dietary-supplement-products-ingredients/constituent-updates" not in blob
    assert (
        "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
        "warning-letters/performax-labs-inc-622337-05042022"
    ) in urls
    assert (
        "https://www.fda.gov/food/hfp-constituent-updates/"
        "fda-sends-warning-letters-multiple-companies-illegally-selling-adulterated-dietary-supplements"
    ) in urls


def test_banned_ephedra_keeps_c0885298_with_a_note_on_its_name(banned_recalled):
    """BANNED_EPHEDRA keeps C0885298 (Sean, 2026-09-26). UMLS names it
    "Ephedra vulgaris preparation", but it is the drug-vocabulary ephedra
    ingredient concept (VANDF IN "EPHEDRA", MEDCIN "ephedra (medication)",
    CHV "ephedra herb medicine"). "Ephedra vulgaris" is a MeSH entry term
    now filed under D029790 Ephedra sinica. The cui_note keeps a later
    reviewer from reading the preferred name as a single-species claim."""
    entry = _find(banned_recalled, "BANNED_EPHEDRA")
    assert entry["cui"] == "C0885298"
    note = entry.get("cui_note") or ""
    assert "Ephedra vulgaris" in note and "VANDF" in note


def test_high_risk_chaparral_cui_is_larrea_tridentata(banned_recalled):
    """HIGH_RISK_CHAPARRAL's reason names Larrea tridentata, so its CUI is
    C0697139 'Larrea tridentata' (Plant; NCBI taxid 66636, MSH, NCI).
    C1050700 is 'Larrea divaricata' (NCBI taxid 108399), the South American
    L. divaricata Cav. ITIS treats the North American usage "Larrea divaricata
    auct. non Cav." as a misapplied name for L. tridentata, so the
    "larrea divaricata" alias stays as a label-matching term. Sean chose the
    species anchor 2026-09-26; verified in UMLS, NCBI, GBIF and ITIS."""
    entry = _find(banned_recalled, "HIGH_RISK_CHAPARRAL")
    assert entry["cui"] == "C0697139"
    assert "larrea divaricata" in {a.lower() for a in entry["aliases"]}
    assert "C1050700" in json.dumps(entry["review"]["change_log"])


def test_banned_ibutamoren_cites_a_live_fda_letter_not_the_andro_pharma_ghost(banned_recalled):
    """BANNED_IBUTAMOREN_MK677 cited "FDA Warning Letter 607248 (Andro Pharma
    LLC)" (andro-pharma-llc-607248-11102020) as its reference and its US
    jurisdiction source, with 2020-11-10 as both regulatory_date ("FDA ban
    effective") and effective_date. The URL returned HTTP 404 on 2026-09-26,
    the Wayback Machine has no capture of it, and no search found the letter.
    FDA Warning Letter 719339 (Musclepower Enterprise Ltd. dba MONSTER KING
    and GE LABS, CDER, 2025-12-12) says "GE Labs MK 677" is marketed as a
    dietary supplement and that ibutamoren is excluded from the dietary
    supplement definition under FD&C Act 201(ff)(3)(B)(ii). A letter dates
    FDA's statement, not when the exclusion took effect, so effective_date is
    null (Sean, 2026-09-26)."""
    entry = _find(banned_recalled, "BANNED_IBUTAMOREN_MK677")
    live = {k: v for k, v in entry.items() if k != "review"}
    blob = json.dumps(live)
    assert "607248" not in blob and "andro-pharma" not in blob.lower()
    assert "Andro Pharma" not in blob and "2020-11-10" not in blob
    urls = [r.get("url") for r in entry["references_structured"]]
    assert (
        "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
        "warning-letters/musclepower-enterprise-ltd-dba-monster-king-and-ge-labs-719339-12122025"
    ) in urls
    us = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "US"]
    assert len(us) == 1 and us[0]["effective_date"] is None
    assert "719339" in us[0]["source"]["citation"]
    assert entry["regulatory_date"] == "2025-12-12"
    assert entry["regulatory_date_label"] == "FDA warning letter"
    log = json.dumps(entry["review"]["change_log"])
    assert "607248" in log and "2020-11-10" in log


# Sean, 2026-09-26 (D10): an FDA warning letter, recall or advisory is not a
# ban. FDA never used "ban" for SARMs; it calls them unapproved new drugs (and,
# when labeled as supplements, excluded from the dietary supplement definition).
# No statute or DEA rule covers them (SARMs Control Acts S.2742/S.2895 were not
# enacted). Each record now dates and names the FDA document that names the
# compound. Receipts: scripts/audits/pending_items_20260926/research.md.
_WL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/"
SARM_PRIMARY_SOURCES = {
    "SARM_OSTARINE": ("2017-10-23", "FDA warning letter", _WL + "infantry-labs-llc-535333-10232017"),
    "SARM_LIGANDROL": ("2017-10-23", "FDA warning letter", _WL + "infantry-labs-llc-535333-10232017"),
    "SARM_ANDARINE": ("2017-12-13", "FDA warning letter", _WL + "dynamic-technical-formulations-535717-12132017"),
    "SARM_RAD140": ("2019-08-24", "FDA recall initiation date",
                    'https://api.fda.gov/drug/enforcement.json?search=recall_number:"D-0800-2020"'),
    "SARM_CARDARINE": ("2021-05-18", "FDA warning letter", _WL + "umbrella-612037-05182021"),
    "BANNED_S23": ("2025-12-12", "FDA warning letter", _WL + "prime-sports-nutrition-719433-12122025"),
    "BANNED_YK11": ("2025-12-12", "FDA warning letter", _WL + "titan-sarms-llc-719645-12122025"),
    "RECALLED_TITAN_SARMS_LLC": ("2025-12-12", "FDA warning letter", _WL + "titan-sarms-llc-719645-12122025"),
    "BANNED_IBUTAMOREN_MK677": ("2025-12-12", "FDA warning letter",
                                _WL + "musclepower-enterprise-ltd-dba-monster-king-and-ge-labs-719339-12122025"),
}


@pytest.mark.parametrize("entry_id", sorted(SARM_PRIMARY_SOURCES) + ["BANNED_SR9009"])
def test_sarm_records_state_what_fda_did_not_a_ban(banned_recalled, entry_id):
    entry = _find(banned_recalled, entry_id)
    live = json.dumps({k: v for k, v in entry.items() if k != "review"}).lower()
    for stale in ("ban effective", "banned in supplements", "fda banned", "fda warning: october 31, 2017",
                  "adulterated", "state_statute\", \"citation\": \"investigated", "clinical status"):
        assert stale not in live, (entry_id, stale)
    us = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "US"]
    assert len(us) == 1 and us[0]["effective_date"] is None, entry_id
    if entry_id in SARM_PRIMARY_SOURCES:
        date, label, url = SARM_PRIMARY_SOURCES[entry_id]
        assert (entry["regulatory_date"], entry["regulatory_date_label"]) == (date, label)
        assert url in [r.get("url") for r in entry["references_structured"]]
        assert us[0]["status"] == "not_lawful" and us[0]["source"]["url"] == url
        assert entry["policy_verification_status"] == "verified"


def _has_harm_source(entry) -> bool:
    import sys
    scripts = str(Path(__file__).resolve().parents[1])
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from scoring_v4.gate_safety import _harm_evidence_sources
    return bool(_harm_evidence_sources(entry))


def test_sr9009_has_no_fda_action_so_its_policy_stays_under_review(banned_recalled):
    """No fda.gov document names SR9009 (warning letters, recalls, Import Alert
    66-41 searched 2026-09-26); the 2017-10-31 date had no source. LEDGER Q58
    (Sean 2026-10-02): verified only as an "Unverified ingredient" on its human
    liver-injury case report, never as a US determination."""
    entry = _find(banned_recalled, "BANNED_SR9009")
    assert entry["regulatory_date"] is None and entry["regulatory_date_label"] is None
    [us] = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "US"]
    assert us["status"] == "under_review"
    assert entry["legal_status_enum"] == "under_review"
    assert entry.get("policy_verification_status") != "verified" or _has_harm_source(entry)


def test_titan_sarms_record_is_a_warning_letter_not_a_recall(banned_recalled):
    """Letter 719645 (CDER, 2025-12-12) calls research-labeled LGD-4033, RAD-140,
    S-4 and YK-11 unapproved new drugs under 505(a). No recall exists and the
    letter makes no dietary-supplement, adulteration or misbranding finding."""
    entry = _find(banned_recalled, "RECALLED_TITAN_SARMS_LLC")
    assert "recall" not in entry["safety_warning_one_liner"].lower()
    assert "fda_recall_url" not in json.dumps(entry["references_structured"])
    assert "unapproved new drugs" in entry["reason"]


def test_verified_sarm_policy_blocks_instead_of_quarantining():
    import sys
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST_OSTARINE", "fullName": "Ostarine", "status": "active",
        "form_factor": "capsule", "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": {"banned_substances": {"found": False, "substances": [], "safety_flags": []}},
        "activeIngredients": [{"name": "Ostarine", "standardName": "Ostarine", "raw_source_text": "Ostarine",
                               "forms": [], "mapped": True}],
        "inactiveIngredients": [],
        "ingredient_quality_data": {"total_active": 1, "ingredients_scorable": [
            {"name": "Ostarine", "canonical_id": "ostarine", "mapped": True, "quantity": 20.0, "unit": "mg"}]},
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED" and result.quarantine_required is False


# Register Q15 (2026-09-26, D10 standard): 36 more records carried "FDA ban
# effective". Each now dates and cites the government document that names the
# compound, labelled as what it is. Only ephedra (21 CFR 119.1), FD&C Red No. 2
# (1976 delisting) and titanium dioxide (EU 2022/63) are bans. Receipts:
# scripts/audits/pending_items_20260926/research.md Q15.
_ISDI = "https://www.fda.gov/food/information-select-dietary-supplement-ingredients-and-other-substances/"
_PEAK = _WL + "peak-nootropics-llc-aka-advanced-nootropics-557887-02052019"
_FR = "https://www.federalregister.gov/documents/"
Q15_PRIMARY_SOURCES = {
    "BANNED_14_BUTANEDIOL": ("1999-05-11", "FDA advisory publication date",
                             _FR + "2000/03/13/00-5925/schedules-of-controlled-substances-addition-of-gamma-hydroxybutyric-acid-to-schedule-i"),
    "BANNED_7_HYDROXYMITRAGYNINE": ("2025-06-25", "FDA warning letter", _WL + "hydroxie-llc-709661-06252025"),
    "BANNED_ARISTOLOCHIC_ACID": ("2000-07-06", "First FDA enforcement action",
                                 "https://www.accessdata.fda.gov/cms_ia/importalert_141.html"),
    "BANNED_BMPEA": ("2015-04-23", "FDA warning letter", _ISDI + "bmpea-dietary-supplements"),
    "BANNED_COMFREY_INTERNAL": ("2001-07-06", "FDA advisory publication date",
                                "https://www.fda.gov/food/dietary-supplements/dietary-supplement-ingredient-directory"),
    "BANNED_DMAA": ("2012-04-24", "FDA warning letter", _ISDI + "dmaa-products-marketed-dietary-supplements"),
    "BANNED_DMBA": ("2015-04-28", "FDA warning letter",
                    "https://www.fda.gov/food/hfp-constituent-updates/recent-fda-action-dietary-supplements-labeled-containing-dmba"),
    "BANNED_DMHA": ("2019-04-10", "FDA warning letter", _ISDI + "dmha-dietary-supplements"),
    "BANNED_EPHEDRA": ("2004-04-12", "FDA ban effective", "https://www.govinfo.gov/content/pkg/FR-2004-02-11/pdf/04-2912.pdf"),
    "BANNED_FDC_RED_2_AMARANTH": ("1976-02-12", "FDA ban effective",
                                  "https://www.govinfo.gov/content/pkg/FR-1976-02-10/pdf/FR-1976-02-10.pdf"),
    "BANNED_HIGENAMINE": ("2022-05-04", "FDA warning letter", _WL + "ironmag-labs-622504-05042022"),
    "BANNED_PHENIBUT": ("2019-04-10", "FDA warning letter", _ISDI + "phenibut-dietary-supplements"),
    "BANNED_PICAMILON": ("2015-11-30", "FDA warning letter",
                         "https://www.fda.gov/food/hfp-constituent-updates/recent-fda-action-dietary-supplements-labeled-containing-picamilon"),
    "BANNED_SIBUTRAMINE": ("2010-10-08", "FDA safety advisory published",
                           _FR + "2010/12/21/2010-31986/abbott-laboratories-inc-withdrawal-of-approval-of-a-new-drug-application-for-meridia"),
    "BANNED_TIANEPTINE": ("2018-11-07", "FDA warning letter", _WL + "ma-labs-llc-566831-11072018"),
    "BANNED_YELLOW_OLEANDER_RECENT": ("2024-01-26", "FDA advisory publication date",
                                      "https://www.fda.gov/food/alerts-advisories-safety-information/fda-issues-warning-about-certain-products-containing-toxic-yellow-oleander"),
    "BANNED_DYMETHAZINE": ("2017-06-05", "FDA warning letter", _WL + "hardcore-formulations-522783-06052017"),
    "NOOTROPIC_ADRAFINIL": ("2019-02-04", "FDA warning letter", _PEAK),
    "NOOTROPIC_ANIRACETAM": ("2019-02-04", "FDA warning letter", _PEAK),
    "NOOTROPIC_MODAFINIL": ("1999-01-27", "DEA scheduling effective",
                            _FR + "1999/01/27/99-1791/schedules-of-controlled-substances-placement-of-modafinil-into-schedule-iv"),
    "NOOTROPIC_OMBERACETAM": ("2019-02-04", "FDA warning letter", _PEAK),
    "NOOTROPIC_PHENYLPIRACETAM": ("2019-02-04", "FDA warning letter", _PEAK),
    "PEPTIDE_MELANOTAN_II": ("2007-08-30", "FDA warning letter",
                             "https://www.fda.gov/regulatory-information/electronic-reading-room/notice-opportunity-hearing-nooh-manookian-edward-8516"),
    "RISK_KRATOM_NATURAL": ("2014-02-28", "First FDA enforcement action",
                            "https://www.accessdata.fda.gov/cms_ia/importalert_1137.html"),
    "STIM_METHYLHEXANAMINE_ANALOGS": ("2015-04-28", "FDA warning letter",
                                      "https://www.fda.gov/food/hfp-constituent-updates/recent-fda-action-dietary-supplements-labeled-containing-dmba"),
}
# No government document names the compound with a US status (or, for
# piracetam, FDA said its letters do not decide supplement lawfulness): the
# safety gate routes a match to review, as for SR9009.
Q15_NO_US_DETERMINATION = ["BANNED_FASORACETAM", "BANNED_IGF1", "BANNED_IGF1_LR3", "BANNED_SUNIFIRAM",
                           "NOOTROPIC_9MEBC", "NOOTROPIC_FLMODAFINIL", "NOOTROPIC_PIRACETAM"]
_GENUINE_BANS = {"BANNED_EPHEDRA", "BANNED_FDC_RED_2_AMARANTH"}


@pytest.mark.parametrize("entry_id", sorted(Q15_PRIMARY_SOURCES))
def test_q15_records_cite_the_document_that_names_the_compound(banned_recalled, entry_id):
    entry = _find(banned_recalled, entry_id)
    date, label, url = Q15_PRIMARY_SOURCES[entry_id]
    assert (entry["regulatory_date"], entry["regulatory_date_label"]) == (date, label)
    assert url in [r.get("url") for r in entry["references_structured"]] + [
        (j.get("source") or {}).get("url") for j in entry["jurisdictions"]]
    assert entry["policy_verification_status"] == "verified"
    [us] = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "US"]
    if entry_id in _GENUINE_BANS:
        assert us["status"] == "banned" and us["effective_date"] == date
        assert entry["legal_status_enum"] == "banned_federal"
    else:
        assert us["status"] == "not_lawful" and us["effective_date"] is None
        assert entry["legal_status_enum"] != "banned_federal"
        live = json.dumps({k: entry[k] for k in ("reason", "safety_warning", "safety_warning_one_liner")}).lower()
        for stale in ("fda banned", "banned by fda", "banned in supplements", "ban effective"):
            assert stale not in live, (entry_id, stale)


@pytest.mark.parametrize("entry_id", Q15_NO_US_DETERMINATION)
def test_q15_records_without_a_us_determination_stay_under_review(banned_recalled, entry_id):
    entry = _find(banned_recalled, entry_id)
    [us] = [j for j in entry["jurisdictions"] if j.get("jurisdiction_code") == "US"]
    assert us["status"] in {"under_review", "not_approved"}
    assert entry["legal_status_enum"] == "under_review"
    # LEDGER Q58: verified only as an "Unverified ingredient" with human harm evidence.
    assert entry.get("policy_verification_status") != "verified" or _has_harm_source(entry)
    assert "ban" not in (entry["regulatory_date_label"] or "").lower()


def test_ban_labels_are_left_only_on_real_bans(banned_recalled):
    labelled = {e["id"] for e in banned_recalled if "ban" in (e.get("regulatory_date_label") or "").lower()}
    assert labelled == _GENUINE_BANS | {"BANNED_ADD_TITANIUM_DIOXIDE"}


def test_dod_rows_cite_the_dod_list_not_a_state_statute(banned_recalled):
    for entry_id in ("SARM_OSTARINE", "SARM_LIGANDROL", "SARM_RAD140", "BANNED_DMAA", "NOOTROPIC_ADRAFINIL",
                     "NOOTROPIC_MODAFINIL", "NOOTROPIC_PHENYLPIRACETAM", "STIM_METHYLHEXANAMINE_ANALOGS",
                     "BANNED_SUNIFIRAM"):
        [dod] = [j for j in _find(banned_recalled, entry_id)["jurisdictions"] if j.get("jurisdiction_code") == "US-DOD"]
        assert dod["source"]["type"] == "regulatory", entry_id
        assert dod["source"]["url"] == "https://www.opss.org/dod-prohibited-dietary-supplement-ingredients", entry_id
        assert dod["jurisdiction_type"] == "agency_scope", entry_id


@pytest.mark.parametrize("name,canonical,verdict,quarantined", [
    ("DMAA", "dmaa", "BLOCKED", False),        # verified: FDA names DMAA
    ("Piracetam", "piracetam", None, True),     # FDA left supplement lawfulness open: review
])
def test_q15_verified_policy_blocks_and_open_policy_routes_to_review(name, canonical, verdict, quarantined):
    import sys
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": f"TEST_{name}", "fullName": name, "status": "active",
        "form_factor": "capsule", "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": {"banned_substances": {"found": False, "substances": [], "safety_flags": []}},
        "activeIngredients": [{"name": name, "standardName": name, "raw_source_text": name,
                               "forms": [], "mapped": True}],
        "inactiveIngredients": [],
        "ingredient_quality_data": {"total_active": 1, "ingredients_scorable": [
            {"name": name, "canonical_id": canonical, "mapped": True, "quantity": 20.0, "unit": "mg"}]},
    }
    result = evaluate_safety_gate(product)
    assert (result.verdict, result.quarantine_required) == (verdict, quarantined)
