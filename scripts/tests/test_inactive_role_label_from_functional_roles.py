"""
Regression suite for inactive_ingredients.display_role_label fallback
to functional_roles.

Phase 1 audit reported 7,281 inactives missing display_role_label across
the targeted 3-brand build (27% of all inactives). Investigation showed:

  - All 7,281 had additive_type=(none), severity_level=(none),
    category=(none) — never matched against harmful_additives.json.
  - 4,139 of those had populated functional_roles populated by the
    cleaner: sweetener_artificial, filler, colorant_artificial,
    anti_caking_agent+glidant, flavor_artificial, emulsifier+surfactant,
    sweetener_natural, sweetener_sugar_alcohol, disintegrant, ...
  - The remaining 3,142 had functional_roles=['(none)'] — truly
    unclassified; correctly emit None.

Root cause: _compute_inactive_role_label only inspected additive_type +
category from the ingredient and the IQM `other_ref` lookup. It never
fell through to functional_roles, which the cleaner uses for many
inactives that don't appear in harmful_additives.json (any non-
hazardous excipient: sweeteners, fillers, flavorings).

Fix: append functional_roles[0] as the lowest-priority candidate. The
existing snake_case → "Title case" fallback handles cases where the
role token isn't yet in the curated _INACTIVE_ROLE_LABELS table.

Tests:
  - Functional roles that ARE in the curated table render their label.
  - Functional roles NOT in the curated table render via snake-case
    prettifier.
  - Empty / sentinel functional_roles stay None (correct behavior).
  - additive_type wins over functional_roles when both are present.
  - Blob-level canary: post-rebuild, inactive coverage rate climbs
    well above the 73% baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _role(ing: dict, other_ref: dict | None = None) -> str | None:
    """Invoke build_final_db._compute_inactive_role_label directly."""
    from scripts.build_final_db import _compute_inactive_role_label
    return _compute_inactive_role_label(ing, other_ref or {})


# ---------------------------------------------------------------------------
# Direct function-level tests
# ---------------------------------------------------------------------------

def test_curated_functional_role_uses_curated_label() -> None:
    """A functional_role value that exists in _INACTIVE_ROLE_LABELS must
    render its curated user-friendly label, not the snake-case fallback."""
    ing = {
        "name": "Microcrystalline Cellulose",
        "additive_type": None,
        "category": None,
        "functional_roles": ["filler"],
    }
    assert _role(ing) == "Filler"


def test_curated_anti_caking_role() -> None:
    ing = {
        "name": "Silicon Dioxide",
        "functional_roles": ["anti_caking_agent", "glidant"],
    }
    # The function picks the first functional_role and looks it up.
    assert _role(ing) == "Anti-caking agent"


def test_uncurated_functional_role_uses_snake_case_fallback() -> None:
    """A functional_role token not yet in _INACTIVE_ROLE_LABELS still
    renders something readable via the snake_case → Title-case fallback.
    sweetener_artificial → 'Sweetener artificial'."""
    ing = {
        "name": "Acesulfame Potassium",
        "functional_roles": ["sweetener_artificial"],
    }
    result = _role(ing)
    assert result is not None
    # Either curated ("Sweetener (artificial)") or fallback ("Sweetener artificial").
    assert "sweetener" in result.lower()
    assert "artificial" in result.lower()


def test_uncurated_colorant_artificial() -> None:
    ing = {"name": "Red 40", "functional_roles": ["colorant_artificial"]}
    result = _role(ing)
    assert result is not None
    assert "colorant" in result.lower() or "color" in result.lower()


def test_empty_functional_roles_still_returns_none() -> None:
    """When everything is empty/none, return None (correct behavior —
    Flutter renders no role label and the entry shows up as plain text
    in 'Other ingredients')."""
    ing = {
        "name": "Mystery Excipient",
        "additive_type": None,
        "category": None,
        "functional_roles": [],
    }
    assert _role(ing) is None


def test_sentinel_none_in_functional_roles_returns_none() -> None:
    """Cleaner sometimes emits ['(none)'] as a placeholder. Treat as empty."""
    ing = {
        "name": "Truly Unknown Inactive",
        "functional_roles": ["(none)"],
    }
    result = _role(ing)
    # Either None (preferred — sentinel filtered) or "(none)" (acceptable
    # but ugly). Lock in the preferred behavior: filter sentinel values.
    assert result != "(none)", (
        f"sentinel '(none)' leaked into display_role_label as {result!r}"
    )


def test_additive_type_wins_over_functional_roles() -> None:
    """If both additive_type AND functional_roles are populated, the
    more-specific additive_type (curated against harmful_additives.json
    or similar) wins. Ensures we don't regress the existing precedence."""
    ing = {
        "name": "Gelatin",
        "additive_type": "capsule_shell",
        "functional_roles": ["filler"],  # incorrect/general
    }
    # The curated label for capsule_shell beats filler.
    assert _role(ing) == "Gelatin capsule" or _role(ing) == "Capsule shell"


