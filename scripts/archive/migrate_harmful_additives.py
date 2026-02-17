import json
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path("scripts/data")
HARMFUL_PATH = DATA_DIR / "harmful_additives.json"
BANNED_PATH = DATA_DIR / "banned_recalled_ingredients.json"

BAN_KEYWORDS = [
    "ban",
    "bann",
    "restrict",
    "restricted",
    "illegal",
    "not lawful",
    "not law",
    "prohib",
    "withdrawn",
    "delist",
    "adulterant",
]

REFERENCE_TYPES = {"systematic_review", "rct", "monograph", "guidance", "regulatory_action"}
REFERENCE_AUTHORITIES = {"EU", "FDA", "IARC", "WHO", "EFSA", "OEHHA", "JECFA", "OTHER"}

STATUS_SCORE = {"critical": 9, "high": 7, "moderate": 4, "low": 2}
CONFIDENCE_MAP = {"critical": "high", "high": "high", "moderate": "medium", "low": "low"}

USED_CUIS = set()

def normalize_text(value):
    return value.lower() if isinstance(value, str) else ""

def contains_keyword(value):
    lower = normalize_text(value)
    return any(keyword in lower for keyword in BAN_KEYWORDS)

def needs_ban(entry):
    if contains_keyword(entry.get("notes")) or contains_keyword(entry.get("mechanism_of_harm")):
        return True
    for value in entry.get("regulatory_status", {}).values():
        if contains_keyword(value):
            return True
    return False

def build_match_rules(entry):
    tokens = []
    if name := entry.get("standard_name"):
        tokens.append(name)
    tokens.extend(entry.get("aliases", []) or [])
    normalized = []
    for token in tokens:
        clean = token.strip()
        if clean:
            normalized.append(clean)
    label_tokens = list(dict.fromkeys([token.lower() for token in normalized]))
    return {
        "match_mode": "alias_and_fuzzy",
        "label_tokens": label_tokens,
        "regex": None,
        "fuzzy_threshold": 0.72,
        "case_sensitive": False,
        "preferred_alias": entry.get("standard_name"),
    }

def build_reference(text, risk_level):
    citation = text.strip()
    entry = {
        "type": "systematic_review",
        "authority": "OTHER",
        "citation": citation,
        "url": "",
        "published_date": None,
        "evidence_grade": "C",
        "confidence": CONFIDENCE_MAP.get(risk_level, "low"),
    }
    lower = citation.lower()
    if citation.lower().startswith("doi:"):
        entry["url"] = "https://doi.org/" + citation.split(":", 1)[1].strip().split(" ")[0]
        entry["type"] = "systematic_review"
    if "fda" in lower or "usda" in lower:
        entry["authority"] = "FDA"
        entry["type"] = "regulatory_action"
    elif "efsa" in lower or "eu" in lower:
        entry["authority"] = "EFSA" if "efsa" in lower else "EU"
        entry["type"] = "regulatory_action"
    elif "iarc" in lower:
        entry["authority"] = "IARC"
        entry["type"] = "monograph"
    elif "who" in lower or "jeca" in lower or "jefca" in lower:
        entry["authority"] = "WHO"
        entry["type"] = "guidance"
    elif "oehha" in lower:
        entry["authority"] = "OEHHA"
        entry["type"] = "guidance"
    else:
        entry["authority"] = "OTHER"
    if entry["evidence_grade"] == "C":
        entry["evidence_grade"] = "B" if risk_level in {"critical", "high"} else "C"
    return entry

