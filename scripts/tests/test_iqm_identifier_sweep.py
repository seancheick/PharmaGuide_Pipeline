"""Hermetic tests for the IQM identifier sweep orchestrator.

These tests do NOT touch the network. All authority clients are stub objects
with deterministic in-memory state. Per the plan's safety contract:

  - The sweep is read-only. Argparse must reject --apply / --write / --apply-mismatches.
  - The 3 seed cases (coq10/disease, 5_htp/branded, phytoestrogens/class-broader)
    MUST fire the strict-mode guards. If any seed slips through as
    `verified_clean`, the live sweep is broken and not allowed to run.
  - Display-name reverse-check must accept legitimate UMLS preferred-name
    disagreements (ubidecarenone ↔ CoQ10) — false-positive rejection here
    would falsely flag every vitamin/cofactor with a different chemical name
    in UMLS.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from api_audit import iqm_identifier_sweep as sweep


# --------------------------------------------------------------------------- #
# Fake authority clients — hermetic, deterministic, no network
# --------------------------------------------------------------------------- #


class FakeUMLS:
    """Stubs UMLSClient.lookup_cui() and search_exact()."""

    def __init__(self, *, concepts=None, exact_index=None):
        self._concepts = concepts or {}
        self._exact_index = exact_index or {}
        self._req = 0

    def lookup_cui(self, cui):
        self._req += 1
        return self._concepts.get(cui)

    def search_exact(self, term):
        self._req += 1
        if term is None:
            return None
        return self._exact_index.get(term.strip().lower())

    def search(self, term, max_results=5):
        self._req += 1
        hit = self.search_exact(term)
        return [hit] if hit else []

    @property
    def request_count(self):
        return self._req


class FakePubChem:
    def __init__(self, *, cid_props=None, cid_synonyms=None, name_to_cid_map=None):
        self._props = cid_props or {}
        self._synonyms = cid_synonyms or {}
        self._n2c = {k.lower(): v for k, v in (name_to_cid_map or {}).items()}
        self._request_count = 0

    def cid_to_properties(self, cid):
        self._request_count += 1
        return self._props.get(int(cid))

    def cid_to_synonyms(self, cid):
        self._request_count += 1
        return list(self._synonyms.get(int(cid), []))

    def cas_to_cid(self, cas):
        self._request_count += 1
        return self._n2c.get(cas.lower())

    def name_to_cid(self, name):
        self._request_count += 1
        return self._n2c.get(name.lower())

    def save_cache(self):
        pass


class FakeGSRS:
    def __init__(self, *, unii_records=None):
        self._records = unii_records or {}
        self._req = 0

    def get_full_substance(self, unii):
        self._req += 1
        return self._records.get(unii)

    def save_cache(self):
        pass

    @property
    def request_count(self):
        return self._req


class FakeRxNorm:
    def __init__(self, *, props_by_rxcui=None):
        self._props = props_by_rxcui or {}
        self._cache: dict = {}

    def properties(self, rxcui):
        return self._props.get(str(rxcui))


# --------------------------------------------------------------------------- #
# Seed-case guard tests — these MUST fail-loud if the strict guards regress
# --------------------------------------------------------------------------- #


def test_seed_coq10_disease_cui_must_be_rejected():
    """C1843920 ('COENZYME Q10 DEFICIENCY', Disease or Syndrome) must be
    rejected when stored as the CUI for the coq10 substance entry."""
    v = sweep.verify_cui_field(
        stored_cui="C1843920",
        standard_name="Coenzyme Q10",
        aliases=["CoQ10", "Co-Enzyme Q10"],
        cui_note=None,
        cui_status=None,
        umls=FakeUMLS(concepts={
            "C1843920": {
                "cui": "C1843920",
                "name": "COENZYME Q10 DEFICIENCY",
                "semantic_types": ["Disease or Syndrome"],
            },
        }),
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity == "high"
    assert v.reason_code == "resolved_to_disease_or_syndrome"


def test_seed_5_htp_branded_cui_must_be_rejected():
    """C5815882 ('Natrol Melatonin + 5-HTP', Clinical Drug) must be
    rejected when stored as the CUI for the 5_htp substance entry."""
    v = sweep.verify_cui_field(
        stored_cui="C5815882",
        standard_name="5-HTP",
        aliases=[],
        cui_note=None,
        cui_status=None,
        umls=FakeUMLS(concepts={
            "C5815882": {
                "cui": "C5815882",
                "name": "Natrol Melatonin + 5-HTP",
                "semantic_types": ["Clinical Drug"],
            },
        }),
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity == "high"
    assert v.reason_code == "resolved_to_branded_or_clinical_drug"


def test_seed_5_htp_combo_product_mislabeled_substance_must_be_rejected():
    """REAL LIVE-API REGRESSION: UMLS C5815882 in production returns
    semantic_types=['Organic Chemical','Pharmacologic Substance'] for the
    combo product 'Natrol Melatonin + 5-HTP' — NOT 'Clinical Drug'. The
    combo-marker guard (Guard 2b) must catch this case via the ' + ' marker
    in the candidate name."""
    v = sweep.verify_cui_field(
        stored_cui="C5815882",
        standard_name="5-HTP",
        aliases=[],
        cui_note=None,
        cui_status=None,
        umls=FakeUMLS(concepts={
            "C5815882": {
                "cui": "C5815882",
                "name": "Natrol Melatonin + 5-HTP",
                "semantic_types": ["Organic Chemical", "Pharmacologic Substance"],
                "atom_count": 1,
                "status": "R",
            },
        }),
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity == "high"
    assert v.reason_code == "resolved_to_multi_compound_or_combo_product"


def test_phytoestrogens_class_broader_must_be_rejected_for_genistein():
    """A CUI resolving to 'Phytoestrogens' (class-level) must NOT be accepted
    for the genistein-the-single-compound entry. Even though the semantic
    types may be substance-like, the class-broader / no-overlap guard fires.
    """
    v = sweep.verify_cui_field(
        stored_cui="C0123456",
        standard_name="Genistein",
        aliases=["4',5,7-Trihydroxyisoflavone"],
        cui_note=None,
        cui_status=None,
        umls=FakeUMLS(concepts={
            "C0123456": {
                "cui": "C0123456",
                "name": "Phytoestrogens",
                "semantic_types": ["Pharmacologic Substance"],
            },
        }),
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity in ("high", "medium")
    # The token-overlap guard fires first (phytoestrogens has no tokens in
    # common with genistein / its single alias). Class-broader is a backup
    # for the case where the candidate DOES share tokens but is broader.
    assert v.reason_code in (
        "no_token_overlap_with_iqm_name",
        "resolved_to_class_broader_than_iqm",
    )


def test_class_broader_guard_fires_when_tokens_overlap():
    """Direct test of the class-broader guard: when candidate shares tokens
    with the IQM name but has a class-marker word, it must be rejected.
    Example: candidate 'Flavonoid compounds' for IQM 'Quercetin' alias 'Flavonoid'.
    """
    v = sweep.verify_cui_field(
        stored_cui="C0099999",
        standard_name="Quercetin",
        aliases=["Flavonoid"],
        cui_note=None,
        cui_status=None,
        umls=FakeUMLS(concepts={
            "C0099999": {
                "cui": "C0099999",
                "name": "Flavonoid compounds",
                "semantic_types": ["Pharmacologic Substance"],
            },
        }),
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.reason_code == "resolved_to_class_broader_than_iqm"


def test_display_name_disagreement_accepted_via_reverse_check():
    """The CRITICAL false-positive guard: UMLS preferred name 'ubidecarenone'
    disagrees with IQM 'Coenzyme Q10', but the CUI is canonical because
    UMLS exact-search for 'Coenzyme Q10' returns the same CUI. Must accept.
    """
    fake_umls = FakeUMLS(
        concepts={
            "C0041536": {
                "cui": "C0041536",
                "name": "ubidecarenone",
                "semantic_types": ["Organic Chemical", "Pharmacologic Substance"],
            },
        },
        exact_index={
            "coenzyme q10": {"cui": "C0041536", "name": "Ubidecarenone"},
        },
    )
    v = sweep.verify_cui_field(
        stored_cui="C0041536",
        standard_name="Coenzyme Q10",
        aliases=["CoQ10"],
        cui_note=None,
        cui_status=None,
        umls=fake_umls,
        iqm_is_class_level=False,
    )
    assert v.status == "verified_clean", f"got status={v.status} reason={v.reason_code}"
    assert v.notes is not None
    assert "canonical" in v.notes.lower()


def test_reverse_check_via_alias():
    """Reverse-check should also match if exact-search on an alias returns
    the stored CUI (e.g., vitamin B12 → cyanocobalamin)."""
    fake_umls = FakeUMLS(
        concepts={
            "C0010441": {
                "cui": "C0010441",
                "name": "Cyanocobalamin",
                "semantic_types": ["Vitamin", "Pharmacologic Substance"],
            },
        },
        exact_index={
            "cobalamin": {"cui": "C0010441", "name": "Cyanocobalamin"},
        },
    )
    v = sweep.verify_cui_field(
        stored_cui="C0010441",
        standard_name="Vitamin B12",
        aliases=["Cobalamin", "Methylcobalamin"],
        cui_note=None,
        cui_status=None,
        umls=fake_umls,
        iqm_is_class_level=False,
    )
    assert v.status == "verified_clean", f"got {v.status} {v.reason_code}"


def test_no_token_overlap_rejected_when_reverse_check_fails():
    """If UMLS preferred name disagrees AND exact-search yields no match,
    reject."""
    fake_umls = FakeUMLS(
        concepts={
            "C9999999": {
                "cui": "C9999999",
                "name": "Some Unrelated Compound",
                "semantic_types": ["Organic Chemical"],
            },
        },
        exact_index={},  # no exact match for the IQM name
    )
    v = sweep.verify_cui_field(
        stored_cui="C9999999",
        standard_name="Coenzyme Q10",
        aliases=["CoQ10"],
        cui_note=None,
        cui_status=None,
        umls=fake_umls,
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity == "high"
    assert v.reason_code == "no_token_overlap_with_iqm_name"


# --------------------------------------------------------------------------- #
# Missing-CUI resolution tests
# --------------------------------------------------------------------------- #


def test_missing_cui_with_approved_null_status_is_skipped():
    """Per the documented null-CUI policy in verify_cui.py — class entries
    and supplement-market shorthand with no UMLS concept are intentional
    nulls. They must NOT be flagged as mismatched."""
    v = sweep.verify_cui_field(
        stored_cui=None,
        standard_name="NAD+ Precursors",
        aliases=[],
        cui_note="Class entry spanning multiple NAD+ precursor compounds.",
        cui_status="no_single_umls_concept",
        umls=FakeUMLS(),
        iqm_is_class_level=True,
    )
    assert v.status == "skipped_intentional_null"


def test_missing_cui_with_clean_exact_match_proposes_it():
    """If standard_name has an unambiguous UMLS exact match passing all
    strict guards, surface it as a low-severity backfill candidate."""
    fake_umls = FakeUMLS(
        concepts={
            "C0123": {
                "cui": "C0123",
                "name": "Hypothetical Compound",
                "semantic_types": ["Organic Chemical"],
            },
        },
        exact_index={
            "hypothetical compound": {"cui": "C0123", "name": "Hypothetical Compound"},
        },
    )
    v = sweep.verify_cui_field(
        stored_cui=None,
        standard_name="Hypothetical Compound",
        aliases=[],
        cui_note=None,
        cui_status=None,
        umls=fake_umls,
        iqm_is_class_level=False,
    )
    assert v.status == "mismatched"
    assert v.severity == "low"
    assert v.reason_code == "missing_cui_has_clean_candidate"
    assert v.proposed_value == "C0123"


def test_missing_cui_with_multiple_clean_candidates_is_ambiguous():
    """If standard_name + each alias each return a different clean CUI,
    record as ambiguous_authority — never auto-pick."""
    fake_umls = FakeUMLS(
        concepts={
            "C0001": {
                "cui": "C0001",
                "name": "Free Base",
                "semantic_types": ["Organic Chemical"],
            },
            "C0002": {
                "cui": "C0002",
                "name": "Salt Form",
                "semantic_types": ["Organic Chemical"],
            },
        },
        exact_index={
            "free base": {"cui": "C0001", "name": "Free Base"},
            "salt form": {"cui": "C0002", "name": "Salt Form"},
        },
    )
    v = sweep.verify_cui_field(
        stored_cui=None,
        standard_name="Free Base",
        aliases=["Salt Form"],
        cui_note=None,
        cui_status=None,
        umls=fake_umls,
        iqm_is_class_level=False,
    )
    assert v.status == "ambiguous_authority"


# --------------------------------------------------------------------------- #
# Cross-source / CAS / CID / UNII / RxCUI tests
# --------------------------------------------------------------------------- #


def test_cas_cid_disagreement_flagged_as_mismatch():
    """Stored CAS conflicting with PubChem CID's synonyms is a real bug."""
    pc = FakePubChem(
        cid_props={123: {"IUPACName": "alpha-D-glucose", "InChIKey": "WQZGKKKJIJFFOK-GASJEMHNSA-N"}},
        cid_synonyms={123: ["alpha-D-glucose", "50-99-7"]},
    )
    v = sweep.verify_pubchem_cid_field(
        stored_cid=123,
        standard_name="Glucose",
        aliases=["D-Glucose"],
        cas_stored="999-99-9",  # IQM stores this, but PubChem synonyms have 50-99-7
        pubchem=pc,
    )
    assert v.status == "mismatched"
    assert v.reason_code == "cas_cid_disagreement"


