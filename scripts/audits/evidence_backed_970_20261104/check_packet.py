"""Check every packet draft against the production owners, in memory only.

Usage: check_packet.py
Packets stay outside the data file. A draft must pass the authoring rules, so it can't
carry an approval, and must keep a receipt for each study it read. Packets use the patch
shape of held_source_closure_20261028 (decision, summary, record_updates, study_contexts,
source_receipts). These ingredients have no backed record yet, so record_updates carries
the whole record body, and applying one starts from {"id": record_id}.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import clinical_applicability as ca  # noqa: E402
from clinical_evidence_schema import validate_ingredient_context  # noqa: E402


def packet_problems(packet):
    problems = []
    receipts = {str(row.get("pmid")) for row in packet.get("source_receipts") or []}
    for key in ("record_id", "decision", "summary", "reviewed_by", "record_updates"):
        if not packet.get(key):
            problems.append(f"packet.{key}_missing")
    for context in packet.get("study_contexts") or []:
        cid = context.get("context_id")
        problems += [f"{cid}:{code}" for code in validate_ingredient_context(context, authoring=True)]
        if context.get("clinical_review"):
            problems.append(f"{cid}:carries_clinical_review")
        if context.get("scoring_eligible") is True:
            problems.append(f"{cid}:scoring_eligible_before_clinical_review")
        for pmid in context.get("source_pmids") or []:
            if str(pmid) not in receipts:
                problems.append(f"{cid}:source_{pmid}_not_in_receipts")
    for pmid in packet.get("read_not_used") or {}:
        if str(pmid) not in receipts:
            problems.append(f"read_not_used_{pmid}_not_in_receipts")
    decision = str(packet.get("decision") or "")
    if decision != "closed_no_credit" and not decision.startswith("held: "):
        problems.append("packet.decision_not_a_no_credit_or_held_decision")
    declared = set((packet.get("record_updates") or {}).get("published_studies") or [])
    cited = {str(ref.get("pmid")) for ref in (packet.get("record_updates") or {}).get("references_structured") or []}
    for context in packet.get("study_contexts") or []:
        if set(context.get("source_pmids") or []) - declared - cited:
            problems.append(f"{context.get('context_id')}:source_not_declared_by_record")
    return problems


def source_review_errors(packet):
    """What the source review owner says of the record once applied, drafts still unsigned."""
    entries = copy.deepcopy(ca.reviewed_entries())
    entries[packet["record_id"]] = {**packet["record_updates"], "study_contexts": packet["study_contexts"]}
    original = ca.reviewed_entries
    ca.reviewed_entries = lambda: entries
    try:
        return ca.assess_clinical_source_review({"id": packet["record_id"]})["errors"]
    finally:
        ca.reviewed_entries = original


def main():
    failed = False
    for path in sorted((HERE / "packet").glob("*.json")):
        packet = json.loads(path.read_text())
        problems = packet_problems(packet)
        failed = failed or bool(problems)
        print(path.stem, "ok" if not problems else problems, "| source review:", source_review_errors(packet))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