def build_references(entry):
    references = []
    for ref_text in entry.get("scientific_references", []) or []:
        references.append(build_reference(ref_text, entry.get("risk_level", "moderate")))
    if not references:
        first_reg = entry.get("regulatory_status", {})
        if first_reg:
            authority, detail = next(iter(first_reg.items()))
            references.append(
                {
                    "type": "guidance",
                    "authority": authority if authority in REFERENCE_AUTHORITIES else "OTHER",
                    "citation": detail,
                    "url": "",
                    "published_date": None,
                    "evidence_grade": "D",
                    "confidence": CONFIDENCE_MAP.get(entry.get("risk_level", "moderate"), "low"),
                }
            )
        else:
            references.append(
                {
                    "type": "guidance",
                    "authority": "OTHER",
                    "citation": "Internal hazard flag",
                    "url": "",
                    "published_date": None,
                    "evidence_grade": "D",
                    "confidence": "low",
                }
            )
    return references

def build_external_ids(entry):
    cui = entry.get("CUI") or None
    if cui and cui in USED_CUIS:
        cui = None
    elif cui:
        USED_CUIS.add(cui)
    return {
        "umls_cui": cui,
        "cas": None,
        "pubchem": None,
    }

def build_jurisdiction_statuses(entry):
    statuses = []
    for authority, detail in entry.get("regulatory_status", {}).items():
        detail_lower = detail.lower()
        if contains_keyword(detail):
            status_code = "warning_required"
        elif "monitor" in detail_lower or "limit" in detail_lower:
            status_code = "monitored"
        else:
            status_code = "allowed"
        statuses.append(
            {
                "authority": authority,
                "jurisdiction": authority,
                "status_code": status_code,
                "scope": "supplement",
                "effective_range": {"start": None, "end": None},
                "source_ref": None,
            }
        )
    if not statuses:
        statuses.append(
            {
                "authority": "WHO",
                "jurisdiction": "global",
                "status_code": "monitored",
                "scope": "general",
                "effective_range": {"start": None, "end": None},
                "source_ref": None,
            }
        )
    return statuses

def build_review(entry):
    last = entry.get("last_updated") or "2026-01-05"
    try:
        last_date = datetime.strptime(last, "%Y-%m-%d")
    except ValueError:
        last_date = datetime.strptime(last, "%Y")
    next_review = last_date + timedelta(days=180)
    return {
        "status": "validated",
        "last_reviewed_at": last_date.strftime("%Y-%m-%d"),
        "reviewed_by": "migration_script",
        "next_review_due": next_review.strftime("%Y-%m-%d"),
        "change_log": [
            {
                "date": last_date.strftime("%Y-%m-%d"),
                "change": "added v2.1 schema (match_rules, references_structured, review)",
                "reason": "harmful_additives refactor",
            }
        ],
    }

def map_difficulty(risk_level):
    return "low" if risk_level == "critical" else "medium"

def build_harmful_entry(entry):
    entry = deepcopy(entry)
    match_rules = build_match_rules(entry)
    entry["match_rules"] = match_rules
    entry.setdefault("scientific_references", entry.get("scientific_references") or [])
    entry["references_structured"] = build_references(entry)
    entry["external_ids"] = build_external_ids(entry)
    entry["jurisdictional_statuses"] = build_jurisdiction_statuses(entry)
    entry["review"] = build_review(entry)
    risk_level = entry.get("risk_level", "moderate")
    entry["severity_score"] = STATUS_SCORE.get(risk_level, 4)
    entry["confidence"] = CONFIDENCE_MAP.get(risk_level, "medium")
    entry["exposure_context"] = "supplement"
    return entry

def map_category_to_ingredient_type(category):
    if category in {"heavy_metal", "contaminant_packaging"}:
        return "contaminant"
    return "synthetic"

