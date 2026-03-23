#!/usr/bin/env python3
"""
Fix harmful_additives.json schema issues (v5.0 → v5.1).

Changes applied:
1. Remove top-level CUI → merge into external_ids.umls_cui (keep external_ids as source of truth)
2. Remove match_rules.label_tokens (redundant with aliases + standard_name)
3. Remove match_rules.regex (always null)
4. Normalize external_ids key casing → lowercase (umls_cui, cas, pubchem_cid)
5. Normalize references_structured to consistent field set
6. Fix jurisdictional_statuses status_codes (allowed → approved, monitored → warning_issued)
7. Remove exposure_context (always "supplement" — dead weight)
8. Remove entity_type where "ingredient" (keep for "class"/"category" entries — meaningful)
9. Remove class_tags (fold info into category)
10. Update _metadata to reflect changes
"""

import json
import copy
from pathlib import Path
from datetime import date

DATA_FILE = Path(__file__).parent / "data" / "harmful_additives.json"

# Canonical references_structured fields
CANONICAL_REF_FIELDS = {
    "type", "authority", "title", "citation", "url",
    "published_date", "evidence_grade", "supports_claims"
}

# Status code mapping
STATUS_CODE_MAP = {
    "allowed": "approved",
    "monitored": "warning_issued",
    "warning_required": "restricted",
}


def normalize_external_ids(entry: dict) -> dict:
    """Merge top-level CUI into external_ids with normalized lowercase keys."""
    top_cui = entry.pop("CUI", None)

    ext = entry.get("external_ids", {})
    if ext is None:
        ext = {}

    normalized = {}

    # umls_cui: prefer external_ids value, fall back to top-level CUI
    umls = ext.get("umls_cui") or ext.get("UMLS_CUI") or top_cui
    normalized["umls_cui"] = umls if umls else None

    # cas: normalize key casing
    cas = ext.get("cas") or ext.get("CAS")
    normalized["cas"] = cas if cas else None

    # pubchem_cid: normalize key casing
    pc = ext.get("pubchem_cid") or ext.get("pubchem") or ext.get("PubChem")
    normalized["pubchem_cid"] = pc if pc else None

    entry["external_ids"] = normalized
    return entry


def normalize_match_rules(entry: dict) -> dict:
    """Remove label_tokens and regex from match_rules."""
    mr = entry.get("match_rules", {})
    if mr is None:
        return entry

    mr.pop("label_tokens", None)
    mr.pop("regex", None)

    entry["match_rules"] = mr
    return entry


def normalize_references_structured(entry: dict) -> dict:
    """Ensure consistent field set in references_structured."""
    refs = entry.get("references_structured", [])
    if not refs:
        entry["references_structured"] = []
        return entry

    normalized_refs = []
    for ref in refs:
        norm = {
            "type": ref.get("type", "regulatory"),
            "authority": ref.get("authority", "OTHER"),
            "title": ref.get("title") or ref.get("citation", ""),
            "citation": ref.get("citation", ""),
            "url": ref.get("url", ""),
            "published_date": ref.get("published_date"),
            "evidence_grade": ref.get("evidence_grade", "R"),
            "supports_claims": ref.get("supports_claims", []),
        }
        normalized_refs.append(norm)

    entry["references_structured"] = normalized_refs
    return entry


def normalize_jurisdictional_statuses(entry: dict) -> dict:
    """Map non-canonical status_codes to canonical enum."""
    statuses = entry.get("jurisdictional_statuses", [])
    if not statuses:
        entry["jurisdictional_statuses"] = []
        return entry

    for status in statuses:
        code = status.get("status_code", "")
        if code in STATUS_CODE_MAP:
            status["status_code"] = STATUS_CODE_MAP[code]

    entry["jurisdictional_statuses"] = statuses
    return entry


def remove_dead_weight_fields(entry: dict) -> dict:
    """Remove fields that carry no information."""
    # exposure_context: always "supplement"
    entry.pop("exposure_context", None)

    # entity_type: remove only if "ingredient" (keep "class"/"category" — meaningful)
    if entry.get("entity_type") == "ingredient":
        entry.pop("entity_type", None)

    # class_tags: remove (info is in category already)
    entry.pop("class_tags", None)

    return entry


def add_changelog_entry(entry: dict, change_text: str) -> dict:
    """Add a changelog entry to the review block."""
    review = entry.get("review", {})
    if not review:
        review = {
            "status": "validated",
            "last_reviewed_at": str(date.today()),
            "reviewed_by": "schema_v5.1_migration",
            "next_review_due": None,
            "change_log": [],
        }

    changelog = review.get("change_log", [])
    changelog.append({
        "date": str(date.today()),
        "change": change_text,
        "reason": "schema_v5.1_migration",
    })
    review["change_log"] = changelog
    entry["review"] = review
    return entry


def process_entry(entry: dict) -> dict:
    """Apply all normalizations to a single entry."""
    entry = normalize_external_ids(entry)
    entry = normalize_match_rules(entry)
    entry = normalize_references_structured(entry)
    entry = normalize_jurisdictional_statuses(entry)
    entry = remove_dead_weight_fields(entry)
    entry = add_changelog_entry(
        entry,
        "Schema v5.1 migration: removed top-level CUI (→ external_ids.umls_cui), "
        "removed label_tokens/regex from match_rules, normalized external_ids casing, "
        "standardized references_structured fields, mapped status_codes to canonical enum, "
        "removed exposure_context/entity_type(ingredient)/class_tags dead-weight fields."
    )
    return entry


