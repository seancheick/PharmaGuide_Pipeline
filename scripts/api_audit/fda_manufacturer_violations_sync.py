#!/usr/bin/env python3
"""Synch manufacturer violation entries from FDA openFDA recall feeds.

This script is designed to complement the existing `fda_weekly_sync.py` pipeline.
It reads the current manufacturer violations data and appends any newly detected
manufacturer recalls that implicate dietary supplements.

Usage:
    python scripts/api_audit/fda_manufacturer_violations_sync.py [--days 30] [--output <path>] [--api-key <FDA_KEY>]

Output:
    writes JSON to file (default: scripts/data/manufacturer_violations.json)

Note:
    1) It uses openFDA `food/enforcement` and `drug/enforcement` sources
       to capture dietary supplement-relevant recalls.
    2) It deduplicates by FDA recall number before adding new entries.
    3) It maintains the existing manufacturer normalization strategy for matching.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure scripts/ source module path is visible when run from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.fda_weekly_sync import (
    fetch_enforcement,
    fetch_fda_rss,
    is_noise,
    classify_record,
)

DATA_PATH = REPO_ROOT / "scripts" / "data" / "manufacturer_violations.json"
DEDUCTION_EXPL_PATH = REPO_ROOT / "scripts" / "data" / "manufacture_deduction_expl.json"
REPORT_DIR = REPO_ROOT / "scripts" / "api_audit" / "reports"

RECENCY_BUCKETS = [
    (365, 1.0),
    (3 * 365, 0.5),
    (5 * 365, 0.25),
    (float("inf"), 0.0),
]
DEFAULT_REPEAT_LOOKBACK_DAYS = 3 * 365

VIOLATION_CODE_MAP = {
    "CRI_TOXIC": -20,
    "CRI_UNDRUG": -15,
    "CRI_ALLER": -12,
    "CRI_CONTA": -15,
    "CRI_ADVERS": -20,
    # v2.1 additions (Phase 1 of 2026-05-13 proposal, landed 2026-05-14).
    # JSON is the source of truth; these are fallbacks for offline runs.
    "CRI_GLP1": -18,
    "CRI_ANABOLIC": -18,
    "CRI_BOT_SUB": -20,
    "HIGH_CII": -10,
    "HIGH_CGMP_CRIT": -12,
    "MOD_CIII_SING": -3,
    "MOD_CGMP": -8,
    "MOD_BRAND": -5,
    "LOW_WARN": -2,
}

SUPPLEMENT_KEYWORDS = [
    "dietary supplement", "supplement", "nutraceutical", "vitamin", "mineral",
    "herbal", "botanical", "fat burner", "weight loss", "pre-workout",
    "sarm", "cbd", "kava", "kratom", "testosterone booster",
]

SUPPLEMENT_FORM_TERMS = [
    "capsule", "capsules", "tablet", "tablets", "softgel", "softgels",
    "gummy", "gummies", "powder", "drink mix", "drops", "extract",
    "tea", "tincture",
]

EXPLICIT_SUPPLEMENT_TERMS = [
    "dietary supplement",
    "supplement",
    "nutraceutical",
    "vitamin",
    "mineral",
    "multivitamin",
    "fat burner",
    "weight loss",
    "pre-workout",
    "testosterone booster",
    "cbd",
    "kava",
    "kratom",
    "sarm",
]

GENERIC_DRUG_ONLY_TERMS = [
    " drugs ",
    " medicines ",
    " medication ",
    " pharmaceutical ",
]

# Dosage forms that are PHARMACEUTICAL-ONLY (never legitimately sold as dietary
# supplements). A drug recall with one of these forms AND no supplement-context
# signal is NOT supplement-relevant and should be filtered out of the manufacturer
# trust database. Matched as case-insensitive substrings on the lowered text.
PHARMACEUTICAL_ONLY_FORMS = [
    "transdermal system",
    "transdermal patch",
    "transdermal",
    "ophthalmic",
    "eye drops",
    "eye drop",
    "eye lubricant",
    "ear drops",
    "ear drop",
    "nasal spray",
    "nasal solution",
    "inhaler",
    "inhalation",
    "nebulizer",
    "injection",
    "injectable",
    "intravenous",
    "iv solution",
    "infusion",
    "suppository",
    "vaginal",
    "rectal",
    "topical cream",
    "topical ointment",
    "dental cream",
    "mouth rinse",
    "enema",
    "irrigation solution",
    "saline",
    "contrast agent",
    "dialysis",
    "surgical",
    "sterile lubricant",
    "antiseptic towelette",
    "antiseptic wipe",
    "antibacterial towelette",
    "hand sanitiz",   # matches sanitizer / sanitizing / sanitized — never a supplement
    "tattoo numbing",
    "numbing spray",
    "benzalkonium",   # appears only in antiseptic wipes / sprays
    "narcotic",       # fentanyl etc. — controlled Rx; never a supplement
    "rx compounding", # compounded Rx only
    "rx only",        # explicit Rx-only labeling
    "ointment",
    "salve",
    "patch ",
    "patches ",
    "implant ",       # excludes "implants" (pl.) too
    "compounded",
    "syringe",
    "tablets, usp",   # USP labeling = explicit Rx manufacturing
    "capsules, usp",
    "active pharmaceutical ingredient",
    "bulk active pharmaceutical",
    "active pharmaceutical",
    "catheter",
    "stent",
]

# Product descriptions that are clearly conventional food, not dietary supplements.
# When matched without a supplement-form term, reject the record.
PURE_FOOD_INDICATORS = [
    "vegetable",
    "vegetables",
    "vegetable(s)",
    "salad",
    "sauce",
    "salsa",
    "dressing",
    "cheese",
    "yogurt",
    "yoghurt",
    "milk",
    "butter",
    "pasta",
    "noodle",
    "noodles",
    "bread",
    "pizza",
    "sandwich",
    "soup",
    "candy ",   # trailing space to avoid "candidate"
    "gum ",
    "ice cream",
    "cereal",
    "pickled",
    "smoked",
    "cured",
    "frozen meal",
    "dried fruit",
    "dried meat",
    "jerky",
    "spice mix",
    "seasoning",
    "dried salt",
    "dried chilli",
    "dried chili",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync manufacturer_violations.json from FDA openFDA data")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days for FDA enforcement events")
    parser.add_argument("--output", default=str(DATA_PATH), help="Output filename for manufacturer_violations.json")
    parser.add_argument("--report", default=None, help="Output report path JSON (default auto)")
    parser.add_argument("--api-key", default=os.environ.get("OPENFDA_API_KEY", ""), help="openFDA API key")
    parser.add_argument("--include-rss", action="store_true", help="Also include FDA RSS sources in candidate selection")
    parser.add_argument("--confirm", action="store_true", help="Interactive confirmation prompt before writing new entries")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist file, only print summary")
    return parser.parse_args()


def is_supplement_record(record: dict) -> bool:
    relevant, _, _ = classify_record(record)
    return relevant


def _has_strong_supplement_signal(record: dict) -> bool:
    """Require a concrete supplement/product signal for RSS-only additions.

    Generic "herbal medicines/drugs" FDA alerts are too broad for the
    manufacturer violations DB unless they also identify a supplement-like
    product form or an explicit dietary-supplement term.
    """
    text = " ".join(
        [
            record.get("product_description") or "",
            record.get("reason_for_recall") or "",
            record.get("title") or "",
            record.get("description") or "",
        ]
    ).lower()
    normalized = " " + re.sub(r'\s+', ' ', text) + " "

    if any(term in normalized for term in SUPPLEMENT_FORM_TERMS):
        return True
    if any(term in normalized for term in EXPLICIT_SUPPLEMENT_TERMS):
        return True
    return False


def _matches_pharmaceutical_only_form(text: str) -> str | None:
    """Return the first pharmaceutical-only form term matched in ``text`` if any.

    Caller normalises whitespace and pads with leading+trailing space so token
    boundaries on every term work correctly. Returns the matched term (for
    diagnostics) or None.
    """
    for term in PHARMACEUTICAL_ONLY_FORMS:
        if term in text:
            return term.strip()
    return None


def _matches_pure_food(text: str) -> str | None:
    """Return the first pure-food indicator matched (caller passes normalised text)."""
    for term in PURE_FOOD_INDICATORS:
        if term in text:
            return term.strip()
    return None


# Supplement-context terms that are UNAMBIGUOUS — finding any of these in the
# record means the product is sold/marketed as a dietary supplement (not as a
# pharmaceutical that happens to use a capsule form). Generic words like
# "capsules" or "tablets" or "drops" are explicitly excluded because Rx drugs
# use those dosage forms too — the filter must not treat "Prazosin Capsules"
# as a supplement just because the word "capsules" appears.
UNAMBIGUOUS_SUPPLEMENT_TERMS = [
    "dietary supplement",
    "nutraceutical",
    "multivitamin",
    "fat burner",
    "weight loss",
    "pre-workout",
    "pre workout",
    "post-workout",
    "post workout",
    "testosterone booster",
    "male enhancement",
    "female enhancement",
    "sexual enhancement",
    "energy shot",
    "energy supplement",
    "sports nutrition",
    "muscle builder",
    "bodybuilding",
    "protein powder",
    "amino acid",
    "creatine",
    "bcaa",
    "kava",
    "kratom",
    "cbd",
    "hemp extract",
    "ashwagandha",
    "turmeric",
    "elderberry",
    "ginseng",
    "moringa",
    "tejocote",
    "fish oil",
    "krill oil",
    "omega-3",
    "collagen peptides",
    "colostrum",
    "probiotic",
    "prebiotic",
    "melatonin",
    "elderberry",
    "garcinia",
    "ephedra",
    "ma huang",
    "sarm",
    "sarms",
    "prohormone",
    "anabolic",
    "growth hormone",
    "peptide",
    "tribulus",
    "horny goat weed",
    "fenugreek",
    "yohimbe",
]


def _has_supplement_context_signal(text: str, signals: list[str]) -> bool:
    """True if the record carries a POSITIVE supplement-context signal that
    overrides pharmaceutical-form rejection.

    The override applies only when:
      (1) The text contains an UNAMBIGUOUS supplement term ("dietary supplement",
          "male enhancement", "kava", "fish oil", "sarms", etc.), OR
      (2) The classifier already tagged it with a strong supplement-adulterant
          signal category (sarms_prohibited, anabolic_steroid_prohormone,
          supplement_adulterant, stimulant_designer, synthetic_cannabinoid, etc.).

    Generic words like "capsules" / "tablets" / "drops" do NOT count as supplement
    context because Rx drugs use those dosage forms too — e.g. "Prazosin
    Hydrochloride Capsules, USP, Rx Only" must NOT be kept as a supplement-relevant
    manufacturer violation.
    """
    if any(term in text for term in UNAMBIGUOUS_SUPPLEMENT_TERMS):
        return True
    # Categories that are UNAMBIGUOUSLY supplement-context on their own —
    # any product flagged with these is almost certainly relevant to supplements.
    UNAMBIGUOUS_SIGNAL_CATEGORIES = {
        "supplement_adulterant",
        "sarms_prohibited",
        "anabolic_steroid_prohormone",
        "stimulant_designer",
        "synthetic_cannabinoid",
        "nootropic_banned",
        "novel_peptide_research_chemical",
        "hepatotoxic_botanical",
    }
    signal_set = set(signals or [])
    if UNAMBIGUOUS_SIGNAL_CATEGORIES & signal_set:
        return True
    # `pharmaceutical_contaminant` keyword list contains BOTH real
    # supplement-spiking adulterants (sildenafil, tadalafil, sibutramine)
    # AND plain Rx drugs that aren't supplement-adulterants (fentanyl,
    # oxycodone, tramadol, furosemide). To distinguish, require
    # `supplement_adulterant` co-occurrence — that signal fires on contextual
    # cues like "undeclared", "undisclosed", "active pharmaceutical ingredient",
    # which only appear when the drug was found IN a supplement (not in its
    # own Rx packaging).
    if "pharmaceutical_contaminant" in signal_set and "supplement_adulterant" in signal_set:
        return True
    # `schedule_I_psychoactive` alone is too broad — fentanyl/heroin etc. don't
    # show up in legal supplements. Require co-occurrence with supplement_adulterant
    # for the same reason as pharmaceutical_contaminant.
    if "schedule_I_psychoactive" in signal_set and "supplement_adulterant" in signal_set:
        return True
    return False


# Tier-1 HARD reject: phrases that DEFINITIVELY mean "not a dietary supplement".
# No supplement-context override can rescue these — if the text contains any of
# these terms, the record is excluded regardless of signal categories.
#
# Distinguished from PHARMACEUTICAL_ONLY_FORMS (Tier-2) because some of those
# terms (e.g. "pellet") can co-occur with legitimate supplement-adulterant
# context (testosterone pellet manufacturers often also produce supplements).
HARD_REJECT_TERMS = [
    "rx only",
    "rx-only",
    "for rx compounding",
    "rx compounding",
    "for prescription use",
    "schedule ii",
    "schedule iii",
    "schedule iv",
    "schedule v",
    "narcotic",
    "controlled substance",
    "bulk active pharmaceutical ingredient",
    "bulk active pharmaceutical",
    "bulk api",
    "active pharmaceutical ingredient",
    "transdermal",
    "injection",
    "injectable",
    "infusion",
    "intravenous",
    "ophthalmic",
    "eye drops",
    "eye drop",
    "eye lubricant",
    "ear drops",
    "ear drop",
    "nasal spray",
    "nasal solution",
    "topical cream",
    "topical ointment",
    "topical solution",
    "rectal",
    "suppository",
    "vaginal",
    "inhaler",
    "inhalation",
    "nebulizer",
    "drug substance",      # phrase appears in pharma impurity recalls (V014 Prazosin)
    "extended-release",
    "extended release",
    "immediate-release",
    "modified-release",
    "delayed-release",
    "sustained-release",
    "tablets, usp",
    "capsules, usp",
    "oral suspension",
    "oral solution",
    "for oral suspension",
    "subj to caution",
    "sterile pellet",      # compounded HRT pellets (F.H. Investments / Asteria)
    "antiseptic wipe",
    "antiseptic towelette",
    "antibacterial towelette",
    "hand wipe",
    "alcohol wipe",
    "isopropyl alcohol",
    "hand sanitiz",        # catches sanitizer / sanitizing / sanitized
    "antimicrobial wipe",
    "antimicrobial alcohol",
    "benzalkonium",
    "benzoyl peroxide",    # OTC topical acne — never a supplement
    "tattoo numbing",
    "numbing spray",
    "ointment",
    "salve",
    "saline",
    "dialysis",
    "contrast agent",
    "irrigation solution",
    "syringe",
    "catheter",
    "stent",
    "sterile lubricant",
    "surgical",
    "compounded",
    "patch ",
    "patches ",
]


def _matches_hard_reject(text: str) -> str | None:
    """Return the first hard-reject term matched (caller passes normalised text)."""
    for term in HARD_REJECT_TERMS:
        if term in text:
            return term.strip()
    return None


def is_eligible_manufacturer_record(record: dict) -> tuple[bool, str]:
    """Apply an additional conservative filter before manufacturer ingestion.

    Layered checks (each can reject):
      1. classify_record (existing relevance gate)
      2. HARD_REJECT_TERMS — unambiguous Rx / OTC / cosmetic / compounded markers
         that no supplement-context signal can override.
      3. PHARMACEUTICAL_ONLY_FORMS (Tier-2) — softer pharma-form markers that
         CAN be overridden by an unambiguous supplement-context signal
         (e.g. testosterone-pellet manufacturer is still supplement-relevant
         because testosterone shows up in illegal anabolic supplements).
      4. PURE_FOOD_INDICATORS — reject conventional food products lacking
         any supplement form term.
      5. RSS strong-signal requirement (unchanged from prior behaviour).
    """
    relevant, primary_category, signals = classify_record(record)
    if not relevant:
        return False, "not_supplement"

    # Build normalised text once for the form/food checks
    pf_text = " ".join(
        [
            record.get("product_description") or "",
            record.get("reason_for_recall") or "",
            record.get("title") or "",
            record.get("description") or "",
        ]
    ).lower()
    pf_text = " " + re.sub(r'\s+', ' ', pf_text) + " "

    # (2) Hard reject — no override possible.
    hard_term = _matches_hard_reject(pf_text)
    if hard_term:
        return False, f"hard_reject:{hard_term}"

    # (3) Soft reject — pharma-form markers that CAN be overridden by
    # unambiguous supplement-context signals.
    pharma_form = _matches_pharmaceutical_only_form(pf_text)
    if pharma_form and not _has_supplement_context_signal(pf_text, signals):
        return False, f"pharmaceutical_only_form:{pharma_form}"

    # (4) Reject pure conventional food products lacking any supplement form term.
    food_indicator = _matches_pure_food(pf_text)
    if food_indicator and not any(term in pf_text for term in SUPPLEMENT_FORM_TERMS):
        return False, f"pure_food:{food_indicator}"

    if record.get("_source_type") != "fda_rss":
        return True, ""

    if primary_category != "supplement_general" or signals:
        return True, ""

    text = " ".join(
        [
            record.get("product_description") or "",
            record.get("reason_for_recall") or "",
            record.get("title") or "",
            record.get("description") or "",
        ]
    ).lower()
    normalized = " " + re.sub(r'\s+', ' ', text) + " "

    if _has_strong_supplement_signal(record):
        return True, ""

    if any(term in normalized for term in GENERIC_DRUG_ONLY_TERMS):
        return False, "weak_rss_signal"

    return False, "weak_rss_signal"


def extract_manufacturer_from_text(record: dict) -> str | None:
    """Extract manufacturer from RSS title or text if structured field is missing."""
    def _clean_entity(value: str) -> str | None:
        value = re.sub(r"\s+", " ", (value or "").strip(" ,.-"))
        value = re.sub(r"\(\s*ebay seller id\s*\)", "", value, flags=re.IGNORECASE).strip(" ,.-")
        if "," in value:
            parts = [part.strip(" ,.-") for part in value.split(",") if part.strip(" ,.-")]
            if parts:
                domain_like = [part for part in parts if "." in part]
                value = domain_like[-1] if domain_like else parts[-1]
        if not value:
            return None
        if len(value) < 3 or len(value) > 120:
            return None
        if value.lower() in {"fda", "patients", "consumers"}:
            return None
        return value

    # Check RSS title for company names
    title = (record.get("title") or "").strip()
    if title:
        # Pattern: "Company Name Issues Recall..."; extract "Company Name"
        match = re.match(r"^([A-Za-z0-9\s&.,'()/-]+?)\s+(?:Issues|Recalls?|Advises|Announces)", title)
        if match:
            company = _clean_entity(match.group(1))
            if company:
                return company
    
    # Check RSS description/reason for addresses or entity names
    reason = (record.get("reason_for_recall") or record.get("description") or "").strip()
    if reason:
        # Pattern: "... X is recalling ..." often appears in FDA recall prose.
        match = re.search(
            r"([A-Za-z0-9][A-Za-z0-9\s&.'()/-]*(?:,\s*[A-Za-z0-9][A-Za-z0-9\s&.'()/-]*)?)\s+is recalling\b",
            reason,
            re.IGNORECASE,
        )
        if match:
            company = _clean_entity(match.group(1))
            if company:
                return company

        # Look for patterns like "Company Name, City, State" or "... by Company Name"
        match = re.search(
            r"(?:by|manufactured by|from)\s+([A-Za-z0-9\s&.,'()/-]+?)(?:,|\s+(?:of|located|in|california|new york|texas))",
            reason,
            re.IGNORECASE,
        )
        if match:
            company = _clean_entity(match.group(1))
            if company:
                return company
    
    return None


def recency_multiplier(days_since: int, deduction_expl: dict | None = None) -> float:
    if deduction_expl:
        ranges = (
            deduction_expl.get("modifiers", {})
            .get("RECENCY", {})
            .get("ranges", {})
        )
        if ranges:
            if days_since <= 365:
                return float(ranges.get("less_than_1_year", {}).get("multiplier", 1.0))
            if days_since <= 3 * 365:
                return float(ranges.get("1_to_3_years", {}).get("multiplier", 0.5))
            if days_since <= 5 * 365:
                return float(ranges.get("3_to_5_years", {}).get("multiplier", 0.25))
            return float(ranges.get("over_5_years", {}).get("multiplier", 0.0))
    for max_days, multiplier in RECENCY_BUCKETS:
        if days_since <= max_days:
            return multiplier
    return 0.0


def normalize_company_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def build_source_identifier(
    *,
    recall_number: str = "",
    source_type: str = "",
    manufacturer: str = "",
    product: str = "",
    reason: str = "",
    link: str = "",
    date_value: str = "",
) -> str:
    """Build a deterministic fallback identifier for records without recall IDs."""
    recall_number = (recall_number or "").strip().upper()
    if recall_number:
        return f"recall::{recall_number}"

    if link:
        return f"link::{link.strip().lower()}"

    parts = [
        source_type.strip().lower(),
        normalize_company_name(manufacturer),
        re.sub(r"\s+", " ", (product or "").strip().lower()),
        re.sub(r"\s+", " ", (reason or "").strip().lower())[:160],
        (date_value or "").strip(),
    ]
    return "fallback::" + "|".join(parts)


def infer_violation_code(reason: str, classification: str, status: str) -> str:
    r = (reason or "").lower()
    if any(tok in r for tok in [" aller", "allergen", "peanut", "wheat", "milk", "nuts"]):
        return "CRI_ALLER"
    if any(tok in r for tok in ["metformin", "sildenafil", "tadalafil", "diclofenac", "dexamethasone", "sibutramine", "phenolphthalein"]):
        return "CRI_UNDRUG"
    if any(tok in r for tok in ["salmonella", "listeria", "e. coli", "ecoli", "botulism"]):
        return "CRI_CONTA"
    if any(tok in r for tok in ["toxic", "poison", "death", "hospital", "serious"]):
        return "CRI_TOXIC"
    if "class ii" in (classification or "").lower():
        return "HIGH_CII"
    if "class i" in (classification or "").lower():
        return "CRI_TOXIC"
    if "class iii" in (classification or "").lower():
        return "MOD_CIII_SING"
    if status.lower() in ["ongoing", "open", "active"]:
        return "HIGH_CGMP_CRIT"
    return "LOW_WARN"


def severity_level_from_code(code: str) -> str:
    if code.startswith("CRI_"):
        return "critical"
    if code.startswith("HIGH_"):
        return "high"
    if code.startswith("MOD_"):
        return "moderate"
    return "low"


def date_from_openfda(value: str) -> str | None:
    # openFDA dates are often YYYYMMDD, or YYYY-MM-DD.
    value = (value or "").strip()
    if not value:
        return None
    try:
        if re.fullmatch(r"\d{8}", value):
            dt = datetime.strptime(value, "%Y%m%d")
            return dt.date().isoformat()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        dt = datetime.fromisoformat(value)
        return dt.date().isoformat()
    except Exception:
        return None


def compute_total_deduction(
    base: int,
    unresolved: bool,
    repeat: bool,
    multi_line: bool,
    recency_mult: float,
    deduction_expl: dict | None = None,
) -> float:
    modifiers = deduction_expl.get("modifiers", {}) if deduction_expl else {}
    extra = 0
    if unresolved:
        extra += int(modifiers.get("UNRESOLVED_VIOLATIONS", {}).get("additional_deduction", -3))
    if repeat:
        extra += int(modifiers.get("REPEAT_VIOLATIONS", {}).get("additional_deduction", -5))
    if multi_line:
        extra += int(modifiers.get("MULTIPLE_PRODUCT_LINES", {}).get("additional_deduction", -3))
    out = (base + extra) * recency_mult
    out = float(round(out, 2))
    return out


def load_deduction_expl() -> dict:
    try:
        with open(DEDUCTION_EXPL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def lookup_base_deduction(code: str, deduction_expl: dict | None = None) -> int:
    if deduction_expl:
        categories = deduction_expl.get("violation_categories", {})
        for category in categories.values():
            for subcategory in category.get("subcategories", {}).values():
                if subcategory.get("code") == code:
                    return int(subcategory.get("base_deduction", VIOLATION_CODE_MAP.get(code, -10)))
    return int(VIOLATION_CODE_MAP.get(code, -10))


def parse_entry_date(value: str | None) -> tuple[str, date]:
    normalized = date_from_openfda(value or "")
    if normalized is None:
        normalized = date.today().isoformat()
    return normalized, datetime.fromisoformat(normalized).date()


def build_repeat_violation_lookup(entries: list[dict], deduction_expl: dict | None = None) -> dict[str, bool]:
    lookback_days = DEFAULT_REPEAT_LOOKBACK_DAYS
    if deduction_expl:
        trigger = (
            deduction_expl.get("modifiers", {})
            .get("REPEAT_VIOLATIONS", {})
            .get("trigger", "")
            .lower()
        )
        if "3 years" in trigger:
            lookback_days = 3 * 365

    counts: dict[str, int] = {}
    for entry in entries:
        manufacturer_key = (
            (entry.get("manufacturer_family_id") or "").strip()
            or (entry.get("manufacturer_id") or "").strip()
            or normalize_company_name(entry.get("manufacturer", ""))
        )
        if not manufacturer_key:
            continue
        _, entry_date = parse_entry_date(entry.get("date"))
        days_since = (date.today() - entry_date).days
        if days_since <= lookback_days:
            counts[manufacturer_key] = counts.get(manufacturer_key, 0) + 1

    return {manufacturer_key: count > 1 for manufacturer_key, count in counts.items()}


def get_entry_grouping_key(entry: dict) -> str:
    return (
        (entry.get("manufacturer_family_id") or "").strip()
        or (entry.get("manufacturer_id") or "").strip()
        or normalize_company_name(entry.get("manufacturer", ""))
    )


def get_new_record_grouping_key(manufacturer: str, manufacturer_id: str) -> str:
    return manufacturer_id or normalize_company_name(manufacturer)


def _ensure_alias_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _maybe_seed_family_metadata(entry: dict) -> None:
    """Preserve curated family fields when present; otherwise keep structure explicit.

    We do not auto-invent manufacturer families. This just guarantees the schema
    can carry them once curated.
    """
    if "manufacturer_family_id" in entry and entry.get("manufacturer_family_id"):
        entry["manufacturer_family_id"] = str(entry["manufacturer_family_id"]).strip()
    if "manufacturer_family_name" in entry and entry.get("manufacturer_family_name"):
        entry["manufacturer_family_name"] = str(entry["manufacturer_family_name"]).strip()
    family_aliases = _ensure_alias_list(entry.get("manufacturer_family_aliases"))
    if family_aliases:
        entry["manufacturer_family_aliases"] = family_aliases


def _maybe_seed_related_cluster_metadata(entry: dict) -> None:
    """Preserve non-scoring related-cluster metadata when present."""
    if "related_brand_cluster_id" in entry and entry.get("related_brand_cluster_id"):
        entry["related_brand_cluster_id"] = str(entry["related_brand_cluster_id"]).strip()
    if "related_brand_cluster_name" in entry and entry.get("related_brand_cluster_name"):
        entry["related_brand_cluster_name"] = str(entry["related_brand_cluster_name"]).strip()
    cluster_aliases = _ensure_alias_list(entry.get("related_brand_cluster_aliases"))
    if cluster_aliases:
        entry["related_brand_cluster_aliases"] = cluster_aliases


def recalculate_all_entries(data: dict, deduction_expl: dict | None = None) -> int:
    entries = data.get("manufacturer_violations", [])
    repeat_lookup = build_repeat_violation_lookup(entries, deduction_expl)
    multi_line_threshold = (
        deduction_expl.get("modifiers", {})
        .get("MULTIPLE_PRODUCT_LINES", {})
        .get("product_line_threshold", 3)
        if deduction_expl
        else 3
    )
    total_deduction_cap = int(deduction_expl.get("total_deduction_cap", -25)) if deduction_expl else -25

    changed = 0
    for entry in entries:
        before = json.dumps(entry, sort_keys=True, default=str)

        normalized_date, entry_date = parse_entry_date(entry.get("date"))
        days_since = (date.today() - entry_date).days
        manufacturer = (entry.get("manufacturer") or "").strip() or "Unknown Manufacturer"
        manufacturer_id = (
            (entry.get("manufacturer_id") or "").strip()
            or normalize_company_name(manufacturer)
            or "unknownmanufacturer"
        )
        violation_code = entry.get("violation_code") or infer_violation_code(
            entry.get("reason", ""),
            entry.get("violation_type", ""),
            "resolved" if entry.get("is_resolved") else "open",
        )
        base_deduction = lookup_base_deduction(violation_code, deduction_expl)
        severity_level = severity_level_from_code(violation_code)
        recency = recency_multiplier(days_since, deduction_expl)
        product_lines_affected = int(entry.get("product_lines_affected") or 1)
        multiple_product_lines = product_lines_affected >= int(multi_line_threshold)
        grouping_key = get_entry_grouping_key(entry)
        repeat_violation = repeat_lookup.get(grouping_key, False)
        is_resolved = bool(entry.get("is_resolved"))
        total_deduction_applied = compute_total_deduction(
            base_deduction,
            not is_resolved,
            repeat_violation,
            multiple_product_lines,
            recency,
            deduction_expl,
        )
        if total_deduction_applied < total_deduction_cap:
            total_deduction_applied = float(total_deduction_cap)

        entry["manufacturer"] = manufacturer
        entry["manufacturer_id"] = manufacturer_id
        _maybe_seed_family_metadata(entry)
        _maybe_seed_related_cluster_metadata(entry)
        entry["date"] = normalized_date
        entry["days_since_violation"] = days_since
        entry["recency_multiplier"] = recency
        entry["violation_code"] = violation_code
        entry["severity_level"] = severity_level
        entry["base_deduction"] = base_deduction
        entry["multiple_product_lines"] = multiple_product_lines
        entry["repeat_violation"] = repeat_violation
        entry["total_deduction_applied"] = total_deduction_applied
        if not entry.get("source_identifier"):
            entry["source_identifier"] = build_source_identifier(
                recall_number=entry.get("fda_recall_id", ""),
                source_type=entry.get("source_type", ""),
                manufacturer=manufacturer,
                product=entry.get("product", ""),
                reason=entry.get("reason", ""),
                link=entry.get("fda_source_url", ""),
                date_value=normalized_date,
            )
        entry["user_facing_note"] = (
            f"⚠️ FDA Recall {entry.get('fda_recall_id') or ''} by {manufacturer} for "
            f"{(entry.get('product') or 'Unknown').strip()}: "
            f"{(entry.get('reason') or '').strip()} "
            f"(classification {entry.get('violation_type') or 'Recall'}). "
            f"Penalty: {total_deduction_applied} pts."
        )

        after = json.dumps(entry, sort_keys=True, default=str)
        if before != after:
            changed += 1

    return changed


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    deduction_expl = load_deduction_expl()

    date_end = datetime.now().strftime("%Y%m%d")
    date_start = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")
    report_filename = args.report or f"fda_manufacturer_violations_sync_report_{date_end}.json"
    report_path = Path(report_filename) if args.report else REPORT_DIR / report_filename
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Fetch data from FDAs.
    food_records = fetch_enforcement("food/enforcement", date_start, date_end, api_key=args.api_key)
    drug_records = fetch_enforcement("drug/enforcement", date_start, date_end, api_key=args.api_key)

    # Optionally include safety alert RSS as extra signal.
    rss_records = []
    if args.include_rss:
        print("[FDA Sync] Fetching FDA MedWatch safety alerts RSS...")
        rss_records.extend(fetch_fda_rss(
            "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml",
            args.days,
        ))
        print(f"           {len(rss_records)} items")

        print("[FDA Sync] Fetching FDA Drugs RSS...")
        rss_drugs = fetch_fda_rss(
            "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml",
            args.days,
        )
        rss_records.extend(rss_drugs)
        print(f"           {len(rss_records)} items total")

    raw_candidates = list(food_records) + list(drug_records) + list(rss_records)

    existing = {
        "deprecated": [],
        "by_recall_id": {},
        "by_identifier": {},
    }
    data = {}
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for violations in data.get("manufacturer_violations", []):
            rid = str(violations.get("fda_recall_id", "")).strip().upper()
            if rid:
                existing["by_recall_id"][rid] = violations
            source_identifier = build_source_identifier(
                recall_number=rid,
                source_type=violations.get("source_type", ""),
                manufacturer=violations.get("manufacturer", ""),
                product=violations.get("product", ""),
                reason=violations.get("reason", ""),
                link=violations.get("fda_source_url", ""),
                date_value=violations.get("date", ""),
            )
            existing["by_identifier"][source_identifier] = violations
    except FileNotFoundError:
        data = {
            "_metadata": {
                "description": "Manufacturer FDA violations and recall history",
                "purpose": "manufacturer_penalties",
                "schema_version": "5.0.0",
                "last_updated": date.today().isoformat(),
                "total_entries": 0,
                "statistics": {},
            },
            "manufacturer_violations": [],
        }
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse existing manufacturer violations data: {e}", file=sys.stderr)
        return 1

    existing_total_entries = len(data.get("manufacturer_violations", []))

    existing_ids = [int(re.sub(r"\D", "", item.get("id", "V0"))) for item in data.get("manufacturer_violations", []) if re.search(r"\d+", item.get("id", ""))]
    next_id = max(existing_ids, default=0) + 1

    added = []
    skipped = 0
    skip_reasons = {
        "not_supplement": 0,
        "weak_rss_signal": 0,
        "existing_recall_id": 0,
        "batch_duplicate_recall_id": 0,
        "existing_source_identifier": 0,
        "batch_duplicate_source": 0,
        "noise_filtered": 0,
    }
    seen_batch_recall_ids: set[str] = set()
    seen_batch_source_identifiers: set[str] = set()

    # if source contains 2+ recalls from same firm => repeat_violation handles 1. We derive later.
    manufacturer_event_counts = {}
    for entry in data.get("manufacturer_violations", []):
        key = get_entry_grouping_key(entry)
        if key:
            manufacturer_event_counts[key] = manufacturer_event_counts.get(key, 0) + 1
    for record in raw_candidates:
        eligible, skip_reason = is_eligible_manufacturer_record(record)
        if not eligible:
            skipped += 1
            # Group hard_reject:*, pharmaceutical_only_form:*, pure_food:*
            # under their umbrella keys so report counters stay sane while
            # preserving detail in the per-record skip_reason.
            if skip_reason.startswith("hard_reject"):
                skip_reasons.setdefault("hard_reject", 0)
                skip_reasons["hard_reject"] += 1
            elif skip_reason.startswith("pharmaceutical_only_form"):
                skip_reasons.setdefault("pharmaceutical_only_form", 0)
                skip_reasons["pharmaceutical_only_form"] += 1
            elif skip_reason.startswith("pure_food"):
                skip_reasons.setdefault("pure_food", 0)
                skip_reasons["pure_food"] += 1
            else:
                skip_reasons.setdefault(skip_reason, 0)
                skip_reasons[skip_reason] += 1
            continue

        recall_number = (record.get("recall_number") or "").strip().upper()
        if recall_number and recall_number in existing["by_recall_id"]:
            skipped += 1
            skip_reasons["existing_recall_id"] += 1
            continue
        if recall_number and recall_number in seen_batch_recall_ids:
            skipped += 1
            skip_reasons["batch_duplicate_recall_id"] += 1
            continue

        # Try structured field first, then fall back to text extraction
        mfr = (record.get("recalling_firm") or "").strip()
        if not mfr:
            mfr = extract_manufacturer_from_text(record) or ""
        if not mfr:
            mfr = "Unknown Manufacturer"

        if any(is_noise(record) for _ in [record]):
            skipped += 1
            skip_reasons["noise_filtered"] += 1
            continue

        d = date_from_openfda(record.get("recall_initiation_date") or record.get("report_date"))
        if d is None:
            d = date.today().isoformat()
        date_obj = datetime.fromisoformat(d).date() if isinstance(d, str) else d
        days_since = (date.today() - date_obj).days
        recency = recency_multiplier(days_since, deduction_expl)
        source_type = record.get("_source_type", "openfda_enforcement")
        product_text = (record.get("product_description") or record.get("product_quantity") or "Unknown").strip()
        reason_text = (record.get("reason_for_recall") or "").strip()
        source_identifier = build_source_identifier(
            recall_number=recall_number,
            source_type=source_type,
            manufacturer=mfr,
            product=product_text,
            reason=reason_text,
            link=record.get("link", ""),
            date_value=d,
        )
        if not recall_number and source_identifier in existing["by_identifier"]:
            skipped += 1
            skip_reasons["existing_source_identifier"] += 1
            continue
        if not recall_number and source_identifier in seen_batch_source_identifiers:
            skipped += 1
            skip_reasons["batch_duplicate_source"] += 1
            continue

        # Look for hint of repeated or unresolved
        key = get_new_record_grouping_key(mfr, normalize_company_name(mfr))
        manufacturer_event_counts[key] = manufacturer_event_counts.get(key, 0) + 1

        code = infer_violation_code(record.get("reason_for_recall"), record.get("classification"), record.get("status"))
        base_deduction = lookup_base_deduction(code, deduction_expl)
        severity_level = severity_level_from_code(code)

        is_resolved = str(record.get("status") or "").lower() in ["terminated", "completed", "closed", "resolved"]
        # repeat inference is per manufacturer history and current batch
        repeat = manufacturer_event_counts[key] > 1
        multiple_product_lines = False

        total_deduction_applied = compute_total_deduction(
            base_deduction,
            not is_resolved,
            repeat,
            multiple_product_lines,
            recency,
            deduction_expl,
        )
        total_deduction_cap = int(deduction_expl.get("total_deduction_cap", -25)) if deduction_expl else -25
        if total_deduction_applied < total_deduction_cap:
            total_deduction_applied = float(total_deduction_cap)

        fda_source_url = ""
        if recall_number:
            fda_source_url = (
                f"https://www.accessdata.fda.gov/scripts/ires/?action=Redirect"
                f"&recall_number={recall_number}"
            )
        elif source_type in ("fda_rss", "dea_federal_register"):
            fda_source_url = record.get("link", "")

        entry = {
            "id": f"V{next_id:03d}",
            "source_type": source_type,
            "fda_source_url": fda_source_url,
            "source_identifier": source_identifier,
            "manufacturer": mfr,
            "manufacturer_id": key or normalize_company_name(mfr),
            "manufacturer_family_id": None,
            "manufacturer_family_name": None,
            "manufacturer_family_aliases": [],
            "related_brand_cluster_id": None,
            "related_brand_cluster_name": None,
            "related_brand_cluster_aliases": [],
            "product": product_text,
            "product_category": "supplement",
            "violation_type": record.get("classification") or "Recall",
            "severity_level": severity_level,
            "violation_code": code,
            "base_deduction": base_deduction,
            "reason": reason_text,
            "contamination_type": code.lower(),
            "date": d,
            "days_since_violation": days_since,
            "recency_multiplier": recency,
            "illnesses_reported": int(record.get("report_date") or 0) if False else None,
            "deaths_reported": None,
            "states_affected": None,
            "product_lines_affected": 1,
            "is_resolved": is_resolved,
            "fda_action": "Recall",
            "fda_recall_id": recall_number,
            "repeat_violation": repeat,
            "multiple_product_lines": multiple_product_lines,
            "total_deduction_applied": total_deduction_applied,
            "user_facing_note": (
                f"⚠️ FDA Recall {recall_number} by {mfr} for {(record.get('product_description') or record.get('product_quantity') or 'Unknown').strip()}: "
                f"{(record.get('reason_for_recall') or '').strip()} (classification {record.get('classification') or 'Recall'}). "
                f"Penalty: {total_deduction_applied} pts."
            ),
            "internal_note": "Auto-generated by fda_manufacturer_violations_sync.py",
            "allergens": None,
            "cdc_outbreak_investigation": None,
            "cgmp_violations": None,
            "contaminants": None,
            "fda_warning_letter_id": None,
            "heavy_metals": None,
            "hospitalizations_reported": None,
            "lead_level_ppm": None,
            "related_violation_ids": None,
            "undeclared_drugs": None,
        }

        added.append(entry)
        if recall_number:
            seen_batch_recall_ids.add(recall_number)
        seen_batch_source_identifiers.add(source_identifier)
        next_id += 1

    # Append new entries and update metadata
    if added:
        data.setdefault("manufacturer_violations", []).extend(added)

    recalculated_count = recalculate_all_entries(data, deduction_expl)

    # recompute meta counters
    stats = {
        "critical_violations": 0,
        "high_violations": 0,
        "moderate_violations": 0,
        "low_violations": 0,
        "unresolved_count": 0,
        "resolved_count": 0,
        "repeat_offenders": 0,
        "active_outbreaks": 0,
    }

    manufacturer_total = {}
    for entry in data.get("manufacturer_violations", []):
        lvl = (entry.get("severity_level") or "").lower()
        stat_key = f"{lvl}_violations"
        if stat_key in stats:
            stats[stat_key] += 1
        if entry.get("is_resolved"):
            stats["resolved_count"] += 1
        else:
            stats["unresolved_count"] += 1
        manufacturer_key = get_entry_grouping_key(entry)
        manufacturer_total[manufacturer_key] = manufacturer_total.get(manufacturer_key, 0) + 1
        if entry.get("cdc_outbreak_investigation"):
            stats["active_outbreaks"] += 1

    stats["repeat_offenders"] = sum(1 for _, c in manufacturer_total.items() if c > 1)

    data.setdefault("_metadata", {})["last_updated"] = date.today().isoformat()
    data["_metadata"]["total_entries"] = len(data.get("manufacturer_violations", []))
    data["_metadata"]["statistics"] = stats

    if args.confirm and added:
        print("Interactive review: the following new entries will be added:")
        for e in added:
            print(f"  - {e['id']} {e['manufacturer']} / {e['product']} / {e['fda_recall_id'] or 'no recall ID'}")
        confirm = input("Proceed and write changes? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted by user. No file written.")
            return 0

    if args.dry_run:
        print(f"dry-run: would add {len(added)} records, skip {skipped} existing/noise")
        report = {
            "generated_at": datetime.now().isoformat(),
            "generated_by": "fda_manufacturer_violations_sync.py",
            "lookback_days": args.days,
            "include_rss": args.include_rss,
            "data_file": str(args.output),
            "report_file": str(report_path),
            "total_candidates": len(raw_candidates),
            "added_count": len(added),
            "skipped_count": skipped,
            "skip_reasons": skip_reasons,
            "existing_total": existing_total_entries,
            "existing_recall_id_total": len(existing["by_recall_id"]),
            "added_ids": [e["id"] for e in added],
            "recalculated_entry_count": recalculated_count,
            "source_counts": {
                "food_enforcement": len(food_records),
                "drug_enforcement": len(drug_records),
                "rss": len(rss_records),
            },
            "statistics": stats,
            "new_entries": added,
            "dry_run": True,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Report saved: {report_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "fda_manufacturer_violations_sync.py",
        "lookback_days": args.days,
        "include_rss": args.include_rss,
        "data_file": str(args.output),
        "report_file": str(report_path),
        "total_candidates": len(raw_candidates),
        "added_count": len(added),
        "skipped_count": skipped,
        "skip_reasons": skip_reasons,
        "existing_total": existing_total_entries,
        "existing_recall_id_total": len(existing["by_recall_id"]),
        "added_ids": [e["id"] for e in added],
        "recalculated_entry_count": recalculated_count,
        "source_counts": {
            "food_enforcement": len(food_records),
            "drug_enforcement": len(drug_records),
            "rss": len(rss_records),
        },
        "statistics": stats,
        "new_entries": added,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote {args.output}: {len(added)} new entries, {skipped} skipped")
    print(f"Report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
