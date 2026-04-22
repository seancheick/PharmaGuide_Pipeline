"""
Sprint E1.4.1 — plural-array normalization for ``condition_ids`` /
``drug_class_ids`` across warning lists.

Post-migration contract:
  * Every warning entry emits ``condition_ids: List[str]`` (not
    ``condition_id``).
  * Every warning entry emits ``drug_class_ids: List[str]`` (not
    ``drug_class_id``).
  * Arrays are sorted, deduplicated, string-typed.
  * Legacy singular keys are absent after normalization.
  * Applied to BOTH ``warnings[]`` and ``warnings_profile_gated[]``.

Backward-safe migration: singular → array of one; existing array →
dedup + sort; missing / null → ``[]``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import _normalize_warning_condition_keys  # noqa: E402


# ---------------------------------------------------------------------------
# Singular → array migration
# ---------------------------------------------------------------------------

def test_singular_condition_id_becomes_array_of_one() -> None:
    w = {"condition_id": "pregnancy", "type": "interaction"}
    out = _normalize_warning_condition_keys(w)
    assert out["condition_ids"] == ["pregnancy"]
    assert "condition_id" not in out


def test_singular_drug_class_id_becomes_array_of_one() -> None:
    w = {"drug_class_id": "warfarin", "type": "drug_interaction"}
    out = _normalize_warning_condition_keys(w)
    assert out["drug_class_ids"] == ["warfarin"]
    assert "drug_class_id" not in out


# ---------------------------------------------------------------------------
# Existing array is dedup + sorted
# ---------------------------------------------------------------------------

def test_existing_array_dedup_and_sort() -> None:
    w = {"condition_ids": ["pregnancy", "liver_disease", "pregnancy"]}
    out = _normalize_warning_condition_keys(w)
    assert out["condition_ids"] == ["liver_disease", "pregnancy"]


def test_drug_class_ids_array_dedup_and_sort() -> None:
    w = {"drug_class_ids": ["statins", "warfarin", "statins", "maoi"]}
    out = _normalize_warning_condition_keys(w)
    assert out["drug_class_ids"] == ["maoi", "statins", "warfarin"]


# ---------------------------------------------------------------------------
# Null / empty / missing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("val", [None, "", [], ["", None], [""]])
def test_null_empty_becomes_empty_array(val) -> None:
    w = {"condition_id": val}
    out = _normalize_warning_condition_keys(w)
    assert out["condition_ids"] == []


def test_missing_keys_still_emit_empty_arrays() -> None:
    w = {"type": "generic_warning"}
    out = _normalize_warning_condition_keys(w)
    assert out["condition_ids"] == []
    assert out["drug_class_ids"] == []


# ---------------------------------------------------------------------------
# Merge: both singular + array present → union
# ---------------------------------------------------------------------------

def test_singular_plus_array_both_present_are_unioned() -> None:
    """Belt-and-suspenders — if upstream code set both, merge them
    without losing data."""
    w = {"condition_id": "pregnancy",
         "condition_ids": ["liver_disease", "kidney_disease"]}
    out = _normalize_warning_condition_keys(w)
    assert out["condition_ids"] == ["kidney_disease", "liver_disease", "pregnancy"]


# ---------------------------------------------------------------------------
# No cross-field mutation
# ---------------------------------------------------------------------------

def test_does_not_mutate_other_fields() -> None:
    w = {
        "condition_id": "pregnancy",
        "severity": "contraindicated",
        "alert_headline": "Do not use during pregnancy",
        "type": "interaction",
    }
    out = _normalize_warning_condition_keys(w)
    assert out["severity"] == "contraindicated"
    assert out["alert_headline"] == "Do not use during pregnancy"
    assert out["type"] == "interaction"
    # Plural keys added, singular removed
    assert out["condition_ids"] == ["pregnancy"]
    assert "condition_id" not in out


def test_idempotent_on_already_plural_shape() -> None:
    w = {"condition_ids": ["pregnancy"], "drug_class_ids": ["maoi"]}
    once = _normalize_warning_condition_keys(w)
    twice = _normalize_warning_condition_keys(once)
    assert once == twice


# ---------------------------------------------------------------------------
# Canary — end-to-end blob shape
# ---------------------------------------------------------------------------

def test_canary_blobs_have_plural_arrays_only() -> None:
    """Every warning in every canary blob must carry plural arrays,
    no singular legacy keys."""
    import json
    canary_ids = ["35491", "306237", "246324", "1002", "19067",
                  "1036", "176872", "266975", "19055"]
    for did in canary_ids:
        p = ROOT / "reports" / "canary_rebuild" / f"{did}.json"
        if not p.exists():
            continue
        blob = json.loads(p.read_text())
        for list_key in ("warnings", "warnings_profile_gated"):
            for w in blob.get(list_key) or []:
                if not isinstance(w, dict):
                    continue
                assert "condition_id" not in w, (
                    f"[{did}] {list_key} entry still has legacy 'condition_id': {w}"
                )
                assert "drug_class_id" not in w, (
                    f"[{did}] {list_key} entry still has legacy 'drug_class_id': {w}"
                )
                assert isinstance(w.get("condition_ids"), list)
                assert isinstance(w.get("drug_class_ids"), list)
                # All entries are strings
                for c in w["condition_ids"]:
                    assert isinstance(c, str) and c
                for c in w["drug_class_ids"]:
                    assert isinstance(c, str) and c
                # Sorted + dedup
                assert w["condition_ids"] == sorted(set(w["condition_ids"]))
                assert w["drug_class_ids"] == sorted(set(w["drug_class_ids"]))


def test_vitafusion_cbd_preserves_pregnancy_condition() -> None:
    """Canary 246324 VitaFusion CBD Mixed Berry has pregnancy-related
    interaction warnings — condition_ids must include 'pregnancy'
    after the migration."""
    import json
    p = ROOT / "reports" / "canary_rebuild" / "246324.json"
    if not p.exists():
        pytest.skip("246324 canary not rebuilt yet")
    blob = json.loads(p.read_text())
    has_pregnancy = False
    for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or []):
        if isinstance(w, dict) and "pregnancy" in (w.get("condition_ids") or []):
            has_pregnancy = True
            break
    assert has_pregnancy, "VitaFusion CBD must retain pregnancy condition mapping"
