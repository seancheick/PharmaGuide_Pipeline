"""Offline tests for the depletion/timing PMID verifier's fail-closed semantics.

Locks the 2026-07-24 hardening (Codex audit): the verifier must (a) extract
PubMed URLs regardless of the `source_type` label, (b) distinguish a transient
failure from a genuine ghost, and (c) exit NONZERO whenever it cannot declare
clean. No network — `_fetch_esummary` is monkeypatched.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api_audit"))

import verify_depletion_timing_pmids as vd  # noqa: E402


def _docsum(pmid: str, title: str = "T") -> str:
    return f'<DocSum><Id>{pmid}</Id><Item Name="Title" Type="String">{title}</Item></DocSum>'


def test_extract_is_label_agnostic_and_flags_malformed():
    data = {
        "depletions": [
            {
                "id": "E1",
                "sources": [
                    # PubMed URL hidden under a non-pubmed label — MUST be caught.
                    {"source_type": "reference", "url": "https://pubmed.ncbi.nlm.nih.gov/22762246", "label": "ref"},
                    # Labelled pubmed but no PMID in URL — MUST be flagged malformed.
                    {"source_type": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/", "label": "bad"},
                    # Genuine non-pubmed source — MUST be ignored.
                    {"source_type": "efsa", "url": "https://efsa.europa.eu/opinion", "label": "efsa"},
                ],
            }
        ]
    }
    recs = vd._extract_from_data(data, "depletions", "medication_depletions.json")
    pmids = [r["pmid"] for r in recs]
    assert "22762246" in pmids, "reference-labelled PubMed URL must be extracted"
    assert None in pmids, "pubmed-labelled URL with no PMID must be flagged (None)"
    assert len(recs) == 2, "the non-pubmed efsa source must be ignored"


def test_transient_failure_is_unresolved_not_invalid(monkeypatch):
    def boom(ids_str, api_key, attempts=4):
        raise vd.TransientVerifyError("HTTP 429")

    monkeypatch.setattr(vd, "_fetch_esummary", boom)
    recs = [{"pmid": "12345678", "entry_id": "E", "file": "f"}]
    out = vd.verify_pmids_live(recs)
    assert out[0]["status"] == "unresolved"
    assert out[0]["verified"] is False  # unresolved is not a pass...
    # ...but it must NOT be reported as a genuine ghost.
    assert out[0]["status"] != "invalid"


def test_valid_and_ghost_classification(monkeypatch):
    def fake_fetch(ids_str, api_key, attempts=4):
        # PubMed answers, but only returns a record for the real id.
        return f"<eSummaryResult>{_docsum('11111111')}</eSummaryResult>"

    monkeypatch.setattr(vd, "_fetch_esummary", fake_fetch)
    recs = [
        {"pmid": "11111111", "entry_id": "real", "file": "f"},
        {"pmid": "99999999", "entry_id": "ghost", "file": "f"},
    ]
    out = {r["entry_id"]: r for r in vd.verify_pmids_live(recs)}
    assert out["real"]["status"] == "valid" and out["real"]["verified"] is True
    assert out["ghost"]["status"] == "invalid" and out["ghost"]["verified"] is False


@pytest.mark.parametrize(
    "invalid,unresolved,malformed,expected",
    [
        (0, 0, 0, 0),   # all clean
        (1, 0, 0, 1),   # ghost → data defect
        (0, 0, 1, 1),   # malformed pubmed source → data defect
        (0, 1, 0, 2),   # transient only → fail-closed
        (1, 1, 0, 1),   # a real defect outranks transient
    ],
)
def test_decide_exit(invalid, unresolved, malformed, expected):
    assert vd._decide_exit(invalid, unresolved, malformed) == expected


def test_live_gate_fails_closed_on_all_transient(monkeypatch):
    """End-to-end: a fully rate-limited run must exit 2, never 0."""
    monkeypatch.setattr(
        vd, "_fetch_esummary",
        lambda ids_str, api_key, attempts=4: (_ for _ in ()).throw(vd.TransientVerifyError("429")),
    )
    assert vd.run(["--live"]) == 2
