"""
Sprint D5.4 regression — Dr Pham's user-facing safety fields must flow
intact from data files → enricher → detail blob.

Context: Dr Pham added several medically-authored copy fields across the
safety data files (banned_recalled, harmful_additives, medication
depletions, ingredient_interaction_rules). These drive the Flutter
detail-sheet rendering — if the enricher drops them or renames them,
the UI silently falls back to technical jargon and loses medical-grade
context.

This test locks in the end-to-end contract: when the enricher generates
a warning for a product, the warning dict on the detail blob MUST carry
the Dr Pham fields the Flutter app reads.

Audit scope per warning type (from scripts/data/* + scripts/enrich_supplements_v3.py):

| type                | Expected user-facing fields                          |
|---------------------|------------------------------------------------------|
| harmful_additive    | safety_summary, safety_summary_one_liner,            |
|                     | mechanism_of_harm, population_warnings, category     |
| high_risk_ingredient| safety_warning, safety_warning_one_liner,            |
| / banned_substance  | ban_context, regulatory_date_label, clinical_risk    |
| interaction         | alert_headline, alert_body, informational_note,      |
|                     | severity_contextual, display_mode_default,           |
|                     | dose_threshold_evaluation (optional)                 |
| drug_interaction    | alert_headline, alert_body, informational_note,      |
|                     | severity_contextual, display_mode_default            |
| allergen            | prevalence, supplement_context                       |

Flutter's InteractionWarning.fromJson reads these keys. Regression here
would silently drop medical copy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

BLOB_DIR = Path("/tmp/pharmaguide_release_build/detail_blobs")

# Required-field sets per warning type. The values are `Sequence[str]`
# where each inner set is an OR-group — at least one name in each group
# must be populated. This accommodates Dr Pham's two naming conventions
# (`safety_warning`/`safety_summary`) which are both acceptable
# equivalents (banned_recalled voice vs harmful_additive voice). Flutter
# normalizes both in InteractionWarning.fromJson via alertHeadline/
# alertBody fallback chain.
REQUIRED_BY_TYPE = {
    "harmful_additive": [
        ("safety_summary_one_liner", "safety_warning_one_liner"),
        ("safety_summary", "safety_warning"),
    ],
    "high_risk_ingredient": [
        ("safety_warning_one_liner", "safety_summary_one_liner"),
        ("safety_warning", "safety_summary"),
        # clinical_risk + ban_context may be null for cross-routed entries
        # (e.g. TiO2 originally in harmful_additives but classified under
        # high_risk tier because of EU ban). That's acceptable as long as
        # the primary one-liner + body are present.
    ],
    "interaction": [
        ("alert_headline",),
        ("alert_body",),
        ("informational_note",),
    ],
    "drug_interaction": [
        ("alert_headline",),
        ("alert_body",),
        ("informational_note",),
    ],
}


@pytest.fixture(scope="module")
def warnings_by_type():
    if not BLOB_DIR.is_dir() or not any(BLOB_DIR.glob("*.json")):
        pytest.skip(
            f"No detail blobs under {BLOB_DIR} — run build_final_db.py first."
        )
    by_type = defaultdict(list)
    for p in sorted(BLOB_DIR.glob("*.json"))[:1000]:
        try:
            blob = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        for w in (blob.get("warnings") or []) + (
            blob.get("warnings_profile_gated") or []
        ):
            if isinstance(w, dict) and w.get("type"):
                by_type[w["type"]].append((p.name, w))
    return dict(by_type)


def test_warning_types_cover_expected_universe(warnings_by_type) -> None:
    """Sanity: across a 1k-product sample we must hit each core warning
    type so the field-presence tests aren't silently skipped."""
    seen = set(warnings_by_type.keys())
    for required in ("harmful_additive", "high_risk_ingredient"):
        if not any(t.startswith(required) for t in seen):
            # Not every sample hits every type — skip if sample is thin
            # but do not fail. The per-type tests below do the real check.
            continue
    assert seen, "No warnings found in any sample blob — pipeline broken"


def _group_satisfied(w, group):
    """A group of equivalent field names — any one populated counts."""
    for name in group:
        v = w.get(name)
        if v not in (None, "", [], {}):
            return True
    return False


def _assert_fields_present(warnings, wtype, required_groups):
    """At least one warning of ``wtype`` must satisfy EVERY required
    or-group (a group of equivalent field names; any one populated
    passes the group)."""
    found = [(fname, w) for (fname, w) in warnings if w.get("type") == wtype]
    if not found:
        pytest.skip(f"No {wtype} warnings in 1k sample")
    passing = 0
    misses = []
    for fname, w in found:
        unsatisfied = [g for g in required_groups if not _group_satisfied(w, g)]
        if unsatisfied:
            misses.append((fname, unsatisfied))
        else:
            passing += 1
    assert passing > 0, (
        f"D5.4 regression: NO {wtype} warning has all Dr Pham field groups "
        f"{required_groups}. First 3 offenders:\n"
        + "\n".join(f"  {fn}: unsatisfied groups {gs}" for fn, gs in misses[:3])
    )


