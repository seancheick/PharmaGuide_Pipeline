"""Unqualified clinical drafts stay outside production decisions.

The November6 glutamine source inventory is deliberately narrower: known,
content-identified papers retain source-only, non-scoring pending stubs beside
one qualified trial. Sean explicitly requires unread studies to remain open.
These stubs assert no regimen/population/outcome and must keep review incomplete.
All other pending drafts retain the original exclusion guard.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
PENDING = "source_verified_pending_clinical_review"


def _pending(node, path):
    if isinstance(node, dict):
        if node.get("review_status") == PENDING:
            yield path + "/" + str(node.get("context_id") or "")
        for key, value in node.items():
            yield from _pending(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _pending(value, f"{path}[{index}]")


def test_no_data_file_holds_a_pending_review_context():
    from clinical_applicability import assess_clinical_source_review
    from clinical_evidence_schema import validate_ingredient_context
    from probiotic_measurements import context_review_finished
    known_unfinished_sources = {
        "38193521", "35106632", "39397201", "34844156",
        "42366260", "41053591", "38243579", "40748005",
    }
    found = []
    allowed = []
    for file in sorted(DATA.glob("*.json")):
        data = json.loads(file.read_text())
        found.extend(_pending(data, file.name))
        if file.name != "backed_clinical_studies.json":
            continue
        for index, record in enumerate(data["backed_clinical_studies"]):
            if record["id"] != "INGR_L_GLUTAMINE":
                continue
            for offset, context in enumerate(record["study_contexts"]):
                if context.get("review_status") != PENDING:
                    continue
                assert len(context["source_pmids"]) == 1
                assert set(context["source_pmids"]) <= known_unfinished_sources
                assert context["components"] == ["INGR_L_GLUTAMINE"]
                assert context["scoring_eligible"] is False
                assert "identity_scope" not in context
                assert not context_review_finished(context)
                assert validate_ingredient_context(context) == []
                assert "review.approval_required" in validate_ingredient_context(
                    context, require_complete_review=True)
                assert not assess_clinical_source_review(record)["is_complete"]
                allowed.append(
                    f"{file.name}/backed_clinical_studies[{index}]/study_contexts[{offset}]/"
                    + context["context_id"])
    assert found == allowed
