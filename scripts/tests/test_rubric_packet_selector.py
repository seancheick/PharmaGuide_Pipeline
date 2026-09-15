"""Regression tests for the reproducible rubric packet selector."""

from __future__ import annotations

import sys
import json
import subprocess
from pathlib import Path

import pytest


AUDIT_DIR = Path(__file__).resolve().parents[1] / "audits" / "rubric_proxy_removal_2026_09_14"
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

from select_packet import _flag, _positive, _verification_selection_flags  # noqa: E402
from select_packet import ID_FILES  # noqa: E402


def test_positive_treats_numeric_zero_string_as_empty() -> None:
    assert not _positive("0")
    assert not _positive("not-a-number")
    assert _positive("2")


def test_flag_does_not_treat_false_string_as_present() -> None:
    assert not _flag("false")
    assert not _flag("0")
    assert _flag("true")


def test_current_reputation_component_is_not_a_plain_unknown() -> None:
    assert _verification_selection_flags({"reputation": 1.0}) == (False, True)


def test_legacy_soft_reputation_component_is_not_a_plain_unknown() -> None:
    assert _verification_selection_flags({"soft": 1.0}) == (False, True)


def test_label_only_gmp_claim_is_not_an_unknown_reputation_group() -> None:
    assert _verification_selection_flags({}, claim_only=True) == (False, False)


def test_label_claim_with_reputation_remains_in_reputation_group() -> None:
    # A label-only GMP claim must not hide an independent brand/reputation
    # signal or make the selector drop the product from pass 2.
    assert _verification_selection_flags({"reputation": 1.0}, claim_only=True) == (False, True)


def test_hard_product_signal_is_not_a_reputation_or_plain_unknown_group() -> None:
    assert _verification_selection_flags({"cert": "9"}) == (False, False)


@pytest.mark.parametrize("defect", [None, "empty_score", "nan", "infinity", "missing_pillar", "over_pillar", "missing_hash", "missing_status"])
def test_diff_refuses_vacuous_or_invalid_unchanged_packets(tmp_path, defect):
    from scoring_v4.quality_score import _config
    ids = [p["id"] for p in json.loads(ID_FILES["pass1"].read_text())["products"]]
    snapshot = {"_meta": {"packet": "pass1", "ids": ids, "input_sha256": "a" * 64, "checkout_commit": "b" * 40}}
    for pid in ids:
        snapshot[pid] = {"score": 100, "status": "scored", "tier": "Exceptional", "cap": None,
                         "pillars": {k: v["weight"] for k, v in _config()["pillars"].items()}}
    row = snapshot[ids[0]]
    if defect == "empty_score":
        row["score"] = None
    elif defect == "nan":
        row["score"] = float("nan")
    elif defect == "infinity":
        row["score"] = float("inf")
    elif defect == "missing_pillar":
        del row["pillars"]["dose"]
    elif defect == "over_pillar":
        row["pillars"]["safety_hygiene"] = 11
    elif defect == "missing_hash":
        snapshot["_meta"].pop("input_sha256")
    elif defect == "missing_status":
        row.pop("status")
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot))
    run = subprocess.run([sys.executable, str(AUDIT_DIR / "diff_packet.py"), str(path), str(path), "--no-moves"],
                         capture_output=True, text=True)
    assert run.returncode == (0 if defect is None else 1), run.stdout + run.stderr
    if defect:
        assert "REFUSED:" in run.stderr
