"""P1.7.3 — manually reviewed cert cluster overrides.

This is the score-moving half of P1.7, so the contract is deliberately
stricter than P1.7.2 auto-rejects:

  * no classifier-driven verification;
  * reviewer must name one cluster by program + record_id;
  * reviewer must provide an explicit action and note;
  * mixed clusters can be limited to reviewed DSLD IDs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _cluster_report(tmp_path: Path) -> Path:
    report = {
        "summary": {},
        "clusters": [
            {
                "program": "Informed Choice",
                "record_id": "INFORMED_CHO_65E7FB3D998C",
                "matched_brand": "GNC",
                "matched_product": "AMP Wheybolic",
                "suggested_action": "review",
                "member_count": 2,
                "members": [
                    {
                        "dsld_id": "175942",
                        "brand_name": "GNC Pro Performance AMP",
                        "product_name": "Amplified Wheybolic Extreme 60 Original Chocolate",
                        "matched_brand": "GNC",
                        "matched_product": "AMP Wheybolic",
                        "triage_hint": {"likely_action": "review", "reasons": ["no_strong_signal"]},
                    },
                    {
                        "dsld_id": "175943",
                        "brand_name": "GNC Pro Performance AMP",
                        "product_name": "Amplified Wheybolic Extreme 60 Vanilla",
                        "matched_brand": "GNC",
                        "matched_product": "AMP Wheybolic",
                        "triage_hint": {"likely_action": "review", "reasons": ["no_strong_signal"]},
                    },
                ],
            },
            {
                "program": "USP Verified",
                "record_id": "USP_MIXED",
                "matched_brand": "Nature Made",
                "matched_product": "Nature Made Vitamin D3 2000 IU Softgels",
                "suggested_action": "review",
                "member_count": 2,
                "members": [
                    {
                        "dsld_id": "2000",
                        "brand_name": "Nature Made",
                        "product_name": "Vitamin D3 2000 IU",
                        "matched_brand": "Nature Made",
                        "matched_product": "Nature Made Vitamin D3 2000 IU Softgels",
                        "triage_hint": {"likely_action": "review", "reasons": ["no_strong_signal"]},
                    },
                    {
                        "dsld_id": "5000",
                        "brand_name": "Nature Made",
                        "product_name": "CoQ10 100 mg",
                        "matched_brand": "Nature Made",
                        "matched_product": "Nature Made Vitamin D3 2000 IU Softgels",
                        "triage_hint": {"likely_action": "reject", "reasons": ["dose_mismatch"]},
                    },
                ],
            },
        ],
    }
    path = tmp_path / "clusters.json"
    path.write_text(json.dumps(report, indent=2))
    return path


def test_find_cluster_by_program_and_record_id(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(
        report.get("clusters", []),
        program="Informed Choice",
        record_id="INFORMED_CHO_65E7FB3D998C",
    )

    assert cluster["matched_product"] == "AMP Wheybolic"
    assert len(cluster["members"]) == 2


def test_find_cluster_errors_on_missing_cluster(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    try:
        find_cluster(report.get("clusters", []), program="IFOS", record_id="NOPE")
    except ValueError as exc:
        assert "cluster not found" in str(exc)
    else:
        raise AssertionError("missing cluster should raise")


def test_generate_verified_product_line_overrides_requires_review_note(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="Informed Choice", record_id="INFORMED_CHO_65E7FB3D998C")

    try:
        generate_reviewed_overrides(
            cluster,
            action="verify_product_line",
            review_note="",
            reviewer="Sean",
            review_source="p173_test",
        )
    except ValueError as exc:
        assert "review note" in str(exc)
    else:
        raise AssertionError("empty review note should raise")


def test_generate_verified_product_line_overrides_for_entire_cluster(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="Informed Choice", record_id="INFORMED_CHO_65E7FB3D998C")
    overrides = generate_reviewed_overrides(
        cluster,
        action="verify_product_line",
        review_note="Reviewer confirmed these are AMP Wheybolic flavor variants on the certified line.",
        reviewer="Sean",
        review_source="p173_test",
    )

    assert len(overrides) == 2
    for entry in overrides:
        assert entry["status"] == "verified"
        assert entry["scope"] == "product_line"
        assert entry["program"] == "Informed Choice"
        assert entry["record_id"] == "INFORMED_CHO_65E7FB3D998C"
        assert entry["matched_product"] == "AMP Wheybolic"
        assert entry["reviewer"] == "Sean"
        assert "Reviewer confirmed" in entry["reason"]
        assert "reviewed_at" in entry


def test_generate_reviewed_overrides_can_limit_to_member_dsld_ids(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="USP Verified", record_id="USP_MIXED")
    overrides = generate_reviewed_overrides(
        cluster,
        action="verify_product_line",
        review_note="Only the D3 product matches this USP row; CoQ10 remains unreviewed.",
        reviewer="Sean",
        review_source="p173_test",
        member_dsld_ids={"2000"},
    )

    assert [entry["dsld_id"] for entry in overrides] == ["2000"]
    assert overrides[0]["product"] == "Vitamin D3 2000 IU"


def test_generate_reviewed_overrides_can_target_alternate_registry_record(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="USP Verified", record_id="USP_MIXED")
    overrides = generate_reviewed_overrides(
        cluster,
        action="verify_product_line",
        review_note="Reviewer matched this member to the alternate 1000 IU registry row.",
        reviewer="Sean",
        review_source="p173_test",
        member_dsld_ids={"2000"},
        override_record_id="USP_ALTERNATE_1000",
        override_matched_brand="Nature Made",
        override_matched_product="Nature Made Vitamin D3 1000 IU Softgels",
    )

    assert [entry["dsld_id"] for entry in overrides] == ["2000"]
    assert overrides[0]["record_id"] == "USP_ALTERNATE_1000"
    assert overrides[0]["matched_brand"] == "Nature Made"
    assert overrides[0]["matched_product"] == "Nature Made Vitamin D3 1000 IU Softgels"
    assert "alternate_record_id=USP_ALTERNATE_1000" in overrides[0]["triage_reasons"]


def test_member_limited_override_keeps_dsld_id_for_shared_brand_product_key(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="USP Verified", record_id="USP_MIXED")
    cluster["members"].append({
        "dsld_id": "2001",
        "brand_name": "Nature Made",
        "product_name": "Vitamin D3 2000 IU",
        "matched_brand": "Nature Made",
        "matched_product": "Nature Made Vitamin D3 2000 IU Softgels",
        "triage_hint": {"likely_action": "review", "reasons": ["form_mismatch"]},
    })

    overrides = generate_reviewed_overrides(
        cluster,
        action="verify_product_line",
        review_note="Only one member has the softgel physical form.",
        reviewer="Sean",
        review_source="p173_test",
        member_dsld_ids={"2000"},
    )

    assert [entry["dsld_id"] for entry in overrides] == ["2000"]
    assert overrides[0]["product"] == "Vitamin D3 2000 IU"


def test_generate_reject_overrides_for_reviewed_members(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import generate_reviewed_overrides, find_cluster

    report = json.loads(_cluster_report(tmp_path).read_text())
    cluster = find_cluster(report["clusters"], program="USP Verified", record_id="USP_MIXED")
    overrides = generate_reviewed_overrides(
        cluster,
        action="reject",
        review_note="Ingredient family does not match the D3 registry row.",
        reviewer="Sean",
        review_source="p173_test",
        member_dsld_ids={"5000"},
    )

    assert [entry["dsld_id"] for entry in overrides] == ["5000"]
    assert overrides[0]["status"] == "rejected"
    assert overrides[0]["scope"] == "claimed_only"


def test_cli_dry_run_does_not_modify_overrides(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import main

    cluster_report = _cluster_report(tmp_path)
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({"_metadata": {"total_overrides": 0}, "overrides": []}, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
        "--program", "Informed Choice",
        "--record-id", "INFORMED_CHO_65E7FB3D998C",
        "--action", "verify_product_line",
        "--reviewer", "Sean",
        "--review-note", "Reviewed the cluster table and confirmed line variants.",
        "--dry-run",
    ])

    assert exit_code == 0
    assert json.loads(overrides_path.read_text())["overrides"] == []


def test_cli_apply_writes_reviewed_overrides(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import main

    cluster_report = _cluster_report(tmp_path)
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({"_metadata": {"total_overrides": 0}, "overrides": []}, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
        "--program", "Informed Choice",
        "--record-id", "INFORMED_CHO_65E7FB3D998C",
        "--action", "verify_product_line",
        "--reviewer", "Sean",
        "--review-note", "Reviewed the cluster table and confirmed line variants.",
    ])

    payload = json.loads(overrides_path.read_text())
    assert exit_code == 0
    assert payload["_metadata"]["total_overrides"] == 2
    assert {entry["scope"] for entry in payload["overrides"]} == {"product_line"}


def test_cli_apply_promotes_existing_pending_review_override(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import main

    cluster_report = _cluster_report(tmp_path)
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({
        "_metadata": {"total_overrides": 1, "last_updated": "2026-01-01"},
        "overrides": [{
            "brand": "GNC Pro Performance AMP",
            "product": "Amplified Wheybolic Extreme 60 Original Chocolate",
            "program": "Informed Choice",
            "status": "pending_review",
            "scope": "product_line",
            "dsld_id": "175942",
            "record_id": "INFORMED_CHO_65E7FB3D998C",
            "reason": "old pending row",
        }],
    }, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
        "--program", "Informed Choice",
        "--record-id", "INFORMED_CHO_65E7FB3D998C",
        "--action", "verify_product_line",
        "--reviewer", "Sean",
        "--review-note", "Reviewed the cluster table and confirmed line variants.",
        "--member-dsld-id", "175942",
    ])

    payload = json.loads(overrides_path.read_text())
    assert exit_code == 0
    assert payload["_metadata"]["total_overrides"] == 1
    assert len(payload["overrides"]) == 1
    assert payload["overrides"][0]["status"] == "verified"
    assert payload["overrides"][0]["reason"].startswith("P1.7.3 manual verify_product_line")


def test_merge_can_replace_conflicting_same_program_dsld_record(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import merge_reviewed_into_overrides_file

    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({
        "_metadata": {"total_overrides": 2, "last_updated": "2026-01-01"},
        "overrides": [
            {
                "brand": "Nature Made",
                "product": "Vitamin C 1000 mg",
                "program": "USP Verified",
                "status": "rejected",
                "scope": "claimed_only",
                "dsld_id": "179445",
                "record_id": "USP_WRONG_500",
                "reason": "old wrong-row reject",
            },
            {
                "brand": "Nature Made",
                "product": "Vitamin C 1000 mg",
                "program": "Informed Choice",
                "status": "rejected",
                "scope": "claimed_only",
                "dsld_id": "179445",
                "record_id": "INFORMED_UNRELATED",
                "reason": "different program should stay",
            },
        ],
    }, indent=2))

    added, replaced, removed_conflicts = merge_reviewed_into_overrides_file(
        overrides_path,
        [{
            "brand": "Nature Made",
            "product": "Vitamin C 1000 mg",
            "program": "USP Verified",
            "status": "verified",
            "scope": "product_line",
            "dsld_id": "179445",
            "record_id": "USP_CORRECT_1000",
            "reason": "manual alternate-row verification",
        }],
        replace_program_dsld_conflicts=True,
    )

    payload = json.loads(overrides_path.read_text())
    assert (added, replaced, removed_conflicts) == (1, 0, 1)
    assert payload["_metadata"]["total_overrides"] == 2
    assert {entry["record_id"] for entry in payload["overrides"]} == {
        "USP_CORRECT_1000",
        "INFORMED_UNRELATED",
    }


def test_cli_alternate_record_requires_conflict_replacement_opt_in(tmp_path: Path):
    from api_audit.cert_override_apply_reviewed import main

    cluster_report = _cluster_report(tmp_path)
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({
        "_metadata": {"total_overrides": 1, "last_updated": "2026-01-01"},
        "overrides": [{
            "brand": "Nature Made",
            "product": "Vitamin D3 2000 IU",
            "program": "USP Verified",
            "status": "rejected",
            "scope": "claimed_only",
            "dsld_id": "2000",
            "record_id": "USP_MIXED",
            "reason": "old wrong-row reject",
        }],
    }, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
        "--program", "USP Verified",
        "--record-id", "USP_MIXED",
        "--action", "verify_product_line",
        "--reviewer", "Sean",
        "--review-note", "Reviewed member against alternate USP row.",
        "--member-dsld-id", "2000",
        "--override-record-id", "USP_ALTERNATE_1000",
        "--override-matched-product", "Nature Made Vitamin D3 1000 IU Softgels",
        "--replace-program-dsld-conflicts",
    ])

    payload = json.loads(overrides_path.read_text())
    assert exit_code == 0
    assert payload["_metadata"]["total_overrides"] == 1
    assert payload["overrides"][0]["record_id"] == "USP_ALTERNATE_1000"
    assert payload["overrides"][0]["status"] == "verified"
