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
