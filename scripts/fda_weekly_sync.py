#!/usr/bin/env python3
"""
FDA Weekly Sync Script

Fetches supplement and medication-related safety data from multiple sources:
  - openFDA food/enforcement   (dietary supplement recalls)
  - openFDA drug/enforcement   (drug recalls with supplement implications)
  - FDA Safety Alerts RSS      (warning letters, safety communications)
  - DEA Federal Register RSS   (new scheduling actions)

Generates a structured sync report for Claude (/fda-weekly-sync skill) to review
and apply to banned_recalled_ingredients.json.

Usage:
    python fda_weekly_sync.py [--days 7] [--output report.json]

Options:
    --days N     Look back N days (default: 7)
    --output     Output report path (default: fda_sync_report_YYYYMMDD.json)
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests


# ─── Config ───────────────────────────────────────────────────────────────────

DATA_FILE = Path(__file__).parent / "data" / "banned_recalled_ingredients.json"
OPENFDA_BASE = "https://api.fda.gov"

# ─── Supplement Detection ──────────────────────────────────────────────────────

# If product_type contains any of these → always relevant (no keyword check needed)
SUPPLEMENT_PRODUCT_TYPES = {"dietary supplement"}

# For product_type = "Food" or "Drug", also check description/reason for these
SUPPLEMENT_KEYWORDS = [
    # General supplement terms
    "dietary supplement", "supplement", "nutraceutical",
    "vitamin", "mineral", "multivitamin",
    "herbal", "botanical", "herb", "plant extract",
    "traditional medicine", "ayurvedic", "tcm",
    # Product categories
    "weight loss", "fat burner", "fat burn", "slimming",
    "bodybuilding", "muscle", "pre-workout", "preworkout", "post-workout",
    "testosterone booster", "testosterone support",
    "sexual enhancement", "male enhancement", "libido", "aphrodisiac", "erectile",
    "energy drink", "energy shot", "nootropic", "cognitive enhancer",
    "sleep aid", "relaxation", "stress relief", "adaptogen",
    "immune support", "detox", "cleanse",
    # Specific ingredient/product keywords
    "protein powder", "amino acid", "creatine", "bcaa",
    "probiotic", "prebiotic", "enzyme",
    "omega-3", "fish oil", "krill oil", "collagen", "biotin",
    "melatonin", "ginseng", "ashwagandha", "turmeric", "elderberry",
    "garcinia", "green tea extract", "raspberry ketone",
    "hoodia", "bitter orange", "synephrine",
    "cbd", "hemp", "cannabidiol", "delta-8", "thc",
    "kava", "kratom", "mitragyna",
    "amanita", "mushroom extract", "functional mushroom",
    "peptide", "sarm", "growth hormone", "hgh",
    "steroid", "prohormone", "anabolic",
    "colostrum", "spirulina", "chlorella", "maca",
    "tribulus", "fenugreek", "horny goat weed",
    "ephedra", "ma huang",
]

# ─── Signal Category Detection ─────────────────────────────────────────────────
# Maps to source_category values in our DB schema.
# The REASON text is checked against these keyword lists to tag each recall
# with the type of concern it represents.

SIGNAL_CATEGORIES = {
    # Prescription drugs spiked into supplements (pharmaceutical_adulterants)
    "supplement_adulterant": [
        "undeclared", "undisclosed", "not declared", "not listed on label",
        "active pharmaceutical ingredient", "pharmaceutical ingredient",
        "prescription drug", "prescription medication", "rx drug",
        "drug substance", "drug ingredient",
    ],
    # Specific known pharmaceutical spiking agents
    "pharmaceutical_contaminant": [
        "sildenafil", "tadalafil", "vardenafil", "avanafil",
        "sibutramine", "phentermine", "fenfluramine", "lorcaserin",
        "orlistat", "metformin", "glipizide", "glibenclamide",
        "meloxicam", "diclofenac", "celecoxib", "naproxen", "ibuprofen",
        "fluoxetine", "sertraline", "paroxetine",
        "alprazolam", "diazepam", "clonazepam", "lorazepam",
        "tramadol", "hydrocodone", "oxycodone", "codeine", "fentanyl",
        "methocarbamol", "cyclobenzaprine",
        "furosemide", "hydrochlorothiazide",
        "phenolphthalein", "bisacodyl",
    ],
    # SARMs marketed as supplements
    "sarms_prohibited": [
        "sarm", "sarms", "selective androgen receptor modulator",
        "rad-140", "rad140", "testolone",
        "lgd-4033", "lgd4033", "ligandrol",
        "mk-677", "mk677", "ibutamoren",
        "ostarine", "mk-2866", "enobosarm",
        "cardarine", "gw-501516", "gw501516",
        "andarine", "s4", "s-4",
        "yk-11", "yk11", "s23", "s-23",
        "ac-262", "sr9009", "stenabolic",
    ],
    # Anabolic steroids and prohormones
    "anabolic_steroid_prohormone": [
        "anabolic steroid", "prohormone", "androgenic",
        "testosterone", "stanozolol", "winstrol",
        "oxandrolone", "anavar", "nandrolone", "deca",
        "trenbolone", "boldenone", "equipoise",
        "methandrostenolone", "dianabol",
        "drostanolone", "masteron", "clostebol",
        "clenbuterol", "dnp", "2,4-dinitrophenol",
        "trendione", "epistane", "superdrol",
    ],
    # Stimulants and sympathomimetics
    "stimulant_designer": [
        "dmaa", "1,3-dimethylamylamine", "geranamine",
        "dmha", "2-amino-6-methylheptane", "octodrine",
        "dmba", "1,3-dimethylbutylamine", "4-amino-2-methylpentane",
        "beta-methylphenethylamine", "bmpea",
        "aegeline", "acacia rigidula",
        "ephedra", "ephedrine", "pseudoephedrine",
        "methylsynephrine", "oxilofrine",
        "amphetamine", "methamphetamine",
        "phenylethylamine", "pea",
    ],
    # Heavy metals and environmental contamination
    "heavy_metal_contamination": [
        "lead", "arsenic", "mercury", "cadmium",
        "heavy metal", "heavy metals", "toxic metal",
    ],
    # Microbial contamination
    "microbial_contamination": [
        "salmonella", "listeria", "listeria monocytogenes",
        "e. coli", "e.coli", "escherichia coli",
        "mold", "mould", "fungal", "aflatoxin", "mycotoxin",
        "microbial", "microbiological", "bacterial",
        "insanitary", "rodent", "pest", "filth",
    ],
    # Liver-toxic botanicals
    "hepatotoxic_botanical": [
        "hepatotoxic", "hepatotoxicity",
        "liver toxicity", "liver injury", "liver damage", "liver failure",
        "drug-induced liver", "dili",
        "hepatitis", "cholestatic",
        "pyrrolizidine", "comfrey", "kava", "kava kava",
        "aristolochic", "aristolochia",
        "pennyroyal", "chaparral",
    ],
    # Schedule I psychoactives being sold as supplements
    "schedule_I_psychoactive": [
        "psilocybin", "psilocin", "magic mushroom",
        "muscimol", "ibotenic acid", "amanita muscaria",
        "mescaline", "peyote",
        "psychoactive", "hallucinogenic", "psychedelic",
        "dmt", "dimethyltryptamine",
        "kratom", "mitragynine", "7-hydroxymitragynine",
        "salvia divinorum", "salvinorin",
    ],
    # Synthetic cannabinoids
    "synthetic_cannabinoid": [
        "synthetic cannabinoid", "synthetic cannabis",
        "spice", "k2", "thc analog", "thc analogue",
        "jwh-", "am-2201", "ab-fubinaca",
        "delta-8 thc", "delta-8", "delta-10 thc",
        "thco", "hhc",
    ],
    # Novel peptides / research chemicals
    "novel_peptide_research_chemical": [
        "novel peptide", "research chemical",
        "tb-500", "bpc-157", "cjc-1295", "ipamorelin",
        "aod-9604", "melanotan", "pt-141", "bremelanotide",
        "ghrp-6", "ghrp-2", "sermorelin",
        "igf-1", "igf1", "insulin-like growth factor",
        "hcg", "human chorionic gonadotropin",
    ],
    # Nootropics with banned status
    "nootropic_banned": [
        "picamilon", "vinpocetine", "huperzine a",
        "adrafinil", "racetam", "piracetam", "aniracetam",
        "phenibut", "phenylpiracetam",
        "tianeptine",
        "n,n-dimethylpentylamine",
    ],
    # General manufacturing violations (insanitary, cgmp, etc.)
    "manufacturing_violation": [
        "cgmp", "current good manufacturing practice",
        "adulterated", "misbranded",
        "unapproved new drug", "new drug application",
        "ndi", "new dietary ingredient",
        "not generally recognized as safe", "gras",
    ],
}

# ─── Known Substance Names ────────────────────────────────────────────────────
# Used for extracting substance names from recall text.
# Covers ALL categories in the DB, not just adulterants.

KNOWN_SUBSTANCES = [
    # Pharmaceutical adulterants — erectile dysfunction
    "sildenafil", "tadalafil", "vardenafil", "avanafil",
    # Pharmaceutical adulterants — weight loss
    "sibutramine", "phentermine", "fenfluramine", "lorcaserin", "orlistat",
    # Pharmaceutical adulterants — diabetes
    "metformin", "glipizide", "glibenclamide",
    # Pharmaceutical adulterants — NSAIDs / pain
    "meloxicam", "diclofenac", "celecoxib", "naproxen", "ibuprofen",
    # Pharmaceutical adulterants — psych / CNS
    "fluoxetine", "sertraline", "alprazolam", "diazepam", "clonazepam",
    "tramadol", "hydrocodone", "oxycodone", "codeine",
    "methocarbamol", "cyclobenzaprine",
    # Pharmaceutical adulterants — diuretics / laxatives
    "furosemide", "hydrochlorothiazide", "phenolphthalein", "bisacodyl",
    # SARMs
    "rad-140", "rad140", "testolone",
    "lgd-4033", "lgd4033", "ligandrol",
    "mk-677", "ibutamoren",
    "ostarine", "enobosarm",
    "cardarine", "gw-501516",
    "andarine", "s-23",
    "yk-11",
    # Anabolic steroids
    "testosterone", "stanozolol", "oxandrolone", "nandrolone",
    "trenbolone", "boldenone", "methandrostenolone", "drostanolone",
    "trendione", "epistane", "superdrol", "clostebol",
    "clenbuterol", "dnp", "2,4-dinitrophenol",
    # Designer stimulants
    "dmaa", "1,3-dimethylamylamine",
    "dmha", "octodrine",
    "dmba", "1,3-dimethylbutylamine",
    "beta-methylphenethylamine", "bmpea",
    "aegeline", "acacia rigidula",
    "ephedrine", "pseudoephedrine", "synephrine", "methylsynephrine", "oxilofrine",
    # Heavy metals
    "arsenic", "lead", "mercury", "cadmium",
    # Schedule I psychoactives
    "psilocybin", "psilocin", "muscimol", "ibotenic acid",
    "mescaline", "dmt", "dimethyltryptamine",
    "salvinorin",
    # Kratom alkaloids
    "mitragynine", "7-hydroxymitragynine",
    # Nootropics with banned status
    "picamilon", "vinpocetine", "phenibut", "tianeptine",
    # Hepatotoxic / toxic botanicals
    "aristolochic acid", "pennyroyal",
    "pyrrolizidine", "comfrey",
    # Novel peptides
    "igf-1", "bpc-157", "tb-500", "melanotan",
    "ipamorelin", "sermorelin",
    # Microbial contaminants (for brand recall extraction)
    "salmonella", "listeria", "aflatoxin",
]

# ─── Noise Filters ────────────────────────────────────────────────────────────
# Supplement-tagged recalls we definitively skip — pure food safety, no
# supplement-specific substance concern.

SKIP_REASON_PATTERNS = [
    # Undeclared allergens with no dangerous substance
    r"undeclared\s+(milk|soy|wheat|peanut|tree nut|egg|fish|shellfish|sesame)\b(?!.*undeclared\s+(?:drug|pharmaceutical|ingredient|substance))",
    # Temperature / cold chain failures
    r"\btemperature\s+(?:abuse|excursion|control)\b",
    r"\bbroken\s+cold\s+chain\b",
    # Pure packaging / label defect with no substance issue
    r"\b(wrong|incorrect|missing)\s+(label|labeling|package|packaging)\b(?!.*undeclared\s+(?:drug|pharmaceutical|ingredient))",
    # Underfill / product quantity
    r"\b(underfill|overfill|quantity|shortage)\b",
]


# ─── openFDA API ──────────────────────────────────────────────────────────────

def build_date_range(days_back: int) -> tuple:
    end = datetime.now()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_enforcement(endpoint: str, date_start: str, date_end: str) -> list:
    """Fetch recall records from an openFDA endpoint within a date range."""
    url = f"{OPENFDA_BASE}/{endpoint}.json"
    all_results = []
    skip = 0

    while skip < 500:  # hard cap per endpoint
        params = {
            "search": f"report_date:[{date_start}+TO+{date_end}]",
            "limit": 100,
            "skip": skip,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for r in results:
                r["_source_type"] = "openfda_enforcement"
                r["_fda_endpoint"] = endpoint
            all_results.extend(results)
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            skip += len(results)
            if skip >= total:
                break
        except requests.RequestException as e:
            print(f"[WARN] {endpoint}: {e}", file=sys.stderr)
            break

    return all_results


def fetch_fda_rss(rss_url: str, days_back: int) -> list:
    """
    Fetch items from an FDA RSS feed, filtering to the last N days.
    Returns items as dicts with _source_type='fda_rss'.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    items = []
    try:
        resp = requests.get(rss_url, timeout=30, headers={"User-Agent": "fda-weekly-sync/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            pub_date_raw = item.findtext("pubDate") or ""
            try:
                pub_date = parsedate_to_datetime(pub_date_raw)
                if pub_date < cutoff:
                    continue
            except Exception:
                pass  # include if date unparseable

            items.append({
                "title": (item.findtext("title") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pub_date": pub_date_raw,
                "product_description": (item.findtext("title") or "").strip(),
                "reason_for_recall": (item.findtext("description") or "").strip(),
                "product_type": "Dietary Supplement",  # default for supplement RSS
                "recalling_firm": "",
                "recall_number": "",
                "classification": "",
                "status": "Ongoing",
                "recall_initiation_date": "",
                "report_date": pub_date_raw,
                "termination_date": None,
                "distribution_pattern": "",
                "_source_type": "fda_rss",
                "_rss_url": rss_url,
            })
    except requests.RequestException as e:
        print(f"[WARN] RSS fetch {rss_url}: {e}", file=sys.stderr)
    except ET.ParseError as e:
        print(f"[WARN] RSS parse {rss_url}: {e}", file=sys.stderr)

    return items


def fetch_dea_federal_register(days_back: int) -> list:
    """
    Fetch DEA scheduling actions from the Federal Register API.
    Catches new Schedule I/II/III designations that affect supplements.
    """
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = "https://www.federalregister.gov/api/v1/articles"
    params = {
        "conditions[agencies][]": "drug-enforcement-administration",
        "conditions[type][]": ["Rule", "Proposed Rule", "Notice"],
        "conditions[publication_date][gte]": since,
        "fields[]": ["title", "abstract", "html_url", "publication_date",
                     "document_number", "action", "agencies"],
        "per_page": 20,
        "order": "newest",
    }
    items = []
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for result in data.get("results", []):
            title = result.get("title", "")
            abstract = result.get("abstract", "") or ""
            combined = f"{title} {abstract}".lower()
            # Only include if supplement-relevant (scheduling of something people take)
            if any(kw in combined for kw in [
                "dietary supplement", "schedule i", "schedule ii", "schedule iii",
                "controlled substance", "analog", "designer drug",
                "cannabinoid", "stimulant", "opioid", "psychedelic",
                "kratom", "mitragynine", "sarm", "anabolic",
            ]):
                items.append({
                    "title": title,
                    "description": abstract,
                    "link": result.get("html_url", ""),
                    "pub_date": result.get("publication_date", ""),
                    "product_description": title,
                    "reason_for_recall": abstract,
                    "product_type": "Controlled Substance / Scheduling Action",
                    "recalling_firm": "DEA",
                    "recall_number": result.get("document_number", ""),
                    "classification": "DEA Scheduling",
                    "status": "Active",
                    "recall_initiation_date": result.get("publication_date", ""),
                    "report_date": result.get("publication_date", ""),
                    "termination_date": None,
                    "distribution_pattern": "Federal",
                    "_source_type": "dea_federal_register",
                })
    except requests.RequestException as e:
        print(f"[WARN] DEA Federal Register: {e}", file=sys.stderr)

    return items


# ─── Supplement Relevance ─────────────────────────────────────────────────────

def is_noise(recall: dict) -> bool:
    """Return True if this recall matches a known noise pattern we always skip."""
    reason = (recall.get("reason_for_recall") or "").lower()
    for pattern in SKIP_REASON_PATTERNS:
        if re.search(pattern, reason, re.IGNORECASE):
            return True
    return False


def classify_record(record: dict) -> tuple:
    """
    Determine if a record is relevant and what signal categories it hits.

    Returns (is_relevant: bool, primary_category: str, signal_categories: list[str])

    Primary category maps directly to source_category values in our DB.
    """
    product_type = (record.get("product_type") or "").lower()
    description = (record.get("product_description") or "").lower()
    reason = (record.get("reason_for_recall") or "").lower()
    title = (record.get("title") or "").lower()
    combined = f"{product_type} {description} {reason} {title}"

    source_type = record.get("_source_type", "")

    # DEA actions are always relevant (scheduling actions affect supplements directly)
    if source_type == "dea_federal_register":
        return True, "schedule_I_psychoactive", ["manufacturing_violation"]

    # Determine if supplement-related
    is_supplement = (
        any(pt in product_type for pt in SUPPLEMENT_PRODUCT_TYPES)
        or any(kw in combined for kw in SUPPLEMENT_KEYWORDS)
    )
    is_drug = "drug" in product_type and not is_supplement

    if not is_supplement and not is_drug:
        return False, "", []

    # Skip pure noise (allergen labels, temperature abuse, etc.)
    if is_supplement and is_noise(record):
        return False, "", []

    # Detect signal categories
    detected = []
    for cat, keywords in SIGNAL_CATEGORIES.items():
        if keywords and any(kw in combined for kw in keywords):
            detected.append(cat)

    # Determine primary category (priority order)
    priority = [
        "supplement_adulterant",
        "pharmaceutical_contaminant",
        "sarms_prohibited",
        "anabolic_steroid_prohormone",
        "schedule_I_psychoactive",
        "stimulant_designer",
        "synthetic_cannabinoid",
        "nootropic_banned",
        "novel_peptide_research_chemical",
        "hepatotoxic_botanical",
        "heavy_metal_contamination",
        "microbial_contamination",
        "manufacturing_violation",
    ]
    primary = next((p for p in priority if p in detected), None)

    if primary is None:
        # No specific signal detected — still include if it's a dietary supplement recall
        if is_supplement:
            primary = "supplement_general"
        elif is_drug and detected:
            primary = detected[0]
        else:
            return False, "", []

    return True, primary, detected


# ─── Substance Extraction ─────────────────────────────────────────────────────

def extract_substances(record: dict) -> list:
    """Extract likely substance names from recall text."""
    text = " ".join([
        record.get("reason_for_recall") or "",
        record.get("product_description") or "",
        record.get("title") or "",
        record.get("description") or "",
    ]).lower()

    found = []

    # Match against known substance list (covers all DB categories)
    for substance in KNOWN_SUBSTANCES:
        if re.search(r"\b" + re.escape(substance) + r"\b", text):
            found.append(substance)

    # Pattern: "contains/found [undeclared] <substance>"
    patterns = [
        r"undeclared\s+([a-z][a-z0-9\s\-,]+?)(?:\s*[,\.;]|\s+and\s|\s+in\s|\s+which)",
        r"contains?\s+(?:undeclared\s+)?([a-z][a-z0-9\s\-,]+?)(?:\s*[,\.;]|\s+and\s|\s+which\s|\s+a\s)",
        r"presence\s+of\s+([a-z][a-z0-9\s\-]+?)(?:\s*[,\.;]|\s+and\s|\s+in\s)",
        r"spiked\s+with\s+([a-z][a-z0-9\s\-]+?)(?:\s*[,\.;]|\s+and\s|\s+in\s)",
        r"found\s+to\s+contain\s+([a-z][a-z0-9\s\-]+?)(?:\s*[,\.;]|\s+and\s)",
        r"adulterated\s+with\s+([a-z][a-z0-9\s\-]+?)(?:\s*[,\.;]|\s+and\s)",
        r"positive\s+(?:test\s+)?for\s+([a-z][a-z0-9\s\-]+?)(?:\s*[,\.;]|\s+and\s|\s+in\s)",
    ]
    for pat in patterns:
        for match in re.finditer(pat, text):
            candidate = match.group(1).strip().rstrip(",")
            # Filter: reasonable name length, not a stop phrase
            if 3 <= len(candidate) <= 60 and candidate not in found:
                stop_phrases = {"the product", "product", "this product", "supplement", "tablet"}
                if candidate not in stop_phrases:
                    found.append(candidate)

    return list(dict.fromkeys(found))  # dedup, preserve order


# ─── Database Cross-reference ─────────────────────────────────────────────────

def load_database(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_existing_index(db: dict) -> dict:
    """Build a name → entry index covering all aliases for fast lookups."""
    index = {}
    for entry in db.get("ingredients", []):
        index[entry.get("standard_name", "").lower()] = entry
        for alias in entry.get("aliases", []):
            index[alias.lower()] = entry
        # Also index by id
        if entry.get("id"):
            index[entry["id"].lower()] = entry
    return index


def find_existing(substance: str, index: dict):
    return index.get(substance.lower())


# ─── Stale Recall Detection ───────────────────────────────────────────────────

def check_stale_recalls(db: dict) -> list:
    """Find recalled entries older than 1 year to verify if still active."""
    today = datetime.now()
    stale = []
    for entry in db.get("ingredients", []):
        if entry.get("status") != "recalled":
            continue
        reg_date = entry.get("regulatory_date")
        if not reg_date:
            continue
        try:
            entry_date = datetime.strptime(reg_date[:10], "%Y-%m-%d")
            age_days = (today - entry_date).days
            if age_days > 365:
                recall_number = None
                for ref in entry.get("references_structured", []):
                    if "recall_number" in (ref.get("citation") or "").lower():
                        recall_number = ref.get("citation")
                        break
                stale.append({
                    "id": entry["id"],
                    "standard_name": entry["standard_name"],
                    "regulatory_date": reg_date,
                    "age_days": age_days,
                    "recall_scope": entry.get("recall_scope"),
                    "match_mode": entry.get("match_mode"),
                    "action": "verify_still_active",
                    "fda_search_url": "https://www.accessdata.fda.gov/scripts/ires/",
                    "note": (
                        f"Entry is {age_days} days old. Verify on FDA whether recall is terminated. "
                        "If product-specific recall is terminated → set match_mode=historical. "
                        "If ingredient-level ban → keep banned/active regardless of recall status."
                    ),
                })
        except (ValueError, TypeError):
            continue
    return stale


# ─── Report Formatting ────────────────────────────────────────────────────────

def format_record_for_report(record: dict, primary_category: str,
                              signal_categories: list, substances: list,
                              known: list, unknown: list) -> dict:
    recall_number = record.get("recall_number", "")
    source_type = record.get("_source_type", "openfda_enforcement")

    entry = {
        "source_type": source_type,
        "recall_number": recall_number,
        "event_id": record.get("event_id"),
        "fda_endpoint": record.get("_fda_endpoint"),
        "product_type": record.get("product_type"),
        "classification": record.get("classification"),
        "recall_status": record.get("status"),
        "product_description": record.get("product_description"),
        "recalling_firm": record.get("recalling_firm"),
        "reason_for_recall": record.get("reason_for_recall"),
        "distribution_pattern": record.get("distribution_pattern"),
        "recall_initiation_date": record.get("recall_initiation_date"),
        "report_date": record.get("report_date"),
        "termination_date": record.get("termination_date"),
        "primary_category": primary_category,
        "signal_categories": signal_categories,
        "extracted_substances": substances,
        "substances_already_tracked": known,
        "substances_new": unknown,
    }

    # Source URL
    if source_type == "openfda_enforcement" and recall_number:
        entry["fda_source_url"] = (
            f"https://www.accessdata.fda.gov/scripts/ires/?action=Redirect"
            f"&recall_number={recall_number}"
        )
    elif source_type == "fda_rss":
        entry["fda_source_url"] = record.get("link", "")
        entry["rss_source"] = record.get("_rss_url", "")
    elif source_type == "dea_federal_register":
        entry["fda_source_url"] = record.get("link", "")

    return entry


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FDA Weekly Sync - generates multi-source recall report for Claude review"
    )
    parser.add_argument("--days", type=int, default=7,
                        help="Days to look back (default: 7)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output report path")
    args = parser.parse_args()

    today_str = datetime.now().strftime("%Y%m%d")
    date_start, date_end = build_date_range(args.days)
    output_path = (
        Path(args.output) if args.output
        else Path(__file__).parent / f"fda_sync_report_{today_str}.json"
    )

    print(f"[FDA Sync] Period: {date_start} → {date_end} ({args.days} days)")

    # ── 1. Fetch all sources ──────────────────────────────────────────────────

    print("[FDA Sync] Fetching openFDA food/enforcement...")
    food_records = fetch_enforcement("food/enforcement", date_start, date_end)
    print(f"           {len(food_records)} records")

    print("[FDA Sync] Fetching openFDA drug/enforcement...")
    drug_records = fetch_enforcement("drug/enforcement", date_start, date_end)
    print(f"           {len(drug_records)} records")

    print("[FDA Sync] Fetching FDA dietary supplement safety alerts RSS...")
    supp_rss = fetch_fda_rss(
        "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/dietary-supplements/rss.xml",
        args.days,
    )
    print(f"           {len(supp_rss)} items")

    print("[FDA Sync] Fetching FDA MedWatch safety alerts RSS...")
    medwatch_rss = fetch_fda_rss(
        "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch-safety-alerts-human-medical-products/rss.xml",
        args.days,
    )
    print(f"           {len(medwatch_rss)} items")

    print("[FDA Sync] Fetching DEA Federal Register scheduling actions...")
    dea_records = fetch_dea_federal_register(args.days)
    print(f"           {len(dea_records)} items")

    all_records = food_records + drug_records + supp_rss + medwatch_rss + dea_records
    print(f"[FDA Sync] Total across all sources: {len(all_records)}")

    # ── 2. Load existing DB ───────────────────────────────────────────────────

    if not DATA_FILE.exists():
        print(f"[ERROR] Database not found: {DATA_FILE}", file=sys.stderr)
        return 1

    db = load_database(DATA_FILE)
    existing_index = build_existing_index(db)
    print(f"[FDA Sync] Existing DB entries: {len(db.get('ingredients', []))}")

    # ── 3. Classify and cross-reference ──────────────────────────────────────

    new_records = []      # require Claude review (substances not in DB, or brand recalls)
    tracked_records = []  # substances already tracked (informational)
    skipped_count = 0
    category_counts = {}

    for record in all_records:
        relevant, primary_cat, signal_cats = classify_record(record)
        if not relevant:
            skipped_count += 1
            continue

        category_counts[primary_cat] = category_counts.get(primary_cat, 0) + 1

        substances = extract_substances(record)
        known = [s for s in substances if find_existing(s, existing_index)]
        unknown = [s for s in substances if not find_existing(s, existing_index)]

        entry = format_record_for_report(
            record, primary_cat, signal_cats, substances, known, unknown
        )

        # Supplement brand recalls with no specific substance → still new
        # (the brand itself may need a recalled_supplement_brands entry)
        is_brand_recall = (
            primary_cat in ("supplement_general", "microbial_contamination")
            and not substances
        )

        if unknown or is_brand_recall:
            new_records.append(entry)
        elif substances:
            tracked_records.append(entry)
        else:
            # No substances extracted but a meaningful signal category — still flag
            entry["note"] = "Signal category detected but substance name not extracted — Claude review needed"
            new_records.append(entry)

    # ── 4. Stale recall check ─────────────────────────────────────────────────

    stale_recalls = check_stale_recalls(db)

    # ── 5. Build report ───────────────────────────────────────────────────────

    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "fda_weekly_sync.py",
        "scan_period": {
            "start": date_start,
            "end": date_end,
            "days_back": args.days,
        },
        "data_file": str(DATA_FILE),
        "data_sources": {
            "openfda_food_enforcement": len(food_records),
            "openfda_drug_enforcement": len(drug_records),
            "fda_supplement_rss": len(supp_rss),
            "fda_medwatch_rss": len(medwatch_rss),
            "dea_federal_register": len(dea_records),
        },
        "wada_note": (
            "WADA prohibited list is NOT fetched automatically — it is updated annually in January. "
            "Check https://www.wada-ama.org/en/prohibited-list manually once per year and update "
            "wada_prohibited_2024 entries accordingly."
        ),
        "summary": {
            "total_fetched": len(all_records),
            "skipped_not_relevant": skipped_count,
            "requiring_claude_review": len(new_records),
            "already_tracked": len(tracked_records),
            "stale_recalled_entries_to_verify": len(stale_recalls),
            "by_category": category_counts,
        },
        "new_records_requiring_review": new_records,
        "records_for_tracked_substances": tracked_records,
        "stale_recalls_to_verify": stale_recalls,
        "claude_instructions": (
            "Review 'new_records_requiring_review'. Each entry has a 'primary_category' that maps "
            "to a source_category in banned_recalled_ingredients.json and 'signal_categories' listing "
            "all detected concern types. "
            "For supplement brand recalls with no extracted substance (primary_category=supplement_general "
            "or microbial_contamination): create a RECALLED_<BRAND_SNAKE> entry with entity_type=product "
            "and recall_scope=<product name>. "
            "For substance-level recalls: create full ingredient entries. "
            "Check stale_recalls_to_verify and set match_mode=historical for terminated product recalls. "
            "Update _metadata after all changes."
        ),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────────────────

    print("\n[FDA Sync] ─── Results ────────────────────────────────────────")
    print(f"  Requiring Claude review  : {len(new_records)}")
    print(f"  Already tracked (info)   : {len(tracked_records)}")
    print(f"  Stale recalls to verify  : {len(stale_recalls)}")
    print(f"  Skipped (not relevant)   : {skipped_count}")
    if category_counts:
        print("  By category:")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"    {cat:<40} {count}")
    print(f"  Report saved             : {output_path}")
    print("\n  NOTE: WADA list is manual — check annually in January.")
    print("[FDA Sync] Done. Run /fda-weekly-sync in Claude Code to apply.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