def test_pubchem_cid_with_aligned_synonyms_is_clean():
    pc = FakePubChem(
        cid_props={456: {"IUPACName": "(2S)-2-amino-4-methylsulfanylbutanoic acid", "InChIKey": "X"}},
        cid_synonyms={456: ["L-Methionine", "Methionine", "63-68-3"]},
    )
    v = sweep.verify_pubchem_cid_field(
        stored_cid=456,
        standard_name="Methionine",
        aliases=["L-Methionine"],
        cas_stored="63-68-3",
        pubchem=pc,
    )
    assert v.status == "verified_clean"


def test_malformed_rxcui_rejected():
    v = sweep.verify_rxcui_field(
        stored_rxcui="abc-not-digits",
        standard_name="Coenzyme Q10",
        rxnorm=FakeRxNorm(),
    )
    assert v.status == "mismatched"
    assert v.reason_code == "malformed_rxcui"


def test_rxcui_name_alignment_check():
    rx = FakeRxNorm(props_by_rxcui={"21406": {
        "rxcui": "21406", "name": "Coenzyme Q10", "tty": "IN", "synonym": "Ubidecarenone",
    }})
    v = sweep.verify_rxcui_field(
        stored_rxcui="21406", standard_name="Coenzyme Q10", rxnorm=rx,
    )
    assert v.status == "verified_clean"


