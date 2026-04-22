"""
Sprint E1.0.3 — regression test for ``label_fidelity_scope_report``.

Feeds a tempdir with one clean blob and one violating blob, invokes the
scope-report computation, asserts per-axis counts and idempotency. Also
exercises the CLI entry point so the ``--fail-on-violations`` exit-code
contract is covered (this is the E1 CI release-gate mechanism).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the scripts package importable when tests run from repo root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reports.label_fidelity_scope_report import (  # noqa: E402
    compute_scope_report,
    main,
    render_markdown,
)


CLEAN_BLOB = {
    "dsld_id": "CLEAN-0001",
    "has_banned_substance": 0,
    "ingredients": [
        {
            "name": "Ashwagandha",
            "raw_name": "Ashwagandha Root Extract",
            "display_label": "Ashwagandha Root Extract",
            "canonical_name": "Ashwagandha",
            "forms": [{"name": "Root Extract"}],
            "notes": [],
            "standardization_note": None,
        }
    ],
    "inactive_ingredients": [{"name": "Vegetable Capsule"}],
    "raw_inactives_count": 1,
    "raw_actives_count": 1,
    "proprietary_blend_detail": {"blends": []},
    "decision_highlights": {
        "positive": "Strong overall quality profile.",
        "caution": "No major caution signal surfaced.",
        "danger": [],
        "trust": "Trust signals limited.",
    },
    "warnings": [],
    "warnings_profile_gated": [],
}


BAD_BLOB = {
    "dsld_id": "BAD-0001",
    "has_banned_substance": 1,
    "ingredients": [
        # Branded identity dropped from display_label — but plant part
        # preserved, so only axis B fires (not axis C).
        {
            "name": "Ashwagandha",
            "raw_name": "KSM-66 Ashwagandha Root Extract",
            "display_label": "Ashwagandha Root",
            "canonical_name": "Ashwagandha",
            "forms": [{"name": "Root"}],
            "notes": [],
            "standardization_note": None,
            "is_banned": False,
        },
        # Plant part dropped (axis C violation)
        {
            "name": "Valerian",
            "display_label": "Valerian",
            "canonical_name": "Valerian",
            "forms": [{"name": "Root Powder"}],
            "notes": [],
            "standardization_note": None,
        },
        # Standardization note dropped (axis D violation)
        {
            "name": "Curcumin",
            "display_label": "Curcumin Extract",
            "canonical_name": "Curcumin",
            "forms": [{"name": "Extract"}],
            "notes": ["Standardized to 95% curcuminoids"],
            "standardization_note": None,
        },
        # Banned ingredient with NO preflight copy — axis S4 violation
        {
            "name": "DMAA",
            "display_label": "DMAA",
            "is_banned": True,
            "safety_warning_one_liner": "",
            "safety_warning": "",
        },
    ],
    "inactive_ingredients": [],  # axis E violation (raw_inactives_count=3 vs 0)
    "raw_inactives_count": 3,
    "raw_actives_count": 4,
    "proprietary_blend_detail": {
        # Blend with members but no total_weight — axis A violation
        "blends": [{"name": "Energy Blend", "members": ["a", "b"], "total_weight": 0}],
    },
    "decision_highlights": {
        # Danger-valence string under positive — axis S1 violation
        "positive": ["Not lawful as a US dietary supplement."],
        "caution": "Check with your doctor.",
        "danger": [],
        "trust": "",
    },
    "warnings": [
        # Critical-mode with condition-specific copy — axis S2 violation
        {
            "type": "interaction",
            "severity": "high",
            "canonical_id": "warfarin_bleeding",
            "display_mode_default": "critical",
            "alert_headline": "May affect bleeding during pregnancy.",
            "alert_body": "",
        },
        # Raw enum leak — no authored copy — axis S3 violation
        {
            "type": "ban_ingredient",
            "severity": "critical",
            "canonical_id": "dmaa_ban",
            "display_mode_default": "critical",
            "alert_headline": "",
            "alert_body": "",
            "safety_warning": "",
            "safety_warning_one_liner": "",
            "detail": "",
        },
        # Duplicate pair — axis S5 violation
        {
            "type": "pregnancy",
            "severity": "high",
            "canonical_id": "preg_rule_001",
            "condition_id": "pregnancy",
            "display_mode_default": "suppress",
            "alert_headline": "May affect pregnancy.",
        },
        {
            "type": "pregnancy",
            "severity": "high",
            "canonical_id": "preg_rule_001",
            "condition_id": "pregnancy",
            "display_mode_default": "suppress",
            "alert_headline": "May affect pregnancy.",
        },
    ],
    "warnings_profile_gated": [],
}


@pytest.fixture()
def fixture_dir(tmp_path: Path) -> Path:
    d = tmp_path / "detail_blobs"
    d.mkdir()
    (d / "clean.json").write_text(json.dumps(CLEAN_BLOB))
    (d / "bad.json").write_text(json.dumps(BAD_BLOB))
    return d


def test_scan_counts_are_correct(fixture_dir: Path) -> None:
    """Per-axis counts on the fixture dir must match expected violations
    emitted by the bad blob only."""
    report = compute_scope_report(fixture_dir)
    assert report["scanned_products"] == 2

    lf = report["label_fidelity"]
    assert lf["A_prop_blend_mass_recovery"]["count"] == 1
    assert lf["B_branded_identity_preserved"]["count"] == 1
    assert lf["C_plant_part_preserved"]["count"] == 1
    assert lf["D_standardization_note_preserved"]["count"] == 1
    assert lf["E_inactive_ingredients_complete"]["count"] == 1

    sc = report["safety_copy"]
    assert sc["S1_no_danger_in_positives"]["count"] == 1
    assert sc["S2_critical_profile_agnostic"]["count"] == 1
    assert sc["S3_no_raw_enum_leaks"]["count"] == 1
    assert sc["S4_banned_substance_preflight"]["count"] == 1
    assert sc["S5_no_duplicate_warnings"]["count"] == 1

    # Totals roll up
    assert report["total_violations"] >= 10


def test_output_is_idempotent(fixture_dir: Path) -> None:
    """Two runs on identical inputs must produce byte-identical JSON."""
    r1 = compute_scope_report(fixture_dir)
    r2 = compute_scope_report(fixture_dir)
    s1 = json.dumps(r1, indent=2, sort_keys=True)
    s2 = json.dumps(r2, indent=2, sort_keys=True)
    assert s1 == s2


def test_markdown_render_is_deterministic(fixture_dir: Path) -> None:
    """Markdown output must also be byte-identical across runs."""
    report = compute_scope_report(fixture_dir)
    m1 = render_markdown(report)
    m2 = render_markdown(report)
    assert m1 == m2
    # Content sanity check: must mention every axis key
    for axis in report["label_fidelity"]:
        assert axis in m1
    for axis in report["safety_copy"]:
        assert axis in m1


def test_cli_fail_on_violations_exit_code(fixture_dir: Path, tmp_path: Path) -> None:
    """CLI returns 1 with --fail-on-violations when counts > 0; 0 without."""
    out_dir = tmp_path / "out"

    # With flag + bad fixture → exit 1
    rc = main([
        "--blobs", str(fixture_dir),
        "--out", str(out_dir),
        "--prefix", "test_run",
        "--fail-on-violations",
    ])
    assert rc == 1
    assert (out_dir / "test_run.json").exists()
    assert (out_dir / "test_run.md").exists()

    # Without flag → exit 0 even with violations
    rc2 = main([
        "--blobs", str(fixture_dir),
        "--out", str(out_dir),
        "--prefix", "test_run2",
    ])
    assert rc2 == 0


def test_cli_clean_fixture_exits_zero(tmp_path: Path) -> None:
    """A fixture dir with zero violations returns 0 even with --fail-on-violations."""
    clean_dir = tmp_path / "clean_blobs"
    clean_dir.mkdir()
    (clean_dir / "a.json").write_text(json.dumps(CLEAN_BLOB))
    out_dir = tmp_path / "out"
    rc = main([
        "--blobs", str(clean_dir),
        "--out", str(out_dir),
        "--prefix", "clean",
        "--fail-on-violations",
    ])
    assert rc == 0
