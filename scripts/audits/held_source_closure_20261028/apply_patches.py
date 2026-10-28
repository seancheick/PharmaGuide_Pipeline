"""Apply the held-source closure patches to backed_clinical_studies.json.

Start from main's data, not this branch's committed copy, or a key a patch no
longer sets survives from the earlier application:
  git show origin/main:scripts/data/backed_clinical_studies.json > scripts/data/backed_clinical_studies.json

Complete patches (check_patch "complete") are applied whole. A held patch
contributes only its verified study contexts, never its record_updates, and
its hold is kept honest:
  * a context still pending clinical review is left out of production data (it
    stays in the patch as the receipt); nothing here approves a draft;
  * a newly approved context is kept only when it carries the agent-authorship
    limitation of the 2026-10-28 attestation; earlier signatures stay as they are;
  * a context citing a PMID absent from the record's references is left out;
  * no held context may carry credit (scoring_eligible is set false and the
    hold is named in its limitations).
A record_updates value of null removes that key (a patch cannot delete),
except a record-level scoring_eligible lifted by a ruling, which becomes true.
Prints "<record_id>\t<complete|held>" for every record touched.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch  # noqa: E402

PENDING = "source_verified_pending_clinical_review"
DATA = ROOT / "scripts/data/backed_clinical_studies.json"
blob = data_batch.load(DATA)
by_id = {r["id"]: r for r in blob["backed_clinical_studies"]}
reports = {}
for path in sorted((HERE / "patches").glob("*.json")):
    reports[path] = json.loads(subprocess.run(
        [sys.executable, str(HERE / "check_patch.py"), str(path)],
        capture_output=True, text=True, check=True).stdout)
touched = []
for path, report in reports.items():
    patch = json.loads(path.read_text())
    record = by_id[patch["record_id"]]
    if report["complete"]:
        for key, value in (patch.get("record_updates") or {}).items():
            if key == "scoring_eligible" and value in (None, True):
                # A ruling that lifts a record-level hold keeps an explicit
                # boolean: clinical_applicability refuses the unscoped
                # fallback for a record whose contexts are later lost.
                record[key] = True
            elif value is None:
                record.pop(key, None)
            else:
                record[key] = value
        record["study_contexts"] = patch["study_contexts"]
        state = "complete"
    else:
        declared = {str(ref.get("pmid")) for ref in record.get("references_structured") or []}
        declared |= {str(p) for p in record.get("published_studies") or []}
        signed = {c.get("context_id") for c in record.get("study_contexts") or []
                  if c.get("review_status") == "clinician_approved"}
        hold = patch["decision"].split(":", 1)[-1].strip()
        contexts = []
        for context in patch["study_contexts"]:
            sources = {str(p) for p in context.get("source_pmids") or []}
            if sources - declared:
                continue
            if context.get("review_status") == PENDING:
                continue
            if (context.get("review_status") == "clinician_approved"
                    and context.get("context_id") not in signed
                    and not any("agent review" in str(text) for text in context.get("limitations") or [])):
                continue
            if context.get("scoring_eligible") is not False and context.get("review_status") != "rejected_source":
                context = {**context, "scoring_eligible": False,
                           "limitations": [*(context.get("limitations") or []),
                                           "Record held, so this context carries no credit: " + hold]}
            contexts.append(context)
        record["study_contexts"] = contexts
        state = "held"
    record["last_updated"] = "2026-10-28"
    touched.append(f"{patch['record_id']}\t{state}")
data_batch.save(DATA, blob)
print("\n".join(touched))