def test_rxcui_name_disagreement_flagged():
    rx = FakeRxNorm(props_by_rxcui={"99999": {
        "rxcui": "99999", "name": "Totally Different Drug", "tty": "IN", "synonym": "",
    }})
    v = sweep.verify_rxcui_field(
        stored_rxcui="99999", standard_name="Coenzyme Q10", rxnorm=rx,
    )
    assert v.status == "mismatched"
    assert v.reason_code == "rxcui_name_does_not_align_with_iqm"


def test_unii_with_aligned_name_is_clean():
    gsrs = FakeGSRS(unii_records={
        "EJ27X76M46": {"_name": "UBIDECARENONE", "names": [{"name": "ubidecarenone"}, {"name": "Coenzyme Q10"}]},
    })
    v = sweep.verify_unii_field(
        stored_unii="EJ27X76M46", standard_name="Coenzyme Q10", cas_stored=None, gsrs=gsrs,
    )
    assert v.status == "verified_clean"


def test_unii_with_misaligned_name_flagged():
    gsrs = FakeGSRS(unii_records={
        "ZZZZZZZZZZ": {"_name": "Unrelated Substance", "names": [{"name": "Unrelated Substance"}]},
    })
    v = sweep.verify_unii_field(
        stored_unii="ZZZZZZZZZZ", standard_name="Coenzyme Q10", cas_stored=None, gsrs=gsrs,
    )
    assert v.status == "mismatched"
    assert v.reason_code == "unii_name_does_not_align_with_iqm"