def test_other_ref_category_wins_over_functional_roles() -> None:
    """The IQM other_ref lookup is more authoritative than the cleaner's
    bag-of-roles classification."""
    ing = {"name": "X", "functional_roles": ["filler"]}
    other_ref = {"additive_type": "preservative"}
    assert _role(ing, other_ref) == "Preservative"


# ---------------------------------------------------------------------------
# Blob-level canary
# ---------------------------------------------------------------------------

_BUILD_CANDIDATES = (
    Path("/tmp/pharmaguide_release_build_canonical_id"),
    Path("/tmp/pharmaguide_release_build_v3"),
    Path("/tmp/pharmaguide_release_build"),
)


def test_addressable_inactives_get_role_label() -> None:
    """Stronger assertion than overall coverage: any inactive whose
    blob has populated ``functional_roles`` MUST carry a non-empty
    ``display_role_label``. This is the contract the fix guarantees —
    the resolution chain is symmetric between the two fields, so when
    one is set the other must be too.

    100% pass on this test, regardless of overall coverage. Anything
    less is a fix regression.
    """
    base = next((p for p in _BUILD_CANDIDATES if (p / "detail_blobs").is_dir()), None)
    if base is None:
        pytest.skip("no build directory available — run targeted rebuild first")

    addressable = 0
    labeled = 0
    misses: list[tuple[str, str, list]] = []
    for p in sorted((base / "detail_blobs").glob("*.json"))[:400]:
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        for ing in b.get("inactive_ingredients") or []:
            fr = ing.get("functional_roles") or []
            # An "addressable" inactive has functional_roles with at
            # least one non-sentinel entry.
            usable = any(
                isinstance(s, str) and s.strip() and s.strip().lower() not in {"(none)", "none", "unknown"}
                for s in fr
            )
            if not usable:
                continue
            addressable += 1
            if ing.get("display_role_label"):
                labeled += 1
            else:
                if len(misses) < 5:
                    misses.append((b.get("dsld_id"), ing.get("name"), fr))

    if addressable == 0:
        pytest.skip("no addressable inactives in sample")
    assert labeled == addressable, (
        f"{addressable - labeled}/{addressable} inactives have functional_roles "
        f"but no display_role_label — the resolution chain is misaligned. First 5:\n"
        + "\n".join(f"  [{did}] {name!r} fr={fr}" for did, name, fr in misses)
    )


def test_inactive_role_label_coverage_above_85_percent() -> None:
    """Overall coverage floor. Pre-fix baseline was 73%. Post-fix should
    be ≥85%. The remaining ≤15% are inactives whose names the cleaner
    can't classify (rare excipients, label fragments, items that should
    actually be ACTIVE but ended up in inactive_ingredients[]). Those
    are upstream cleaner / reference-data gaps — separate from this
    blob-builder fix.

    Known unclassified at audit-time (2026-05-12, GNC+CVS+DoctorsBest
    sample): Titanium Dioxide, Talc, Fish Body Oil, Riboflavin,
    Phytonadione, Vitamin E. These need:
      - harmful_additives.json entries for Titanium Dioxide + Talc
      - cleaner reclassification for Riboflavin / Vitamin E /
        Phytonadione (currently leaking from active → inactive)
    See follow-up audit ticket.
    """
    base = next((p for p in _BUILD_CANDIDATES if (p / "detail_blobs").is_dir()), None)
    if base is None:
        pytest.skip("no build directory available — run targeted rebuild first")

    total = 0
    present = 0
    for p in sorted((base / "detail_blobs").glob("*.json"))[:400]:
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        for ing in b.get("inactive_ingredients") or []:
            total += 1
            if ing.get("display_role_label"):
                present += 1

    if total == 0:
        pytest.skip("no inactive_ingredients in sample")
    rate = present / total
    assert rate >= 0.85, (
        f"only {present}/{total} ({rate:.1%}) inactives carry display_role_label "
        f"in first 400 blobs at {base} — pre-fix baseline was 73%, expected ≥85% post-fix"
    )
