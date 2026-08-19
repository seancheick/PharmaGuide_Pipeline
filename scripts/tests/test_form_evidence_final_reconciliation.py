"""Release contract for the reference-level form-evidence reconciliation."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from iqm_form_evidence import load_backlog_file, validate_iqm_form_evidence


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
IQM_PATH = SCRIPTS_DIR / "data" / "ingredient_quality_map.json"
BACKLOG_PATH = SCRIPTS_DIR / "data" / "iqm_excellent_evidence_backlog.json"
CLINICAL_PATH = SCRIPTS_DIR / "data" / "backed_clinical_studies.json"
AUDIT_DIR = SCRIPTS_DIR / "audits" / "form_evidence_20260813"
REFERENCE_LEDGER_PATH = AUDIT_DIR / "reference_level_reconciliation_20260818.json"
FINAL_MANIFEST_PATH = AUDIT_DIR / "final_reconciliation_manifest_20260818.json"

KEEP = "KEEP_FORM_SOURCE"
REPLACEMENTS = {
    ("hmb", "hmb calcium salt (hmb-ca)"): {"21134325"},
    ("hmb", "hmb free acid (hmb-fa)"): {"21134325"},
    ("collagen", "collagen tripeptides"): {"26934933"},
    # 2026-08-19. PMID 32188111 (Nutrients 2020) is a randomized three-period
    # crossover in 21 adults aged 65-74 comparing ubiquinol vs ubiquinone
    # capsules head to head. Ubiquinol was NOT significantly more bioavailable
    # (1.7-fold, 95% CI 0.9-3.1, p = 0.129), which is what makes it valid here:
    # `ubiquinol` and `ubiquinone crystal-dispersed` are both scored 13, and the
    # study supports that parity rather than a redox-form premium.
    #
    # Deliberately NOT applied to `coq10::ubiquinol crystal-free`: that study
    # dosed plain ubiquinol capsules, not a crystal-free formulation, so it does
    # not answer the crystal-free claim. That form stays in the backlog.
    ("coq10", "ubiquinol"): {"32188111"},
}


def _load(path: Path) -> object:
    return json.loads(path.read_text())


def _form(iqm: dict, ingredient_key: str, form_key: str) -> dict:
    return iqm[ingredient_key]["forms"][form_key]


def _reference_ids(form: dict) -> set[str]:
    evidence = form.get("form_evidence")
    if not isinstance(evidence, dict):
        return set()
    refs = evidence.get("references_structured") or []
    return {
        str(reference.get("pmid") or "ODS")
        for reference in refs
        if isinstance(reference, dict)
    }


def test_reference_ledger_is_complete_and_uses_the_reviewed_dispositions():
    rows = _load(REFERENCE_LEDGER_PATH)

    assert isinstance(rows, list)
    assert len(rows) == 120
    assert len({(r["ingredient"], r["form"]) for r in rows}) == 89
    assert Counter(r["verdict"] for r in rows) == {
        "KEEP_FORM_SOURCE": 51,
        "MOVE_TO_CLINICAL_EVIDENCE": 34,
        "REMOVE_OFF_AXIS": 20,
        "REPLACE_WITH_BETTER_SOURCE": 15,
    }


def test_iqm_uses_only_retained_or_verified_replacement_form_sources():
    iqm = _load(IQM_PATH)
    rows = _load(REFERENCE_LEDGER_PATH)
    expected: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in rows:
        key = (row["ingredient"], row["form"])
        if row["verdict"] == KEEP:
            expected[key].add(str(row["ref"]))
    for key, pmids in REPLACEMENTS.items():
        expected[key].update(pmids)

    for ingredient_key, form_key in {
        (r["ingredient"], r["form"]) for r in rows
    }:
        form = _form(iqm, ingredient_key, form_key)
        assert isinstance(form.get("aliases"), list) and form["aliases"]
        assert _reference_ids(form) == expected[(ingredient_key, form_key)]
        if expected[(ingredient_key, form_key)]:
            assert form["form_evidence"]["score_supported"] is True
        else:
            assert "form_evidence" not in form


def test_score_corrections_are_narrow_and_match_the_reviewed_form_axis():
    iqm = _load(IQM_PATH)
    expected = {
        ("vitamin_c", "calcium ascorbate"): (13, 13),
        ("magnesium", "magnesium aspartate"): (13, 13),
        ("hmb", "hmb free acid (hmb-fa)"): (14, 14),
        ("dha", "DHA fish oil rTG"): (14, 17),
        ("epa", "EPA fish oil rTG"): (14, 17),
    }

    for (ingredient_key, form_key), (bio_score, total_score) in expected.items():
        form = _form(iqm, ingredient_key, form_key)
        assert (form["bio_score"], form["score"]) == (bio_score, total_score)


def test_backlog_exactly_tracks_legacy_excellent_forms_without_verified_evidence():
    iqm = _load(IQM_PATH)
    backlog = load_backlog_file(BACKLOG_PATH)

    assert validate_iqm_form_evidence(iqm, backlog=backlog) == []
    for key in backlog:
        ingredient_key, form_key = key.split("::", 1)
        form = _form(iqm, ingredient_key, form_key)
        assert form["bio_score"] >= 12
        assert "form_evidence" not in form


def test_clinical_only_sources_exist_once_and_do_not_overstate_mixed_results():
    entries = _load(CLINICAL_PATH)["backed_clinical_studies"]
    all_pmids = [
        str(ref.get("pmid"))
        for entry in entries
        for ref in entry.get("references_structured") or []
        if isinstance(ref, dict) and ref.get("pmid")
    ]

    for pmid in ("40535538", "40707016", "42485904"):
        assert all_pmids.count(pmid) == 1

    by_id = {entry["id"]: entry for entry in entries}
    assert by_id["STRAIN_HN019"]["effect_direction"] == "mixed"
    assert by_id["PRECLIN_PTEROSTILBENE"]["effect_direction"] == "mixed"
    assert by_id["STRAIN_BC30"]["standard_name"].endswith("GBI-30, 6086")
    assert by_id["STRAIN_REUTERI_DSM17938"]["standard_name"].endswith("DSM 17938")
    assert not any(
        "dsm 17938" in alias.casefold()
        for alias in by_id["STRAIN_REUTERI_PRODENTIS"]["aliases"]
    )


def test_final_manifest_records_every_iqm_mutation_once():
    manifest = _load(FINAL_MANIFEST_PATH)
    changes = manifest["changes"]

    assert manifest["schema_version"] == "1.0.0"
    assert manifest["review_date"] == "2026-08-18"
    assert len(changes) == 89
    assert len({(c["ingredient_key"], c["form_key"]) for c in changes}) == 89
    assert manifest["summary"] == {
        "audited_forms": 89,
        "forms_with_verified_evidence": 49,
        "forms_returned_to_legacy_backlog": 40,
        "score_corrections": 5,
    }


def test_batch_usage_explains_that_stages_do_not_suppress_release():
    runner = (SCRIPTS_DIR.parent / "batch_run_all_datasets.sh").read_text()

    assert (
        "--stages enrich,score    # Enrich + score, then snapshot + full release"
        in runner
    )