def test_unii_malformed_rejected():
    v = sweep.verify_unii_field(
        stored_unii="notaunii", standard_name="X", cas_stored=None, gsrs=FakeGSRS(),
    )
    assert v.status == "mismatched"
    assert v.reason_code == "malformed_unii"


def test_cas_malformed_rejected():
    v = sweep.verify_cas_field(stored_cas="not-cas", standard_name="X", pubchem=FakePubChem())
    assert v.status == "mismatched"
    assert v.reason_code == "malformed_cas"


def test_cas_aligned_resolution_clean():
    pc = FakePubChem(
        cid_props={789: {"IUPACName": "X", "InChIKey": "Y"}},
        cid_synonyms={789: ["Vitamin C", "Ascorbic acid", "50-81-7"]},
        name_to_cid_map={"50-81-7": 789, "ascorbic acid": 789},
    )
    v = sweep.verify_cas_field(stored_cas="50-81-7", standard_name="Vitamin C", pubchem=pc)
    assert v.status == "verified_clean"


# --------------------------------------------------------------------------- #
# Seed-finding & report-shape tests
# --------------------------------------------------------------------------- #


def test_seed_findings_are_pre_populated():
    seeds = sweep.SEED_FINDINGS
    canonical_ids = {s["canonical_id"] for s in seeds}
    assert "coq10" in canonical_ids
    assert "5_htp" in canonical_ids
    assert "genistein" in canonical_ids
    # All seeds carry the seed=True marker
    assert all(s.get("seed") is True for s in seeds)
    # The 2 fixable seeds carry proposed values
    proposable = [s for s in seeds if s["canonical_id"] in {"coq10", "5_htp"}]
    for s in proposable:
        assert s.get("proposed_value")
        assert s.get("severity") == "high"


