"""Shared collagen subtype taxonomy.

Single source of truth for classifying a collagen ingredient into its clinical
subtype, used by BOTH the enricher (enrich_supplements_v3.py — stamps an
authoritative `collagen_subtype` on each collagen row) and the v4 scorer
(scoring_v4/modules/collagen_profile.py — maps subtype -> clinical dose entry,
falling back to this classifier when no subtype was emitted).

Each subtype has a DISTINCT studied clinical dose (see
data/rda_therapeutic_dosing.json), so collapsing them loses the dose signal:

    undenatured_type_ii  UC-II                40 mg
    eggshell_membrane    NEM                  500 mg
    hydrolyzed_type_ii   BioCell / sternum    500-2000 mg
    gelatin              denatured collagen   5-15 g
    peptides_i_iii       hydrolyzed peptides  2.5-10 g  (incl. marine; default)

UC-II and NEM are SPECIFIC ingredients — they must be recognized from the row's
own identity, never a co-ingredient named only in the product title. The product
name is consulted ONLY for the lower-precedence hydrolyzed-Type-II disambiguation
("Type II Collagen Complex" naming on an otherwise generic collagen row).
"""
from __future__ import annotations

import re
from typing import Optional

# subtype constants
UNDENATURED_TYPE_II = "undenatured_type_ii"
EGGSHELL_MEMBRANE = "eggshell_membrane"
HYDROLYZED_TYPE_II = "hydrolyzed_type_ii"
GELATIN = "gelatin"
PEPTIDES_I_III = "peptides_i_iii"

# subtype -> the alias key to look up in rda_therapeutic_dosing.json
SUBTYPE_TO_DOSING_ALIAS = {
    UNDENATURED_TYPE_II: "uc-ii",
    EGGSHELL_MEMBRANE: "nem",
    HYDROLYZED_TYPE_II: "biocell",
    GELATIN: "gelatin",
    PEPTIDES_I_III: "collagen",
}

_UC2_RE = re.compile(r"\buc-?ii\b|undenatured|\bnt2\b|native\s+type\s*(ii|2)\b")
# chicken sternum / sternal cartilage is the Type-II collagen source.
_HYDROLYZED_TYPE2_RE = re.compile(r"\bbiocell\b|hydrolyzed\s+type\s*(ii|2)\b|stern(al|um)")
_TYPE2_RE = re.compile(r"type\s*(ii|2)\b")
# other collagen types (I/III/1/3) — a multi-type product (I & III, I/II/III) is a
# hydrolyzed PEPTIDE blend, not a pure Type-II joint ingredient.
_OTHER_TYPE_RE = re.compile(r"type\s*i\b|type\s*iii\b|type\s*[13]\b")
_HYDROLYZED_TOKENS = ("hydrolyzed", "hydrolysed", "hydrolysate", "peptide")


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


UNSPECIFIED = "unspecified"

_PEPTIDE_SIGNAL = ("hydrolyzed", "hydrolysed", "hydrolysate", "peptide", "marine",
                   "fish", "tuna", "naticol", "verisol", "peptan")


def _classify(rt: str, ft: str, strict: bool) -> Optional[str]:
    # row-identity only: a 40 mg / 500 mg specific ingredient must be on THIS row
    if _UC2_RE.search(rt):
        return UNDENATURED_TYPE_II
    if "eggshell membrane" in rt or re.search(r"\bnem\b", rt):
        return EGGSHELL_MEMBRANE
    # hydrolyzed Type II (BioCell): explicit biocell/sternum on the row, OR a pure
    # Type-II disclosure (often only in the product name), not a multi-type blend.
    if _HYDROLYZED_TYPE2_RE.search(ft) or (
            _TYPE2_RE.search(ft) and not _OTHER_TYPE_RE.search(ft)):
        return HYDROLYZED_TYPE_II
    if ("gelatin" in rt or "gelatine" in rt) and not any(h in rt for h in _HYDROLYZED_TOKENS):
        return GELATIN
    # hydrolyzed Type I & III peptides (incl. marine). In strict (row-only) mode we
    # assert peptides only on a positive peptide signal; a bare "collagen" row is
    # left unspecified for the scorer to resolve with product context.
    if not strict or any(s in rt for s in _PEPTIDE_SIGNAL):
        return PEPTIDES_I_III
    return None


def classify_collagen_subtype(row_text: str, product_name: Optional[str] = None) -> str:
    """Classify a collagen row into its clinical subtype, most specific first.

    `row_text` is the row's own identity text (matched_form / name /
    standard_name / forms). `product_name` is consulted ONLY for the
    hydrolyzed-Type-II naming case. Always returns a concrete subtype
    (defaults to peptides_i_iii). Used by the scorer (full product context).
    """
    rt = _norm(row_text)
    ft = rt + (" " + _norm(product_name) if product_name else "")
    return _classify(rt, ft, strict=False)


def classify_collagen_subtype_strict(row_text: str) -> Optional[str]:
    """Row-only classification for the ENRICHER: asserts a subtype only when the
    ROW itself proves it (UC-II / NEM / BioCell-sternum / pure Type-II / gelatin /
    explicit hydrolyzed-peptide). Returns None for a generic "collagen" row with no
    distinguishing signal, so the enricher emits `unspecified` and the scorer
    resolves it with product context (avoids a wrong stamp the scorer would trust).
    """
    rt = _norm(row_text)
    return _classify(rt, rt, strict=True)
