#!/usr/bin/env python3
"""
Sprint 2 regression tests for backfill_unii_from_cache.py.

Pins the contracts the user approved:
  * Dry-run by default
  * --apply REQUIRES --entry-ids (no implicit "apply everything")
  * NO --apply-all flag exists
  * Regression guard refuses any backfill that would introduce a new
    SAME_UNII_DIFFERENT_NAMES critical finding (not in the allowlist)
  * Per-entry FDA-cache + DSLD-consensus evidence in proposal output
  * Confidence tier assignment matches the documented rules

Uses synthetic in-memory fixtures so we never touch real data files.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
API_AUDIT_DIR = SCRIPTS_DIR / "api_audit"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(API_AUDIT_DIR))


# ============================================================================
# Section 1 — CLI contract: no apply-all, --apply requires --entry-ids
# ============================================================================


def test_no_apply_all_flag_exists():
    """The script MUST NOT REGISTER an --apply-all (or similar bulk) flag
    with argparse. Source-level check guards against accidental future
    addition. We specifically look for `add_argument("--apply-all"` patterns
    rather than the bare string so the docstring's NEGATIVE statement
    ("NO --apply-all flag exists") doesn't false-positive."""
    src = (API_AUDIT_DIR / "backfill_unii_from_cache.py").read_text(encoding="utf-8")
    for forbidden in (
        '"--apply-all"', "'--apply-all'",
        '"--apply_all"', "'--apply_all'",
        '"--applyAll"', "'--applyAll'",
        '"--all"', "'--all'",
    ):
        # Check both bare flag and add_argument context
        bad_patterns = [
            f"add_argument({forbidden}",
            f"add_argument( {forbidden}",
        ]
        for p in bad_patterns:
            assert p not in src, (
                f"Forbidden bulk-apply argparse registration {p!r} found in backfill script"
            )


def test_apply_flag_is_only_apply_argument():
    """Argparse should register exactly one apply-related argument named
    `--apply` (boolean). Belt-and-suspenders alongside the negative test
    above."""
    import re
    src = (API_AUDIT_DIR / "backfill_unii_from_cache.py").read_text(encoding="utf-8")
    add_arg_apply = re.findall(r'add_argument\s*\(\s*"--apply[^"]*"', src)
    assert add_arg_apply == ['add_argument(\n        "--apply"'] or add_arg_apply == ['add_argument("--apply"'], (
        f"Expected exactly one add_argument('--apply', ...). "
        f"Found: {add_arg_apply}. Any other --apply* flag is a bulk-apply "
        "vector and is forbidden per the approved plan."
    )


def test_apply_without_entry_ids_refused():
    """`--apply` with no --entry-ids must return non-zero exit code AND
    write nothing. Avoids accidental bulk apply if a user types --apply alone."""
    import backfill_unii_from_cache as bf

    rc = bf.main(argv=["--apply"])
    assert rc != 0, "Expected non-zero exit when --apply has no --entry-ids"


def test_apply_with_unknown_entry_ids_refused(tmp_path):
    """--apply --entry-ids NOT_A_REAL_ENTRY must refuse cleanly."""
    import backfill_unii_from_cache as bf

    # Use the live repo for reference data (this won't write anything because
    # the unknown ID won't match any candidate).
    rc = bf.main(
        argv=[
            "--apply",
            "--entry-ids",
            "ENTRY_THAT_DOES_NOT_EXIST_xyz",
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )
    assert rc != 0, "Expected non-zero exit when --entry-ids matches no candidates"


# ============================================================================
# Section 2 — _normalize_unii contract still applies inside backfill
# ============================================================================


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("TQI9LJM246", "TQI9LJM246"),
        ("  tqi9ljm246  ", "TQI9LJM246"),
        ("0", None),
        ("1", None),
        ("", None),
        (None, None),
        ("INVALID!XX", None),
        ("TOOSHORT", None),
        ("TOOLONGUNII1", None),
    ],
)
def test_normalize_unii_contract(inp, expected):
    import backfill_unii_from_cache as bf

    assert bf._normalize_unii(inp) == expected


# ============================================================================
# Section 3 — is_backfill_candidate (skip rules)
# ============================================================================


def test_governed_null_entries_skipped():
    """Entries with cui_status='governed_null' are intentional no-UNII
    markers (polymer classes, blend descriptors). MUST NOT be candidates."""
    import backfill_unii_from_cache as bf

    entry = {
        "id": "NHA_FOO",
        "standard_name": "Foo",
        "external_ids": {},
        "cui_status": "governed_null",
    }
    assert bf.is_backfill_candidate(entry) is False


