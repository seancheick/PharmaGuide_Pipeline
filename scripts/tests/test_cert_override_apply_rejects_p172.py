"""P1.7.2 — apply cluster-report `reject` suggestions to overrides.

The cluster report (P1.7.1) auto-flagged 18 clusters / ~144 products
as `suggested_action: reject` based on conservative heuristics:

  - `dose_mismatch` — explicit dose/form tokens differ between
    product_name and matched_product (e.g. Vit E 200 IU vs 1000 IU)
  - `brand_mismatch` — product brand and matched_brand share no core
    token (e.g. Nordic Naturals vs Naturalis Inc)

Reject overrides write `status: rejected` to
`scripts/data/curated_overrides/cert_verification_overrides.json`.
The cert_resolver consumes them at load time and returns
`scope="claimed_only"` for the matching products, locking in the
"not verified" answer.

SCORING IMPACT: zero. Both `needs_review` and `claimed_only` already
score 0 in B4a; this slice is audit hygiene that demotes ambiguous
matches to definitive non-matches. The follow-up P1.7.3 slice will
handle the higher-risk `verified` overrides for legitimate
product-line variants.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# --- Generator contract -------------------------------------------------


def test_generate_override_entries_from_reject_cluster():
    """A cluster with suggested_action=reject produces one override entry
    per member, with status=rejected and forensic metadata preserved."""
    from api_audit.cert_override_apply_rejects import generate_overrides_for_cluster

    cluster = {
        "program": "USP Verified",
        "record_id": "USP_VITE_1000",
        "matched_brand": "Nature Made",
        "matched_product": "Nature Made Vitamin E 1000 IU (450 Mg) Dl-Alpha",
        "suggested_action": "reject",
        "members": [
            {
                "dsld_id": "99001",
                "brand_name": "Nature Made",
                "product_name": "Vitamin E 200 IU",
                "matched_brand": "Nature Made",
                "matched_product": "Nature Made Vitamin E 1000 IU (450 Mg) Dl-Alpha",
                "triage_hint": {"likely_action": "reject", "reasons": ["dose_mismatch"]},
            },
            {
                "dsld_id": "99002",
                "brand_name": "Nature Made",
                "product_name": "Vitamin E 400 IU",
                "matched_brand": "Nature Made",
                "matched_product": "Nature Made Vitamin E 1000 IU (450 Mg) Dl-Alpha",
                "triage_hint": {"likely_action": "reject", "reasons": ["dose_mismatch"]},
            },
        ],
    }
    overrides = generate_overrides_for_cluster(cluster, review_source="p172_test")

    assert len(overrides) == 2
    for entry, expected_dsld in zip(overrides, ["99001", "99002"]):
        assert entry["status"] == "rejected"
        assert entry["program"] == "USP Verified"
        assert entry["dsld_id"] == expected_dsld
        assert entry["record_id"] == "USP_VITE_1000"
        assert entry["matched_product"] == "Nature Made Vitamin E 1000 IU (450 Mg) Dl-Alpha"
        assert "dose_mismatch" in entry["reason"]
        assert entry["review_source"] == "p172_test"
        assert "reviewed_at" in entry


def test_generate_overrides_only_for_reject_clusters():
    """Non-reject clusters return empty — generator is conservative."""
    from api_audit.cert_override_apply_rejects import generate_overrides_for_cluster

    cluster = {
        "suggested_action": "review",  # not reject
        "members": [{"dsld_id": "X", "brand_name": "Y", "product_name": "Z"}],
    }
    assert generate_overrides_for_cluster(cluster, review_source="t") == []


def test_generate_overrides_uses_specific_reason_codes():
    """The override `reason` field surfaces the triage-hint reason codes
    for forensics — same vocabulary as the cluster report."""
    from api_audit.cert_override_apply_rejects import generate_overrides_for_cluster

    cluster = {
        "program": "IFOS", "record_id": "IFOS_X",
        "suggested_action": "reject",
        "members": [{
            "dsld_id": "N1", "brand_name": "Nordic Naturals",
            "product_name": "Ultimate Omega",
            "matched_brand": "Naturalis Inc", "matched_product": "Other Product",
            "triage_hint": {"likely_action": "reject",
                            "reasons": ["brand_mismatch"]},
        }],
    }
    overrides = generate_overrides_for_cluster(cluster, review_source="t")
    assert "brand_mismatch" in overrides[0]["reason"]


# --- File-level merge contract ------------------------------------------


def test_merge_new_overrides_appends_without_duplicating(tmp_path: Path):
    """The merge function appends new entries to the existing overrides
    file. Existing entries are preserved verbatim. Duplicates (by
    program+record_id+dsld_id) are suppressed."""
    from api_audit.cert_override_apply_rejects import merge_into_overrides_file

    existing_path = tmp_path / "overrides.json"
    existing = {
        "_metadata": {"schema_version": "6.0.0", "total_overrides": 1, "last_updated": "2025-01-01"},
        "overrides": [
            {"brand": "X", "product": "Y", "program": "USP Verified",
             "status": "verified", "scope": "sku", "dsld_id": "OLD-1",
             "record_id": "USP_X"},
        ],
    }
    existing_path.write_text(json.dumps(existing, indent=2))

    new_entries = [
        {"brand": "Z", "product": "Q", "program": "USP Verified",
         "status": "rejected", "dsld_id": "NEW-1", "record_id": "USP_Z",
         "reason": "dose_mismatch"},
    ]
    added = merge_into_overrides_file(existing_path, new_entries)

    payload = json.loads(existing_path.read_text())
    assert payload["_metadata"]["total_overrides"] == 2
    assert added == 1
    assert any(o["dsld_id"] == "OLD-1" for o in payload["overrides"])
    assert any(o["dsld_id"] == "NEW-1" for o in payload["overrides"])


def test_merge_idempotent_on_rerun(tmp_path: Path):
    """Running the merge twice with the same input doesn't duplicate."""
    from api_audit.cert_override_apply_rejects import merge_into_overrides_file

    existing_path = tmp_path / "overrides.json"
    existing_path.write_text(json.dumps({
        "_metadata": {"schema_version": "6.0.0", "total_overrides": 0, "last_updated": "x"},
        "overrides": [],
    }, indent=2))

    new = [{
        "brand": "X", "product": "Y", "program": "P",
        "status": "rejected", "dsld_id": "1", "record_id": "R1",
        "reason": "t",
    }]
    added1 = merge_into_overrides_file(existing_path, new)
    added2 = merge_into_overrides_file(existing_path, new)
    assert added1 == 1
    assert added2 == 0  # second run is a no-op
    payload = json.loads(existing_path.read_text())
    assert len(payload["overrides"]) == 1


