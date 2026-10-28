"""Production clinical data holds only finished study contexts.

A context left at ``source_verified_pending_clinical_review`` is a draft: it can
be mistaken for a reviewed source or promoted by accident. Drafts live in audit
receipts until they are approved or rejected (Sean, 2026-10-28). The status
stays legal for authoring (``validate_ingredient_context(authoring=True)``).
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
    found = [hit for file in sorted(DATA.glob("*.json"))
             for hit in _pending(json.loads(file.read_text()), file.name)]
    assert found == []