def test_entries_with_unii_skipped():
    """Entries that already have a valid UNII are not candidates."""
    import backfill_unii_from_cache as bf

    entry = {
        "id": "NHA_FOO",
        "standard_name": "Foo",
        "external_ids": {"unii": "ABCDEF1234"},
    }
    assert bf.is_backfill_candidate(entry) is False


def test_entries_with_placeholder_unii_are_candidates():
    """Entries with placeholder UNII values ('0', '1', '') count as missing
    and ARE candidates."""
    import backfill_unii_from_cache as bf

    for placeholder in ("", "0", "1"):
        entry = {
            "id": "NHA_FOO",
            "standard_name": "Foo",
            "external_ids": {"unii": placeholder},
        }
        assert bf.is_backfill_candidate(entry) is True, (
            f"Placeholder UNII {placeholder!r} should count as missing"
        )


def test_entries_without_external_ids_are_candidates():
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo"}
    assert bf.is_backfill_candidate(entry) is True


# ============================================================================
# Section 4 — propose_for_entry happy path + confidence scoring
# ============================================================================


def test_propose_high_confidence_when_fda_exact_and_dsld_consensus():
    """FDA cache exact match on standard_name + ≥5 DSLD products → HIGH."""
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo Acid", "aliases": []}
    fda_name_to_unii = {"foo acid": "FOOAC123XY"}
    dsld_index = {
        ("foo acid", "FOOAC123XY"): {
            "count": 12,
            "brands": {"GNC", "CVS", "Nature Made", "Doctors_Best"},
            "sample_label_names": ["Foo Acid"],
        }
    }

    p = bf.propose_for_entry("other_ingredients.json", "NHA_FOO", entry, fda_name_to_unii, dsld_index)
    assert p is not None
    assert p.proposed_unii == "FOOAC123XY"
    assert p.confidence == "high"
    assert "FDA cache exact" in p.rationale


def test_propose_medium_confidence_when_fda_only():
    """FDA cache match but no DSLD consensus → MEDIUM."""
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo Acid", "aliases": []}
    fda_name_to_unii = {"foo acid": "FOOAC123XY"}
    dsld_index: Dict = {}  # empty DSLD

    p = bf.propose_for_entry("other_ingredients.json", "NHA_FOO", entry, fda_name_to_unii, dsld_index)
    assert p is not None
    assert p.confidence == "medium"


def test_propose_medium_confidence_when_dsld_consensus_only():
    """DSLD consensus only (≥5 products) → MEDIUM."""
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo Acid", "aliases": []}
    fda_name_to_unii: Dict[str, str] = {}
    dsld_index = {
        ("foo acid", "FOOAC123XY"): {
            "count": 9,
            "brands": {"GNC", "CVS"},
            "sample_label_names": ["Foo Acid"],
        }
    }

    p = bf.propose_for_entry("other_ingredients.json", "NHA_FOO", entry, fda_name_to_unii, dsld_index)
    assert p is not None
    assert p.confidence == "medium"


def test_propose_low_confidence_when_weak_signals():
    """Single DSLD product, no FDA exact → LOW."""
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo Acid", "aliases": []}
    fda_name_to_unii: Dict[str, str] = {}
    dsld_index = {
        ("foo acid", "FOOAC123XY"): {
            "count": 1,  # below DSLD_CONSENSUS_THRESHOLD
            "brands": {"GNC"},
            "sample_label_names": ["Foo Acid"],
        }
    }

    p = bf.propose_for_entry("other_ingredients.json", "NHA_FOO", entry, fda_name_to_unii, dsld_index)
    assert p is not None
    assert p.confidence == "low"


def test_propose_returns_none_when_no_signal():
    """Entry with no FDA cache match AND no DSLD consensus → no proposal."""
    import backfill_unii_from_cache as bf

    entry = {"id": "NHA_FOO", "standard_name": "Foo Acid", "aliases": []}
    p = bf.propose_for_entry(
        "other_ingredients.json", "NHA_FOO", entry, {}, {}
    )
    assert p is None


def test_propose_returns_none_for_governed_null_entry():
    import backfill_unii_from_cache as bf

    entry = {
        "id": "NHA_FOO",
        "standard_name": "Foo",
        "external_ids": {},
        "cui_status": "governed_null",
    }
    p = bf.propose_for_entry(
        "other_ingredients.json", "NHA_FOO", entry,
        {"foo": "ABCDEF1234"},  # FDA would match — but entry is governed_null
        {},
    )
    assert p is None, "governed_null entries must NEVER receive a backfill proposal"


# ============================================================================
# Section 5 — pre-apply regression guard (CRITICAL — user-required)
# ============================================================================


