#!/usr/bin/env python3
"""
Notes alignment auditor for PharmaGuide data files.

What this script does:
  1. Reads a data file (backed_clinical_studies, harmful_additives, or banned_recalled).
  2. Cross-references prose fields (notes, mechanism_of_harm, notable_studies, reason)
     against the entry's own structured fields and known external data.
  3. Flags five categories of misalignment:
       - CONTRADICTION: prose contradicts a structured field value
       - OVERSTATEMENT: prose uses stronger language than evidence supports
       - STALE_CLAIM: prose references outdated data (retracted, superseded, or stale)
       - NUMERIC_MISMATCH: prose cites a different number than a structured field
       - UNSUPPORTED_CLAIM: prose makes a specific factual claim with no PMID/DOI backing

  This is a deterministic pattern-matching auditor, not an AI prose reviewer.
  It catches the most dangerous misalignments without requiring an LLM.

Operator runbook:
  1. Audit backed_clinical_studies.json:
       python3 scripts/api_audit/audit_notes_alignment.py --file scripts/data/backed_clinical_studies.json --db clinical
  2. Audit harmful_additives.json:
       python3 scripts/api_audit/audit_notes_alignment.py --file scripts/data/harmful_additives.json --db additives
  3. Audit banned_recalled_ingredients.json:
       python3 scripts/api_audit/audit_notes_alignment.py --file scripts/data/banned_recalled_ingredients.json --db banned
  4. Audit all files:
       python3 scripts/api_audit/audit_notes_alignment.py --all
  5. Save report:
       python3 scripts/api_audit/audit_notes_alignment.py --all --output /tmp/notes_alignment_report.json
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

# ---------------------------------------------------------------------------
# Severity language patterns
# ---------------------------------------------------------------------------

# Words implying strong causal claims
CAUSAL_STRONG = re.compile(
    r"\b(causes?|proven to|definitively|conclusively|establishes?|confirms? that"
    r"|demonstrated? that|shows? that .+ causes?)\b", re.I
)

# Words appropriate for weaker/observational evidence
CAUSAL_HEDGED = re.compile(
    r"\b(may|might|suggests?|associated with|linked to|correlat|"
    r"preliminary|limited evidence|some studies|small studies?|pilot)\b", re.I
)

# Strong safety reassurance language
SAFETY_REASSURANCE = re.compile(
    r"\b(completely safe|no safety concern|no risk|harmless|"
    r"perfectly safe|zero risk|no adverse|no danger|no health risk)\b", re.I
)

# Severity escalation keywords in prose
SEVERITY_CRITICAL_KW = re.compile(
    r"\b(fatal|death|lethal|life[- ]threatening|organ failure|"
    r"liver failure|renal failure|cardiac arrest|seizure|anaphylaxis)\b", re.I
)
SEVERITY_HIGH_KW = re.compile(
    r"\b(carcinogenic|cancer|tumor|tumour|genotoxic|mutagenic|"
    r"hepatotoxic|nephrotoxic|neurotoxic|endocrine disruptor|"
    r"teratogenic|reproductive toxicity)\b", re.I
)

# ADI/dose number extraction from prose
ADI_IN_PROSE = re.compile(
    r"(?:ADI|TDI|TWI)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:mg|ug|mcg|g)/\s*kg", re.I
)

# Study type keywords in prose
RCT_PROSE_KW = re.compile(
    r"\b(randomized controlled|randomised controlled|placebo-controlled|"
    r"double-blind|double blind|triple-blind|parallel-arm RCT|"
    r"db-rct|rcts?|phase\s+[ivx]+)\b",
    re.I,
)
META_PROSE_KW = re.compile(
    r"\b(meta-analysis|meta analysis|systematic review|cochrane review)\b", re.I
)
OBSERVATIONAL_PROSE_KW = re.compile(
    r"\b(observational|cohort study|case-control|cross-sectional|"
    r"epidemiological|retrospective|prospective cohort)\b", re.I
)
ANIMAL_PROSE_KW = re.compile(
    r"\b(animal stud|mouse|mice|rat model|rodent|in vivo animal|"
    r"murine|preclinical animal)\b", re.I
)
INVITRO_PROSE_KW = re.compile(
    r"\b(in vitro|cell line|cell culture|test tube)\b", re.I
)

# PMID / DOI / NCT patterns for "has citation" checks
CITATION_RE = re.compile(
    r"(PMID\s*:?\s*\d{5,8}|10\.\d{4,9}/\S+|NCT\d{8}|"
    r"pubmed\.ncbi|doi\.org)", re.I
)


# ---------------------------------------------------------------------------
# Study type strength scale (matches scoring engine)
# ---------------------------------------------------------------------------

STUDY_STRENGTH = {
    "in_vitro": 1,
    "animal_study": 2,
    "observational": 3,
    "rct_single": 4,
    "clinical_strain": 4,
    "rct_multiple": 5,
    "meta_analysis": 6,
    "systematic_review": 6,
    "systematic_review_meta": 7,
}

SEVERITY_RANK = {
    "low": 1,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def _all_prose(entry: dict) -> str:
    """Concatenate all prose fields into one string for pattern matching."""
    parts = []
    for key in ("notes", "mechanism_of_harm", "notable_studies",
                "clinical_notes", "reason", "scientific_references"):
        val = entry.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val)
    return " ".join(parts)


def _references_structured(entry: dict) -> list[dict]:
    refs = entry.get("references_structured", [])
    if isinstance(refs, list):
        return [ref for ref in refs if isinstance(ref, dict)]
    return []


def _has_retracted_reference(entry: dict) -> bool:
    return any(bool(ref.get("retracted")) for ref in _references_structured(entry))


def _structured_ref_text(entry: dict) -> str:
    parts: list[str] = []
    for ref in _references_structured(entry):
        for key in ("title", "citation", "url", "notes", "doi", "pmid"):
            val = ref.get(key)
            if isinstance(val, str):
                parts.append(val)
    return " ".join(parts)


def check_study_type_contradiction(entry: dict) -> list[dict]:
    """Check if prose implies a different study type than the structured field."""
    issues = []
    study_type = entry.get("study_type", "")
    prose = _all_prose(entry)
    if not study_type or not prose:
        return issues

    claimed_strength = STUDY_STRENGTH.get(study_type, 0)

    # Prose says the entry itself is a meta-analysis/systematic review while
    # the structured study_type is weaker. Only inspect notes/clinical_notes,
    # not notable_studies, because entries can legitimately cite meta-analyses.
    if claimed_strength < STUDY_STRENGTH["systematic_review_meta"]:
        own_claim_text = " ".join(
            str(entry.get(field, "")) for field in ("notes", "clinical_notes")
        )
        own_claim_text = own_claim_text.lower()
        if META_PROSE_KW.search(own_claim_text):
            issues.append({
                "type": "CONTRADICTION",
                "subtype": "meta_claim_vs_study_type",
                "detail": (
                    f"study_type={study_type} but notes/clinical_notes describe "
                    "the entry as a meta-analysis or systematic review"
                ),
                "field": "study_type",
            })

    # Prose says "animal study" or "in vitro" but study_type claims human evidence
    if claimed_strength >= STUDY_STRENGTH["rct_single"]:
        animal_hits = ANIMAL_PROSE_KW.findall(prose)
        invitro_hits = INVITRO_PROSE_KW.findall(prose)
        # Only flag if prose ONLY mentions animal/in-vitro and no human keywords
        has_human_kw = RCT_PROSE_KW.search(prose) or bool(
            re.search(r"\b(human|clinical trial|volunteers|participants|subjects|patients)\b", prose, re.I)
        )
        if (animal_hits or invitro_hits) and not has_human_kw:
            issues.append({
                "type": "CONTRADICTION",
                "subtype": "study_type_vs_prose",
                "detail": (
                    f"study_type={study_type} (strength {claimed_strength}) "
                    f"but prose only mentions: {animal_hits + invitro_hits}"
                ),
                "field": "study_type",
            })

    # Prose says "no RCT" / "no controlled trial" but study_type is rct
    no_rct = re.search(
        r"\b(no\s+(?:dedicated\s+)?(?:randomized|placebo[- ]controlled|RCT|controlled trial))",
        prose, re.I,
    )
    if no_rct and study_type.startswith("rct"):
        issues.append({
            "type": "CONTRADICTION",
            "subtype": "no_rct_claim_vs_rct_type",
            "detail": f"study_type={study_type} but prose says: '{no_rct.group(0)}'",
            "field": "study_type",
        })

    return issues


def check_severity_alignment(entry: dict) -> list[dict]:
    """Check if severity language in prose matches structured severity."""
    issues = []
    severity = entry.get("severity_level") or entry.get("clinical_risk_enum", "")
    if not severity:
        return issues

    prose = _all_prose(entry)
    sev_rank = SEVERITY_RANK.get(severity.lower(), 0)

    # Low severity but prose mentions fatal/organ-failure language
    if sev_rank <= 1 and SEVERITY_CRITICAL_KW.search(prose):
        match = SEVERITY_CRITICAL_KW.search(prose)
        term = match.group(0).lower()
        if not (term == "anaphylaxis" and "rare" in prose.lower()):
            issues.append({
                "type": "CONTRADICTION",
                "subtype": "severity_understatement",
                "detail": (
                    f"severity_level={severity} but prose mentions "
                    f"'{match.group(0)}' — consider upgrading severity"
                ),
                "field": "severity_level",
            })

    # High/critical severity but prose says "no safety concern"
    if sev_rank >= 3 and SAFETY_REASSURANCE.search(prose):
        match = SAFETY_REASSURANCE.search(prose)
        issues.append({
            "type": "CONTRADICTION",
            "subtype": "severity_vs_reassurance",
            "detail": (
                f"severity_level={severity} but prose says "
                f"'{match.group(0)}'"
            ),
            "field": "notes",
        })

    # Low severity but prose mentions carcinogenic/genotoxic
    if sev_rank <= 2 and SEVERITY_HIGH_KW.search(prose):
        match = SEVERITY_HIGH_KW.search(prose)
        # Only flag if the entry doesn't provide regulatory context
        has_context = any(
            kw in prose.lower()
            for kw in ("iarc", "group 2", "group 1", "ntp", "prop 65",
                       "efsa", "delisted", "not classified", "not considered",
                       "historical", "formerly", "no longer")
        )
        if not has_context:
            issues.append({
                "type": "OVERSTATEMENT",
                "subtype": "severity_escalation_in_prose",
                "detail": (
                    f"severity_level={severity} but prose mentions "
                    f"'{match.group(0)}' without IARC/regulatory context"
                ),
                "field": "notes",
            })

    return issues


def check_adi_numeric_consistency(entry: dict) -> list[dict]:
    """Check if ADI numbers in prose match structured regulatory_status values."""
    issues = []
    reg = entry.get("regulatory_status", {})
    prose = _all_prose(entry)

    # Extract ADI from regulatory fields
    struct_adis = {}
    for region, text in reg.items():
        if not isinstance(text, str):
            continue
        match = ADI_IN_PROSE.search(text)
        if match:
            try:
                struct_adis[region] = float(match.group(1))
            except ValueError:
                pass

    # Extract ADI from prose (notes, mechanism_of_harm)
    for key in ("notes", "mechanism_of_harm"):
        text = entry.get(key, "")
        if not isinstance(text, str):
            continue
        for match in ADI_IN_PROSE.finditer(text):
            try:
                prose_adi = float(match.group(1))
            except ValueError:
                continue
            # Compare against structured values
            for region, struct_val in struct_adis.items():
                if abs(prose_adi - struct_val) > max(struct_val * 0.15, 0.01):
                    issues.append({
                        "type": "NUMERIC_MISMATCH",
                        "subtype": "adi_value_inconsistency",
                        "detail": (
                            f"{key} says ADI {prose_adi} but "
                            f"regulatory_status.{region} says {struct_val}"
                        ),
                        "field": key,
                    })

    return issues


def check_overstatement(entry: dict) -> list[dict]:
    """Check if prose uses causal language inappropriate for the evidence level."""
    issues = []
    study_type = entry.get("study_type", "")
    evidence_level = entry.get("evidence_level", "")
    prose = _all_prose(entry)

    strength = STUDY_STRENGTH.get(study_type, 0)

    # Strong causal language with weak evidence
    # Skip entries without study_type — these are safety/regulatory entries where
    # describing established toxicological mechanisms with direct language is appropriate
    # (e.g., "cadmium causes kidney damage" is established toxicology, not a clinical claim)
    if study_type and strength <= STUDY_STRENGTH.get("observational", 3):
        causal_hits = CAUSAL_STRONG.findall(prose)
        if causal_hits and not CAUSAL_HEDGED.search(prose):
            issues.append({
                "type": "OVERSTATEMENT",
                "subtype": "causal_language_weak_evidence",
                "detail": (
                    f"study_type={study_type} but prose uses strong language: "
                    f"{causal_hits[:3]}. Consider hedging with 'may', 'suggests', etc."
                ),
                "field": "notes",
            })

    # Preclinical evidence but prose implies human-level confidence
    if evidence_level == "preclinical":
        human_claim = re.search(
            r"\b(in humans|human studies show|clinical evidence demonstrates|"
            r"patients showed|volunteers experienced)\b",
            prose, re.I,
        )
        if human_claim:
            issues.append({
                "type": "OVERSTATEMENT",
                "subtype": "preclinical_with_human_claims",
                "detail": (
                    f"evidence_level=preclinical but prose says: "
                    f"'{human_claim.group(0)}'"
                ),
                "field": "notes",
            })

    return issues


def check_unsupported_claims(entry: dict) -> list[dict]:
    """Check if prose makes specific factual claims without citation backing."""
    issues = []
    primary_prose_fields = {
        key: entry.get(key, "")
        for key in ("notes", "clinical_notes")
        if isinstance(entry.get(key, ""), str)
    }
    combined_primary = " ".join(primary_prose_fields.values())
    if not combined_primary:
        return issues

    refs = _references_structured(entry)
    has_any_ref = bool(refs) or bool(CITATION_RE.search(_all_prose(entry)))

    # Specific percentage claims without any reference
    pct_claims = re.findall(
        r"\d+(?:\.\d+)?%\s+(?:reduction|increase|improvement|decrease)",
        combined_primary,
        re.I,
    )
    if pct_claims and not has_any_ref:
        issues.append({
            "type": "UNSUPPORTED_CLAIM",
            "subtype": "percentage_claim_no_citation",
            "detail": (
                f"Primary prose claims specific outcomes ({pct_claims[:2]}) "
                "but entry has no references"
            ),
            "field": "notes",
        })

    # "Study X found Y" pattern without PMID
    study_claim = re.search(
        r"(?:study|trial|research)\s+(?:found|showed|demonstrated|reported)",
        combined_primary,
        re.I,
    )
    if study_claim and not CITATION_RE.search(combined_primary):
        # Check if notable_studies or scientific_references has the citation
        notable = entry.get("notable_studies", "")
        sci_refs = " ".join(str(r) for r in entry.get("scientific_references", []))
        all_ref_text = (notable or "") + " " + sci_refs + " " + _structured_ref_text(entry)
        if not CITATION_RE.search(all_ref_text):
            issues.append({
                "type": "UNSUPPORTED_CLAIM",
                "subtype": "study_claim_no_pmid",
                "detail": (
                    "Primary prose references a study finding but no PMID/DOI "
                    "appears in notes, clinical_notes, notable_studies, "
                    "references_structured, or scientific_references"
                ),
                "field": "notes",
            })

    return issues


def check_stale_claims(entry: dict) -> list[dict]:
    """Check for potentially stale claims based on available signals."""
    issues = []
    prose = _all_prose(entry)
    if not prose:
        return issues

    if _has_retracted_reference(entry):
        study_or_efficacy_claim = re.search(
            r"\b(study|trial|research|improves?|reduces?|increases?|demonstrates?|shows?)\b",
            prose,
            re.I,
        )
        if study_or_efficacy_claim:
            issues.append({
                "type": "STALE_CLAIM",
                "subtype": "retracted_reference_present",
                "detail": (
                    "Entry still makes study/efficacy claims while at least one "
                    "structured reference is marked retracted"
                ),
                "field": "references_structured",
            })

    # "GRAS" claim but status is banned/recalled
    status = entry.get("status", "")
    if status in ("banned", "recalled"):
        if re.search(r"\bGRAS\b", prose):
            negated_gras = re.search(
                r"\b(not|no longer|not generally recognized as safe|isn't|is not)\b.{0,30}\bGRAS\b",
                prose,
                re.I,
            )
            if not negated_gras and not re.search(
                r"(former|previously|no longer|revoked|removed)\s+GRAS",
                prose,
                re.I,
            ):
                issues.append({
                    "type": "STALE_CLAIM",
                    "subtype": "gras_on_banned_entry",
                    "detail": "Notes mention GRAS but entry status is " + status,
                    "field": "notes",
                })

    # "FDA approved" on a banned entry
    if status == "banned" and re.search(r"FDA\s+approved", prose, re.I):
        if not re.search(r"(formerly|previously|was)\s+FDA\s+approved", prose, re.I):
            issues.append({
                "type": "STALE_CLAIM",
                "subtype": "fda_approved_on_banned",
                "detail": "Notes say 'FDA approved' but status is banned",
                "field": "notes",
            })

    return issues


def check_status_reason_alignment(entry: dict) -> list[dict]:
    """For banned/recalled: check if reason/notes align with status and risk."""
    issues = []
    status = entry.get("status", "")
    risk = entry.get("clinical_risk_enum", "")
    reason = entry.get("reason", "")
    if not status or not reason:
        return issues

    risk_rank = SEVERITY_RANK.get(risk, 0)

    # Critical risk but reason says "not inherently dangerous"
    if risk_rank >= 4 and re.search(r"not inherently dangerous|low risk|minimal concern", reason, re.I):
        issues.append({
            "type": "CONTRADICTION",
            "subtype": "risk_vs_reason_downplay",
            "detail": f"clinical_risk_enum={risk} but reason downplays risk",
            "field": "reason",
        })

    # Banned status but reason suggests it should be watchlist
    # Exclude medical-context "monitor" (e.g., "renal function monitoring", "dosing monitoring")
    # Exclude self-referential "this watchlist covers..."
    if status == "banned":
        watchlist_hit = re.search(
            r"\b(should be (?:on )?watchlist|move to watchlist|downgrade to watchlist"
            r"|review needed for status|status.*under review)\b",
            reason, re.I,
        )
        if watchlist_hit:
            issues.append({
                "type": "CONTRADICTION",
                "subtype": "banned_but_watchlist_language",
                "detail": f"status={status} but reason says: '{watchlist_hit.group(0)}'",
                "field": "reason",
            })

    return issues


# ---------------------------------------------------------------------------
# Check sets per DB type
# ---------------------------------------------------------------------------

ALL_CHECKS_CLINICAL = [
    check_study_type_contradiction,
    check_overstatement,
    check_unsupported_claims,
    check_stale_claims,
]

ALL_CHECKS_ADDITIVES = [
    check_severity_alignment,
    check_adi_numeric_consistency,
    check_overstatement,
    check_unsupported_claims,
    check_stale_claims,
]

ALL_CHECKS_BANNED = [
    check_severity_alignment,
    check_overstatement,
    check_unsupported_claims,
    check_stale_claims,
    check_status_reason_alignment,
]

# Universal checks that apply to any JSON file
ALL_CHECKS_GENERIC = [
    check_study_type_contradiction,
    check_severity_alignment,
    check_adi_numeric_consistency,
    check_overstatement,
    check_unsupported_claims,
    check_stale_claims,
    check_status_reason_alignment,
]


def _detect_db_type(data: dict) -> tuple[str, str, list]:
    """Auto-detect DB type from file structure and return (name, list_key, checks)."""
    if "backed_clinical_studies" in data:
        return "clinical", "backed_clinical_studies", ALL_CHECKS_CLINICAL
    if "harmful_additives" in data:
        return "additives", "harmful_additives", ALL_CHECKS_ADDITIVES
    if "ingredients" in data:
        # Check if it's banned_recalled by looking for status/legal_status_enum
        entries = data["ingredients"]
        if entries and isinstance(entries, list) and entries[0].get("status"):
            return "banned", "ingredients", ALL_CHECKS_BANNED

    # Generic: find the first top-level list key that isn't _metadata
    for key, val in data.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return key, key, ALL_CHECKS_GENERIC

    return "unknown", "", ALL_CHECKS_GENERIC


def audit_file(
    data: dict,
    list_key: str,
    checks: list,
) -> dict:
    """Run alignment checks on all entries in a data file."""
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "total_entries": len(entries),
        "entries_with_issues": 0,
        "total_issues": 0,
        "by_type": {},
        "issues": [],
    }

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")
        entry_issues = []

        for check_fn in checks:
            entry_issues.extend(check_fn(entry))

        if entry_issues:
            results["entries_with_issues"] += 1
            results["total_issues"] += len(entry_issues)
            for issue in entry_issues:
                issue["id"] = eid
                issue["name"] = name
                results["issues"].append(issue)
                itype = issue["type"]
                results["by_type"][itype] = results["by_type"].get(itype, 0) + 1

    return results


def _build_summary(all_results: dict[str, dict]) -> dict[str, Any]:
    total_entries = 0
    entries_with_issues = 0
    total_issues = 0
    by_type: dict[str, int] = {}
    for results in all_results.values():
        total_entries += results.get("total_entries", 0)
        entries_with_issues += results.get("entries_with_issues", 0)
        total_issues += results.get("total_issues", 0)
        for issue_type, count in results.get("by_type", {}).items():
            by_type[issue_type] = by_type.get(issue_type, 0) + count
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_entries": total_entries,
        "entries_with_issues": entries_with_issues,
        "total_issues": total_issues,
        "by_type": by_type,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DB_CONFIGS = {
    "clinical": {
        "path": DATA_DIR / "backed_clinical_studies.json",
        "list_key": "backed_clinical_studies",
        "checks": ALL_CHECKS_CLINICAL,
    },
    "additives": {
        "path": DATA_DIR / "harmful_additives.json",
        "list_key": "harmful_additives",
        "checks": ALL_CHECKS_ADDITIVES,
    },
    "banned": {
        "path": DATA_DIR / "banned_recalled_ingredients.json",
        "list_key": "ingredients",
        "checks": ALL_CHECKS_BANNED,
    },
}


def _print_results(db_name: str, results: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Notes Alignment Audit: {db_name}")
    print(f"{'=' * 60}")
    print(f"  Total entries:        {results['total_entries']}")
    print(f"  Entries with issues:  {results['entries_with_issues']}")
    print(f"  Total issues:         {results['total_issues']}")

    if results["by_type"]:
        print(f"\n  By type:")
        for itype, count in sorted(results["by_type"].items()):
            print(f"    {itype:25s}  {count}")

    if results["issues"]:
        # Group by type for display
        by_type: dict[str, list] = {}
        for issue in results["issues"]:
            by_type.setdefault(issue["type"], []).append(issue)

        for itype, issues in sorted(by_type.items()):
            print(f"\n  --- {itype} ({len(issues)}) ---")
            for issue in issues[:15]:
                print(f"    {issue['id']:40s}  [{issue['subtype']}]")
                detail = issue["detail"]
                # Wrap long detail lines
                if len(detail) > 90:
                    detail = detail[:87] + "..."
                print(f"      {detail}")
            if len(issues) > 15:
                print(f"    ... and {len(issues) - 15} more")

    print(f"{'=' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit prose notes alignment against structured fields"
    )
    parser.add_argument("--file", type=Path, help="Path to any JSON data file")
    parser.add_argument("--db", choices=["clinical", "additives", "banned"],
                        help="Database type (auto-detected if omitted)")
    parser.add_argument("--list-key", type=str,
                        help="Top-level list key (auto-detected if omitted)")
    parser.add_argument("--all", action="store_true",
                        help="Audit all three core data files")
    parser.add_argument("--output", type=Path, help="Save JSON report")
    args = parser.parse_args()

    if not args.all and not args.file:
        parser.error("Either --all or --file is required")

    all_results = {}

    if args.all:
        for db_name, cfg in DB_CONFIGS.items():
            if not cfg["path"].exists():
                print(f"  [SKIP] {cfg['path']} not found", file=sys.stderr)
                continue
            data = json.loads(cfg["path"].read_text())
            results = audit_file(data, cfg["list_key"], cfg["checks"])
            all_results[db_name] = results
            _print_results(db_name, results)
    else:
        data = json.loads(args.file.read_text())
        if args.db:
            cfg = DB_CONFIGS[args.db]
            db_name = args.db
            list_key = args.list_key or cfg["list_key"]
            checks = cfg["checks"]
        else:
            # Auto-detect from file structure
            db_name, list_key, checks = _detect_db_type(data)
            if args.list_key:
                list_key = args.list_key
            print(f"  Auto-detected: db={db_name}, list_key={list_key}", file=sys.stderr)
        results = audit_file(data, list_key, checks)
        all_results[db_name] = results
        _print_results(db_name, results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": _build_summary(all_results), "results": all_results}
        args.output.write_text(json.dumps(payload, indent=2))
        print(f"  Report saved to {args.output}")


if __name__ == "__main__":
    main()