def update_metadata(metadata: dict, entries: list) -> dict:
    """Update _metadata to reflect schema v5.1 changes."""
    metadata["schema_version"] = "5.1.0"
    metadata["last_updated"] = str(date.today())
    metadata["total_entries"] = len(entries)

    # Recalculate risk breakdown
    risk = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    for e in entries:
        sev = e.get("severity_level", "low")
        risk[sev] = risk.get(sev, 0) + 1
    metadata["risk_breakdown"] = risk

    # Update fields documentation
    metadata["fields"] = {
        "id": "Unique identifier for the additive",
        "standard_name": "Common name for the additive",
        "aliases": "Alternative names, E-numbers, chemical names for matching",
        "category": "Classification of additive type",
        "mechanism_of_harm": "Scientific explanation of how the additive causes harm",
        "regulatory_status": "Approval status in US, EU, and other jurisdictions",
        "population_warnings": "Specific populations at higher risk",
        "notes": "Additional context and recent research findings",
        "scientific_references": "DOIs and citations for claims",
        "last_updated": "Date of last review",
        "match_rules": "Deterministic matching metadata (match_mode, fuzzy_threshold, case_sensitive, preferred_alias)",
        "references_structured": "Structured citations (type, authority, title, citation, url, published_date, evidence_grade, supports_claims)",
        "external_ids": "External identifiers (umls_cui, cas, pubchem_cid) — all lowercase keys",
        "jurisdictional_statuses": "Normalized jurisdiction status codes (approved, permitted_with_limit, restricted, warning_issued, banned, not_evaluated)",
        "review": "Governance metadata (review status, reviewer, cadence, change_log)",
        "confidence": "Confidence level pegged to evidence (high, medium, low)",
        "severity_level": "critical | high | moderate | low",
        "dose_thresholds": "ADI/TDI with value, unit, source (null if not established)",
        "entity_relationships": "Links to related entries (null if none)"
    }

    # Add migration record
    metadata["last_audit"] = str(date.today())
    metadata["audit_notes"] = (
        f"Schema v5.1 migration completed {date.today()}. "
        "Removed: top-level CUI, match_rules.label_tokens, match_rules.regex, "
        "exposure_context, entity_type (ingredient only), class_tags. "
        "Normalized: external_ids key casing (lowercase), references_structured "
        "field set, jurisdictional status_codes (allowed→approved, monitored→warning_issued, "
        "warning_required→restricted)."
    )

    # Remove entity_type from dead-weight note
    removed_fields = [
        "CUI (top-level, merged into external_ids.umls_cui)",
        "match_rules.label_tokens (redundant with aliases)",
        "match_rules.regex (always null)",
        "exposure_context (always 'supplement')",
        "entity_type (when 'ingredient' — kept for 'class'/'category')",
        "class_tags (info in category)",
    ]
    metadata["v5.1_removed_fields"] = removed_fields

    return metadata


def main():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    original_count = len(data["harmful_additives"])
    print(f"Loaded {original_count} entries")

    # Process each entry
    processed = []
    for entry in data["harmful_additives"]:
        processed.append(process_entry(copy.deepcopy(entry)))

    data["harmful_additives"] = processed
    data["_metadata"] = update_metadata(data["_metadata"], processed)

    # Write output
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Processed {len(processed)} entries")
    print(f"Schema version: {data['_metadata']['schema_version']}")
    print(f"Risk breakdown: {data['_metadata']['risk_breakdown']}")

    # Validation
    errors = []
    for e in processed:
        if "CUI" in e:
            errors.append(f"{e['id']}: still has top-level CUI")
        mr = e.get("match_rules", {})
        if "label_tokens" in mr:
            errors.append(f"{e['id']}: still has label_tokens")
        if "regex" in mr:
            errors.append(f"{e['id']}: still has regex")
        ext = e.get("external_ids", {})
        for k in ext:
            if k != k.lower():
                errors.append(f"{e['id']}: external_ids has non-lowercase key '{k}'")
        if "exposure_context" in e:
            errors.append(f"{e['id']}: still has exposure_context")
        if e.get("entity_type") == "ingredient":
            errors.append(f"{e['id']}: still has entity_type=ingredient")
        for j in e.get("jurisdictional_statuses", []):
            if j.get("status_code") in STATUS_CODE_MAP:
                errors.append(f"{e['id']}: unmapped status_code '{j['status_code']}'")
        for ref in e.get("references_structured", []):
            missing = CANONICAL_REF_FIELDS - set(ref.keys())
            if missing:
                errors.append(f"{e['id']}: ref missing fields {missing}")
            extra = set(ref.keys()) - CANONICAL_REF_FIELDS
            if extra:
                errors.append(f"{e['id']}: ref has extra fields {extra}")

    if errors:
        print(f"\n{len(errors)} VALIDATION ERRORS:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\nAll validations passed.")


if __name__ == "__main__":
    main()