def test_pre_apply_guard_blocks_when_creates_new_collision():
    """The regression guard MUST refuse a backfill that would create a new
    SAME_UNII_DIFFERENT_NAMES critical finding.

    Synthetic scenario:
      * Existing entry A in IQM has UNII=COLLISION12 with standard_name='Alpha'
      * Candidate entry B (no UNII yet) has standard_name='Beta' (unrelated to Alpha)
      * If we backfill B with UNII=COLLISION12, the audit will flag this as
        SAME_UNII_DIFFERENT_NAMES critical (two unrelated names, same UNII).
      * Guard must block.
    """
    import backfill_unii_from_cache as bf

    entries: List[Tuple[str, str, Dict[str, Any]]] = [
        (
            "ingredient_quality_map.json",
            "alpha",
            {"standard_name": "Alpha", "external_ids": {"unii": "COLLISION1"}},
        ),
        (
            "other_ingredients.json",
            "NHA_BETA",
            {"id": "NHA_BETA", "standard_name": "Beta", "external_ids": {}},
        ),
    ]

    proposal = bf.Proposal(
        entry_id="NHA_BETA",
        file="other_ingredients.json",
        standard_name="Beta",
        current_unii=None,
        current_cui=None,
        current_cui_status=None,
        proposed_unii="COLLISION1",
    )

    guard = bf.pre_apply_guard(
        entries=entries,
        proposal=proposal,
        unii_to_fda_names={},  # No FDA exoneration available
        exoneration_allowlist={},  # No explicit allowlist
    )

    assert guard["verdict"] == "BLOCKED"
    assert guard["would_create_new_critical_finding"] is True
    assert "COLLISION1" in guard["newly_introduced_critical_uniis"]
    assert guard["collision_detail"], "Should describe which entries collide"


def test_pre_apply_guard_allows_when_no_collision():
    """Safe backfill (new UNII not already in any other entry) → SAFE verdict."""
    import backfill_unii_from_cache as bf

    entries: List[Tuple[str, str, Dict[str, Any]]] = [
        (
            "ingredient_quality_map.json",
            "alpha",
            {"standard_name": "Alpha", "external_ids": {"unii": "EXISTING12"}},
        ),
        (
            "other_ingredients.json",
            "NHA_BETA",
            {"id": "NHA_BETA", "standard_name": "Beta", "external_ids": {}},
        ),
    ]

    proposal = bf.Proposal(
        entry_id="NHA_BETA",
        file="other_ingredients.json",
        standard_name="Beta",
        current_unii=None,
        current_cui=None,
        current_cui_status=None,
        proposed_unii="BRANDNEWUN",  # 10-char alphanumeric, not in any existing entry
    )

    guard = bf.pre_apply_guard(
        entries=entries,
        proposal=proposal,
        unii_to_fda_names={},
        exoneration_allowlist={},
    )

    assert guard["verdict"] == "SAFE"
    assert guard["would_create_new_critical_finding"] is False
    assert guard["newly_introduced_critical_uniis"] == []


def test_pre_apply_guard_respects_allowlist():
    """If a collision WOULD occur but the UNII is in the exoneration allowlist,
    guard should NOT flag it as a new critical finding (allowlisted)."""
    import backfill_unii_from_cache as bf

    entries: List[Tuple[str, str, Dict[str, Any]]] = [
        (
            "ingredient_quality_map.json",
            "alpha",
            {"standard_name": "Alpha", "external_ids": {"unii": "ALLOWED123"}},
        ),
        (
            "other_ingredients.json",
            "NHA_BETA",
            {"id": "NHA_BETA", "standard_name": "Beta", "external_ids": {}},
        ),
    ]

    # Allowlist this UNII — even though Alpha/Beta are unrelated, the
    # exoneration overrides the critical classification.
    allowlist = {
        "ALLOWED123": {
            "unii": "ALLOWED123",
            "fda_canonical_name": "Test Substance",
            "rationale": "Alpha and Beta are documented synonyms for the same compound — both are valid common names per FDA SCOGS.",
            "entries": [
                {"file": "ingredient_quality_map.json", "entry_id": "alpha"},
                {"file": "other_ingredients.json", "entry_id": "NHA_BETA"},
            ],
        }
    }

    proposal = bf.Proposal(
        entry_id="NHA_BETA",
        file="other_ingredients.json",
        standard_name="Beta",
        current_unii=None,
        current_cui=None,
        current_cui_status=None,
        proposed_unii="ALLOWED123",
    )

    guard = bf.pre_apply_guard(
        entries=entries,
        proposal=proposal,
        unii_to_fda_names={},
        exoneration_allowlist=allowlist,
    )

    # Allowlisted → NOT critical
    assert guard["verdict"] == "SAFE"
    assert guard["would_create_new_critical_finding"] is False