def test_per_parent_record_schema(tmp_path):
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps({
        "_metadata": {"schema_version": "5.0.0"},
        "test_entry": {
            "standard_name": "Test Compound",
            "cui": "C0041536",
            "rxcui": None,
            "external_ids": {"unii": None, "pubchem_cid": None, "cas": None},
            "aliases": [],
        },
    }))
    out = tmp_path / "out"
    cache = tmp_path / "cache"
    fake_umls = FakeUMLS(
        concepts={"C0041536": {
            "cui": "C0041536", "name": "Test Compound",
            "semantic_types": ["Organic Chemical"],
        }},
        exact_index={"test compound": {"cui": "C0041536", "name": "Test Compound"}},
    )
    summary = sweep.run_sweep(
        iqm_path=iqm_path, out_dir=out, cache_dir=cache,
        limit=None, only_id=None,
        umls=fake_umls, pubchem=FakePubChem(), gsrs=FakeGSRS(), rxnorm=FakeRxNorm(),
    )
    pp = json.loads((out / "per_parent" / "test_entry.json").read_text())
    # Required schema fields
    assert "canonical_id" in pp and pp["canonical_id"] == "test_entry"
    assert "iqm_snapshot_sha256" in pp
    assert "verified_at" in pp
    assert "fields" in pp
    for required_field in (
        "cui", "rxcui", "external_ids.unii", "external_ids.pubchem_cid",
        "external_ids.cas", "external_ids.inchi_key",
    ):
        assert required_field in pp["fields"]
        assert "stored" in pp["fields"][required_field]
        assert "verdict" in pp["fields"][required_field]
    # Master report exists
    assert (out / "MASTER_REPORT.md").exists()
    assert (out / "findings.jsonl").exists()
    assert (out / "queue.csv").exists()
    assert summary["parents_audited"] == 1


