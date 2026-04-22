"""
Sprint E1.3.4 — enzyme recognition credit.

Config-gated small bonus for enzyme-containing products so Plantizyme-
style enzyme panels don't emit a misleading 0/25 Section A score when
the label discloses named enzymes but no individual doses. Points are
conservative and capped.

Config (``section_A_ingredient_quality.enzyme_recognition``):
  * ``per_enzyme_points``  — points per unique mapped enzyme
  * ``max_points``         — hard per-product cap
  * ``require_named_enzyme`` — enzyme name must be in KNOWN_ENZYMES
  * ``min_activity_gate``  — (optional, off by default) require a
    numeric activity value in an allowed unit (DU/HUT/FIP/…)

Dev rule: "We reward verifiable enzyme activity, not just ingredient
names." When min_activity_gate is enabled (future toggle once Dr Pham
has the audit data), enzymes with ``NP`` units get 0 points.
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

from score_supplements import _compute_enzyme_recognition_bonus  # noqa: E402


DEFAULT_CFG = {
    "enabled": True,
    "per_enzyme_points": 0.5,
    "max_points": 2.5,
    "require_named_enzyme": True,
    "min_activity_gate": {
        "enabled": False,
        "allowed_units": ["DU", "HUT", "FIP", "ALU", "CU", "SKB"],
        "min_value": 1,
    },
}


def _enzyme(name, unit="NP", qty=0, category="enzyme"):
    return {
        "name": name,
        "standard_name": name,
        "category": category,
        "quantity": qty,
        "unit": unit,
    }


# ---------------------------------------------------------------------------
# Canary — Plantizyme 5 enzymes with NP units
# ---------------------------------------------------------------------------

def test_plantizyme_canary_hits_cap() -> None:
    """5 unique mapped enzymes × 0.5 pts = 2.5, at cap."""
    ingredients = [
        _enzyme("Amylase"), _enzyme("Protease"), _enzyme("Lipase"),
        _enzyme("Cellulase"), _enzyme("Lactase"),
    ]
    out = _compute_enzyme_recognition_bonus(ingredients, DEFAULT_CFG)
    assert out["enzyme_recognition_points"] == pytest.approx(2.5)
    assert out["recognized_enzymes_count"] == 5


# ---------------------------------------------------------------------------
# Gate — disabled returns 0 regardless
# ---------------------------------------------------------------------------

def test_disabled_returns_zero() -> None:
    cfg = {**DEFAULT_CFG, "enabled": False}
    out = _compute_enzyme_recognition_bonus([_enzyme("Amylase")], cfg)
    assert out["enzyme_recognition_points"] == 0.0


def test_missing_config_returns_zero() -> None:
    out = _compute_enzyme_recognition_bonus([_enzyme("Amylase")], {})
    assert out["enzyme_recognition_points"] == 0.0


# ---------------------------------------------------------------------------
# Cap enforcement — never exceeds max_points
# ---------------------------------------------------------------------------

def test_cap_enforced() -> None:
    """10 enzymes × 0.5 = 5.0, capped at 2.5."""
    ingredients = [_enzyme(n) for n in (
        "Amylase", "Protease", "Lipase", "Cellulase", "Lactase",
        "Bromelain", "Papain", "Pepsin", "Rennin", "Trypsin",
    )]
    out = _compute_enzyme_recognition_bonus(ingredients, DEFAULT_CFG)
    assert out["enzyme_recognition_points"] == 2.5


# ---------------------------------------------------------------------------
# Deduplication — same enzyme across blends counted once
# ---------------------------------------------------------------------------

def test_duplicate_enzyme_not_double_counted() -> None:
    ingredients = [
        _enzyme("Amylase"), _enzyme("Amylase"),  # duplicate
        _enzyme("amylase"),                       # case-insensitive dup
        _enzyme("Protease"),
    ]
    out = _compute_enzyme_recognition_bonus(ingredients, DEFAULT_CFG)
    # 2 unique enzymes × 0.5 = 1.0
    assert out["enzyme_recognition_points"] == pytest.approx(1.0)
    assert out["recognized_enzymes_count"] == 2


# ---------------------------------------------------------------------------
# Non-enzyme products — 0 points, no side effects
# ---------------------------------------------------------------------------

def test_non_enzyme_product_gets_zero() -> None:
    ingredients = [
        {"name": "Vitamin C", "category": "vitamin"},
        {"name": "Turmeric Root Extract", "category": "botanical"},
    ]
    out = _compute_enzyme_recognition_bonus(ingredients, DEFAULT_CFG)
    assert out["enzyme_recognition_points"] == 0.0


def test_empty_ingredient_list() -> None:
    out = _compute_enzyme_recognition_bonus([], DEFAULT_CFG)
    assert out["enzyme_recognition_points"] == 0.0


def test_unknown_enzyme_name_not_credited() -> None:
    """require_named_enzyme=True means random "Enzyme Complex" string
    without a matching enzyme in KNOWN_ENZYMES gets 0."""
    out = _compute_enzyme_recognition_bonus(
        [{"name": "Mystery Enzyme Blend", "category": "enzyme"}], DEFAULT_CFG,
    )
    assert out["enzyme_recognition_points"] == 0.0


# ---------------------------------------------------------------------------
# Optional stricter gate — activity-unit requirement
# ---------------------------------------------------------------------------

def test_min_activity_gate_enabled_rejects_np_units() -> None:
    cfg = {**DEFAULT_CFG, "min_activity_gate": {
        "enabled": True,
        "allowed_units": ["DU", "HUT", "FIP"],
        "min_value": 1,
    }}
    out = _compute_enzyme_recognition_bonus(
        [_enzyme("Amylase"), _enzyme("Protease")],  # NP units
        cfg,
    )
    assert out["enzyme_recognition_points"] == 0.0


def test_min_activity_gate_enabled_accepts_valid_unit() -> None:
    cfg = {**DEFAULT_CFG, "min_activity_gate": {
        "enabled": True,
        "allowed_units": ["DU", "HUT", "FIP"],
        "min_value": 1,
    }}
    out = _compute_enzyme_recognition_bonus(
        [_enzyme("Amylase", unit="DU", qty=500)],
        cfg,
    )
    assert out["enzyme_recognition_points"] == pytest.approx(0.5)


def test_min_activity_gate_rejects_below_min_value() -> None:
    cfg = {**DEFAULT_CFG, "min_activity_gate": {
        "enabled": True,
        "allowed_units": ["DU"],
        "min_value": 100,
    }}
    out = _compute_enzyme_recognition_bonus(
        [_enzyme("Amylase", unit="DU", qty=50)],
        cfg,
    )
    assert out["enzyme_recognition_points"] == 0.0


# ---------------------------------------------------------------------------
# Non-mutation guarantee
# ---------------------------------------------------------------------------

def test_does_not_mutate_input_ingredients() -> None:
    ingredients = [_enzyme("Amylase")]
    original = ingredients[0].copy()
    _compute_enzyme_recognition_bonus(ingredients, DEFAULT_CFG)
    assert ingredients[0] == original


# ---------------------------------------------------------------------------
# Output shape — controlled keys
# ---------------------------------------------------------------------------

def test_output_shape_stable() -> None:
    out = _compute_enzyme_recognition_bonus([_enzyme("Amylase")], DEFAULT_CFG)
    assert set(out.keys()) == {
        "enzyme_recognition_points",
        "recognized_enzymes_count",
        "recognized_enzymes",
    }
    assert isinstance(out["recognized_enzymes"], list)
    assert "amylase" in [e.lower() for e in out["recognized_enzymes"]]


# ---------------------------------------------------------------------------
# End-to-end: 35491 Plantizyme canary Section A ≥ 2.5
# ---------------------------------------------------------------------------

def test_canary_35491_plantizyme_section_a_at_least_cap() -> None:
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "35491.json"
    if not blob_path.exists():
        pytest.skip("35491 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())
    sa = blob.get("section_breakdown", {}).get("ingredient_quality", {}).get("score", 0)
    assert sa >= 2.5, (
        f"Sprint §E1.3.4 DoD: Plantizyme Section A must be ≥ 2.5/25; got {sa}"
    )
