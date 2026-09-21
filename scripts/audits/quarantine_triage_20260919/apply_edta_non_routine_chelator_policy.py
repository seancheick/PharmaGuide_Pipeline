#!/usr/bin/env python3
"""Apply the approved standalone-oral-EDTA safety policy (2026-09-21).

Clinical decision (Dr. Pham / PharmaGuide Clinical Team, Phase 3): the 16
standalone, deliberately orally marketed EDTA products are
``BLOCKED + visible Safety card + no quality score``, with reason semantics
``NON_ROUTINE_CHELATOR`` / ``CLINICIAN_REVIEW_REQUIRED``. The disposition
records that standalone oral chelation is non-routine and requires clinical
review; it is NOT a claim that the labelled oral dose is proven acutely toxic.

What this script authors
------------------------
Two entries in ``scripts/data/banned_recalled_ingredients.json`` -- one per
DISTINCT chemical identity. Disodium edetate and calcium disodium edetate are
not clinically interchangeable and must never collapse into a generic "EDTA"
safety identity, so each carries its own id, aliases and copy.

Both entries are scoped to the DECLARED-ACTIVE label role:

* ``match_mode: "active"`` -- the enricher's own role gate, so the substance
  declared as an inactive excipient (a preservative in a multivitamin) never
  produces a banned hit at all.
* ``hard_verdict_roles: ["active"]`` + ``role_scope_out_of_scope:
  "not_applicable"`` -- the v4 safety gate treats an out-of-scope role as not
  applicable rather than as an unresolved policy question, so an excipient
  occurrence cannot quarantine a product this rule was never written to cover.

``verdict_reason_code: "NON_ROUTINE_CHELATOR"`` makes the exported
``blocking_reason`` state the policy instead of the registry tier.

Consumer copy is authored in the registry's own sanctioned Safety-card fields
(``safety_warning_one_liner`` <= 80 chars, ``safety_warning`` <= 200 chars)
rather than hard-coded in the client.

Idempotent: re-running verifies the authored values instead of rewriting them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY = REPO_ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"

REVIEWER = "PharmaGuide Clinical Team - Dr. Pham"
REVIEW_DATE = "2026-09-21"

_FDA_CHELATION_QA = (
    "https://www.fda.gov/drugs/medication-health-fraud/"
    "questions-and-answers-unapproved-chelation-products"
)
_FDA_CHELATION_WARNING = (
    "https://www.fda.gov/drugs/drug-safety-and-availability/"
    "fda-warns-consumers-about-potential-health-risks-using-thorne-"
    "researchs-captomer-products"
)

_ONE_LINER = "Chelating agent - not scored as a routine supplement."
_WARNING = (
    "Chelating agent (EDTA). FDA has not approved any over-the-counter "
    "chelation treatment; medically used chelation agents require clinical "
    "supervision. EDTA forms differ in their risks."
)

_POLICY_REASON = (
    "Edetate {form} is a metal-chelating agent. FDA has never approved any "
    "chelation product for over-the-counter use for any health condition, and "
    "medically used chelation agents require prescription supervision. A "
    "standalone product sold to be swallowed as a chelator is therefore not "
    "an ordinary dietary supplement and receives no PharmaGuide quality "
    "score. This is a non-routine-use policy determination: it is not a "
    "finding that the labelled oral dose is proven acutely toxic, and the "
    "disodium and calcium disodium forms are distinct identities with "
    "different clinical uses."
)


def _entry(
    *,
    entry_id: str,
    standard_name: str,
    aliases: list[str],
    form_label: str,
    negative_terms: list[str],
) -> dict:
    return {
        "id": entry_id,
        "standard_name": standard_name,
        "aliases": aliases,
        "reason": _POLICY_REASON.format(form=form_label),
        "status": "banned",
        "class_tags": [
            "non_routine_use_policy",
            "metal_chelator",
            "clinician_review_required",
        ],
        "match_rules": {
            "exclusions": [],
            "case_sensitive": False,
            "priority": 1,
            "match_type": "normalized",
            "confidence": "high",
            "negative_match_terms": negative_terms,
        },
        "legal_status_enum": "not_lawful_as_supplement",
        "clinical_risk_enum": "high",
        "policy_verification_status": "verified",
        "policy_verified_at": REVIEW_DATE,
        "hard_verdict_roles": ["active"],
        "role_scope_out_of_scope": "not_applicable",
        "verdict_reason_code": "NON_ROUTINE_CHELATOR",
        "jurisdictions": [
            {
                "region": "US",
                "level": "federal",
                "status": "not_lawful",
                "effective_date": "2016-02-02",
                "source": {
                    "type": "fda_advisory",
                    "citation": (
                        "FDA: no chelation product has ever been approved for "
                        "over-the-counter use; FDA-approved chelation products "
                        "require a prescription and clinical supervision."
                    ),
                    "url": _FDA_CHELATION_QA,
                    "accessed_date": REVIEW_DATE,
                },
                "jurisdiction_type": "country",
                "jurisdiction_code": "US",
                "last_verified_date": REVIEW_DATE,
            }
        ],
        "references_structured": [
            {
                "type": "fda_advisory",
                "title": "Questions and Answers on Unapproved Chelation Products",
                "evidence_grade": "R",
                "date": "2016-02-02",
                "url": _FDA_CHELATION_QA,
                "supports_claims": ["regulatory_status", "policy_basis"],
                "evidence_summary": (
                    "FDA has never approved any chelation product for "
                    "over-the-counter use for any health condition; all "
                    "FDA-approved chelation products require a prescription."
                ),
            },
            {
                "type": "fda_advisory",
                "title": (
                    "FDA warns consumers about potential health risks from "
                    "using Thorne Research's Captomer products"
                ),
                "evidence_grade": "R",
                "date": "2015-11-30",
                "url": _FDA_CHELATION_WARNING,
                "supports_claims": ["regulatory_action"],
                "evidence_summary": (
                    "FDA advises consumers to avoid all products offered "
                    "over the counter for chelation and states there are no "
                    "FDA-approved OTC chelation products."
                ),
            },
        ],
        "source_category": "non_routine_use_policy",
        "entity_type": "ingredient",
        "review": {
            "status": "validated",
            "last_reviewed_at": REVIEW_DATE,
            "next_review_due": "2027-03-21",
            "reviewed_by": REVIEWER,
            "change_log": [
                {
                    "date": REVIEW_DATE,
                    "change": (
                        "Authored for the Phase-3 clinical decision: "
                        "standalone oral EDTA is BLOCKED with a visible Safety "
                        "card and no quality score (NON_ROUTINE_CHELATOR); "
                        "declared-active role only, so excipient occurrences "
                        "are unaffected."
                    ),
                    "by": REVIEWER,
                }
            ],
        },
        "regulatory_date": "2016-02-02",
        "regulatory_date_label": "FDA chelation-products advisory",
        "match_mode": "active",
        "cui": None,
        # Honest null: the registry's own CUI verifier
        # (scripts/api_audit/verify_cui.py --search) returns no concept for
        # either form name. The identity is established from the DSLD ingredient
        # name and the distinct salt chemistry, not from a UMLS concept -- so no
        # identifier is invented here.
        "cui_status": "no_confirmed_umls_match",
        "cui_note": (
            "No UMLS concept resolved for this chelating-salt name via the "
            "registry's own verifier. Identity is authored from the DSLD "
            "ingredient name; no identifier is invented."
        ),
        "external_ids": {},
        "ban_context": "substance",
        "safety_warning": _WARNING,
        "safety_warning_one_liner": _ONE_LINER,
    }


ENTRIES: list[dict] = [
    _entry(
        entry_id="BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM",
        standard_name="Edetate Disodium",
        aliases=[
            "EDTA Disodium",
            "Disodium EDTA",
            "Disodium Edetate",
            "Edetate Disodium Anhydrous",
            "Edetate Sodium",
            "Sodium Edetate",
        ],
        form_label="disodium",
        # "Edetate calcium disodium" and "calcium disodium EDTA" are the OTHER
        # identity. Excluding them keeps the two never collapsed.
        negative_terms=["calcium disodium"],
    ),
    _entry(
        entry_id="BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE",
        standard_name="Edetate Calcium Disodium",
        aliases=[
            "Calcium Disodium EDTA",
            "Calcium Disodium Edetate",
            "Edetate Calcium Disodium Anhydrous",
            "Calcium EDTA",
        ],
        form_label="calcium disodium",
        # No veto needed: every alias above already names the calcium form, so
        # the disodium identity cannot be shadowed by this entry.
        negative_terms=[],
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify only")
    args = parser.parse_args()

    assert len(_ONE_LINER) <= 80, len(_ONE_LINER)
    assert len(_WARNING) <= 200, len(_WARNING)

    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = payload["ingredients"]
    by_id = {str(e.get("id")): e for e in entries}

    changed: list[str] = []
    for entry in ENTRIES:
        entry_id = entry["id"]
        existing = by_id.get(entry_id)
        if existing is None:
            if args.check:
                print(f"MISSING: {entry_id}")
                return 1
            entries.append(entry)
            changed.append(f"added {entry_id}")
            continue
        for key, value in entry.items():
            if existing.get(key) != value:
                if args.check:
                    print(f"DRIFT: {entry_id}.{key}")
                    return 1
                existing[key] = value
                changed.append(f"{entry_id}.{key}")
        print(f"  ok (already present): {entry_id}")

    if changed and not args.check:
        payload["_metadata"]["total_entries"] = len(entries)
        payload["_metadata"]["last_updated"] = REVIEW_DATE
        REGISTRY.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("changed:", changed)

    # Verify each identity is reachable through the resolver's own index and
    # that the two alias sets do NOT collide.
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from inactive_ingredient_resolver import (  # noqa: E402
        InactiveIngredientResolver,
        SOURCE_BANNED_RECALLED,
    )

    resolver = InactiveIngredientResolver()
    probes = {
        "Edetate Disodium": "BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM",
        "EDTA Disodium": "BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM",
        "Calcium Disodium EDTA": (
            "BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE"
        ),
    }
    for term, expected in probes.items():
        hit = resolver.resolve(raw_name=term)
        assert hit.matched_source == SOURCE_BANNED_RECALLED, (term, hit)
        assert hit.matched_rule_id == expected, (term, hit.matched_rule_id)
        print(f"  resolves: {term} -> {hit.matched_rule_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
