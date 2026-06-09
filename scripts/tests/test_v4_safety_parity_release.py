"""v4 safety parity gate against released artifacts.

Clinical invariant: a product that v3 marks BLOCKED must not become scoreable
or SAFE/POOR in v4. This catches missing safety-signal propagation
between enrichment, scoring, final DB, and v4 module dispatch.
"""

from __future__ import annotations

import glob
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _load_release_ids() -> set[str]:
    db_path = ROOT / "scripts" / "dist" / "pharmaguide_core.db"
    if not db_path.exists():
        pytest.skip("release DB not present")
    conn = sqlite3.connect(db_path)
    try:
        return {str(row[0]) for row in conn.execute("select dsld_id from products_core")}
    finally:
        conn.close()


def _load_json_records(pattern: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in glob.glob(str(ROOT / pattern)):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for rec in data:
            if not isinstance(rec, dict):
                continue
            dsld_id = str(rec.get("dsld_id") or rec.get("id") or "")
            if dsld_id:
                rows[dsld_id] = rec
    return rows


# Intentional 2026-06-08 reclassification: FD&C Red No. 3 / Erythrosine was moved
# from status=banned (hard BLOCK) to high_risk + penalize_anyway (CAUTION) in
# banned_recalled_ingredients.json — FDA federally REVOKED it (Jan 2025, Delaney)
# but it is legal until the 2027 reformulation deadline, matching FD&C Green No. 3.
# These release products were v3-BLOCKED SOLELY by Red 3 and now correctly read
# v4 CAUTION. They must still WARN (CAUTION) — never silently become SAFE/POOR.
# (Diagnostic 2026-06-08: of 83 v3-BLOCKED, exactly these 4 downgrade, all Red-3-only.)
RED3_RECLASSIFIED_TO_CAUTION = {"315819", "315092", "306181", "312638"}

# Intentional 2026-06-09 reclassification: Simethicone / polydimethylsiloxane
# moved from banned hard-block to watchlist with inactive excipient acceptable.
# These GNC Re-Feed products contain it as an inactive silicone antifoaming
# excipient, so v4 should keep scoring while carrying a warning-only signal.
SIMETHICONE_RECLASSIFIED_TO_WARNING_ONLY = {"33233", "33246", "37250"}


def test_v3_blocked_release_products_remain_v4_blocked() -> None:
    from score_supplements_v4 import score_product_v4

    release_ids = _load_release_ids()
    scored = _load_json_records("scripts/products/output_*_scored/scored/*.json")
    enriched = _load_json_records("scripts/products/output_*_enriched/enriched/*.json")

    blocked_ids = sorted(
        dsld_id
        for dsld_id in release_ids
        if (scored.get(dsld_id) or {}).get("verdict") == "BLOCKED"
    )
    assert blocked_ids, "release artifact should contain v3 BLOCKED canaries"

    failures = []
    for dsld_id in blocked_ids:
        product = enriched.get(dsld_id)
        if not product:
            failures.append((dsld_id, "missing enriched blob", None))
            continue
        out = score_product_v4(product)
        verdict = out.get("v4_verdict")
        if dsld_id in RED3_RECLASSIFIED_TO_CAUTION:
            # Intentional Red 3 reclassification: BLOCK → CAUTION. Still must WARN,
            # never silently downgrade to SAFE/POOR/None.
            if verdict != "CAUTION":
                failures.append((dsld_id, "red3-reclassified must remain CAUTION", verdict))
            continue
        if dsld_id in SIMETHICONE_RECLASSIFIED_TO_WARNING_ONLY:
            safety_gate = (out.get("v4_breakdown") or {}).get("safety_gate") or {}
            signals = set(safety_gate.get("safety_signals") or [])
            if (
                safety_gate.get("short_circuits_scoring")
                or "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY" not in signals
            ):
                failures.append((dsld_id, "simethicone inactive must be warning-only", safety_gate))
            continue
        if verdict != "BLOCKED":
            failures.append((
                dsld_id,
                product.get("brandName") or product.get("brand_name"),
                product.get("productName") or product.get("product_name") or product.get("fullName"),
                verdict,
                out.get("raw_score_v4_100"),
            ))

    assert failures == []


def test_excipient_acceptable_watchlist_warning_does_not_disqualify_safe() -> None:
    from build_final_db import blob_has_profile_gated_hard_safety_warning

    blob = {
        "warnings": [{
            "type": "watchlist_substance",
            "severity": "moderate",
            "ingredient_role": "inactive",
            "inactive_policy": "excipient_acceptable",
            "display_mode_default": "informational",
        }]
    }

    assert blob_has_profile_gated_hard_safety_warning(blob) is False


def test_active_watchlist_warning_still_disqualifies_safe() -> None:
    from build_final_db import blob_has_profile_gated_hard_safety_warning

    blob = {
        "warnings": [{
            "type": "watchlist_substance",
            "severity": "moderate",
            "ingredient_role": "active",
            "inactive_policy": "penalize_anyway",
            "display_mode_default": "informational",
        }]
    }

    assert blob_has_profile_gated_hard_safety_warning(blob) is True


# --------------------------------------------------------------------------- #
# Tier-1 parity extension (Phase B1): high_risk / watchlist substances matched
# via `token_bounded` must still drive CAUTION. v3 gives these CAUTION; v4
# previously skipped them because gate_safety._VERDICT_MATCH_TYPES only
# honored {exact, alias}, letting DHEA / Kava / HCA fall through to SAFE.
# Root cause confirmed via full-corpus delta (12 shipped CAUTION→SAFE).
# --------------------------------------------------------------------------- #

def _synthetic_substance_product(*, status: str, match_type: str,
                                 banned_id: str, name: str) -> dict:
    return {
        "dsld_id": "TEST_SYNTH",
        "product_name": f"Synthetic {name}",
        "contaminant_data": {
            "banned_substances": {
                "found": True,
                "substances": [
                    {
                        "ingredient": name,
                        "banned_name": name,
                        "banned_id": banned_id,
                        "status": status,
                        "match_type": match_type,
                        "match_method": match_type,
                    }
                ],
            }
        },
    }


def test_high_risk_token_bounded_substance_yields_caution() -> None:
    """DHEA-shaped hit (status=high_risk, match_type=token_bounded, real
    banned_id) must produce CAUTION, not fall through to SAFE."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _synthetic_substance_product(
        status="high_risk", match_type="token_bounded",
        banned_id="BANNED_DHEA", name="Dehydroepiandrosterone (DHEA)",
    )
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION", (
        f"high_risk token_bounded substance must yield CAUTION; got {result.verdict!r}"
    )
    assert "B0_HIGH_RISK_SUBSTANCE" in result.safety_signals


def test_watchlist_token_bounded_substance_yields_caution() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _synthetic_substance_product(
        status="watchlist", match_type="token_bounded",
        banned_id="RISK_EXAMPLE", name="Example Watchlist Botanical",
    )
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION", (
        f"watchlist token_bounded substance must yield CAUTION; got {result.verdict!r}"
    )


def test_exact_high_risk_still_yields_caution() -> None:
    """Regression guard: the existing exact-match CAUTION path is unchanged."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _synthetic_substance_product(
        status="high_risk", match_type="exact",
        banned_id="BANNED_DHEA", name="Dehydroepiandrosterone (DHEA)",
    )
    assert evaluate_safety_gate(product).verdict == "CAUTION"


def test_banned_token_bounded_not_auto_blocked_by_caution_fix() -> None:
    """Scoping guard: extending token_bounded to CAUTION must NOT silently
    promote banned+token_bounded to BLOCKED. A false hard-BLOCK is worse than
    a false CAUTION; the 8 banned+token_bounded corpus hits go to manual B1
    review, not auto-block. This test locks that scope decision."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _synthetic_substance_product(
        status="banned", match_type="token_bounded",
        banned_id="BANNED_EXAMPLE", name="Example Banned Token Match",
    )
    result = evaluate_safety_gate(product)
    assert result.verdict != "BLOCKED", (
        "banned+token_bounded must not auto-BLOCK (manual review); "
        f"got {result.verdict!r}"
    )
    assert result.needs_review is True
