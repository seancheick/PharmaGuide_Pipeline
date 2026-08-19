"""Release contract for the 2026-08-18 form-score reconciliation."""

from __future__ import annotations

import json
from pathlib import Path

from iqm_form_evidence import load_backlog_file, validate_iqm_form_evidence


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
IQM_PATH = SCRIPTS_DIR / "data" / "ingredient_quality_map.json"
BACKLOG_PATH = SCRIPTS_DIR / "data" / "iqm_excellent_evidence_backlog.json"
MANIFEST_PATH = (
    SCRIPTS_DIR
    / "audits"
    / "form_evidence_20260813"
    / "score_reconciliation_manifest.json"
)

ALLOWED_ACTIONS = {
    "RESTORE_LEGACY",
    "KEEP_CORRECTION",
    "TAXONOMY_FIX",
    "NO_CHANGE",
}


def _load() -> tuple[dict, dict]:
    return json.loads(IQM_PATH.read_text()), json.loads(MANIFEST_PATH.read_text())


def test_reconciliation_manifest_is_complete_and_matches_iqm():
    iqm, manifest = _load()
    rows = manifest["changes"]

    assert manifest["schema_version"] == "1.0.0"
    assert len(rows) == 182
    assert len({(row["ingredient_key"], row["form_key"]) for row in rows}) == 182

    for row in rows:
        assert row["action"] in ALLOWED_ACTIONS
        assert row["provenance_status"] in {
            "legacy_curated_unvalidated",
            "source_verified",
            "clinician_reviewed_correction",
            "audit_locked_correction",
        }
        assert row["rationale"].strip()
        assert isinstance(row["citation_ids"], list)
        form = iqm[row["ingredient_key"]]["forms"][row["form_key"]]
        assert form["bio_score"] == row["final_score"]
        assert form["score"] == row["final_total_score"]
        if row["action"] == "RESTORE_LEGACY":
            assert row["final_score"] == row["pre_migration_score"]
            assert row["final_total_score"] == row["pre_migration_total_score"]

    assert manifest["summary"]["scores_restored"] == 161
    assert manifest["summary"]["affirmative_corrections_preserved"] == 21


def test_legacy_excellent_forms_are_frozen_without_weakening_new_score_gate():
    iqm, manifest = _load()
    backlog = load_backlog_file(BACKLOG_PATH)
    legacy_keys = {
        f'{row["ingredient_key"]}::{row["form_key"]}'
        for row in manifest["changes"]
        if row["provenance_status"] == "legacy_curated_unvalidated"
        and row["final_score"] >= 12
    }

    assert backlog == legacy_keys
    assert validate_iqm_form_evidence(iqm, backlog=backlog) == []

    # A newly introduced unsupported Excellent form is not grandfathered.
    iqm["test_new_form"] = {
        "standard_name": "Test new form",
        "forms": {"unsupported": {"bio_score": 12, "score": 12}},
    }
    assert validate_iqm_form_evidence(iqm, backlog=backlog) == [
        "test_new_form::unsupported: Excellent bio_score 12 lacks approved form_evidence"
    ]


def test_verified_form_axis_canaries_keep_market_relevant_scores_and_sources():
    iqm, manifest = _load()
    rows = {
        (row["ingredient_key"], row["form_key"]): row
        for row in manifest["changes"]
    }
    expected = {
        ("fish_oil", "triglyceride (rTG) form"): (14, "20638827"),
        ("mct_oil", "c8 mct oil (pure caprylic)"): (15, "29955698"),
        ("vitamin_d", "calcidiol (25-hydroxy D3)"): (14, "34101900"),
        ("quercetin", "isoquercetin (EMIQ)"): (13, "20638359"),
        ("calcium", "calcium citrate malate"): (14, "3124946"),
    }

    for key, (score, pmid) in expected.items():
        row = rows[key]
        form = iqm[key[0]]["forms"][key[1]]
        assert row["final_score"] == score
        assert row["provenance_status"] == "source_verified"
        assert row["citation_ids"] == [f"PMID:{pmid}"]
        assert form["form_evidence"]["score_supported"] is True
        assert {
            reference.get("pmid")
            for reference in form["form_evidence"]["references_structured"]
        } == {pmid}


def test_taxonomy_repairs_do_not_change_ingredient_identity_contracts():
    iqm, manifest = _load()
    taxonomy_rows = [
        row for row in manifest["changes"] if row["action"] == "TAXONOMY_FIX"
    ]

    assert len(taxonomy_rows) == 7
    assert iqm["creatine_monohydrate"]["standard_name"] == "Creatine"
    assert (
        iqm["taurine"]["forms"]["magnesium taurate (as taurine source)"]
        ["cross_ref"]["primary_parent"]
        == "magnesium"
    )
    assert "added plant-compound component" in (
        iqm["vitamin_c"]["forms"]["vitamin C with bioflavonoids"]
        ["consumer_note"]
    )


def test_reconciled_forms_remain_in_the_matching_map():
    iqm, manifest = _load()

    for row in manifest["changes"]:
        ingredient = iqm.get(row["ingredient_key"])
        assert isinstance(ingredient, dict)
        form = ingredient.get("forms", {}).get(row["form_key"])
        assert isinstance(form, dict)
        assert isinstance(form.get("aliases"), list) and form["aliases"]
