"""Real Supp.ai lookup keys must never become public PubMed identifiers."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest_suppai as ing


def _row(metadata, sentences=None):
    return ing.build_research_pair_row(
        "C0000378-C0000578",
        sentences or [{"paper_id": "25006211", "sentence": "Rat ovarian steroid experiment.", "uid": 1}],
        metadata, {}, {},
    )


@pytest.mark.parametrize("pmid", [1809554, "1809554"])
def test_actual_metadata_pmid_owns_all_public_links(pmid):
    row = _row({"25006211": {"pmid": pmid, "year": 1991}})
    assert row["top_pmids"] == ["1809554"]
    assert row["top_sentences"][0]["pmid"] == "1809554"
    assert row["top_papers"][0]["pmid"] == 1809554
    assert row["paper_count"] == 1


@pytest.mark.parametrize("pmid", [None, "", "not-a-pmid", 0, -1, True])
def test_missing_or_invalid_actual_pmid_never_falls_back_to_internal_key(pmid):
    assert ing.compress_paper_meta("25006211", {"25006211": {"pmid": pmid}}) is None
    assert _row({"25006211": {"pmid": pmid}}) is None


def test_distinct_internal_keys_for_same_public_paper_count_once():
    meta = {k: {"pmid": 1809554, "year": 1991} for k in ["25006211", "999"]}
    row = _row(meta, [
        {"paper_id": "25006211", "sentence": "First sentence.", "uid": 1},
        {"paper_id": "999", "sentence": "Second sentence.", "uid": 2},
    ])
    assert row["paper_count"] == 1
    assert row["top_pmids"] == ["1809554"]
    assert len(row["top_papers"]) == 1
    assert all(s["pmid"] == "1809554" for s in row["top_sentences"])


def test_retraction_filter_still_uses_internal_metadata_key():
    assert _row({"25006211": {"pmid": 1809554, "retraction": True}}) is None
