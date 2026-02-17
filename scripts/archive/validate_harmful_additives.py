import json
import sys
from pathlib import Path

DATA_PATH = Path("scripts/data/harmful_additives.json")
ALLOWED_STATUS_CODES = {"allowed", "monitored", "warning_required"}
BANNED_STATUS_CODES = {"banned", "restricted", "not_lawful", "illegal", "adulterant"}
REFERENCE_TYPES = {
    "regulatory_action",
    "systematic_review",
    "rct",
    "monograph",
    "guidance",
    "other",
}
REFERENCE_AUTHORITIES = {"EU", "FDA", "IARC", "WHO", "EFSA", "OEHHA", "JECFA", "OTHER"}
AUTHORITATIVE_AUTHORITIES = {"FDA", "EFSA", "IARC", "WHO", "JECFA", "OEHHA"}
EVIDENCE_GRADES = {"A", "B", "C", "D"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}


def error(msg):
    print(f"[validate_harmful_additives] ERROR: {msg}")
    sys.exit(1)


def validate_entry(entry, seen_cuis):
    if "match_rules" not in entry:
        error(f"{entry['id']} missing match_rules")
    mr = entry["match_rules"]
    if not mr.get("match_mode") or not mr.get("label_tokens"):
        error(f"{entry['id']} has invalid match_rules")
    if not isinstance(mr["label_tokens"], list) or not mr["label_tokens"]:
        error(f"{entry['id']} needs non-empty label_tokens")

    refs = entry.get("references_structured") or []
    if not refs:
        error(f"{entry['id']} missing references_structured")
    for ref in refs:
        if ref.get("type") not in REFERENCE_TYPES:
            error(f"{entry['id']} reference {ref} has invalid type")
        authority = ref.get("authority")
        if authority and authority not in REFERENCE_AUTHORITIES:
            error(f"{entry['id']} reference authority {authority} unknown")
        if ref.get("evidence_grade") not in EVIDENCE_GRADES:
            error(f"{entry['id']} reference grade invalid")
        if ref.get("confidence") not in CONFIDENCE_LEVELS:
            error(f"{entry['id']} reference confidence invalid")
        if not ref.get("citation"):
            error(f"{entry['id']} reference missing citation")

    if "external_ids" not in entry:
        error(f"{entry['id']} missing external_ids")
    cui = (entry["external_ids"].get("umls_cui") or "").strip()
    if cui:
        if cui in seen_cuis:
            error(
                f"{entry['id']} duplicates external_ids.umls_cui {cui} with {seen_cuis[cui]}"
            )
        seen_cuis[cui] = entry["id"]

    statuses = entry.get("jurisdictional_statuses") or []
    if not statuses:
        error(f"{entry['id']} missing jurisdictional_statuses")
    for status in statuses:
        code = status.get("status_code")
        if not code:
            error(f"{entry['id']} jurisdiction missing status_code")
        if code in BANNED_STATUS_CODES:
            error(f"{entry['id']} cannot expose banned status {code}")
        if code not in ALLOWED_STATUS_CODES:
            error(f"{entry['id']} status_code {code} is not recognized")

    review = entry.get("review")
    if not review:
        error(f"{entry['id']} missing review block")
    for key in ("status", "last_reviewed_at", "reviewed_by", "next_review_due"):
        if not review.get(key):
            error(f"{entry['id']} review missing {key}")
    if review.get("status") == "deprecated":
        relationships = entry.get("entity_relationships") or []
        if not any(
            rel.get("type") in {"supersedes", "superseded_by"} and rel.get("target_id")
            for rel in relationships
        ):
            error(
                f"{entry['id']} deprecated but missing supersedes/superseded_by relationship"
            )

    if entry.get("confidence") not in CONFIDENCE_LEVELS:
        error(f"{entry['id']} confidence must be high/medium/low")
    if entry.get("confidence") == "high":
        authoritative = [
            ref
            for ref in refs
            if ref.get("authority") in AUTHORITATIVE_AUTHORITIES
        ]
        if len(authoritative) < 2:
            error(
                f"{entry['id']} confidence high but only {len(authoritative)} authoritative references"
            )
    score = entry.get("severity_score")
    if score is None or not isinstance(score, (int, float)):
        error(f"{entry['id']} needs numeric severity_score")


def main():
    data = json.loads(DATA_PATH.read_text())
    entries = data.get("harmful_additives", [])
    seen_cuis = {}
    for entry in entries:
        validate_entry(entry, seen_cuis)
    print(f"[validate_harmful_additives] {len(entries)} entries validated successfully.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        error("harmful_additives.json not found")
