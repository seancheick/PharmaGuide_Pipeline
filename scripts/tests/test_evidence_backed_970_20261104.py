"""970-label Evidence review: true rejections earn nothing and packet drafts stay unsigned."""
import importlib.util
import json
from pathlib import Path

import pytest

from clinical_applicability import assess_clinical_applicability, reviewed_entries

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audits" / "evidence_backed_970_20261104"
NAT = "INGR_N_ACETYL_L_TYROSINE"


def _nat_row(name, form=None):
    row = {"name": name, "canonical_id": "l_tyrosine", "quantity": 350, "unit": "mg",
           "raw_source_path": "ingredientRows[0]"}
    if form:
        row["forms"] = [{"name": form}]
    return row


@pytest.mark.parametrize("name,form", [
    ("N-Acetyl L-Tyrosine", None),
    ("N-Acetyl-L-Tyrosine", None),
    ("N-Acetyl Tyrosine", None),
    ("NALT", None),
    ("L-Tyrosine", "N-Acetyl-L-Tyrosine"),
    ("Tyrosine", "Acetyl-L-Tyrosine"),
])
def test_n_acetyl_tyrosine_is_rejected_on_every_spelling(name, form):
    row = _nat_row(name, form)
    entry = {**reviewed_entries()[NAT], "ingredient": name, "matched_source_row_refs": ["ingredientRows[0]"]}
    result = assess_clinical_applicability({"activeIngredients": [row]}, entry, assess_amount=False)
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "clinical_form_excluded"


def test_rejection_record_cannot_reach_or_credit_free_tyrosine():
    record = reviewed_entries()[NAT]
    names = {record["standard_name"].lower(), *(alias.lower() for alias in record["aliases"])}
    assert not names & {"tyrosine", "l-tyrosine", "l tyrosine"}
    assert record["effect_direction"] == "null"
    assert not record.get("study_contexts")


def test_rejection_record_says_who_reviewed_it_and_cites_only_what_was_read():
    record = reviewed_entries()[NAT]
    text = json.dumps(record)
    assert "Agent review (Claude)" in record["applicability"]["reason"]
    assert "clinician_approved" not in text and "Dr. Pham" not in text
    cited = {ref["pmid"] for ref in record["references_structured"]}
    assert cited == set(record["published_studies"])
    assert set(record["applicability"]["source_pmids"]) <= cited


def test_packet_drafts_pass_the_authoring_rules_and_carry_no_approval():
    spec = importlib.util.spec_from_file_location("check_packet", AUDIT / "check_packet.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    packets = sorted((AUDIT / "packet").glob("*.json"))
    assert packets
    for path in packets:
        assert check.packet_problems(json.loads(path.read_text(encoding="utf-8"))) == []
        assert "clinician_approved" not in path.read_text(encoding="utf-8")


def test_packet_drafts_stay_outside_the_data_file():
    packeted = {path.stem for path in (AUDIT / "packet").glob("*.json")}
    assert not packeted & set(reviewed_entries())