def test_merge_preserves_existing_metadata_purpose_and_status_meanings(tmp_path: Path):
    """The _metadata block's documentation fields (purpose, status_meanings)
    must NOT be clobbered. Only counts / last_updated change."""
    from api_audit.cert_override_apply_rejects import merge_into_overrides_file

    existing_path = tmp_path / "overrides.json"
    existing = {
        "_metadata": {
            "schema_version": "6.0.0",
            "description": "Manual overrides for cert verification scope.",
            "purpose": "cert_verification_manual_override",
            "last_updated": "2025-01-01",
            "total_overrides": 0,
            "status_meanings": {
                "verified": "Manually confirmed by reviewer.",
                "pending_review": "Auto-flagged.",
                "rejected": "Reviewer confirmed NOT valid.",
            },
        },
        "overrides": [],
    }
    existing_path.write_text(json.dumps(existing, indent=2))

    new = [{"brand": "X", "product": "Y", "program": "P", "status": "rejected",
            "dsld_id": "1", "record_id": "R1", "reason": "t"}]
    merge_into_overrides_file(existing_path, new)

    payload = json.loads(existing_path.read_text())
    meta = payload["_metadata"]
    assert meta["description"] == "Manual overrides for cert verification scope."
    assert meta["purpose"] == "cert_verification_manual_override"
    assert "status_meanings" in meta
    assert meta["status_meanings"]["rejected"] == "Reviewer confirmed NOT valid."


