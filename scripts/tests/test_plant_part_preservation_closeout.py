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
    # Label-native text owns the display (47d70a39, 641fe823): the literal label
    # name, with the form when the name lacks its plant part.
    assert ing.get("display_label") == "KSM-66 (Ashwagandha Root Extract)"


def test_ksm66_standardization_locked() -> None:
    b = _load("306237")
    ing = _find_ingredient(b, "ksm-66")
    assert ing.get("standardization_note") == "5% withanolides"


def test_bioperine_display_label_locked() -> None:
    b = _load("306237")
    # The 5mg enhancer is recognized but not in the scored-ingredient bucket.
    # The existing label display owner retains its literal identity and fruit.
    ing = next((r for r in b["display_ingredients"]
                if r.get("raw_source_path") == "ingredientRows[1]"), None)
    assert ing is not None
    assert ing["label_display_name"] == "Bioperine"
    assert ing["label_display_form"] == "Black Pepper Fruit Extract"
    assert ing["canonical_id"] == "piperine"
    assert ing["exact_dose_text"] == "5 mg"


def test_bioperine_standardization_locked() -> None:
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from build_final_db import _compute_standardization_note

    # Frozen NIH raw306237 prints min95%piperine. Assess the native row with
    # the existing extraction owner; an unassessed display row has analysis=None.
    raw = json.loads((ROOT / "scripts/tests/fixtures/plant_part_306237_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    ing = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
               if r["raw_source_path"] == "ingredientRows[1]")
    assert ing["name"] == "Bioperine" and ing["quantity"] == 5
    assert ing["raw_taxonomy"]["forms"][0]["name"] == "Black Pepper Fruit Extract"
    assert ing["role_classification"] == "recognized_non_scorable"
    assert _compute_standardization_note(ing) == "95% piperine"


def test_green_tea_standardization_locked() -> None:
    """Raw1036 lists15mg leaf extract without an EGCG percentage/forms."""
    b = _load("1036")
    ing = _find_ingredient(b, "green tea")
    assert ing["name"] == "Green Tea leaf extract"
    assert ing["quantity"] == 15 and ing["unit"] == "mg"
    assert ing.get("standardization_note") is None
    assert ing["matched_form"] == "green tea extract (unspecified)"
    assert all(marker.get("estimated_dose_mg") is None
               for marker in ing["delivers_markers"])
    concerns = [w for w in b.get("warnings", [])
                if "egcg" in str(w.get("dose_decision") or {}).lower()]
    assert concerns
    assert all(w["dose_decision"]["evaluation_status"] == "amount_unknown" and
               w["dose_decision"]["consumer_disposition"] == "block"
               for w in concerns)



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


# The v3 Section A score lock was retired on 2026-09-22: blobs carry no v3
# section_breakdown (test_build_final_db::test_blob_carries_no_v3_score_husks).