def test_findings_jsonl_sort_order_seeds_first_then_severity():
    findings = [
        {"canonical_id": "z_low", "severity": "low", "field": "x"},
        {"canonical_id": "a_high", "severity": "high", "field": "y"},
        {"canonical_id": "m_med", "severity": "medium", "field": "z"},
        {"canonical_id": "coq10", "severity": "high", "field": "cui", "seed": True},
    ]
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "f.jsonl"
        sweep.write_findings_jsonl(findings, p)
        lines = p.read_text().strip().splitlines()
        parsed = [json.loads(line) for line in lines]
    # seeds first
    assert parsed[0]["seed"] is True
    # Then high
    assert parsed[1]["severity"] == "high"
    assert parsed[1]["canonical_id"] == "a_high"
    # Then medium, low
    severities = [p["severity"] for p in parsed[1:]]
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    assert severities == sorted(severities, key=lambda s: sev_rank.get(s, 3))


def test_queue_csv_contains_seed_and_high_only():
    findings = [
        {"canonical_id": "low_only", "severity": "low", "field": "cui", "current_value": "C0", "evidence": "x"},
        {"canonical_id": "med_only", "severity": "medium", "field": "rxcui", "current_value": "1", "evidence": "y"},
        {"canonical_id": "hi", "severity": "high", "field": "cui", "current_value": "C1", "proposed_value": "C2", "reason_code": "r", "evidence": "z"},
        {"canonical_id": "coq10", "severity": "high", "field": "cui", "current_value": "C1843920", "proposed_value": "C0041536", "reason_code": "r", "evidence": "seed", "seed": True},
    ]
    import tempfile
    import csv as _csv
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "q.csv"
        sweep.write_queue_csv(findings, p)
        rows = list(_csv.reader(p.read_text().splitlines()))
    header, *body = rows
    assert "canonical_id" in header
    cids = [r[0] for r in body]
    assert "coq10" in cids
    assert "hi" in cids
    assert "low_only" not in cids
    assert "med_only" not in cids


# --------------------------------------------------------------------------- #
# Safety-rail tests
# --------------------------------------------------------------------------- #


def test_argparse_does_not_accept_apply_flag(capsys):
    """The orchestrator must explicitly reject --apply, --write,
    --apply-mismatches. Compliance with spec §'Do NOT auto-fix'."""
    for bad in ("--apply", "--write", "--apply-mismatches"):
        old_argv = sys.argv
        sys.argv = ["iqm_identifier_sweep.py", "--file", "/tmp/x", "--out", "/tmp/y", "--cache", "/tmp/z", bad]
        try:
            rc = sweep.main()
            assert rc == 2
        finally:
            sys.argv = old_argv


def test_offline_mode_runs_without_clients(tmp_path):
    """In --offline mode, the sweep produces unresolvable verdicts for
    everything that needs a live API call, but still emits per_parent records
    and reports."""
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps({
        "_metadata": {"schema_version": "5.0.0"},
        "x": {"standard_name": "X", "cui": "C0000001"},
    }))
    summary = sweep.run_sweep(
        iqm_path=iqm_path, out_dir=tmp_path / "out", cache_dir=tmp_path / "cache",
        limit=None, only_id=None,
        umls=None, pubchem=None, gsrs=None, rxnorm=None,
    )
    assert summary["parents_audited"] == 1
    assert (tmp_path / "out" / "per_parent" / "x.json").exists()
    rec = json.loads((tmp_path / "out" / "per_parent" / "x.json").read_text())
    assert rec["fields"]["cui"]["verdict"]["status"] == "unresolvable"


