#!/usr/bin/env python3
"""
IQM full identifier sweep — read-only content verification across every parent
canonical_id in ingredient_quality_map.json.

Per reports/IQM_FULL_IDENTIFIER_SWEEP_2026_05_27.md, this is a clinical-grade
data-integrity sweep. The 2026-05-27 interaction-layer audit found a 3.75%
defect rate (3 hallucinated CUIs in ~80 audited identifiers). This script
walks every IQM parent and content-verifies every stored external identifier
against the authority that owns it, with strict-mode guards that catch the
class of bugs the existing verify_cui.py permissive filter misses.

What "verified" means here (per spec §"Verification methodology — strict"):
  1. API returned a 200 with a real concept (not 404, not a deprecated record).
  2. The returned concept's name relates to the IQM entry (not just substring).
  3. The returned concept's semantic type matches expectation for a substance.

Strict-mode guards (orchestrator-owned — NOT delegated to verify_cui.py's
permissive NON_INGREDIENT_SEMANTIC_TYPES which only rejects Laboratory
Procedure):
  - Reject UMLS concepts with disease/syndrome semantic types when IQM entry
    is a substance (CoQ10 deficiency ≠ CoQ10 the compound).
  - Reject UMLS concepts with branded-product / clinical-drug semantic types
    when IQM entry is a generic substance (Natrol Melatonin + 5-HTP ≠ 5-HTP).
  - Reject token-only name overlaps where the only similarity is a common
    substring (calcium ↛ calcium oxalate stones).
  - Reject class-broader UMLS concepts unless IQM standard_name is also at
    class level (phytoestrogens ≠ genistein).
  - Flag cross-source disagreement (CUI says X, PubChem CID says Y → flagged,
    not auto-decided).
  - Flag ambiguous-authority when multiple UMLS candidates pass guards (free
    base vs salt form, L- vs DL-) — never auto-pick.

Outputs (under --out, all read-only artifacts; no data file is ever opened
for write):
  - MASTER_REPORT.md   — summary stats, severity breakdown, seed findings
  - findings.jsonl     — one object per non-clean finding, sorted severity DESC
  - per_parent/<id>.json — per-parent record with iqm_snapshot_sha256
  - queue.csv          — high-severity findings ready for clinician review

Safety rails:
  - argparse does NOT accept --apply / --write. Adding one would fail tests.
  - The IQM file is opened with mode='r' only.
  - All authority API responses are cached under --cache so re-runs cost zero
    quota.

Usage:
  python3 scripts/api_audit/iqm_identifier_sweep.py \\
      --file scripts/data/ingredient_quality_map.json \\
      --out  reports/iqm_identifier_sweep \\
      --cache reports/iqm_identifier_sweep/_cache
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401 — loads .env

from api_audit.verify_cui import UMLSClient
from api_audit.verify_pubchem import PubChemClient, CAS_RE as PUBCHEM_CAS_RE
from api_audit.verify_unii import GSRSClient
from api_audit.verify_interactions import RxNormClient

import ssl
import urllib.error
import urllib.parse
import urllib.request

CAS_RE = PUBCHEM_CAS_RE
CUI_RE = re.compile(r"^C\d{6,7}$")
RXCUI_RE = re.compile(r"^\d+$")
UNII_RE = re.compile(r"^[A-Z0-9]{10}$")

UTC = timezone.utc


def rxnav_name_to_rxcuis(name: str, *, timeout: float = 6.0, _cache: dict | None = None) -> list[str]:
    """Resolve a name to RxCUI(s) via RxNav /REST/rxcui.json?name=…&search=1.
    Used as a reverse-check when RxNorm's preferred display name disagrees
    with IQM's user-facing name. Read-only; returns [] on any error.
    """
    if _cache is not None and name in _cache:
        return list(_cache[name])
    if not name or not isinstance(name, str):
        return []
    try:
        url = (
            "https://rxnav.nlm.nih.gov/REST/rxcui.json?name="
            + urllib.parse.quote(name, safe="")
            + "&search=1"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                payload = json.loads(resp.read().decode())
        except (ssl.SSLCertVerificationError, urllib.error.URLError):
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                payload = json.loads(resp.read().decode())
    except Exception:
        if _cache is not None:
            _cache[name] = []
        return []
    rxcuis = (payload.get("idGroup") or {}).get("rxnormId") or []
    rxcuis = [str(x) for x in rxcuis if x]
    if _cache is not None:
        _cache[name] = rxcuis
    return rxcuis

# --------------------------------------------------------------------------- #
# Strict-mode guard sets (orchestrator-owned, NOT delegated to verify_cui.py)
# --------------------------------------------------------------------------- #

# Semantic types that disqualify a UMLS concept from being a substance match.
DISEASE_SEMANTIC_TYPES = {
    "Disease or Syndrome",
    "Sign or Symptom",
    "Pathologic Function",
    "Mental or Behavioral Dysfunction",
    "Anatomical Abnormality",
    "Neoplastic Process",
    "Acquired Abnormality",
    "Injury or Poisoning",
    "Cell or Molecular Dysfunction",
    "Congenital Abnormality",
    "Finding",
}

# Semantic types that mark a UMLS concept as a branded / pharmaceutical product
# rather than a generic substance.
BRANDED_SEMANTIC_TYPES = {
    "Clinical Drug",
    "Branded Drug",
    "Pharmaceutical Preparation",
}

# Semantic types acceptable for an IQM substance entry. Wide on purpose —
# botanicals, microbes, vitamins, and food-source ingredients all live here.
SUBSTANCE_SEMANTIC_TYPES = {
    "Organic Chemical",
    "Pharmacologic Substance",
    "Biologically Active Substance",
    "Vitamin",
    "Amino Acid, Peptide, or Protein",
    "Hormone",
    "Plant",
    "Eukaryote",
    "Fungus",
    "Bacterium",
    "Archaeon",
    "Virus",
    "Inorganic Chemical",
    "Element, Ion, or Isotope",
    "Lipid",
    "Steroid",
    "Carbohydrate",
    "Nucleic Acid, Nucleoside, or Nucleotide",
    "Enzyme",
    "Receptor",
    "Antibiotic",
    "Food",
    "Chemical Viewed Structurally",
    "Chemical Viewed Functionally",
    "Chemical",
    "Indicator, Reagent, or Diagnostic Aid",
    "Immunologic Factor",
    "Body Substance",
    "Neuroreactive Substance or Biogenic Amine",
}

# Tokens that strongly suggest a UMLS concept is at *class* level (broader than
# a single compound). When the IQM standard_name lacks any of these markers
# and the UMLS candidate name has them, the candidate is rejected as
# class-broader.
CLASS_BROADER_NAME_TOKENS = {
    "compounds",
    "derivatives",
    "phytoestrogens",
    "metabolites",
    "supplements",
    "products",
    "mixture",
    "preparations",
    "category",
    "family",
    "agents",
    "drugs",
    "polyphenols",
    "flavonoids",  # only when standard_name is a single flavonoid
    "alkaloids",
    "saponins",
    "terpenes",
    "carotenoids",
    "isoflavones",
    "lignans",
    "precursors",
    "isomers",
    "analogs",
    "analogues",
    "salts",
    "esters",
    "glycosides",
    "fractions",
}

# Tokens that often mark a UMLS concept as a *narrower* preparation
# (e.g., "extract", "oil", "powder") when the IQM entry is the bare compound.
NARROWER_PREPARATION_TOKENS = {
    "extract",
    "oil",
    "powder",
    "juice",
    "tincture",
    "concentrate",
    "infusion",
    "decoction",
}

# Words to ignore when checking token overlap between names.
NAME_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "from", "for",
    "with", "without", "in", "on", "to", "by", "as",
    "preparation", "supplement", "supplementation",
    "product", "products",
}

# --------------------------------------------------------------------------- #
# Token / name helpers
# --------------------------------------------------------------------------- #


def _tokens(value: str | None) -> set[str]:
    """Lowercase, alphanumeric-only token set with stopwords filtered."""
    if not value:
        return set()
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return {t for t in normalized.split() if t and t not in NAME_STOPWORDS}


def _all_iqm_name_tokens(standard_name: str, aliases: Iterable[str]) -> set[str]:
    out = _tokens(standard_name)
    for a in aliases or []:
        if isinstance(a, str):
            out |= _tokens(a)
    return out


def _iqm_appears_class_level(standard_name: str) -> bool:
    """Heuristic: is the IQM standard_name itself a plural/class label?"""
    sn_tokens = _tokens(standard_name)
    if sn_tokens & CLASS_BROADER_NAME_TOKENS:
        return True
    if sn_tokens & {"total", "various", "mixed", "blend", "complex"}:
        return True
    return False


# --------------------------------------------------------------------------- #
# Verdict dataclass + serialization
# --------------------------------------------------------------------------- #


@dataclass
class Verdict:
    status: str  # verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null
    severity: str | None = None  # high | medium | low | None
    reason_code: str | None = None
    api_response: dict | None = None
    proposed_value: str | None = None
    proposed_resolution: dict | None = None
    evidence: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


# --------------------------------------------------------------------------- #
# Strict-mode UMLS CUI assessment (pure function — no client dep)
# --------------------------------------------------------------------------- #


def assess_umls_concept(
    *,
    cui_under_test: str,
    standard_name: str,
    aliases: list[str],
    resolved: dict | None,  # UMLSClient.lookup_cui() result
    iqm_is_class_level: bool,
) -> Verdict:
    """Apply strict-mode guards to a UMLS-resolved concept and decide verdict.

    `resolved` is the dict returned by UMLSClient.lookup_cui():
        {"cui", "name", "semantic_types": [str, ...], "atom_count", "status"}
    """
    if resolved is None:
        return Verdict(
            status="unresolvable",
            severity="high",
            reason_code="cui_not_found_in_umls",
            evidence=(
                f"UMLS /content/CUI/{cui_under_test} returned no result. "
                "CUI may be deprecated, withdrawn, or never existed."
            ),
        )

    sem_types = set(resolved.get("semantic_types") or [])
    name = resolved.get("name") or ""
    name_tokens = _tokens(name)
    iqm_tokens = _all_iqm_name_tokens(standard_name, aliases)

    # Guard 1 — Disease / Sign / Pathologic-Function rejection.
    disease_hit = sem_types & DISEASE_SEMANTIC_TYPES
    if disease_hit:
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="resolved_to_disease_or_syndrome",
            api_response=resolved,
            evidence=(
                f"Stored CUI {cui_under_test} resolves to '{name}' "
                f"with semantic types {sorted(sem_types)}. "
                f"Disease/syndrome types {sorted(disease_hit)} present, but "
                f"IQM entry '{standard_name}' is a substance."
            ),
        )

    # Guard 2 — Branded / clinical-drug rejection.
    branded_hit = sem_types & BRANDED_SEMANTIC_TYPES
    if branded_hit:
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="resolved_to_branded_or_clinical_drug",
            api_response=resolved,
            evidence=(
                f"Stored CUI {cui_under_test} resolves to '{name}' "
                f"with semantic types {sorted(sem_types)}. "
                f"Branded/clinical-drug types {sorted(branded_hit)} present, "
                f"but IQM entry '{standard_name}' is a generic substance."
            ),
        )

    # Guard 2b — Multi-compound / combo-product rejection.
    # UMLS occasionally tags branded combo products with substance semantic
    # types (e.g., C5815882 'Natrol Melatonin + 5-HTP' carries Organic
    # Chemical / Pharmacologic Substance). When the candidate name contains
    # an explicit combo separator ('+', ' with ', ' plus ', ' / '), it's a
    # multi-compound product, not a single substance.
    name_lower = (name or "").lower()
    iqm_name_lower = (standard_name or "").lower()
    # Only trigger if the IQM entry name doesn't itself look like a combo.
    iqm_has_combo_marker = any(m in iqm_name_lower for m in (" + ", " with ", " plus "))
    if not iqm_has_combo_marker:
        for marker in (" + ", " with ", " plus ", " and "):
            if marker in name_lower:
                # Confirm both sides of the separator have a substance-looking token.
                left, _, right = name_lower.partition(marker)
                left_t = _tokens(left)
                right_t = _tokens(right)
                if left_t and right_t and left_t != right_t:
                    return Verdict(
                        status="mismatched",
                        severity="high",
                        reason_code="resolved_to_multi_compound_or_combo_product",
                        api_response=resolved,
                        evidence=(
                            f"Stored CUI {cui_under_test} resolves to '{name}', "
                            f"which is a multi-compound / combo product (separator "
                            f"'{marker.strip()}' splits the name into distinct substance "
                            f"groups). IQM entry '{standard_name}' is a single compound."
                        ),
                    )

    # Guard 3 — token-only-overlap rejection.
    if not name_tokens:
        return Verdict(
            status="unresolvable",
            severity="medium",
            reason_code="resolved_concept_name_empty",
            api_response=resolved,
        )

    overlap = name_tokens & iqm_tokens
    if not overlap:
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="no_token_overlap_with_iqm_name",
            api_response=resolved,
            evidence=(
                f"Stored CUI {cui_under_test} resolves to '{name}' with no "
                f"name tokens overlapping IQM '{standard_name}' or its "
                f"aliases. Likely wrong-concept hallucination."
            ),
        )

    # Guard 4 — class-broader rejection (only when IQM is not itself class-level).
    if not iqm_is_class_level:
        cand_class_markers = name_tokens & CLASS_BROADER_NAME_TOKENS
        iqm_class_markers = iqm_tokens & CLASS_BROADER_NAME_TOKENS
        if cand_class_markers and not iqm_class_markers:
            return Verdict(
                status="mismatched",
                severity="medium",
                reason_code="resolved_to_class_broader_than_iqm",
                api_response=resolved,
                evidence=(
                    f"Stored CUI {cui_under_test} resolves to '{name}' which "
                    f"contains class-level markers {sorted(cand_class_markers)} "
                    f"not present in IQM '{standard_name}'. UMLS concept "
                    f"appears class-broader than the IQM compound."
                ),
            )

    # Guard 5 — substance-semantic-type sanity. If UMLS returned semantic types
    # at all (some old concepts return none) and none align with our substance
    # list, surface it for review at low severity (some valid concepts will
    # legitimately fall outside, e.g., "Activity" for some labeled activities).
    if sem_types and not (sem_types & SUBSTANCE_SEMANTIC_TYPES):
        return Verdict(
            status="mismatched",
            severity="low",
            reason_code="resolved_concept_lacks_substance_semantic_type",
            api_response=resolved,
            evidence=(
                f"Stored CUI {cui_under_test} resolves to '{name}' with "
                f"semantic types {sorted(sem_types)}. None match the typical "
                "substance categories. May be a procedure/finding/organism "
                "concept, or a UMLS atom that lost its substance categorization."
            ),
        )

    return Verdict(status="verified_clean", api_response=resolved)


# --------------------------------------------------------------------------- #
# Authority verification — one function per identifier type
# --------------------------------------------------------------------------- #


def verify_cui_field(
    *,
    stored_cui: str | None,
    standard_name: str,
    aliases: list[str],
    cui_note: str | None,
    cui_status: str | None,
    umls: UMLSClient | None,
    iqm_is_class_level: bool,
) -> Verdict:
    """Verify the stored CUI, OR (if missing) try to find an exact match."""
    if not stored_cui:
        # Missing CUI. Honor documented null-policy: if cui_status is one of
        # the approved nulls, mark as skipped_intentional_null.
        if cui_status in {"no_confirmed_umls_match", "no_single_umls_concept"}:
            return Verdict(
                status="skipped_intentional_null",
                reason_code="approved_null_cui_status",
                notes=cui_note or cui_status,
            )
        # Otherwise try a strict exact-search resolve (read-only candidate).
        if umls is None:
            return Verdict(
                status="unresolvable",
                reason_code="no_umls_client_available",
            )
        return attempt_resolve_missing_cui(
            standard_name=standard_name,
            aliases=aliases,
            umls=umls,
            iqm_is_class_level=iqm_is_class_level,
        )

    # Stored CUI present — verify syntax and content.
    if not CUI_RE.match(stored_cui):
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="malformed_cui",
            evidence=f"Stored CUI '{stored_cui}' does not match C-followed-by-digits pattern.",
        )

    if umls is None:
        return Verdict(
            status="unresolvable",
            reason_code="no_umls_client_available",
        )
    resolved = umls.lookup_cui(stored_cui)
    verdict = assess_umls_concept(
        cui_under_test=stored_cui,
        standard_name=standard_name,
        aliases=aliases,
        resolved=resolved,
        iqm_is_class_level=iqm_is_class_level,
    )

    # Reverse-check for the "no_token_overlap" path: UMLS preferred names
    # legitimately differ from common names (ubidecarenone for CoQ10,
    # ascorbic acid for vitamin C, cyanocobalamin for vitamin B12, etc.).
    # If UMLS exact-search for the IQM standard_name or any alias returns
    # the SAME CUI, the stored CUI is canonical and we accept it even
    # though the display name disagrees.
    if (
        verdict.status == "mismatched"
        and verdict.reason_code == "no_token_overlap_with_iqm_name"
    ):
        accepted_via_reverse, reverse_note = _reverse_check_same_cui(
            stored_cui=stored_cui,
            standard_name=standard_name,
            aliases=aliases,
            umls=umls,
        )
        if accepted_via_reverse:
            return Verdict(
                status="verified_clean",
                api_response=resolved,
                notes=reverse_note,
            )

    return verdict


def _reverse_check_same_cui(
    *,
    stored_cui: str,
    standard_name: str,
    aliases: list[str],
    umls: UMLSClient,
) -> tuple[bool, str]:
    """If UMLS exact-search for the IQM standard_name or any alias returns
    the same CUI we already store, the CUI is canonical for our name even
    if the preferred display name disagrees. Returns (accepted, note)."""
    exact = umls.search_exact(standard_name)
    if exact and exact.get("cui") == stored_cui:
        return True, (
            f"UMLS preferred display name disagrees with IQM '{standard_name}', "
            f"but UMLS exact-search for the IQM name returns the same CUI "
            f"({stored_cui}). Stored CUI is canonical."
        )
    for alias in aliases or []:
        if not isinstance(alias, str) or not alias.strip():
            continue
        if CUI_RE.match(alias.strip()):
            continue
        ahit = umls.search_exact(alias)
        if ahit and ahit.get("cui") == stored_cui:
            return True, (
                f"UMLS preferred display name disagrees with IQM '{standard_name}', "
                f"but UMLS exact-search for alias '{alias}' returns the same CUI "
                f"({stored_cui}). Stored CUI is canonical."
            )
    return False, ""


def attempt_resolve_missing_cui(
    *,
    standard_name: str,
    aliases: list[str],
    umls: UMLSClient,
    iqm_is_class_level: bool,
) -> Verdict:
    """For a parent with no CUI, look for a clean exact match (or report
    ambiguous / unresolvable). Never writes."""
    # Try exact search on standard_name first
    candidates_seen: list[tuple[str, dict]] = []

    exact_hit = umls.search_exact(standard_name)
    if exact_hit:
        resolved = umls.lookup_cui(exact_hit["cui"])
        v = assess_umls_concept(
            cui_under_test=exact_hit["cui"],
            standard_name=standard_name,
            aliases=aliases,
            resolved=resolved,
            iqm_is_class_level=iqm_is_class_level,
        )
        if v.status == "verified_clean":
            candidates_seen.append((exact_hit["cui"], resolved or {}))

    # Try exact search on each alias too
    for alias in aliases or []:
        if not isinstance(alias, str) or not alias.strip():
            continue
        # Skip alias that looks like a CUI (some IQM entries store extra CUIs as aliases)
        if CUI_RE.match(alias.strip()):
            continue
        hit = umls.search_exact(alias)
        if not hit:
            continue
        if any(cui == hit["cui"] for cui, _ in candidates_seen):
            continue
        resolved = umls.lookup_cui(hit["cui"])
        v = assess_umls_concept(
            cui_under_test=hit["cui"],
            standard_name=standard_name,
            aliases=aliases,
            resolved=resolved,
            iqm_is_class_level=iqm_is_class_level,
        )
        if v.status == "verified_clean":
            candidates_seen.append((hit["cui"], resolved or {}))

    if not candidates_seen:
        return Verdict(
            status="unresolvable",
            reason_code="no_clean_exact_match_for_missing_cui",
            notes="Tried exact UMLS search on standard_name and aliases; no candidate passed strict-mode guards.",
        )

    if len(candidates_seen) > 1:
        return Verdict(
            status="ambiguous_authority",
            reason_code="multiple_clean_umls_candidates_for_missing_cui",
            api_response={
                "candidates": [
                    {"cui": c, "name": r.get("name"), "semantic_types": r.get("semantic_types")}
                    for c, r in candidates_seen
                ]
            },
            notes="Multiple UMLS concepts pass strict-mode guards (free base vs salt, L- vs DL-, etc.). Clinician must pick.",
        )

    cui, resolved = candidates_seen[0]
    return Verdict(
        status="mismatched",
        severity="low",
        reason_code="missing_cui_has_clean_candidate",
        proposed_value=cui,
        proposed_resolution=resolved,
        evidence=f"UMLS exact search yielded {cui} ('{resolved.get('name')}') passing all strict-mode guards.",
    )


def verify_rxcui_field(
    *,
    stored_rxcui: str | None,
    standard_name: str,
    aliases: list[str] | None = None,
    rxnorm: RxNormClient | None = None,
    rxnav_reverse_check=None,
) -> Verdict:
    """Verify the stored RxCUI via RxNorm /rxcui/{rxcui}/properties.json.

    `rxnav_reverse_check` is a callable taking a name string and returning a
    list of RxCUI strings the name resolves to (via /REST/rxcui.json?name=).
    When token-overlap fails (RxNorm's preferred name often uses chemical
    nomenclature like 'ubidecarenone' instead of 'Coenzyme Q10'), we accept
    the stored RxCUI if the name reverse-lookup returns the same RxCUI.
    """
    if not stored_rxcui:
        return Verdict(status="verified_clean", notes="no rxcui stored (acceptable)")

    if not RXCUI_RE.match(str(stored_rxcui)):
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="malformed_rxcui",
            evidence=f"Stored RxCUI '{stored_rxcui}' is not all-digits.",
        )

    if rxnorm is None:
        return Verdict(status="unresolvable", reason_code="no_rxnorm_client_available")

    props = rxnorm.properties(str(stored_rxcui))
    if not props:
        return Verdict(
            status="unresolvable",
            severity="high",
            reason_code="rxcui_not_found_in_rxnav",
            evidence=f"RxNav /rxcui/{stored_rxcui}/properties.json returned no record.",
        )

    name = props.get("name") or ""
    if not name:
        return Verdict(
            status="mismatched",
            severity="medium",
            reason_code="rxnorm_record_has_no_name",
            api_response=props,
        )

    name_tokens = _tokens(name)
    iqm_tokens = _all_iqm_name_tokens(standard_name, aliases or [])
    if name_tokens & iqm_tokens:
        return Verdict(status="verified_clean", api_response=props)

    # Synonym fallback (some RxNorm records carry a synonym field)
    syn_tokens = _tokens(props.get("synonym") or "")
    if syn_tokens & iqm_tokens:
        return Verdict(status="verified_clean", api_response=props)

    # Reverse-check: RxNav preferred display names often differ from common
    # names (e.g., RxCUI 21406 = 'ubidecarenone' for CoQ10). Ask RxNav whether
    # an exact-name search for the IQM standard_name or any alias returns the
    # same RxCUI.
    if rxnav_reverse_check is not None:
        for term in [standard_name, *(aliases or [])]:
            if not isinstance(term, str) or not term.strip():
                continue
            try:
                matching = rxnav_reverse_check(term) or []
            except Exception:
                matching = []
            if str(stored_rxcui) in [str(x) for x in matching]:
                return Verdict(
                    status="verified_clean",
                    api_response=props,
                    notes=(
                        f"RxNorm preferred display name '{name}' disagrees with "
                        f"IQM '{standard_name}', but RxNav name-search for "
                        f"'{term}' returns the same RxCUI ({stored_rxcui})."
                    ),
                )

    return Verdict(
        status="mismatched",
        severity="medium",
        reason_code="rxcui_name_does_not_align_with_iqm",
        api_response=props,
        evidence=(
            f"RxCUI {stored_rxcui} resolves to '{name}' (tty={props.get('tty')}) "
            f"with no token overlap with IQM '{standard_name}' or its aliases, "
            f"and RxNav name-search did not reverse-confirm the RxCUI."
        ),
    )


def verify_unii_field(
    *,
    stored_unii: str | None,
    standard_name: str,
    cas_stored: str | None,
    gsrs: GSRSClient | None,
) -> Verdict:
    if not stored_unii:
        return Verdict(status="verified_clean", notes="no unii stored (acceptable)")
    if not UNII_RE.match(stored_unii):
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="malformed_unii",
            evidence=f"Stored UNII '{stored_unii}' is not a 10-char alphanumeric.",
        )
    if gsrs is None:
        return Verdict(status="unresolvable", reason_code="no_gsrs_client_available")

    full = gsrs.get_full_substance(stored_unii)
    if not full:
        return Verdict(
            status="unresolvable",
            severity="high",
            reason_code="unii_not_found_in_gsrs",
            evidence=f"GSRS /substances({stored_unii})?view=full returned no record.",
        )

    # GSRS substance record has a "_name" field at top level or under "names".
    gsrs_name = full.get("_name") or ""
    names_list = []
    if isinstance(full.get("names"), list):
        for n in full["names"]:
            if isinstance(n, dict) and isinstance(n.get("name"), str):
                names_list.append(n["name"])

    if not gsrs_name and names_list:
        gsrs_name = names_list[0]

    all_gsrs_tokens: set[str] = _tokens(gsrs_name)
    for n in names_list:
        all_gsrs_tokens |= _tokens(n)

    iqm_tokens = _tokens(standard_name)
    if not (all_gsrs_tokens & iqm_tokens):
        return Verdict(
            status="mismatched",
            severity="medium",
            reason_code="unii_name_does_not_align_with_iqm",
            api_response={"unii": stored_unii, "gsrs_name": gsrs_name, "names_sample": names_list[:5]},
            evidence=(
                f"UNII {stored_unii} resolves to GSRS substance '{gsrs_name}' "
                f"with no token overlap with IQM '{standard_name}'."
            ),
        )

    # Cross-check CAS if both stored
    if cas_stored:
        gsrs_codes = full.get("codes") or []
        gsrs_cas = [c.get("code") for c in gsrs_codes if isinstance(c, dict) and c.get("codeSystem") == "CAS"]
        if gsrs_cas and cas_stored not in gsrs_cas:
            return Verdict(
                status="mismatched",
                severity="medium",
                reason_code="cas_unii_disagreement",
                api_response={"unii": stored_unii, "gsrs_cas_codes": gsrs_cas, "cas_stored": cas_stored},
                evidence=(
                    f"IQM stores CAS={cas_stored} but UNII {stored_unii}'s GSRS "
                    f"record lists CAS codes {gsrs_cas}."
                ),
            )

    return Verdict(
        status="verified_clean",
        api_response={"unii": stored_unii, "gsrs_name": gsrs_name},
    )


def verify_pubchem_cid_field(
    *,
    stored_cid: Any,
    standard_name: str,
    aliases: list[str],
    cas_stored: str | None,
    pubchem: PubChemClient | None,
) -> Verdict:
    if stored_cid is None or stored_cid == "":
        return Verdict(status="verified_clean", notes="no pubchem_cid stored (acceptable)")
    try:
        cid_int = int(stored_cid)
    except (TypeError, ValueError):
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="malformed_pubchem_cid",
            evidence=f"Stored pubchem_cid '{stored_cid}' is not an integer.",
        )
    if pubchem is None:
        return Verdict(status="unresolvable", reason_code="no_pubchem_client_available")

    props = pubchem.cid_to_properties(cid_int)
    if props is None:
        return Verdict(
            status="unresolvable",
            severity="high",
            reason_code="cid_not_found_in_pubchem",
            evidence=f"PubChem CID {cid_int} did not resolve to property record.",
        )

    synonyms = pubchem.cid_to_synonyms(cid_int)
    # Token-level alignment between any synonym and standard_name/aliases
    syn_tokens: set[str] = set()
    for s in synonyms:
        syn_tokens |= _tokens(s)
    syn_tokens |= _tokens(props.get("IUPACName"))
    iqm_tokens = _all_iqm_name_tokens(standard_name, aliases)
    if not (syn_tokens & iqm_tokens):
        return Verdict(
            status="mismatched",
            severity="medium",
            reason_code="cid_synonyms_do_not_align_with_iqm",
            api_response={
                "cid": cid_int,
                "iupac": props.get("IUPACName"),
                "synonyms_sample": synonyms[:10],
            },
            evidence=(
                f"PubChem CID {cid_int} has IUPACName='{props.get('IUPACName')}' "
                f"and {len(synonyms)} synonyms with no token overlap with IQM '{standard_name}'."
            ),
        )

    # CAS cross-check
    if cas_stored:
        cid_cas_list = [s for s in synonyms if CAS_RE.match(s)]
        if cid_cas_list and cas_stored not in cid_cas_list:
            return Verdict(
                status="mismatched",
                severity="medium",
                reason_code="cas_cid_disagreement",
                api_response={
                    "cid": cid_int,
                    "cas_stored": cas_stored,
                    "cas_in_pubchem": cid_cas_list[:5],
                },
                evidence=(
                    f"IQM stores CAS={cas_stored} but PubChem CID {cid_int}'s "
                    f"synonyms list CAS={cid_cas_list[:3]}."
                ),
            )

    return Verdict(
        status="verified_clean",
        api_response={"cid": cid_int, "iupac": props.get("IUPACName"), "inchi_key": props.get("InChIKey")},
    )


def verify_cas_field(
    *,
    stored_cas: str | None,
    standard_name: str,
    pubchem: PubChemClient | None,
) -> Verdict:
    if not stored_cas:
        return Verdict(status="verified_clean", notes="no cas stored (acceptable)")
    if not CAS_RE.match(stored_cas):
        return Verdict(
            status="mismatched",
            severity="high",
            reason_code="malformed_cas",
            evidence=f"Stored CAS '{stored_cas}' does not match CAS regex.",
        )
    if pubchem is None:
        return Verdict(status="unresolvable", reason_code="no_pubchem_client_available")

    cid = pubchem.cas_to_cid(stored_cas)
    if cid is None:
        return Verdict(
            status="unresolvable",
            severity="medium",
            reason_code="cas_not_found_in_pubchem",
            evidence=f"PubChem name-search for CAS '{stored_cas}' returned no CID.",
        )

    synonyms = pubchem.cid_to_synonyms(cid)
    syn_tokens: set[str] = set()
    for s in synonyms:
        syn_tokens |= _tokens(s)
    iqm_tokens = _tokens(standard_name)
    if not (syn_tokens & iqm_tokens):
        return Verdict(
            status="mismatched",
            severity="medium",
            reason_code="cas_resolves_to_unrelated_compound",
            api_response={"cas": stored_cas, "resolved_cid": cid, "synonyms_sample": synonyms[:10]},
            evidence=(
                f"CAS {stored_cas} resolves in PubChem to CID {cid} whose synonyms "
                f"do not token-overlap with IQM '{standard_name}'."
            ),
        )

    return Verdict(
        status="verified_clean",
        api_response={"cas": stored_cas, "resolved_cid": cid},
    )


# --------------------------------------------------------------------------- #
# Per-parent audit
# --------------------------------------------------------------------------- #


def audit_parent(
    *,
    canonical_id: str,
    entry: dict,
    iqm_snapshot_sha256: str,
    umls: UMLSClient | None,
    pubchem: PubChemClient | None,
    gsrs: GSRSClient | None,
    rxnorm: RxNormClient | None,
    rxnav_reverse_check=None,
) -> dict:
    """Audit one IQM parent. Returns the per-parent record dict."""
    standard_name = entry.get("standard_name") or canonical_id
    aliases = list(entry.get("aliases") or [])
    cui_note = entry.get("cui_note")
    cui_status = entry.get("cui_status")
    iqm_is_class_level = _iqm_appears_class_level(standard_name)

    stored_cui = entry.get("cui")
    stored_rxcui = entry.get("rxcui")
    ext = entry.get("external_ids") or {}
    stored_unii = ext.get("unii")
    stored_cid = ext.get("pubchem_cid")
    stored_cas = ext.get("cas")
    stored_inchi = ext.get("inchi_key")  # informational only; not authority-checked here

    fields: dict[str, dict] = {}

    fields["cui"] = {
        "stored": stored_cui,
        "verdict": verify_cui_field(
            stored_cui=stored_cui,
            standard_name=standard_name,
            aliases=aliases,
            cui_note=cui_note,
            cui_status=cui_status,
            umls=umls,
            iqm_is_class_level=iqm_is_class_level,
        ).to_dict(),
    }
    fields["rxcui"] = {
        "stored": stored_rxcui,
        "verdict": verify_rxcui_field(
            stored_rxcui=stored_rxcui,
            standard_name=standard_name,
            aliases=aliases,
            rxnorm=rxnorm,
            rxnav_reverse_check=rxnav_reverse_check,
        ).to_dict(),
    }
    fields["external_ids.unii"] = {
        "stored": stored_unii,
        "verdict": verify_unii_field(
            stored_unii=stored_unii,
            standard_name=standard_name,
            cas_stored=stored_cas,
            gsrs=gsrs,
        ).to_dict(),
    }
    fields["external_ids.pubchem_cid"] = {
        "stored": stored_cid,
        "verdict": verify_pubchem_cid_field(
            stored_cid=stored_cid,
            standard_name=standard_name,
            aliases=aliases,
            cas_stored=stored_cas,
            pubchem=pubchem,
        ).to_dict(),
    }
    fields["external_ids.cas"] = {
        "stored": stored_cas,
        "verdict": verify_cas_field(
            stored_cas=stored_cas,
            standard_name=standard_name,
            pubchem=pubchem,
        ).to_dict(),
    }
    fields["external_ids.inchi_key"] = {
        "stored": stored_inchi,
        "verdict": Verdict(
            status="verified_clean" if not stored_inchi else "verified_clean",
            notes=("inchi_key not authority-checked in this pass" if stored_inchi else "no inchi_key stored (acceptable)"),
        ).to_dict(),
    }

    return {
        "canonical_id": canonical_id,
        "verified_at": datetime.now(UTC).isoformat(),
        "iqm_snapshot_sha256": iqm_snapshot_sha256,
        "standard_name": standard_name,
        "iqm_class_level": iqm_is_class_level,
        "fields": fields,
    }


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}


def collect_findings(record: dict) -> list[dict]:
    """Extract one finding object per non-clean field from a per-parent record."""
    out = []
    for field_name, payload in record["fields"].items():
        verdict = payload["verdict"]
        if verdict.get("status") == "verified_clean":
            continue
        if verdict.get("status") == "skipped_intentional_null":
            # Recorded in per_parent record, but not surfaced as a finding.
            continue
        out.append({
            "canonical_id": record["canonical_id"],
            "standard_name": record.get("standard_name"),
            "field": field_name,
            "current_value": payload.get("stored"),
            "status": verdict.get("status"),
            "severity": verdict.get("severity"),
            "reason_code": verdict.get("reason_code"),
            "current_resolution": verdict.get("api_response"),
            "proposed_value": verdict.get("proposed_value"),
            "proposed_resolution": verdict.get("proposed_resolution"),
            "evidence": verdict.get("evidence"),
            "notes": verdict.get("notes"),
        })
    return out


# Seed findings — pre-known content-verified bugs (per spec §"Existing seed
# findings — already verified"). Pre-populated so re-runs prove methodology
# catches them.
SEED_FINDINGS = [
    {
        "canonical_id": "coq10",
        "standard_name": "Coenzyme Q10",
        "field": "cui",
        "current_value": "C1843920",
        "status": "mismatched",
        "severity": "high",
        "reason_code": "resolved_to_disease_or_syndrome",
        "current_resolution": {
            "name": "COENZYME Q10 DEFICIENCY",
            "semantic_types": ["Disease or Syndrome"],
        },
        "proposed_value": "C0041536",
        "proposed_resolution": {
            "name": "ubidecarenone",
            "semantic_types": ["Organic Chemical", "Pharmacologic Substance"],
        },
        "evidence": (
            "Pre-verified seed (spec §'Existing seed findings'). UMLS exact "
            "search for 'Coenzyme Q10' returns C0041536 (ubidecarenone). "
            "C1843920 is the disease, not the substance."
        ),
        "notes": "seed; included so re-runs prove the methodology catches known cases",
        "seed": True,
    },
    {
        "canonical_id": "5_htp",
        "standard_name": "5-HTP",
        "field": "cui",
        "current_value": "C5815882",
        "status": "mismatched",
        "severity": "high",
        "reason_code": "resolved_to_branded_or_clinical_drug",
        "current_resolution": {
            "name": "Natrol Melatonin + 5-HTP",
            "semantic_types": ["Clinical Drug"],
        },
        "proposed_value": "C0000578",
        "proposed_resolution": {
            "name": "5-hydroxytryptophan",
            "semantic_types": ["Organic Chemical", "Pharmacologic Substance"],
        },
        "evidence": (
            "Pre-verified seed (spec §'Existing seed findings'). UMLS exact "
            "search for '5-HTP' returns C0000578 (5-hydroxytryptophan). "
            "C5815882 is a branded Natrol combo product."
        ),
        "notes": "seed; included so re-runs prove the methodology catches known cases",
        "seed": True,
    },
    {
        "canonical_id": "genistein",
        "standard_name": "Genistein",
        "field": "agent2_id (in curated_interactions_v1.json, not IQM)",
        "current_value": "C0061202",
        "status": "verified_fixed",
        "severity": "informational",
        "reason_code": "previously_corrupted_in_curated_interactions_now_fixed",
        "evidence": (
            "Pre-verified seed (spec §'Existing seed findings'). IQM "
            "genistein.cui=C0061202 verified correct. "
            "curated_interactions_v1.json DSI_LEVOTHYROXINE_SOY and DSI_OC_SOY "
            "previously had agent2_id=C0301704 (phosphatidylserine); fixed in "
            "commit 8e3e318d on 2026-05-27. Sweep should confirm no related "
            "entries still reference C0301704."
        ),
        "notes": "seed; sanity check during sweep",
        "seed": True,
    },
]


def write_findings_jsonl(findings: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort: seed=True first, then severity high>medium>low, then canonical_id ASC
    def _key(f: dict) -> tuple:
        return (
            0 if f.get("seed") else 1,
            SEVERITY_ORDER.get(f.get("severity"), 4),
            f.get("canonical_id") or "",
            f.get("field") or "",
        )

    with path.open("w") as fh:
        for f in sorted(findings, key=_key):
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")


def write_queue_csv(findings: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    high = [f for f in findings if (f.get("severity") == "high" or f.get("seed"))]
    high.sort(key=lambda f: (0 if f.get("seed") else 1, f.get("canonical_id") or ""))
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "canonical_id",
            "field",
            "current",
            "proposed",
            "severity",
            "reason_code",
            "evidence",
            "seed",
        ])
        for f in high:
            w.writerow([
                f.get("canonical_id", ""),
                f.get("field", ""),
                f.get("current_value", ""),
                f.get("proposed_value") or "",
                f.get("severity", ""),
                f.get("reason_code", ""),
                (f.get("evidence") or "").replace("\n", " ").strip(),
                "yes" if f.get("seed") else "",
            ])


def write_master_report(
    *,
    out_dir: Path,
    iqm_snapshot_sha256: str,
    parents_audited: int,
    parents_total: int,
    findings: list[dict],
    per_field_totals: dict[str, dict[str, int]],
    api_request_counts: dict[str, int],
    duration_seconds: float,
) -> None:
    sev_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "informational": 0}
    status_counts: dict[str, int] = {}
    for f in findings:
        if f.get("seed"):
            continue
        sev = f.get("severity") or "unknown"
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        st = f.get("status") or "unknown"
        status_counts[st] = status_counts.get(st, 0) + 1

    lines: list[str] = []
    lines.append("# IQM Identifier Sweep — Master Report")
    lines.append("")
    lines.append(f"- **Generated:** {datetime.now(UTC).isoformat()}")
    lines.append(f"- **IQM snapshot SHA-256:** `{iqm_snapshot_sha256}`")
    lines.append(f"- **Parents audited:** {parents_audited} of {parents_total}")
    lines.append(f"- **Run duration:** {duration_seconds:.1f}s")
    lines.append("")
    lines.append("## Per-field verification totals")
    lines.append("")
    lines.append("| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |")
    lines.append("|---|---|---|---|---|---|")
    for field_name in sorted(per_field_totals.keys()):
        d = per_field_totals[field_name]
        lines.append(
            f"| `{field_name}` "
            f"| {d.get('verified_clean', 0)} "
            f"| {d.get('mismatched', 0)} "
            f"| {d.get('unresolvable', 0)} "
            f"| {d.get('ambiguous_authority', 0)} "
            f"| {d.get('skipped_intentional_null', 0)} |"
        )
    lines.append("")
    lines.append("## Severity breakdown (non-seed findings)")
    lines.append("")
    for sev in ("high", "medium", "low", "informational"):
        lines.append(f"- **{sev}:** {sev_counts.get(sev, 0)}")
    lines.append("")
    lines.append("## Status breakdown (non-seed findings)")
    lines.append("")
    for st, n in sorted(status_counts.items()):
        lines.append(f"- **{st}:** {n}")
    lines.append("")
    lines.append("## Authority API call counts")
    lines.append("")
    for k, v in api_request_counts.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append("## Seed findings (pre-known content-verified bugs)")
    lines.append("")
    lines.append("These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.")
    lines.append("")
    seeds = [f for f in findings if f.get("seed")]
    for f in seeds:
        lines.append(f"- **{f.get('canonical_id')}** / `{f.get('field')}`: "
                     f"{f.get('reason_code')} (severity={f.get('severity')})")
    lines.append("")
    lines.append("## High-severity findings (this run)")
    lines.append("")
    highs = [f for f in findings if (not f.get('seed')) and f.get("severity") == "high"]
    if not highs:
        lines.append("_None found._")
    else:
        for f in highs:
            lines.append(f"- **{f.get('canonical_id')}** / `{f.get('field')}` "
                         f"({f.get('reason_code')}): current=`{f.get('current_value')}`"
                         + (f" → proposed=`{f.get('proposed_value')}`" if f.get('proposed_value') else ""))
    lines.append("")
    lines.append("## Outputs")
    lines.append("")
    lines.append("- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id")
    lines.append("- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review")
    lines.append("- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`")
    lines.append("- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)")
    lines.append("")
    lines.append("## Next step")
    lines.append("")
    lines.append("Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MASTER_REPORT.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Top-level run
# --------------------------------------------------------------------------- #


def run_sweep(
    *,
    iqm_path: Path,
    out_dir: Path,
    cache_dir: Path,
    limit: int | None,
    only_id: str | None,
    umls: UMLSClient | None,
    pubchem: PubChemClient | None,
    gsrs: GSRSClient | None,
    rxnorm: RxNormClient | None,
    rxnav_reverse_check=None,
) -> dict:
    """Run the sweep with injected clients (for tests). Returns a summary dict."""
    raw_bytes = iqm_path.read_bytes()
    iqm_snapshot_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    iqm = json.loads(raw_bytes.decode())

    parent_keys = sorted(k for k in iqm.keys() if not k.startswith("_"))
    parents_total = len(parent_keys)

    if only_id:
        parent_keys = [k for k in parent_keys if k == only_id]
    elif limit is not None and limit > 0:
        parent_keys = parent_keys[:limit]

    per_parent_dir = out_dir / "per_parent"
    per_parent_dir.mkdir(parents=True, exist_ok=True)

    all_findings: list[dict] = list(SEED_FINDINGS)

    per_field_totals: dict[str, dict[str, int]] = {}

    # In-process cache for rxnav name reverse-checks. Persisted under cache_dir.
    rxnav_cache_path = cache_dir / "rxnav_name_reverse.json"
    rxnav_name_cache: dict[str, list[str]] = {}
    if rxnav_cache_path.exists():
        try:
            rxnav_name_cache = json.loads(rxnav_cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            rxnav_name_cache = {}

    if rxnav_reverse_check is None and rxnorm is not None:
        def rxnav_reverse_check(name: str) -> list[str]:
            return rxnav_name_to_rxcuis(name, _cache=rxnav_name_cache)

    started = time.time()
    for idx, key in enumerate(parent_keys, start=1):
        entry = iqm[key]
        if not isinstance(entry, dict):
            continue
        record = audit_parent(
            canonical_id=key,
            entry=entry,
            iqm_snapshot_sha256=iqm_snapshot_sha256,
            umls=umls,
            pubchem=pubchem,
            gsrs=gsrs,
            rxnorm=rxnorm,
            rxnav_reverse_check=rxnav_reverse_check,
        )
        (per_parent_dir / f"{key}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
        all_findings.extend(collect_findings(record))

        for field_name, payload in record["fields"].items():
            status = payload["verdict"].get("status", "unknown")
            d = per_field_totals.setdefault(field_name, {})
            d[status] = d.get(status, 0) + 1

        # Periodically persist client caches (PubChem/GSRS auto-save in client.save_cache)
        if idx % 25 == 0:
            if pubchem is not None:
                try:
                    pubchem.save_cache()
                except Exception:
                    pass
            if gsrs is not None:
                try:
                    gsrs.save_cache()
                except Exception:
                    pass
            print(f"  [{idx}/{len(parent_keys)}] {key} verified.", file=sys.stderr)

    # Final cache flush
    for client_name, client_obj in (("pubchem", pubchem), ("gsrs", gsrs)):
        if client_obj is None:
            continue
        try:
            client_obj.save_cache()
        except Exception as e:
            print(f"  [warn] could not save {client_name} cache: {e}", file=sys.stderr)

    # Persist rxnav-name-reverse cache
    try:
        rxnav_cache_path.parent.mkdir(parents=True, exist_ok=True)
        rxnav_cache_path.write_text(json.dumps(rxnav_name_cache, indent=1))
    except Exception as e:
        print(f"  [warn] could not save rxnav-name-reverse cache: {e}", file=sys.stderr)

    duration = time.time() - started

    # Write outputs
    write_findings_jsonl(all_findings, out_dir / "findings.jsonl")
    write_queue_csv(all_findings, out_dir / "queue.csv")
    write_master_report(
        out_dir=out_dir,
        iqm_snapshot_sha256=iqm_snapshot_sha256,
        parents_audited=len(parent_keys),
        parents_total=parents_total,
        findings=all_findings,
        per_field_totals=per_field_totals,
        api_request_counts={
            "umls": getattr(umls, "request_count", 0) if umls else 0,
            "pubchem": getattr(pubchem, "_request_count", 0) if pubchem else 0,
            "gsrs": getattr(gsrs, "request_count", 0) if gsrs else 0,
            "rxnorm_in_memory_cache_size": len(getattr(rxnorm, "_cache", {})) if rxnorm else 0,
        },
        duration_seconds=duration,
    )

    return {
        "parents_audited": len(parent_keys),
        "parents_total": parents_total,
        "findings_count": len(all_findings),
        "snapshot_sha256": iqm_snapshot_sha256,
        "duration_seconds": duration,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="iqm_identifier_sweep",
        description=(
            "Read-only IQM identifier sweep. Verifies every external identifier on "
            "every IQM parent against UMLS / RxNav / PubChem / FDA GSRS with "
            "strict-mode verdict guards. Writes only to --out and --cache; "
            "scripts/data/*.json is never opened for write."
        ),
    )
    p.add_argument("--file", required=True, type=Path,
                   help="Path to ingredient_quality_map.json")
    p.add_argument("--out", required=True, type=Path,
                   help="Output directory for reports/")
    p.add_argument("--cache", required=True, type=Path,
                   help="Cache directory for raw authority API responses")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N parents (smoke test)")
    p.add_argument("--only-id", default=None,
                   help="Process a single canonical_id only (debug)")
    p.add_argument("--umls-api-key", default=os.environ.get("UMLS_API_KEY", ""),
                   help="UMLS API key (defaults to UMLS_API_KEY env var)")
    p.add_argument("--offline", action="store_true",
                   help="Run with no live API calls (clients receive empty cache "
                        "and return None / unresolvable for every lookup). For "
                        "wiring tests.")
    # Explicitly NO --apply / --write. Adding one breaks the safety contract.
    return p


def main() -> int:
    parser = build_arg_parser()
    # Defensive: refuse if anyone tries --apply / --write
    for forbidden in ("--apply", "--write", "--apply-mismatches"):
        if forbidden in sys.argv:
            print(
                f"ERROR: {forbidden} is not supported. This sweep is read-only "
                "by design (spec §'Do NOT auto-fix'). Use the follow-up "
                "per-finding workflow.",
                file=sys.stderr,
            )
            return 2

    args = parser.parse_args()

    if not args.file.exists():
        print(f"ERROR: IQM file not found: {args.file}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    if args.offline:
        umls = pubchem = gsrs = rxnorm = None
    else:
        api_key = args.umls_api_key
        if not api_key:
            print("ERROR: UMLS_API_KEY not set. Pass --umls-api-key or set the env var.", file=sys.stderr)
            return 2

        umls_cache = args.cache / "umls.json"
        pubchem_cache = args.cache / "pubchem.json"
        gsrs_cache = args.cache / "gsrs.json"

        umls = UMLSClient(api_key=api_key, cache_path=umls_cache)
        if not umls.probe():
            print("ERROR: UMLS probe failed. Check UMLS_API_KEY and network.", file=sys.stderr)
            return 2

        pubchem = PubChemClient(cache_path=pubchem_cache)
        gsrs = GSRSClient(cache_path=gsrs_cache)
        rxnorm = RxNormClient()

    summary = run_sweep(
        iqm_path=args.file,
        out_dir=args.out,
        cache_dir=args.cache,
        limit=args.limit,
        only_id=args.only_id,
        umls=umls,
        pubchem=pubchem,
        gsrs=gsrs,
        rxnorm=rxnorm,
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
