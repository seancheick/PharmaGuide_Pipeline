"""Per-entry identifier integrity tests for harmful_additives.json.

Pattern mirrors scripts/tests/test_banned_recalled_identifier_integrity.py and
scripts/tests/test_iqm_identifier_integrity.py: one assertion per Wave 9.D
correction, content-verified against UMLS / RxNav / FDA GSRS / PubChem before
the entry is written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HA_PATH = REPO_ROOT / "scripts" / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def harmful_additives() -> list[dict]:
    payload = json.loads(HA_PATH.read_text())
    return payload["harmful_additives"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"harmful_additives.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.D.2 — HIGH-severity corrections (UNII + RxCUI)
# --------------------------------------------------------------------------- #


def test_add_polysorbate_20_unii_is_canonical_gsrs_record(harmful_additives):
    """ADD_POLYSORBATE_20 must use UNII 7T1F30V5YH ('POLYSORBATE 20' per
    FDA GSRS). The stored 4R0MI3KBZF returned no record from GSRS on
    2026-05-28 (deprecated or never-registered UNII). GSRS substance
    name search resolved 'Polysorbate 20' AND its synonym 'Tween 20'
    to the same UNII 7T1F30V5YH — content-verified via live GSRS REST API."""
    entry = _find(harmful_additives, "ADD_POLYSORBATE_20")
    assert (entry.get("external_ids") or {}).get("unii") == "7T1F30V5YH", (
        "ADD_POLYSORBATE_20.external_ids.unii must be 7T1F30V5YH "
        "(GSRS-registered POLYSORBATE 20), not the deprecated 4R0MI3KBZF."
    )


def test_add_senna_rxcui_cleared_to_null(harmful_additives):
    """ADD_SENNA must not carry rxcui '237929' — that RxCUI returns no
    record from RxNav (/REST/rxcui/237929/properties.json → 404 on
    2026-05-28). Cleared to null with rxcui_note documenting the
    deprecation. cui (C0330722) and unii (AK7JF626KX) remain valid and
    untouched."""
    entry = _find(harmful_additives, "ADD_SENNA")
    assert entry.get("rxcui") is None, (
        "ADD_SENNA.rxcui must be null (RxNav 404 on 237929)."
    )
    assert entry.get("rxcui_note"), (
        "ADD_SENNA must have an rxcui_note explaining the deprecation."
    )


def test_add_tyramine_rich_extract_cui_backfilled(harmful_additives):
    """ADD_TYRAMINE_RICH_EXTRACT must use cui C0041479 ('tyramine' —
    Organic Chemical / Pharmacologic Substance / Biologically Active
    Substance). The entry was sweep-flagged as 'missing_cui_has_clean_
    candidate'; the harm mechanism (sympathomimetic biogenic amine causing
    hypertensive crisis with MAOIs) is driven specifically by the tyramine
    content of the extracts, so the tyramine substance CUI is the
    appropriate canonical identifier. Verified via live UMLS REST API
    2026-05-28 (search_exact returned C0041479)."""
    entry = _find(harmful_additives, "ADD_TYRAMINE_RICH_EXTRACT")
    assert entry.get("cui") == "C0041479", (
        "ADD_TYRAMINE_RICH_EXTRACT.cui must be C0041479 (tyramine — the "
        "harmful constituent that drives the MAOI contraindication)."
    )


# --------------------------------------------------------------------------- #
# Wave 9.D.3 — Policy locks for medium-severity findings
# --------------------------------------------------------------------------- #
#
# The 2026-05-28 sweep flagged 29 medium-severity findings across CAS,
# PubChem CID, and UNII fields. Each was reviewed and found to be a
# documented-exception pattern that PubChem / GSRS structural limitations
# produce on polymer / mixture / class entries — not a real bug.
#
# Three buckets locked here:
#   1. Polymer/mixture CAS not indexed by PubChem (21 entries). PubChem
#      indexes discrete compounds; polymers, oils, polysaccharides, and
#      surfactant mixtures (polysorbates etc.) often have FDA-registered
#      CAS numbers that don't resolve to a single CID. The stored CAS is
#      regulatorily correct; the PubChem absence is the structural
#      limitation, not a data error.
#
#   2. CAS-UNII / CAS-CID indexing variance for polymeric substances
#      (5 entries: 2 unrelated-CID, 2 CAS-UNII-disagree, 1 CID-name-
#      misalign). Polymeric/mixture additives commonly have multiple
#      legitimate CAS registrations; one is in IQM, others are in GSRS,
#      and PubChem may index under a third. Same generic substance.
#
#   3. Class-entry UNII pointing at representative compound (3 entries:
#      sugar_alcohols, synthetic_antioxidants, syrups). Same pattern as
#      Wave 9.C.4 banned_recalled (Phthalates → DIBUTYL PHTHALATE,
#      Synthetic Estrogens → ETHINYL ESTRADIOL, etc.).
#
# Pattern matches IQM Wave 6.Y Batches 4 & 5 and banned_recalled Wave
# 9.C.4 — when the strict-mode guard intentionally fails on a
# policy-acceptable mapping, lock it explicitly so a future agent can't
# silently rewrite it without re-checking the policy.

_BUCKET_1_POLYMER_CAS_NOT_IN_PUBCHEM = [
    # (canonical_id, cas, reason)
    ("ADD_CANOLA_OIL",                      "8002-13-9",   "Plant-oil mixture; not a discrete PubChem-indexable compound."),
    ("ADD_CROSPOVIDONE",                    "9003-39-8",   "Crosslinked polymer (povidone)."),
    ("ADD_HYDROGENATED_COCONUT_OIL",        "84836-98-6",  "Hydrogenated triglyceride mixture."),
    ("ADD_HYDROGENATED_STARCH_HYDROLYSATE", "68425-17-2",  "Hydrogenated oligo-/polysaccharide hydrolysate mixture."),
    ("ADD_MALTODEXTRIN",                    "9050-36-6",   "Polysaccharide (variable DP); not a discrete CID."),
    ("ADD_MICROCRYSTALLINE_CELLULOSE",      "9004-34-6",   "Polymeric cellulose."),
    ("ADD_MINERAL_OIL",                     "8042-47-5",   "Petroleum-distillate hydrocarbon mixture."),
    ("ADD_PALM_OIL",                        "8002-75-3",   "Plant-oil triglyceride mixture."),
    ("ADD_POLYDEXTROSE",                    "68424-04-4",  "Branched glucose polymer (variable structure)."),
    ("ADD_POLYETHYLENE_GLYCOL",             "25322-68-3",  "PEG polymer (variable MW)."),
    ("ADD_POLYSORBATE80",                   "9005-65-6",   "Polyoxyethylene sorbitan ester (surfactant mixture)."),
    ("ADD_POLYSORBATE_20",                  "9005-64-5",   "Polyoxyethylene sorbitan ester (surfactant mixture)."),
    ("ADD_POLYSORBATE_40",                  "9005-66-7",   "Polyoxyethylene sorbitan ester (surfactant mixture)."),
    ("ADD_POLYSORBATE_65",                  "9005-71-4",   "Polyoxyethylene sorbitan ester (surfactant mixture)."),
    ("ADD_POLYVINYLPYRROLIDONE",            "9003-39-8",   "PVP polymer."),
    ("ADD_SHELLAC",                         "9000-59-3",   "Natural resin (multi-component lac secretion)."),
    ("ADD_SODIUM_CASEINATE",                "9005-46-3",   "Milk-protein salt (variable composition)."),
    ("ADD_SODIUM_COPPER_CHLOROPHYLLIN",     "11006-34-1",  "Copper-substituted chlorophyllin salt mixture."),
    ("ADD_SODIUM_HEXAMETAPHOSPHATE",        "10124-56-8",  "Polymeric phosphate (variable chain length)."),
    ("ADD_SOY_MONOGLYCERIDES",              "68554-09-6",  "Mono-/di-glyceride mixture from soy."),
    ("ADD_THAUMATIN",                       "53850-34-3",  "Protein (sweet protein; PubChem doesn't typically index proteins as CIDs)."),
]


@pytest.mark.parametrize(
    "canonical_id,locked_cas,reason",
    _BUCKET_1_POLYMER_CAS_NOT_IN_PUBCHEM,
)
def test_wave_9d3_polymer_cas_locked_despite_pubchem_absence(
    harmful_additives, canonical_id, locked_cas, reason
):
    """The 21 polymer / mixture / protein CAS numbers below all return
    'cas_not_found_in_pubchem' from the sweep. Each CAS is the
    FDA-registered authoritative identifier for the substance; the
    PubChem absence is a structural limitation of PubChem (which indexes
    discrete compounds, not polymers/mixtures), not a data error. Lock
    the (canonical_id, cas) pair so a future sweep agent doesn't rewrite
    these on a name-search false positive."""
    entry = _find(harmful_additives, canonical_id)
    actual = (entry.get("external_ids") or {}).get("cas")
    assert actual == locked_cas, (
        f"{canonical_id}.external_ids.cas must remain {locked_cas} "
        f"(policy-accepted: {reason}). PubChem absence is a structural "
        f"limitation, not a data error."
    )


_BUCKET_2_POLYMER_CROSS_AUTHORITY_VARIANCE = [
    # (canonical_id, field, locked_value, reason)
    ("ADD_CANDURIN_SILVER", "external_ids.cas", "12001-26-2",
     "Candurin Silver is a mica-based pearlescent pigment; 12001-26-2 is "
     "mica's CAS. PubChem's CID 131842327 indexes under a different name "
     "but represents the same substance — naming variance, not bug."),
    ("ADD_CARRAGEENAN", "external_ids.cas", "9000-07-1",
     "Carrageenan is a sulphated polysaccharide; 9000-07-1 is the "
     "FDA-registered CAS. PubChem CID 78126884 indexes under different "
     "synonyms — same substance, naming variance."),
    ("ADD_SODIUM_HEXAMETAPHOSPHATE", "external_ids.unii", "P1BM4ZH95L",
     "Polymeric phosphate with multiple legitimate CAS registrations. "
     "IQM stores 10124-56-8; UNII's GSRS record lists 10361-03-2 / "
     "50813-16-6 / 68915-31-1 — same generic substance, different "
     "polymer-chain CAS variants."),
    ("ADD_SOY_MONOGLYCERIDES", "external_ids.unii", "230OU9XXE4",
     "Soy mono-/di-glyceride mixture. IQM stores 68554-09-6; GSRS lists "
     "31566-31-1 / 11099-07-3 / 91052-47-0 — same mixture, different "
     "manufacturing-grade CAS registrations."),
    ("ADD_HYDROGENATED_STARCH_HYDROLYSATE", "external_ids.pubchem_cid", 91932559,
     "Polymeric hydrogenated saccharide mixture. CID 91932559 is the best "
     "PubChem proxy but its synonym list doesn't include 'hydrogenated "
     "starch hydrolysate' verbatim. Naming variance for a polymer."),
]


@pytest.mark.parametrize(
    "canonical_id,field,locked_value,reason",
    _BUCKET_2_POLYMER_CROSS_AUTHORITY_VARIANCE,
)
def test_wave_9d3_polymer_cross_authority_variance_locked(
    harmful_additives, canonical_id, field, locked_value, reason
):
    """5 polymeric / mixture entries where PubChem, GSRS, and IQM
    legitimately disagree on which CAS / CID / UNII representation is
    canonical. Locked because the existing identifier is the
    FDA-registered authoritative value; the disagreement is naming
    variance not data corruption."""
    entry = _find(harmful_additives, canonical_id)
    # navigate the field path (e.g., 'external_ids.cas' → entry['external_ids']['cas'])
    if "." in field:
        outer, inner = field.split(".", 1)
        actual = (entry.get(outer) or {}).get(inner)
    else:
        actual = entry.get(field)
    assert actual == locked_value, (
        f"{canonical_id}.{field} must remain {locked_value!r} "
        f"(policy-accepted: {reason}). Cross-authority variance is "
        f"structural, not a data error."
    )


_BUCKET_3_CLASS_ENTRY_REPRESENTATIVE_UNII = [
    # (canonical_id, locked_unii, gsrs_target, reason)
    ("ADD_SUGAR_ALCOHOLS", "3OWL53L36A", "<sugar-alcohol representative>",
     "Sugar Alcohols (class) — UNII points at a representative sugar "
     "alcohol used for regulatory enforcement on the class. Class-vs-"
     "representative-compound mapping, same pattern as banned_recalled "
     "BANNED_ADD_PHTHALATES Wave 9.C.4."),
    ("ADD_SYNTHETIC_ANTIOXIDANTS", "9T1410R4OR", "<antioxidant representative>",
     "Synthetic Antioxidants (class) — UNII points at a representative "
     "synthetic antioxidant for class enforcement. Same pattern."),
]


@pytest.mark.parametrize(
    "canonical_id,locked_unii,gsrs_target,reason",
    _BUCKET_3_CLASS_ENTRY_REPRESENTATIVE_UNII,
)
def test_wave_9d3_class_entry_unii_policy_locked(
    harmful_additives, canonical_id, locked_unii, gsrs_target, reason
):
    """3 class-level entries where the UNII intentionally points at a
    representative compound used for regulatory enforcement on the class.
    Same documented-exception pattern as Wave 9.C.4."""
    entry = _find(harmful_additives, canonical_id)
    actual = (entry.get("external_ids") or {}).get("unii")
    assert actual == locked_unii, (
        f"{canonical_id}.external_ids.unii must remain {locked_unii} "
        f"({gsrs_target}; policy-accepted: {reason})."
    )


def test_class_or_variant_rows_do_not_claim_exact_unii_owned_by_atomic_rows(harmful_additives):
    """Representative UNII values are not safe when another same-tier harmful
    row owns the exact FDA/GSRS identity. The broader/variant rows still match by
    label aliases; the exact UNII stays on the exact substance row only."""
    corn_syrup = _find(harmful_additives, "ADD_CORN_SYRUP_SOLIDS")
    syrups = _find(harmful_additives, "ADD_SYRUPS")
    corn_oil = _find(harmful_additives, "ADD_CORN_OIL")
    partially_hydrogenated = _find(
        harmful_additives,
        "ADD_PARTIALLY_HYDROGENATED_CORN_OIL",
    )

    assert (corn_syrup.get("external_ids") or {}).get("unii") == "9G5L16BK6N"
    assert (syrups.get("external_ids") or {}).get("unii") is None
    assert syrups.get("unii_note")

    assert (corn_oil.get("external_ids") or {}).get("unii") == "8470G57WFM"
    assert (partially_hydrogenated.get("external_ids") or {}).get("unii") is None
    assert partially_hydrogenated.get("rxcui") is None
    assert partially_hydrogenated.get("gsrs") is None
    assert partially_hydrogenated.get("unii_note")
    assert partially_hydrogenated.get("rxcui_note")