def test_only_id_filter_processes_single_parent(tmp_path):
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps({
        "_metadata": {"schema_version": "5.0.0"},
        "a": {"standard_name": "A"},
        "b": {"standard_name": "B"},
    }))
    summary = sweep.run_sweep(
        iqm_path=iqm_path, out_dir=tmp_path / "out", cache_dir=tmp_path / "cache",
        limit=None, only_id="b",
        umls=None, pubchem=None, gsrs=None, rxnorm=None,
    )
    assert summary["parents_audited"] == 1
    assert (tmp_path / "out" / "per_parent" / "b.json").exists()
    assert not (tmp_path / "out" / "per_parent" / "a.json").exists()


def test_iqm_snapshot_sha256_is_recorded(tmp_path):
    iqm_bytes = json.dumps({"_metadata": {"v": 1}, "x": {"standard_name": "X"}}).encode()
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_bytes(iqm_bytes)
    expected_sha = hashlib.sha256(iqm_bytes).hexdigest()
    sweep.run_sweep(
        iqm_path=iqm_path, out_dir=tmp_path / "out", cache_dir=tmp_path / "cache",
        limit=None, only_id=None,
        umls=None, pubchem=None, gsrs=None, rxnorm=None,
    )
    rec = json.loads((tmp_path / "out" / "per_parent" / "x.json").read_text())
    assert rec["iqm_snapshot_sha256"] == expected_sha
    master = (tmp_path / "out" / "MASTER_REPORT.md").read_text()
    assert expected_sha in master


# --------------------------------------------------------------------------- #
# Token helper sanity
# --------------------------------------------------------------------------- #


def test_token_helper_drops_stopwords():
    toks = sweep._tokens("Extract of Ashwagandha root powder")
    # 'of' is a stopword; 'extract'/'powder' are NOT stopwords here (they have
    # meaning for distinguishing preparation vs compound)
    assert "of" not in toks
    assert "ashwagandha" in toks
    assert "root" in toks


def test_class_level_detection():
    assert sweep._iqm_appears_class_level("Total Carotenoids") is True
    assert sweep._iqm_appears_class_level("NAD+ Precursors") is True
    assert sweep._iqm_appears_class_level("Various Flavonoids") is True
    assert sweep._iqm_appears_class_level("Coenzyme Q10") is False
    assert sweep._iqm_appears_class_level("Genistein") is False


# --------------------------------------------------------------------------- #
# Wave 9.C.1 — flat-array schema support (banned_recalled / harmful_additives)
# --------------------------------------------------------------------------- #


def test_load_parents_default_dict_keyed_schema():
    data = {
        "_metadata": {"schema_version": "5.0.0"},
        "coq10": {"standard_name": "Coenzyme Q10"},
        "5_htp": {"standard_name": "5-HTP"},
    }
    parents = sweep._load_parents(data, list_key=None)
    keys = [cid for cid, _ in parents]
    assert keys == sorted(["coq10", "5_htp"])


def test_load_parents_flat_array_under_ingredients_key():
    data = {
        "_metadata": {"schema_version": "5.4.1"},
        "ingredients": [
            {"id": "BANNED_RED_YEAST_RICE", "standard_name": "Red Yeast Rice (Monacolin K)"},
            {"id": "ADULTERANT_MELOXICAM", "standard_name": "Meloxicam (adulterant)"},
        ],
    }
    parents = sweep._load_parents(data, list_key="ingredients")
    keys = [cid for cid, _ in parents]
    assert keys == sorted(["BANNED_RED_YEAST_RICE", "ADULTERANT_MELOXICAM"])
    by_id = dict(parents)
    assert by_id["BANNED_RED_YEAST_RICE"]["standard_name"] == "Red Yeast Rice (Monacolin K)"