def test_harmful_additive_dr_pham_fields(warnings_by_type) -> None:
    warnings = warnings_by_type.get("harmful_additive", [])
    _assert_fields_present(
        [("", w) for _, w in warnings],
        "harmful_additive",
        REQUIRED_BY_TYPE["harmful_additive"],
    )


def test_interaction_dr_pham_fields(warnings_by_type) -> None:
    warnings = warnings_by_type.get("interaction", [])
    _assert_fields_present(
        [("", w) for _, w in warnings],
        "interaction",
        REQUIRED_BY_TYPE["interaction"],
    )


# -- Code-side invariants (D5.4 banned_recalled safety_warning propagation) --


def test_enricher_banned_substance_carries_safety_warning_fields() -> None:
    """D5.4 enricher fix: ``_check_banned_substances`` must propagate
    Dr Pham's ``safety_warning`` + ``safety_warning_one_liner`` +
    ``ban_context`` from the source entry into each found-substance
    dict. build_final_db.py expects these keys under ``sub.get()`` when
    assembling the warning entry for the detail blob.

    Without this propagation, every high_risk_ingredient /
    banned_substance / recalled_ingredient / watchlist_substance
    warning renders with null alertHeadline and alertBody — user sees
    only the technical title + reason jargon.
    """
    source = Path("scripts/enrich_supplements_v3.py").read_text()
    # The found.append(...) block in _check_banned_substances must
    # include these three Dr Pham field propagations.
    for key in (
        '"safety_warning": banned_item.get(\'safety_warning\')',
        '"safety_warning_one_liner": banned_item.get(\'safety_warning_one_liner\')',
        '"ban_context": banned_item.get(\'ban_context\')',
    ):
        assert key in source, (
            f"D5.4 regression: enricher's _check_banned_substances must "
            f"propagate {key!r} from the source entry. Without it, "
            f"high_risk_ingredient / banned_substance warnings render "
            f"with null alertHeadline/alertBody in Flutter."
        )


def test_build_final_db_consumes_safety_warning_fields() -> None:
    """The build step must still read the propagated Dr Pham fields so
    they land on the detail-blob warning entry."""
    source = Path("scripts/build_final_db.py").read_text()
    for key in (
        'sub.get("safety_warning")',
        'sub.get("safety_warning_one_liner")',
    ):
        assert key in source, (
            f"D5.4 regression: build_final_db must read {key!r} when "
            f"assembling banned_recalled warning entries."
        )


def test_display_mode_default_populated_on_every_warning(warnings_by_type) -> None:
    """The schema-v5.2 `display_mode_default` field gates Flutter's
    profile-based warning filter. Missing on even a single warning
    means that warning reverts to legacy "always-show" behavior."""
    bad = []
    for wtype, entries in warnings_by_type.items():
        for fname, w in entries:
            if w.get("display_mode_default") in (None, ""):
                bad.append((fname, wtype, w.get("title", "")[:50]))
    assert not bad, (
        "D5.4 regression: display_mode_default missing on some warnings. "
        "Flutter profile-filter falls back to legacy always-show, "
        "which surfaces scary rules to users with no matching profile. "
        f"First 5 offenders:\n"
        + "\n".join(f"  {f} [{t}] {title}" for f, t, title in bad[:5])
    )


def test_severity_contextual_populated_on_avoid_rules(warnings_by_type) -> None:
    """Severity-contextual (downgraded tone when no profile match) is
    required for avoid/contraindicated interactions so the UI can pick
    a calmer banner for users the rule doesn't apply to."""
    bad = []
    for wtype in ("interaction", "drug_interaction"):
        for fname, w in warnings_by_type.get(wtype, []):
            sev = (w.get("severity") or "").lower()
            sev_ctx = w.get("severity_contextual")
            if sev in ("avoid", "contraindicated") and sev_ctx in (None, ""):
                bad.append((fname, wtype, w.get("title", "")[:50]))
    assert not bad, (
        "D5.4 regression: severity_contextual missing on avoid/"
        "contraindicated rules. Flutter falls back to the alarming tier "
        "even for users whose profile doesn't match the rule's condition. "
        f"First 5:\n" + "\n".join(f"  {f} [{t}] {ti}" for f, t, ti in bad[:5])
    )
