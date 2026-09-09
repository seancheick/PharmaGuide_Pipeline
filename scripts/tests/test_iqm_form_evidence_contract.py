"""Contract tests for structured IQM form evidence and atomic migrations."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from iqm_form_evidence import (
    AXIS_REQUIRED_CLAIMS,
    SUPPORTED_AXES,
    ManifestError,
    excellent_axis_coverage,
    resolve_form_axis,
    apply_manifest_file,
    backlog_initial_digest,
    build_initial_backlog,
    catalog_evidence_gaps,
    catalog_form_usage,
    collect_pubmed_pmids,
    form_digest,
    load_backlog_file,
    validate_exported_form_evidence,
    validate_iqm_form,
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
    """Wrap one form as an IQM.

    A form that owns evidence also owns its assessment axis (hoisted out of
    `form_evidence` on 2026-09-09), so the default is supplied here rather than
    repeated in every case that is really testing something else.
    """
    form = dict(form)
    if "form_evidence" in form and "form_evidence_axis" not in form:
        form["form_evidence_axis"] = "systemic_bioavailability"
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

    citrate = iqm["magnesium"]["forms"]["magnesium citrate"]
    citrate["form_evidence"] = _approved_evidence()
    citrate["form_evidence_axis"] = "systemic_bioavailability"
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
                        "set": {
                            "form_evidence": _approved_evidence(),
                            "form_evidence_axis": "systemic_bioavailability",
                        },
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


# ---------------------------------------------------------------------------
# Canonical form-level assessment axis
#
# The axis used to live only inside `form_evidence`, which does not exist until
# evidence is finished. A form awaiting review therefore had no declared axis,
# so a reviewer could not tell which evidence standard applied to it. The size
# of that group is not yet established: an early keyword estimate was retracted
# as unreliable, and the real number comes from the reviewed classification
# manifest rather than from prose matching.
#
# `form_evidence_axis` is now the single authored home for that value.
# `form_evidence.axis` is derived from it during migration and must never
# disagree: one value, one place, nothing to drift.
# ---------------------------------------------------------------------------


def test_microbial_substrate_utilization_is_a_supported_axis():
    """Prebiotics need their own standard.

    ISAPP requires selective microbial utilisation plus a demonstrated host
    benefit. "Reaches the colon" is not sufficient, so this cannot be folded
    into delivery_to_site without flattening two different questions.
    """
    assert "microbial_substrate_utilization" in SUPPORTED_AXES


def test_form_level_axis_is_the_authored_value():
    form = {"bio_score": 14, "score": 14, "natural": False}
    form["form_evidence_axis"] = "systemic_bioavailability"
    assert resolve_form_axis(form) == "systemic_bioavailability"


def test_form_level_axis_rejects_a_value_outside_the_vocabulary():
    iqm = _iqm(
        {
            "bio_score": 11,
            "score": 11,
            "natural": False,
            "form_evidence_axis": "vibes_based_absorption",
        }
    )
    assert validate_iqm_form_evidence(iqm, backlog=set()) == [
        "magnesium::magnesium citrate: unsupported form_evidence_axis"
    ]


def test_a_nested_axis_is_rejected_rather_than_reconciled():
    """Two fields that must 'match' can drift, so there is only one field.

    Before the hoist this was a disagreement check. Now the nested copy is not
    a second opinion to reconcile — it is simply not allowed to exist.
    """
    evidence = _approved_evidence()
    evidence["axis"] = "delivery_to_site"
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence_axis": "systemic_bioavailability",
            "form_evidence": evidence,
        }
    )
    assert validate_iqm_form_evidence(iqm, backlog=set()) == [
        "magnesium::magnesium citrate: axis belongs on the form"
        " (form_evidence_axis), not inside form_evidence"
    ]


def test_assigning_an_axis_alone_never_clears_a_backlog_form():
    """Classification is not evidence.

    A backlogged Excellent form that gains only an axis must stay backlogged,
    keep its score, and raise no error. Clearing still requires approved
    evidence at strong or moderate.
    """
    form = {
        "bio_score": 14,
        "score": 14,
        "natural": False,
        "form_evidence_axis": "organism_survivability",
    }
    iqm = _iqm(form)
    key = "magnesium::magnesium citrate"

    assert validate_iqm_form_evidence(iqm, backlog={key}) == []
    assert form["bio_score"] == 14
    coverage = excellent_axis_coverage(iqm)
    assert (coverage.canonical, coverage.legacy, coverage.total, coverage.missing) == (
        1,
        0,
        1,
        [],
    )


def test_axis_coverage_counts_only_excellent_forms():
    """Lower-rated forms are not forced into a classification they have not
    been reviewed for. Coverage is a promotion gate, not a census."""
    iqm = {
        "_metadata": {"schema_version": "5.4.15"},
        "magnesium": {
            "standard_name": "Magnesium",
            "forms": {
                "magnesium citrate": {
                    "bio_score": 14,
                    "score": 14,
                    "natural": False,
                    "form_evidence_axis": "systemic_bioavailability",
                },
                "magnesium oxide": {"bio_score": 3, "score": 3, "natural": False},
            },
        },
    }
    coverage = excellent_axis_coverage(iqm)
    assert (coverage.canonical, coverage.legacy, coverage.total) == (1, 0, 1)
    assert coverage.missing == []


def test_axis_coverage_reports_gaps_without_failing_validation():
    """Enforcement stays off until coverage is complete.

    Failing every missing axis today would block the pipeline on 195 forms
    nobody has reviewed yet.
    """
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})
    key = "magnesium::magnesium citrate"

    coverage = excellent_axis_coverage(iqm)
    assert (coverage.canonical, coverage.legacy, coverage.total) == (0, 0, 1)
    assert coverage.missing == [key]
    assert validate_iqm_form_evidence(iqm, backlog={key}) == []


def test_complete_axis_coverage_can_be_enforced_once_reached():
    """The switch exists and is off by default; turning it on is the final
    step after all Excellent forms carry a reviewed axis."""
    iqm = _iqm({"bio_score": 14, "score": 14, "natural": False})
    key = "magnesium::magnesium citrate"

    assert validate_iqm_form_evidence(
        iqm, backlog={key}, require_axis_coverage=True
    ) == [f"{key}: Excellent form lacks a reviewed form_evidence_axis"]


def test_canonical_axis_alone_satisfies_evidence_validation():
    """The whole point of hoisting the field.

    A record carrying no nested `axis` must validate when the form declares
    one. Before this, `form_evidence_axis` was decorative: the nested copy was
    still the required input, so a canonical-only record failed with
    "unsupported evidence axis".
    """
    evidence = _approved_evidence()
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence_axis": "systemic_bioavailability",
            "form_evidence": evidence,
        }
    )
    assert validate_iqm_form_evidence(iqm, backlog=set()) == []


def test_prebiotic_axis_rejects_evidence_that_only_shows_bioavailability():
    """An axis name that constrains nothing is decoration.

    Pharmacokinetic evidence filed under the prebiotic axis must not clear a
    backlog entry: ISAPP requires selective utilisation AND a host benefit.
    """
    evidence = _approved_evidence()
    evidence["references_structured"][0]["supports_claims"] = ["oral_bioavailability"]
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence_axis": "microbial_substrate_utilization",
            "form_evidence": evidence,
        }
    )
    assert validate_iqm_form_evidence(iqm, backlog=set()) == [
        "magnesium::magnesium citrate: microbial_substrate_utilization evidence "
        "must support host_benefit, selective_microbial_utilization"
    ]


def test_prebiotic_axis_accepts_selective_utilisation_with_host_benefit():
    evidence = _approved_evidence()
    evidence["references_structured"][0]["supports_claims"] = [
        "selective_microbial_utilization",
        "host_benefit",
    ]
    iqm = _iqm(
        {
            "bio_score": 14,
            "score": 14,
            "natural": False,
            "form_evidence_axis": "microbial_substrate_utilization",
            "form_evidence": evidence,
        }
    )
    assert validate_iqm_form_evidence(iqm, backlog=set()) == []


def test_required_claims_are_declared_only_for_axes_that_need_them():
    """The map is narrow by design. Existing axes keep the generic rules they
    shipped with; only the new axis gained a semantic gate."""
    assert set(AXIS_REQUIRED_CLAIMS) == {"microbial_substrate_utilization"}


def test_axis_coverage_separates_canonical_from_legacy():
    """0/250 canonical must never read as 55/250 done.

    After the hoist, `legacy` counts nested axes that should no longer exist,
    and such a form is still `missing` a usable canonical axis.
    """
    legacy_evidence = _approved_evidence()
    legacy_evidence["axis"] = "systemic_bioavailability"
    iqm = {
        "_metadata": {"schema_version": "5.4.15"},
        "magnesium": {
            "standard_name": "Magnesium",
            "forms": {
                "magnesium citrate": {
                    "bio_score": 14,
                    "score": 14,
                    "natural": False,
                    "form_evidence_axis": "systemic_bioavailability",
                },
                "magnesium malate": {
                    "bio_score": 13,
                    "score": 13,
                    "natural": False,
                    "form_evidence": legacy_evidence,
                },
                "magnesium taurate": {"bio_score": 12, "score": 12, "natural": False},
            },
        },
    }
    coverage = excellent_axis_coverage(iqm)
    assert coverage.canonical == 1
    assert coverage.legacy == 1
    assert coverage.total == 3
    assert coverage.missing == [
        "magnesium::magnesium malate",
        "magnesium::magnesium taurate",
    ]


# --- the axis seam: one validator, one owning form -------------------------
#
# `form_evidence_axis` lives on the form, but the evidence record is what gets
# validated. Every caller that hands over a bare evidence block loses the axis
# and gets "unsupported evidence axis" for a perfectly valid hoisted record.
# These tests hold the seam shut at each production consumer.


def _hoisted_form(bio_score: int = 14) -> dict:
    """An already-migrated form: axis on the form, absent from the evidence."""
    evidence = _approved_evidence()
    axis = "systemic_bioavailability"
    return {
        "bio_score": bio_score,
        "score": bio_score,
        "natural": False,
        "form_evidence_axis": axis,
        "form_evidence": evidence,
    }


def test_manifest_hoists_the_axis_and_drops_the_nested_copy_atomically(
    tmp_path: Path,
):
    """The migration must be expressible as one change per form.

    Setting the canonical field and rewriting the evidence without its nested
    `axis` in a single change means no form is ever observable in a state where
    both copies are missing.
    """
    iqm_path = tmp_path / "ingredient_quality_map.json"
    manifest_path = tmp_path / "manifest.json"
    # Genuine pre-migration shape: the axis exists only inside the evidence.
    legacy_evidence = _approved_evidence()
    legacy_evidence["axis"] = "systemic_bioavailability"
    original = {
        "_metadata": {"schema_version": "5.4.15"},
        "magnesium": {
            "standard_name": "Magnesium",
            "forms": {
                "magnesium citrate": {
                    "bio_score": 14,
                    "score": 14,
                    "natural": False,
                    "form_evidence": legacy_evidence,
                }
            },
        },
    }
    form = original["magnesium"]["forms"]["magnesium citrate"]
    iqm_path.write_text(json.dumps(original, indent=2) + "\n")
    hoisted_evidence = _approved_evidence()
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "changes": [
                    {
                        "ingredient_key": "magnesium",
                        "form_key": "magnesium citrate",
                        "expected_form_sha256": form_digest(form),
                        "set": {
                            "form_evidence_axis": "systemic_bioavailability",
                            "form_evidence": hoisted_evidence,
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    summary = apply_manifest_file(iqm_path, manifest_path)

    assert summary == {"expected": 1, "applied": 1, "unchanged": 0}
    migrated = json.loads(iqm_path.read_text())["magnesium"]["forms"][
        "magnesium citrate"
    ]
    assert migrated["form_evidence_axis"] == "systemic_bioavailability"
    assert "axis" not in migrated["form_evidence"]
    assert validate_iqm_form_evidence(
        json.loads(iqm_path.read_text()), backlog=set()
    ) == []


def test_hoisted_evidence_is_not_pushed_back_into_the_backlog():
    """The backlog lists forms whose evidence is missing or invalid.

    A migrated form has complete evidence. Rebuilding the backlog without the
    form-level axis would re-open 55 settled reviews.
    """
    iqm = _iqm(_hoisted_form())

    backlog = build_initial_backlog(iqm, created_on="2026-09-09")

    assert backlog["remaining_forms"] == []


def test_hoisted_evidence_does_not_appear_as_a_catalog_evidence_gap():
    iqm = _iqm(_hoisted_form())

    gaps = catalog_evidence_gaps(iqm, {"magnesium::magnesium citrate": {}})

    assert gaps == []


def test_no_production_caller_validates_evidence_without_its_owning_form():
    """The structural guarantee behind the three tests above.

    `validate_iqm_form` is the only public validator precisely so that a future
    caller cannot reintroduce this defect by forgetting a keyword argument.
    """
    offenders = sorted(
        str(path.relative_to(SCRIPTS_DIR))
        for path in SCRIPTS_DIR.rglob("*.py")
        if "tests" not in path.parts
        and path.name != "iqm_form_evidence.py"
        and "validate_form_evidence" in path.read_text(encoding="utf-8")
    )

    assert offenders == []


def test_nested_axis_is_rejected_and_no_longer_resolves():
    """Post-hoist, the nested copy is not a fallback but an error.

    Leaving it readable would let a future edit reintroduce a second source of
    truth that silently wins whenever the form-level field is absent.
    """
    evidence = _approved_evidence()
    evidence["axis"] = "systemic_bioavailability"
    form = {
        "bio_score": 14,
        "score": 14,
        "natural": False,
        "form_evidence_axis": "systemic_bioavailability",
        "form_evidence": evidence,
    }

    assert resolve_form_axis({"form_evidence": evidence}) is None
    assert validate_iqm_form(form, label="magnesium::magnesium citrate") == [
        "magnesium::magnesium citrate: axis belongs on the form"
        " (form_evidence_axis), not inside form_evidence"
    ]


def test_shipped_iqm_carries_no_nested_axis_and_full_canonical_coverage():
    """The migration's permanent invariant, asserted against shipped data."""
    iqm = json.loads(IQM_PATH.read_text(encoding="utf-8"))

    coverage = excellent_axis_coverage(iqm)

    assert coverage.legacy == 0
    assert coverage.canonical == 55
    assert coverage.total == 250
    assert len(coverage.missing) == 195
    assert sorted(coverage.missing) == sorted(load_backlog_file(BACKLOG_PATH))