def test_load_parents_flat_array_under_harmful_additives_key():
    data = {
        "_metadata": {"schema_version": "5.4.0"},
        "harmful_additives": [
            {"id": "ADD_ACESULFAME_K", "standard_name": "Acesulfame Potassium"},
            {"id": "ADD_BHA", "standard_name": "Butylated hydroxyanisole"},
        ],
    }
    parents = sweep._load_parents(data, list_key="harmful_additives")
    keys = [cid for cid, _ in parents]
    assert keys == sorted(["ADD_ACESULFAME_K", "ADD_BHA"])


def test_load_parents_flat_array_skips_non_dict_entries():
    data = {
        "ingredients": [
            {"id": "VALID_1", "x": 1},
            "this is not a dict",
            None,
            {"id": "VALID_2", "x": 2},
        ],
    }
    parents = sweep._load_parents(data, list_key="ingredients")
    keys = [cid for cid, _ in parents]
    assert keys == ["VALID_1", "VALID_2"]


def test_load_parents_flat_array_skips_entries_without_id():
    data = {
        "ingredients": [
            {"id": "HAS_ID", "x": 1},
            {"no_id_here": True, "standard_name": "orphan"},
            {"id": "", "x": "empty id rejected"},
        ],
    }
    parents = sweep._load_parents(data, list_key="ingredients")
    keys = [cid for cid, _ in parents]
    assert keys == ["HAS_ID"]


def test_load_parents_flat_array_raises_when_key_points_to_non_list():
    data = {"ingredients": {"this": "is a dict, not a list"}}
    with pytest.raises(ValueError, match="expected list"):
        sweep._load_parents(data, list_key="ingredients")


def test_load_parents_flat_array_missing_key_returns_empty():
    data = {"_metadata": {"v": 1}, "other_key": []}
    parents = sweep._load_parents(data, list_key="ingredients")
    assert parents == []


def test_run_sweep_flat_array_end_to_end(tmp_path):
    target = tmp_path / "banned.json"
    target.write_text(json.dumps({
        "_metadata": {"schema_version": "5.4.1"},
        "ingredients": [
            {
                "id": "BANNED_TEST_ALPHA",
                "standard_name": "Test alpha compound",
                "cui": "C0000001",
                "external_ids": {"unii": "TEST111111"},
            },
            {
                "id": "BANNED_TEST_BETA",
                "standard_name": "Test beta compound",
                "cui": None,
                "external_ids": {},
            },
        ],
    }))
    summary = sweep.run_sweep(
        iqm_path=target,
        out_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        limit=None,
        only_id=None,
        umls=None, pubchem=None, gsrs=None, rxnorm=None,
        list_key="ingredients",
    )
    assert summary["parents_audited"] == 2
    pp_a = json.loads((tmp_path / "out" / "per_parent" / "BANNED_TEST_ALPHA.json").read_text())
    pp_b = json.loads((tmp_path / "out" / "per_parent" / "BANNED_TEST_BETA.json").read_text())
    assert pp_a["canonical_id"] == "BANNED_TEST_ALPHA"
    assert pp_a["standard_name"] == "Test alpha compound"
    assert pp_b["canonical_id"] == "BANNED_TEST_BETA"
    assert pp_a["iqm_snapshot_sha256"] == pp_b["iqm_snapshot_sha256"]
    master = (tmp_path / "out" / "MASTER_REPORT.md").read_text()
    assert pp_a["iqm_snapshot_sha256"] in master


def test_argparse_accepts_list_key():
    parser = sweep.build_arg_parser()
    args = parser.parse_args([
        "--file", "/tmp/x", "--out", "/tmp/o", "--cache", "/tmp/c",
        "--list-key", "ingredients",
    ])
    assert args.list_key == "ingredients"


def test_argparse_list_key_defaults_to_none():
    parser = sweep.build_arg_parser()
    args = parser.parse_args([
        "--file", "/tmp/x", "--out", "/tmp/o", "--cache", "/tmp/c",
    ])
    assert args.list_key is None