def test_apply_one_entry_refuses_when_guard_blocks():
    """apply_one_entry must raise ApplyRefused when guard verdict is BLOCKED.
    Sanity check: an apply call with a blocked guard MUST NOT mutate any file."""
    import backfill_unii_from_cache as bf

    proposal = bf.Proposal(
        entry_id="NHA_BETA",
        file="other_ingredients.json",
        standard_name="Beta",
        current_unii=None,
        current_cui=None,
        current_cui_status=None,
        proposed_unii="COLLISION1",
    )
    blocked_guard = {
        "would_create_new_critical_finding": True,
        "newly_introduced_critical_uniis": ["COLLISION1"],
        "baseline_critical_count": 0,
        "post_apply_critical_count": 1,
        "collision_detail": [{"unii": "COLLISION1", "colliding_entries": []}],
        "verdict": "BLOCKED",
    }

    with pytest.raises(bf.ApplyRefused):
        bf.apply_one_entry(REPO_ROOT, proposal, blocked_guard)


# ============================================================================
# Section 6 — DSLD consensus index
# ============================================================================


def test_dsld_consensus_index_missing_staging_returns_empty(tmp_path):
    """When DSLD staging tree is absent, index is empty (no crash)."""
    import backfill_unii_from_cache as bf

    nonexistent = tmp_path / "no_such_dir"
    idx = bf.build_dsld_consensus_index(nonexistent)
    assert idx == {}


def test_dsld_consensus_index_indexes_real_rows(tmp_path):
    """Synthetic DSLD layout: 2 brands, each with 1 product, both products
    list 'Foo Acid' with the same uniiCode. Index should aggregate."""
    import backfill_unii_from_cache as bf

    brand_a = tmp_path / "BrandA"
    brand_b = tmp_path / "BrandB"
    brand_a.mkdir()
    brand_b.mkdir()

    product = {
        "ingredientRows": [
            {"name": "Foo Acid", "uniiCode": "FOOAC123XY", "forms": []},
            {"name": "Bar", "uniiCode": "0", "forms": []},  # placeholder skipped
        ]
    }
    (brand_a / "p1.json").write_text(json.dumps(product), encoding="utf-8")
    (brand_b / "p2.json").write_text(json.dumps(product), encoding="utf-8")

    idx = bf.build_dsld_consensus_index(tmp_path)
    assert ("foo acid", "FOOAC123XY") in idx
    bucket = idx[("foo acid", "FOOAC123XY")]
    assert bucket["count"] == 2
    assert bucket["brands"] == {"BrandA", "BrandB"}
    # Placeholder UNII row should NOT be indexed
    assert ("bar", "0") not in idx
    assert ("bar", "1") not in idx


# ============================================================================
# Section 7 — proposal report shape
# ============================================================================


def test_render_proposal_report_shape(tmp_path):
    """Generated JSON has _metadata + proposals[] with per-confidence counts
    and the operator runbook copy."""
    import backfill_unii_from_cache as bf

    proposals = [
        bf.Proposal(
            entry_id="NHA_A",
            file="other_ingredients.json",
            standard_name="A",
            current_unii=None,
            current_cui=None,
            current_cui_status=None,
            proposed_unii="AAAAAAAAAA",
            confidence="high",
            rationale="test",
            pre_apply_guard={"verdict": "SAFE", "would_create_new_critical_finding": False},
        ),
        bf.Proposal(
            entry_id="NHA_B",
            file="other_ingredients.json",
            standard_name="B",
            current_unii=None,
            current_cui=None,
            current_cui_status=None,
            proposed_unii="BBBBBBBBBB",
            confidence="medium",
            rationale="test",
            pre_apply_guard={"verdict": "SAFE", "would_create_new_critical_finding": False},
        ),
    ]
    out = tmp_path / "report.json"
    bf.render_proposal_report(proposals, out)
    blob = json.loads(out.read_text(encoding="utf-8"))

    assert blob["_metadata"]["schema_version"] == "1.0.0"
    assert blob["_metadata"]["total_proposals"] == 2
    assert blob["_metadata"]["by_confidence"]["high"] == 1
    assert blob["_metadata"]["by_confidence"]["medium"] == 1
    assert blob["_metadata"]["by_confidence"]["low"] == 0
    assert "operator_runbook" in blob["_metadata"]
    assert len(blob["proposals"]) == 2
    # Sorted: high first
    assert blob["proposals"][0]["entry_id"] == "NHA_A"
    assert blob["proposals"][1]["entry_id"] == "NHA_B"
