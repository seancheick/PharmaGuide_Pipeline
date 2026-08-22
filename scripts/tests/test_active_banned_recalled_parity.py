"""
Active-side banned_recalled parity tests.

Counterpart to test_inactive_ingredient_resolver. The inactive fix
closed the gap where banned inactives shipped with no safety signal.
This suite locks in PARITY on the active path: every active ingredient
matching a banned_recalled rule (banned / high_risk / recalled) must
carry is_safety_concern=true on the blob. Watchlist actives must carry
at least an informational warning. Banned-status actives additionally
must carry is_banned=true.

The active path previously computed is_safety_concern from
``harmful_additives.json`` hits only. That missed Yohimbe (82 occurrences),
Cannabidiol (30), Garcinia Cambogia (11), Red Yeast Rice (9), Bitter
Orange, Cascara Sagrada, 7-Keto-DHEA, Vinpocetine, Tansy, Colloidal
Silver — all of which live in ``banned_recalled_ingredients.json``,
not ``harmful_additives.json``.

Tests:
  - test_banned_recalled_policy_signals
    (policy from source: banned → both signals, high_risk → concern only,
     generic Red Yeast Rice → concern only, explicit monacolin/lovastatin →
     banned, safe nutrients → neither)
  - test_banned_status_reaches_the_blob_from_source
    (propagation: source-built blob carries both signals)
  - test_no_banned_active_ships_with_severity_status_na
    (canary-corpus integration test)
  - test_active_parity_audit_clean
    (gate: scripts/audit_active_banned_recalled_parity.py exit 0)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.release_artifact_paths import catalog_dist_dir

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


_BUILD_CANDIDATES = (
    catalog_dist_dir(),
    # 2026-05-13: scripts/dist/ is the canonical current build (produced by
    # rebuild_dashboard_snapshot.sh + release_full.sh). Prefer it so the
    # audit reflects what's actually shipping. The /tmp/* paths below are
    # historical sandbox dirs that may carry stale data from prior runs.
    ROOT / "scripts" / "dist",
    Path("/tmp/pharmaguide_release_build_inactives"),
    Path("/tmp/pharmaguide_release_build_canonical_id"),
    Path("/tmp/pharmaguide_release_build_v3"),
    Path("/tmp/pharmaguide_release_build"),
)


def _find_build_dir() -> Path | None:
    for c in _BUILD_CANDIDATES:
        if (c / "detail_blobs").is_dir():
            return c
    return None


def _resolver():
    """The safety policy itself — the source these signals are derived from."""
    from inactive_ingredient_resolver import InactiveIngredientResolver

    return InactiveIngredientResolver()


# ---------------------------------------------------------------------------
# Policy, asserted from source
# ---------------------------------------------------------------------------
#
# These assertions used to read whichever generated build happened to be on
# disk and take the first matching blob alphabetically. That is not a statement
# about the code: when generic Red Yeast Rice moved from an automatic
# unapproved-drug block to a high-risk review, every blob in a fresh build
# followed and this file still failed against a build made before the change.
# The policy is deterministic from `banned_recalled_ingredients.json`, so assert
# it there. Artifact conformance stays with `test_active_parity_audit_clean`,
# which runs the real audit against a real build.


@pytest.mark.parametrize(
    "label,expect_banned,expect_concern",
    [
        # Generic RYR is a high-risk review, not an automatic unapproved-drug
        # block: monacolin K content ranges from none to substantial, and the
        # FDA prohibition addresses enhanced or added lovastatin.
        ("Red Yeast Rice", False, True),
        ("Red Yeast Rice Powder", False, True),
        # Explicit statin evidence is what blocks.
        ("Red Yeast Rice Extract (Monacolin K)", True, True),
        ("Monacolin K", True, True),
        ("Lovastatin", True, True),
        # banned status implies both signals
        ("Cannabidiol", True, True),
        # high_risk status implies concern only
        ("Yohimbe", False, True),
        ("Garcinia Cambogia", False, True),
        # regression: safe nutrients must stay unflagged
        ("Vitamin C", False, False),
        ("Calcium Carbonate", False, False),
    ],
)
def test_banned_recalled_policy_signals(label, expect_banned, expect_concern) -> None:
    r = _resolver().resolve(raw_name=label)
    assert bool(r.is_banned) is expect_banned, (
        f"{label}: is_banned={r.is_banned!r} via {r.matched_rule_id!r}"
    )
    assert bool(r.is_safety_concern) is expect_concern, (
        f"{label}: is_safety_concern={r.is_safety_concern!r} via {r.matched_rule_id!r}"
    )


def test_banned_status_reaches_the_blob_from_source() -> None:
    """Propagation: a banned active must carry both blob signals.

    Built from source rather than discovered on disk, so a stale artifact can
    neither pass nor fail it.
    """
    from build_final_db import build_detail_blob
    from test_inactive_active_form_duplicate_2026_06 import (
        _enriched,
        _scored_minimal,
    )

    enriched = _enriched(
        active=[{
            "name": "Cannabidiol",
            "standardName": "Cannabidiol",
            "canonical_id": "cannabidiol",
        }],
        inactive=[],
        product_name="Banned Active Propagation Canary",
    )
    blob = build_detail_blob(enriched, _scored_minimal())
    row = next(
        ing for ing in blob["ingredients"]
        if "cannabidiol" in str(ing.get("name") or "").lower()
    )
    assert row.get("is_banned") is True, row
    assert row.get("is_safety_concern") is True, row


# ---------------------------------------------------------------------------

def test_active_parity_audit_clean() -> None:
    """The audit script must exit 0 (no BLOCKER or HIGH findings) against
    any build dir we can find. This is the release-gate test — locks in
    the architectural invariant for all future builds."""
    base = _find_build_dir()
    if base is None:
        pytest.skip("no build dir available")
    out = ROOT / "reports" / "audit_active_parity_test_output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_active_banned_recalled_parity.py"),
         "--build-dir", str(base), "--out", str(out)],
        capture_output=True,
    )
    if r.returncode != 0:
        # Parse the report and surface the specific gaps so the failure
        # message tells the next reader what's wrong.
        try:
            report = json.loads(out.read_text())
            summary = report.get("summary", {})
            examples = report.get("examples_by_severity", {})
            sample = []
            for sev in ("BLOCKER", "HIGH"):
                for ex in (examples.get(sev) or [])[:3]:
                    sample.append(f"  [{sev}] {ex.get('dsld_id')} | {ex.get('ingredient')!r} "
                                  f"status={ex.get('banned_status')} rule={ex.get('matched_rule_id')}")
            pytest.fail(
                f"active-side banned_recalled parity audit FAILED.\n"
                f"  summary: {summary}\n"
                f"  first samples:\n" + "\n".join(sample) + "\n"
                f"  full report: {out}\n"
                f"  stderr: {r.stderr.decode()[:300]}"
            )
        except Exception:
            pytest.fail(
                f"audit exited {r.returncode} but report unparseable. "
                f"stderr: {r.stderr.decode()[:500]}"
            )


def test_no_banned_active_ships_with_severity_status_na() -> None:
    """Architectural invariant: no active ingredient matching a banned_recalled
    rule may carry severity_status='n/a' (or its absence) when status is
    in {banned, high_risk, recalled}. Catches regressions even if the
    audit script grows but specific behavior changes."""
    base = _find_build_dir()
    if base is None:
        pytest.skip("no build dir available")
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver, _normalize
    resolver = InactiveIngredientResolver()
    banned_index = {}
    for e in resolver.iter_banned_recalled_entries_for_audit():
        for n in [e.get("standard_name")] + (e.get("aliases") or []):
            if isinstance(n, str):
                t = _normalize(n)
                if t and t not in banned_index:
                    banned_index[t] = e

    violations = []
    for p in sorted((base / "detail_blobs").glob("*.json"))[:300]:
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        for ing in b.get("ingredients") or []:
            terms = [_normalize(ing.get(k)) for k in ("name", "raw_source_text", "standard_name")]
            entry = None
            for t in terms:
                if t and t in banned_index:
                    entry = banned_index[t]
                    break
            if not entry:
                continue
            status = (entry.get("status") or "").lower()
            if status not in ("banned", "high_risk", "recalled"):
                continue
            if not bool(ing.get("is_safety_concern")):
                violations.append({
                    "dsld_id": b.get("dsld_id"),
                    "ingredient": ing.get("name"),
                    "status": status,
                    "rule_id": entry.get("id"),
                })
            if len(violations) >= 5:
                break
        if len(violations) >= 5:
            break

    assert not violations, (
        "actives matching banned_recalled (banned/high_risk/recalled) "
        f"missing is_safety_concern=true. First 5: {violations}"
    )