# --- End-to-end resolver behavior ---------------------------------------


def test_resolver_applies_reject_override(tmp_path: Path):
    """After a reject override is applied, the cert_resolver returns
    scope=claimed_only for that brand+product+program combination —
    locking the false-positive answer."""
    from cert_resolver import (
        CertRegistry, normalize_brand, normalize_product, _check_override,
    )

    # Build a minimal registry with one override entry
    registry = CertRegistry()
    override = {
        "brand": "Nature Made", "product": "Vitamin E 200 IU",
        "program": "USP Verified", "status": "rejected",
        "record_id": "USP_VITE_1000",
        "reason": "dose_mismatch: 200 IU vs 1000 IU",
        "dsld_id": "99001",
    }
    key = (normalize_brand("Nature Made"), normalize_product("Vitamin E 200 IU"))
    registry.overrides_by_brand_product.setdefault(key, []).append(override)

    resolution = _check_override(
        normalize_brand("Nature Made"),
        normalize_product("Vitamin E 200 IU"),
        "USP Verified",
        registry,
    )
    assert resolution is not None
    assert resolution.scope == "claimed_only"
    assert "rejected" in (resolution.notes or "").lower()


# --- CLI ----------------------------------------------------------------


def test_cli_dry_run_reports_counts_without_writing(tmp_path: Path):
    """`--dry-run` reports the would-add count but doesn't modify the file."""
    from api_audit.cert_override_apply_rejects import main

    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({
        "_metadata": {"schema_version": "6.0.0", "total_overrides": 0, "last_updated": "x"},
        "overrides": [],
    }, indent=2))

    cluster_report = tmp_path / "clusters.json"
    cluster_report.write_text(json.dumps({
        "summary": {},
        "clusters": [{
            "program": "USP Verified", "record_id": "USP_X",
            "matched_brand": "Nature Made",
            "matched_product": "Nature Made Vitamin E 1000 IU",
            "suggested_action": "reject",
            "member_count": 1,
            "members": [{
                "dsld_id": "99001", "brand_name": "Nature Made",
                "product_name": "Vitamin E 200 IU",
                "matched_brand": "Nature Made",
                "matched_product": "Nature Made Vitamin E 1000 IU",
                "triage_hint": {"likely_action": "reject",
                                "reasons": ["dose_mismatch"]},
            }],
        }],
    }, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
        "--dry-run",
    ])
    assert exit_code == 0
    # Dry-run did not modify the file
    payload = json.loads(overrides_path.read_text())
    assert payload["_metadata"]["total_overrides"] == 0
    assert payload["overrides"] == []


def test_cli_apply_writes_overrides(tmp_path: Path):
    """Without `--dry-run`, the CLI writes new override entries."""
    from api_audit.cert_override_apply_rejects import main

    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({
        "_metadata": {"schema_version": "6.0.0", "total_overrides": 0, "last_updated": "x"},
        "overrides": [],
    }, indent=2))

    cluster_report = tmp_path / "clusters.json"
    cluster_report.write_text(json.dumps({
        "summary": {},
        "clusters": [{
            "program": "USP Verified", "record_id": "USP_X",
            "matched_brand": "Nature Made",
            "matched_product": "Nature Made Vitamin E 1000 IU",
            "suggested_action": "reject",
            "member_count": 1,
            "members": [{
                "dsld_id": "99001", "brand_name": "Nature Made",
                "product_name": "Vitamin E 200 IU",
                "matched_brand": "Nature Made",
                "matched_product": "Nature Made Vitamin E 1000 IU",
                "triage_hint": {"likely_action": "reject",
                                "reasons": ["dose_mismatch"]},
            }],
        }],
    }, indent=2))

    exit_code = main([
        "--cluster-report", str(cluster_report),
        "--overrides-path", str(overrides_path),
    ])
    assert exit_code == 0
    payload = json.loads(overrides_path.read_text())
    assert payload["_metadata"]["total_overrides"] == 1
    assert len(payload["overrides"]) == 1
    assert payload["overrides"][0]["status"] == "rejected"
    assert payload["overrides"][0]["dsld_id"] == "99001"
