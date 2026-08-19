"""Contract tests for structured IQM form evidence and atomic migrations."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from iqm_form_evidence import (
    ManifestError,
    apply_manifest_file,
    backlog_initial_digest,
    build_initial_backlog,
    catalog_evidence_gaps,
    catalog_form_usage,
    collect_pubmed_pmids,
    form_digest,
    load_backlog_file,
    validate_exported_form_evidence,
    validate_iqm_form_evidence,
    verify_pubmed_content,
)


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
IQM_PATH = SCRIPTS_DIR / "data" / "ingredient_quality_map.json"
BACKLOG_PATH = SCRIPTS_DIR / "data" / "iqm_excellent_evidence_backlog.json"
ADJUDICATION_REPORT_PATH = (
    SCRIPTS_DIR / "audits" / "form_evidence_20260813" / "adjudication_report.json"
)
CLINICAL_REVIEW_QUEUE_PATH = (
    SCRIPTS_DIR / "audits" / "form_evidence_20260813" / "clinical_review_queue.csv"
)


def _reference(*, pmid: str = "14596323") -> dict:
    return {
        "type": "pubmed",
        "authority": "NCBI PubMed",
        "pmid": pmid,
        "doi": "10.1080/07315724.2003.10719348",
        "title": "Mg citrate found more bioavailable than other Mg preparations in a randomised, double-blind study.",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "published_date": "2003-09-01",
        "publication_types": ["Randomized Controlled Trial", "Journal Article"],
        "evidence_grade": "rct",
        "retracted": False,
        "supports_claims": ["oral_bioavailability"],
        "verification_source": "pubmed_eutils",
        "verified_on": "2026-08-13",
    }


def _approved_evidence() -> dict:
    return {
        "schema_version": "1.0.0",
        "axis": "systemic_bioavailability",
        "evidence_level": "moderate",
        "score_supported": True,
        "rationale": "A direct human comparison supports the assigned form-quality tier.",
        "review": {
            "status": "source_verified",
            "by": "PharmaGuide evidence audit",
            "date": "2026-08-13",
        },
        "references_structured": [_reference()],
    }


def _iqm(form: dict) -> dict:
    return {
        "_metadata": {"schema_version": "5.4.15"},
        "magnesium": {
            "standard_name": "Magnesium",
            "forms": {"magnesium citrate": form},
        },
    }


def test_excellent_form_requires_approved_structured_evidence():
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})

    issues = validate_iqm_form_evidence(iqm, backlog=set())

    assert issues == [
        "magnesium::magnesium citrate: Excellent bio_score 14 lacks approved form_evidence"
    ]


def test_frozen_backlog_allows_existing_gap_but_rejects_stale_entries():
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})

    assert validate_iqm_form_evidence(
        iqm,
        backlog={"magnesium::magnesium citrate"},
    ) == []

    iqm["magnesium"]["forms"]["magnesium citrate"]["form_evidence"] = (
        _approved_evidence()
    )
    assert validate_iqm_form_evidence(
        iqm,
        backlog={"magnesium::magnesium citrate"},
    ) == [
        "magnesium::magnesium citrate: approved evidence is still listed in the backlog"
    ]


def test_backlog_rejects_form_resolved_by_score_recalibration():
    iqm = _iqm({"bio_score": 11, "score": 11, "natural": False})

    assert validate_iqm_form_evidence(
        iqm,
        backlog={"magnesium::magnesium citrate"},
    ) == [
        "magnesium::magnesium citrate: non-Excellent form is still listed in the backlog"
    ]


@pytest.mark.parametrize("level", ["limited", "mechanistic_only", "none"])
def test_excellent_form_rejects_evidence_too_weak_for_public_tier(level: str):
    evidence = _approved_evidence()
    evidence["evidence_level"] = level
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )

    issues = validate_iqm_form_evidence(iqm, backlog=set())

    assert any("requires strong or moderate evidence" in issue for issue in issues)


def test_pubmed_reference_requires_claim_scope_and_verification_receipt():
    evidence = _approved_evidence()
    reference = evidence["references_structured"][0]
    reference["supports_claims"] = []
    reference.pop("verified_on")
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )

    issues = validate_iqm_form_evidence(iqm, backlog=set())

    assert any("supports_claims must be non-empty" in issue for issue in issues)
    assert any("verified_on must be an ISO date" in issue for issue in issues)


def test_authoritative_guidance_is_a_supported_source_type():
    evidence = _approved_evidence()
    evidence["references_structured"] = [
        {
            "type": "authoritative_guidance",
            "authority": "NIH Office of Dietary Supplements",
            "title": "Magnesium — Health Professional Fact Sheet",
            "url": "https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/",
            "supports_claims": ["form_class_context"],
            "verification_source": "official_source_review",
            "verified_on": "2026-08-13",
        }
    ]
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )

    assert validate_iqm_form_evidence(iqm, backlog=set()) == []


def test_exported_form_evidence_is_compact_and_still_source_verified():
    compact = {
        "evidence_level": "moderate",
        "references_structured": [_reference()],
    }

    assert validate_exported_form_evidence(compact, label="row") == []

    compact["rationale"] = "Internal adjudication must not ship."
    issues = validate_exported_form_evidence(compact, label="row")

    assert issues == ["row: internal field rationale must not be exported"]


def test_manifest_apply_is_atomic_when_any_precondition_is_stale(tmp_path: Path):
    iqm_path = tmp_path / "ingredient_quality_map.json"
    manifest_path = tmp_path / "manifest.json"
    original = _iqm({"bio_score": 14, "score": 14, "natural": False})
    iqm_path.write_text(json.dumps(original, indent=2) + "\n")
    form = original["magnesium"]["forms"]["magnesium citrate"]
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "changes": [
                    {
                        "ingredient_key": "magnesium",
                        "form_key": "magnesium citrate",
                        "expected_form_sha256": form_digest(form),
                        "set": {"form_evidence": _approved_evidence()},
                    },
                    {
                        "ingredient_key": "vitamin_c",
                        "form_key": "ascorbic acid",
                        "expected_form_sha256": "missing",
                        "set": {"form_evidence": _approved_evidence()},
                    },
                ],
            },
            indent=2,
        )
        + "\n"
    )

    with pytest.raises(ManifestError, match="vitamin_c::ascorbic acid"):
        apply_manifest_file(iqm_path, manifest_path)

    assert json.loads(iqm_path.read_text()) == original


def test_manifest_apply_can_atomically_remove_stale_form_evidence(tmp_path: Path):
    iqm_path = tmp_path / "ingredient_quality_map.json"
    manifest_path = tmp_path / "manifest.json"
    original = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": _approved_evidence(),
        }
    )
    form = original["magnesium"]["forms"]["magnesium citrate"]
    iqm_path.write_text(json.dumps(original, indent=2) + "\n")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "changes": [
                    {
                        "ingredient_key": "magnesium",
                        "form_key": "magnesium citrate",
                        "expected_form_sha256": form_digest(form),
                        "unset": ["form_evidence"],
                    }
                ],
            }
        )
    )

    result = apply_manifest_file(iqm_path, manifest_path)
    updated = json.loads(iqm_path.read_text())

    assert result == {"expected": 1, "applied": 1, "unchanged": 0}
    assert "form_evidence" not in updated["magnesium"]["forms"]["magnesium citrate"]


def test_manifest_apply_updates_all_entries_and_reports_exact_counts(tmp_path: Path):
    iqm_path = tmp_path / "ingredient_quality_map.json"
    manifest_path = tmp_path / "manifest.json"
    original = _iqm({"bio_score": 14, "score": 14, "natural": False})
    iqm_path.write_text(json.dumps(original, indent=2) + "\n")
    form = original["magnesium"]["forms"]["magnesium citrate"]
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "changes": [
                    {
                        "ingredient_key": "magnesium",
                        "form_key": "magnesium citrate",
                        "expected_form_sha256": form_digest(form),
                        "set": {"form_evidence": _approved_evidence()},
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    summary = apply_manifest_file(iqm_path, manifest_path)

    assert summary == {"expected": 1, "applied": 1, "unchanged": 0}
    updated = json.loads(iqm_path.read_text())
    assert (
        updated["magnesium"]["forms"]["magnesium citrate"]["form_evidence"]
        == _approved_evidence()
    )


def test_backlog_freezes_initial_keys_and_only_remaining_keys_gate():
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})

    backlog = build_initial_backlog(iqm, created_on="2026-08-13")

    assert backlog["_metadata"]["initial_forms_sha256"] == backlog_initial_digest(
        backlog["initial_forms"]
    )
    assert backlog["initial_forms"] == ["magnesium::magnesium citrate"]
    assert backlog["remaining_forms"] == ["magnesium::magnesium citrate"]


def test_backlog_loader_rejects_growth_beyond_frozen_initial_set(tmp_path: Path):
    path = tmp_path / "backlog.json"
    path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "schema_version": "5.0.0",
                    "initial_forms_sha256": backlog_initial_digest(
                        ["magnesium::magnesium citrate"]
                    ),
                },
                "initial_forms": ["magnesium::magnesium citrate"],
                "remaining_forms": [
                    "magnesium::magnesium citrate",
                    "vitamin_c::ascorbic acid",
                ],
            }
        )
    )

    with pytest.raises(ManifestError, match="not in the frozen initial set"):
        load_backlog_file(path)


def test_backlog_loader_rejects_mutated_initial_set(tmp_path: Path):
    path = tmp_path / "backlog.json"
    path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "schema_version": "5.0.0",
                    "initial_forms_sha256": "stale",
                },
                "initial_forms": ["magnesium::magnesium citrate"],
                "remaining_forms": ["magnesium::magnesium citrate"],
            }
        )
    )

    with pytest.raises(ManifestError, match="initial_forms_sha256"):
        load_backlog_file(path)


def test_quality_map_has_no_untracked_excellent_evidence_gap():
    iqm = json.loads(IQM_PATH.read_text())
    backlog = load_backlog_file(BACKLOG_PATH)

    assert validate_iqm_form_evidence(iqm, backlog=backlog) == []


def test_catalog_usage_reads_primary_and_multi_form_matches(tmp_path: Path):
    enriched_dir = tmp_path / "output_Test_enriched" / "enriched"
    enriched_dir.mkdir(parents=True)
    (enriched_dir / "batch.json").write_text(
        json.dumps(
            [
                {
                    "dsld_id": "P1",
                    "ingredient_quality_data": {
                        "ingredients": [
                            {
                                "canonical_id": "magnesium",
                                "matched_form": "magnesium citrate",
                                "bio_score": 14,
                            },
                            {
                                "canonical_id": "calcium",
                                "matched_form": "calcium carbonate",
                                "matched_forms": [
                                    {"form_key": "calcium citrate"},
                                    {"form_key": "calcium malate"},
                                ],
                                "bio_score": 13,
                            },
                        ]
                    },
                }
            ]
        )
    )

    usage = catalog_form_usage(tmp_path)

    assert usage["magnesium::magnesium citrate"] == {
        "ingredient_rows": 1,
        "products": 1,
    }
    assert usage["calcium::calcium citrate"]["products"] == 1
    assert usage["calcium::calcium malate"]["products"] == 1


def test_catalog_usage_streams_large_top_level_arrays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    enriched_dir = tmp_path / "output_Test_enriched" / "enriched"
    enriched_dir.mkdir(parents=True)
    path = enriched_dir / "batch.json"
    path.write_text(
        json.dumps(
            [
                {
                    "ingredient_quality_data": {
                        "ingredients": [
                            {
                                "canonical_id": "magnesium",
                                "matched_form": "magnesium citrate",
                            }
                        ]
                    }
                }
            ]
        )
    )

    def fail_read_text(*_args, **_kwargs):
        raise AssertionError("catalog audit must not read a whole enriched file")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    usage = catalog_form_usage(tmp_path)

    assert usage["magnesium::magnesium citrate"]["products"] == 1


def test_catalog_usage_counts_rows_and_products_separately(tmp_path: Path):
    enriched_dir = tmp_path / "output_Test_enriched" / "enriched"
    enriched_dir.mkdir(parents=True)
    (enriched_dir / "batch.json").write_text(
        json.dumps(
            [
                {
                    "ingredient_quality_data": {
                        "ingredients": [
                            {
                                "canonical_id": "magnesium",
                                "matched_form": "magnesium citrate",
                            },
                            {
                                "canonical_id": "magnesium",
                                "matched_form": "magnesium citrate",
                            },
                        ]
                    }
                }
            ]
        )
    )

    usage = catalog_form_usage(tmp_path)

    assert usage["magnesium::magnesium citrate"] == {
        "ingredient_rows": 2,
        "products": 1,
    }


def test_catalog_gate_reports_only_used_excellent_forms_without_evidence():
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})
    usage = {
        "magnesium::magnesium citrate": {"ingredient_rows": 10, "products": 8},
        "vitamin_c::ascorbic acid": {"ingredient_rows": 20, "products": 20},
    }

    assert catalog_evidence_gaps(iqm, usage) == [
        {
            "key": "magnesium::magnesium citrate",
            "bio_score": 14,
            "ingredient_rows": 10,
            "products": 8,
            "issues": [
                "magnesium::magnesium citrate: Excellent bio_score 14 lacks approved form_evidence"
            ],
        }
    ]


def test_live_pubmed_check_detects_wrong_paper_and_retraction():
    evidence = _approved_evidence()
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )
    articles = {
        "14596323": {
            "pmid": "14596323",
            "title": "A completely unrelated paper.",
            "doi": "10.0000/wrong",
            "retracted": True,
        }
    }

    issues = verify_pubmed_content(iqm, articles)

    assert any("title does not match live PubMed" in issue for issue in issues)
    assert any("DOI does not match live PubMed" in issue for issue in issues)
    assert any("is retracted" in issue for issue in issues)


def test_live_pubmed_check_accepts_matching_content():
    evidence = _approved_evidence()
    reference = evidence["references_structured"][0]
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )
    articles = {
        reference["pmid"]: {
            "pmid": reference["pmid"],
            "title": reference["title"],
            "doi": reference["doi"],
            "retracted": False,
        }
    }

    assert verify_pubmed_content(iqm, articles) == []


def test_pubmed_collection_is_sorted_and_deduplicated():
    evidence = _approved_evidence()
    evidence["references_structured"].append(_reference())
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence": evidence,
        }
    )

    assert collect_pubmed_pmids(iqm) == ["14596323"]


def test_iqm_form_evidence_audit_summary_matches_adjudication_report():
    iqm = json.loads(IQM_PATH.read_text(encoding="utf-8"))
    report = json.loads(ADJUDICATION_REPORT_PATH.read_text(encoding="utf-8"))
    summary = " ".join(
        iqm["_metadata"]["schema_updates"]["5.5.0"]["changes"]
    )

    assert f"Live-verified {report['live_pmids_verified']} PubMed records" in summary
    assert f"retained {report['excellent_retained']} Excellent forms" in summary
    assert (
        f"Recalibrated {report['recalibrated_to_good']} unsupported Excellent forms"
        in summary
    )


def test_clinical_review_queue_is_complete_provisional_and_axis_aware():
    iqm = json.loads(IQM_PATH.read_text(encoding="utf-8"))
    report = json.loads(ADJUDICATION_REPORT_PATH.read_text(encoding="utf-8"))
    with CLINICAL_REVIEW_QUEUE_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    report_keys = {entry["key"] for entry in report["lowered"]}
    queue_keys = {f"{row['ingredient']}::{row['form']}" for row in rows}
    assert len(rows) == report["recalibrated_to_good"]
    assert queue_keys == report_keys
    assert {row["review_status"] for row in rows} == {
        "not_clinically_approved"
    }
    assert all(not row["clinician_decision"] for row in rows)
    assert all(not row["clinician_approved_score"] for row in rows)
    assert all(not row["clinician_notes"] for row in rows)

    expected_priority_pmids = {
        "vitamin_d::calcidiol (25-hydroxy D3)": "28187226|29713796",
        "vitamin_b9_folate::metafolin": "33255787",
        "fish_oil::triglyceride (rTG) form": "20638827",
        "quercetin::isoquercetin (EMIQ)": "20638359",
    }
    by_key = {f"{row['ingredient']}::{row['form']}": row for row in rows}
    for key, pmids in expected_priority_pmids.items():
        assert by_key[key]["review_bucket"] == "priority_evidence_recheck"
        assert by_key[key]["proposed_axis"] == "systemic_bioavailability"
        assert by_key[key]["candidate_pmids"] == pmids

    for row in rows:
        category = iqm[row["ingredient"]]["category"]
        if category == "probiotics":
            assert row["proposed_axis"] == "organism_survivability"
            assert row["review_bucket"] == "local_delivery_recheck"

    local_ingredients = {
        "alpha_amylase",
        "digestive_enzymes",
        "immunoglobulin",
        "inulin",
        "manuka_honey",
        "prebiotics",
        "psyllium",
        "slippery_elm",
    }
    for row in rows:
        if row["ingredient"] in local_ingredients:
            assert row["proposed_axis"] == "delivery_to_site"
            assert row["review_bucket"] == "local_delivery_recheck"
