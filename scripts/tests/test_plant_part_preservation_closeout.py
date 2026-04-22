"""
Sprint E1.3.5 — plant-part / form / standardization preservation closeout.

Test-only task. The actual preservation logic shipped in E1.2.2
(display_label composition) and E1.2.2.c (tight standardization regex).
This file LOCKS those guarantees so any future regression — normalizer
change, IQM update, Dr Pham authoring sweep — breaks CI immediately.

No new logic. No new fields. Just contracts against the 9 canary
blobs in ``reports/canary_rebuild/`` that cover the botanical axis.

Dev anchor: "We don't improve botanicals here — we prove we didn't
break them."

Covers sprint §E1.3.5 DoD:
  * Contract test #5 (plant_part_preserved) in
    test_label_fidelity_contract.py is auto-gated and already activates
    on blob presence. This file adds exact-value assertions for the
    named-product canaries.
  * ≥ 95% plant-part preservation (metric C) — enforced via the
    label-fidelity contract suite; here we lock specific product
    canaries so wins don't regress silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANARY_DIR = ROOT / "reports" / "canary_rebuild"


def _load(did: str) -> dict:
    p = CANARY_DIR / f"{did}.json"
    if not p.exists():
        pytest.skip(f"canary {did} not rebuilt yet")
    return json.loads(p.read_text())


def _find_ingredient(blob: dict, name_contains: str) -> dict:
    """Return first ingredient whose name contains the substring (case-
    insensitive). Useful because DSLD disclosed names vary."""
    needle = name_contains.lower()
    for ing in blob.get("ingredients") or []:
        if needle in (ing.get("name") or "").lower():
            return ing
    pytest.fail(f"ingredient containing {name_contains!r} not found in blob")


# ---------------------------------------------------------------------------
# Exact-value locks on known canary ingredients
# ---------------------------------------------------------------------------

def test_ksm66_ashwagandha_display_label_locked() -> None:
    """Canary 306237 — KSM-66 composite must exactly preserve brand +
    base + plant part + form."""
    b = _load("306237")
    ing = _find_ingredient(b, "ksm-66")
    assert ing.get("display_label") == "KSM-66 Ashwagandha Root Extract"


def test_ksm66_standardization_locked() -> None:
    b = _load("306237")
    ing = _find_ingredient(b, "ksm-66")
    assert ing.get("standardization_note") == "5% withanolides"


def test_bioperine_display_label_locked() -> None:
    b = _load("306237")
    ing = _find_ingredient(b, "bioperine")
    assert ing.get("display_label") == "BioPerine Black Pepper Fruit Extract"


def test_bioperine_standardization_locked() -> None:
    b = _load("306237")
    ing = _find_ingredient(b, "bioperine")
    assert ing.get("standardization_note") == "95% piperine"


def test_green_tea_standardization_locked() -> None:
    """Canary 1036 Green Tea leaf extract — matched_form source path."""
    b = _load("1036")
    ing = _find_ingredient(b, "green tea")
    assert ing.get("standardization_note") == "50% EGCG"


# ---------------------------------------------------------------------------
# Over-normalization guard — display must NOT collapse to canonical
# ---------------------------------------------------------------------------

def test_display_label_never_collapses_to_bare_canonical() -> None:
    """Dev anchor: 'Don't drop plant part when form exists.' A composite
    display of `KSM-66 Ashwagandha Root Extract` must never degrade to
    just `Ashwagandha`."""
    b = _load("306237")
    ing = _find_ingredient(b, "ksm-66")
    label = (ing.get("display_label") or "").strip().lower()
    # Must be strictly more than the bare canonical
    assert label != "ashwagandha"
    assert "root" in label
    assert "extract" in label


def test_display_preserves_plant_part_across_canaries() -> None:
    """Parametric check: for any ingredient whose DSLD forms[0].name
    contains a plant-part token, the display_label must too (invariant
    #5 from E1.0.1)."""
    import re
    PLANT_PART_RE = re.compile(
        r"\b(root|leaf|leaves|seed|bark|rhizome|flower|fruit|stem|aerial)\b",
        re.IGNORECASE,
    )
    violations = []
    for did in ("35491", "306237", "246324", "1002", "19067",
                "1036", "176872", "266975", "19055"):
        try:
            blob = _load(did)
        except pytest.skip.Exception:
            continue
        for ing in blob.get("ingredients") or []:
            forms = ing.get("forms") or []
            form_blob = " ".join(
                f.get("name", "") for f in forms if isinstance(f, dict)
            )
            m = PLANT_PART_RE.search(form_blob)
            if not m:
                continue
            part = m.group(1).lower()
            display = (ing.get("display_label") or "").lower()
            equivalents = {"leaf": ("leaf", "leaves"),
                           "leaves": ("leaf", "leaves")}
            acceptable = equivalents.get(part, (part,))
            if not any(e in display for e in acceptable):
                violations.append(
                    (did, ing.get("name"), part, ing.get("display_label"))
                )
    assert not violations, (
        "plant-part dropped from display_label: "
        + "; ".join(f"[{d}] {n!r} part={p!r} display={lab!r}" for d, n, p, lab in violations[:5])
    )


# ---------------------------------------------------------------------------
# Negative cases — no spurious extraction
# ---------------------------------------------------------------------------

def test_extract_alone_is_not_a_plant_part() -> None:
    """Canary 246324 VitaFusion "Hemp extract" — the bare word "extract"
    in forms[0].name is NOT a plant part. Must not accidentally get
    stamped as such in display_label."""
    b = _load("246324")
    ing = _find_ingredient(b, "hemp extract")
    label = (ing.get("display_label") or "").lower()
    # Must preserve "Hemp extract" as a single term, not split "extract"
    # into a plant-part slot
    assert label == "hemp extract"


def test_no_spurious_standardization_on_non_botanical() -> None:
    """Canary 266975 Nature Made Vitamin E — no standardization claim
    should appear (the 180 mg dose is a plain vitamin E, not a
    standardized botanical)."""
    b = _load("266975")
    ing = _find_ingredient(b, "vitamin e")
    assert ing.get("standardization_note") is None


def test_simple_enzyme_has_no_standardization() -> None:
    """Canary 35491 Plantizyme enzymes — enzymes don't have
    standardization percentages. None on all."""
    b = _load("35491")
    for ing in b.get("ingredients") or []:
        assert ing.get("standardization_note") is None, (
            f"unexpected standardization on enzyme {ing.get('name')!r}: "
            f"{ing.get('standardization_note')!r}"
        )


# ---------------------------------------------------------------------------
# Section A "zero change" lock — this sprint task CANNOT change scores
# ---------------------------------------------------------------------------

# Section A values as of post-E1.3.4 (locked here so any regression in
# E1.3.5 that accidentally touches score math is caught immediately).
_POST_E1_3_4_SECTION_A = {
    "35491":  2.50,
    "306237": 18.08,
    "246324":  0.00,
    "1002":   14.00,
    "19067":  20.00,
    "1036":   19.50,
    "176872": 15.25,
    "266975":  7.00,
    "19055":   1.00,
}


@pytest.mark.parametrize("did,expected", list(_POST_E1_3_4_SECTION_A.items()))
def test_section_a_unchanged_by_plant_part_closeout(did: str, expected: float) -> None:
    """Dev hard stop: E1.3.5 must produce zero score change across
    every canary."""
    b = _load(did)
    actual = b["section_breakdown"]["ingredient_quality"]["score"]
    assert actual == pytest.approx(expected, abs=0.01), (
        f"[{did}] Section A shifted: expected {expected}, got {actual}. "
        f"E1.3.5 is test-only — any score change is a bug."
    )
