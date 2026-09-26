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
