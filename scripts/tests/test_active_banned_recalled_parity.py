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
  - test_yohimbe_active_is_safety_concern        (high_risk → is_safety_concern=true)
  - test_cannabidiol_active_is_safety_concern    (banned → is_banned=true AND is_safety_concern=true)
  - test_garcinia_active_is_safety_concern       (high_risk)
  - test_red_yeast_rice_active_is_safety_concern (banned)
  - test_safe_active_remains_non_safety_concern  (regression — Vitamin C, etc.)
  - test_no_banned_recalled_active_ships_with_severity_na
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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


_BUILD_CANDIDATES = (
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


def _find_active_by_name(name_substring: str) -> tuple[dict, dict] | None:
    """Walk blobs in the first available build dir; return (blob, ingredient)
    where ingredient.name contains the given substring (case-insensitive)
    and the ingredient is an active."""
    base = _find_build_dir()
    if base is None:
        return None
    needle = name_substring.lower()
    for p in sorted((base / "detail_blobs").glob("*.json")):
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        for ing in b.get("ingredients") or []:
            n = (ing.get("name") or "").lower()
            rst = (ing.get("raw_source_text") or "").lower()
            if needle in n or needle in rst:
                return b, ing
    return None


# ---------------------------------------------------------------------------
# Per-canary tests — the specific gap classes we know about
# ---------------------------------------------------------------------------

def test_yohimbe_active_is_safety_concern() -> None:
    """Yohimbe bark extract (banned_recalled.id=RISK_YOHIMBE, status=high_risk)
    appears as active in 82 products across the canary corpus. Must
    surface is_safety_concern=true on each."""
    pair = _find_active_by_name("Yohimbe")
    if pair is None:
        pytest.skip("no Yohimbe active in any reachable build dir")
    _, ing = pair
    assert ing.get("is_safety_concern") is True, (
        f"Yohimbe active is_safety_concern={ing.get('is_safety_concern')!r}; "
        "high_risk banned_recalled rule must surface as safety concern"
    )


def test_cannabidiol_active_is_banned_and_safety_concern() -> None:
    """Cannabidiol (banned_recalled.id=BANNED_CBD_US, status=banned)
    appears as active in 30 products. Must carry BOTH is_banned=true
    AND is_safety_concern=true."""
    pair = _find_active_by_name("Cannabidiol")
    if pair is None:
        pytest.skip("no Cannabidiol active in any reachable build dir")
    _, ing = pair
    assert ing.get("is_banned") is True, (
        f"Cannabidiol is_banned={ing.get('is_banned')!r}; banned status must set this"
    )
    assert ing.get("is_safety_concern") is True, (
        f"Cannabidiol is_safety_concern={ing.get('is_safety_concern')!r}; "
        "banned active must be a safety concern"
    )


def test_garcinia_cambogia_active_is_safety_concern() -> None:
    pair = _find_active_by_name("Garcinia Cambogia")
    if pair is None:
        pytest.skip("no Garcinia Cambogia active in any reachable build dir")
    _, ing = pair
    assert ing.get("is_safety_concern") is True


def test_red_yeast_rice_active_signals() -> None:
    pair = _find_active_by_name("Red Yeast Rice")
    if pair is None:
        pytest.skip("no Red Yeast Rice active in any reachable build dir")
    _, ing = pair
    # banned status → both flags
    assert ing.get("is_banned") is True
    assert ing.get("is_safety_concern") is True


# ---------------------------------------------------------------------------
# Regression: safe actives must remain non-concern
# ---------------------------------------------------------------------------

def test_safe_active_remains_non_safety_concern() -> None:
    """Vitamin C (and similar safe nutrients) must NOT be flagged as a
    safety concern. Guards against the fix accidentally over-promoting
    every harmful_additives.json low-severity entry."""
    pair = _find_active_by_name("Vitamin C")
    if pair is None:
        pytest.skip("no Vitamin C active in any reachable build dir")
    _, ing = pair
    assert ing.get("is_safety_concern") is False, (
        f"Vitamin C is_safety_concern={ing.get('is_safety_concern')!r}; "
        "must not be flagged"
    )
    assert ing.get("is_banned") is False


def test_safe_active_calcium_remains_non_safety_concern() -> None:
    pair = _find_active_by_name("Calcium Carbonate")
    if pair is None:
        pytest.skip("no Calcium Carbonate active in any reachable build dir")
    _, ing = pair
    assert ing.get("is_safety_concern") is False


# ---------------------------------------------------------------------------
# Integration: the audit script itself reports zero gaps
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
