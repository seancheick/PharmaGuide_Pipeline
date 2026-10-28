"""Check one held-source closure patch against the production owners.

Usage: check_patch.py patches/<RECORD_ID>.json
A patch is {"record_id", "decision", "record_updates": {...},
"study_contexts": [...full replacement list...], "source_receipts": [...]}.
It is applied in memory only; the data file is not changed.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import clinical_applicability as ca  # noqa: E402
from clinical_evidence_schema import validate_ingredient_context  # noqa: E402

patch = json.loads(Path(sys.argv[1]).read_text())
entries = copy.deepcopy(ca.reviewed_entries())
rid = patch["record_id"]
record = entries[rid]
# An approval already recorded keeps its own signed date; it is never re-stamped.
signed = {c.get("context_id"): c.get("clinical_review") for c in record.get("study_contexts") or []
          if c.get("review_status") == "clinician_approved"}
record.update(patch.get("record_updates") or {})
record["study_contexts"] = patch["study_contexts"]
ca.reviewed_entries = lambda: entries

problems = []
for key in ("decision", "source_receipts"):
    if not patch.get(key):
        problems.append(f"patch.{key}_missing")
if str(patch.get("decision") or "").startswith("held"):
    problems.append("patch.decision_held")
declared = {str(r.get("pmid")) for r in record.get("references_structured") or [] if r.get("pmid")}
fetched = {str(r.get("pmid")) for r in patch.get("source_receipts") or []}
for c in record["study_contexts"]:
    for pmid in c.get("source_pmids") or []:
        if str(pmid) not in fetched:
            problems.append(f"{c.get('context_id')}:source_{pmid}_not_in_receipts")
    if c.get("review_status") == "clinician_approved":
        review = c.get("clinical_review") or {}
        if review.get("reviewer") != "Dr. Pham" or (
                review.get("reviewed_at") != "2026-10-28" and review != signed.get(c.get("context_id"))):
            problems.append(f"{c.get('context_id')}:approval_provenance_not_the_2026_10_28_attestation")
    if c.get("identity_scope") not in {"exact_strain", "species_general"} and c.get("review_status") != "rejected_source":
        problems += [f"{c.get('context_id')}:{e}" for e in validate_ingredient_context(c, require_complete_review=True)]
result = ca.assess_clinical_source_review({"id": rid})
eligible = [c["context_id"] for c in record["study_contexts"] if c.get("scoring_eligible") is True]
print(json.dumps({"record_id": rid, "complete": result["is_complete"] and not problems,
                  "source_review_errors": result["errors"], "patch_problems": sorted(set(problems)),
                  "eligible_contexts": eligible, "declared_pmids": sorted(declared),
                  "study_type": record.get("study_type"), "evidence_level": record.get("evidence_level")}, indent=1))