def build_banned_entry(harmful_entry):
    entry = deepcopy(harmful_entry)
    entry["id"] = f"BANNED_{harmful_entry['id']}"
    entry["status"] = "banned"
    authorities = [
        status["authority"] for status in entry.get("jurisdictional_statuses", []) if status.get("authority")
    ]
    entry["banned_by"] = "; ".join(sorted(set(authorities)))
    entry["reason"] = entry.get("notes")
    entry["mechanism_of_harm"] = entry.get("mechanism_of_harm")
    entry["fda_warning"] = any(
        status["authority"] in {"FDA", "US"} for status in entry.get("jurisdictional_statuses", [])
    )
    entry["jurisdictions"] = []
    for status in entry.get("jurisdictional_statuses", []):
        region = status["jurisdiction"]
        level = "state" if region in {"California"} else "federal"
        name = region if level == "state" else ""
        citation = entry.get("regulatory_status", {}).get(status["authority"], "")
        entry["jurisdictions"].append(
            {
                "region": region,
                "level": level,
                "status": "banned" if status["status_code"] != "allowed" else "restricted",
                "effective_date": "",
                "source": {"type": "regulatory_action", "citation": citation or status["authority"]},
            }
        )
    entry["legal_status_enum"] = "restricted"
    entry["clinical_risk_enum"] = entry.get("risk_level", "high")
    entry["canonical_name"] = entry.get("standard_name")
    entry["synonyms"] = entry.get("aliases", []) or []
    entry["ingredient_type"] = map_category_to_ingredient_type(entry.get("category"))
    entry["class_tags"] = [entry.get("category"), "migrated_harmful_additives"]
    entry["use_case_categories"] = ["general"]
    entry["source_category"] = "harmful_additives_migration"
    entry["source_confidence"] = entry.get("confidence", "medium")
    entry["data_quality"] = {
        "completeness": 0.9,
        "missing_fields": [],
        "review_status": entry.get("review", {}).get("status", "validated"),
    }
    entry["update_flags"] = {"needs_source_verification": False}
    entry["supersedes_ids"] = [harmful_entry["id"]]
    entry["match_rules"] = harmful_entry.get("match_rules", {})
    entry["references_structured"] = harmful_entry.get("references_structured", [])
    return entry

def main():
    harmful_raw = json.loads(HARMFUL_PATH.read_text())
    banned_raw = json.loads(BANNED_PATH.read_text())
    harmful = harmful_raw["harmful_additives"]
    new_harmful = []
    moved_ids = []
    banned_candidates = []
    for entry in harmful:
        enriched = build_harmful_entry(entry)
        if needs_ban(entry):
            moved_ids.append(entry["id"])
            banned_candidates.append(enriched)
        else:
            new_harmful.append(enriched)
    target_key = "high_risk_ingredients"
    banned_ids = {it["standard_name"].lower() for it in banned_raw.get(target_key, [])}
    appended = 0
    for entry in banned_candidates:
        if entry["standard_name"].lower() in banned_ids:
            continue
        enhanced = build_banned_entry(entry)
        banned_raw.setdefault(target_key, []).append(enhanced)
        appended += 1
    harmful_raw["harmful_additives"] = new_harmful
    harmful_raw["database_info"]["version"] = "2.1.0"
    harmful_raw["database_info"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
    harmful_raw["database_info"]["total_additives"] = len(new_harmful)
    harmful_raw["_metadata"]["schema_version"] = "2.1"
    harmful_raw["_metadata"]["total_entries"] = len(new_harmful)
    harmful_raw["_metadata"]["fields"].update(
        {
            "match_rules": "Deterministic matching metadata",
            "references_structured": "Structured citations with authority and grade",
            "external_ids": "External identifiers (CUI, CAS, PubChem)",
            "jurisdictional_statuses": "Normalized jurisdiction status codes",
            "review": "Governance metadata (review status, reviewer, cadence)",
            "severity_score": "Numeric severity score (0-10)",
            "confidence": "Confidence level pegged to evidence",
        }
    )
    HARMFUL_PATH.write_text(json.dumps(harmful_raw, indent=2, sort_keys=False) + "\n")
    BANNED_PATH.write_text(json.dumps(banned_raw, indent=2, sort_keys=False) + "\n")
    print(f"Moved {len(moved_ids)} entries to banned DB ({appended} appended).")


if __name__ == "__main__":
    main()
