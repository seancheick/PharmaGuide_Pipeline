"""Metadata + runtime-config contract for `manufacture_deduction_expl.json`.

DESPITE THE NAME, this file is NOT explanation-only. It is the
canonical runtime config for manufacturer trust-score deductions,
consumed by:

* ``scripts/api_audit/fda_manufacturer_violations_sync.py``:
  - ``lookup_base_deduction(code)`` reads
    ``violation_categories.*.subcategories.*.{code,base_deduction}``
  - ``recency_multiplier(days_since)`` reads ``modifiers.RECENCY.ranges``
  - ``build_repeat_violation_lookup(...)`` reads
    ``modifiers.REPEAT_VIOLATIONS.trigger``
  - ``compute_modifier_extras(...)`` reads
    ``modifiers.UNRESOLVED_VIOLATIONS.additional_deduction`` etc.

* ``scripts/db_integrity_sanity_check.check_manufacture_deduction_expl``
  validates the top-level structure (cap + 4 severity tiers).

* ``scripts/preflight.py`` lists it as a required data file.

The ``description`` / ``examples`` fields ARE human-readable documentation
(not consumed by code). The rest is live config — drift between the JSON
and the runtime is a real defect.

This test pins the runtime invariants the consumers above depend on.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "manufacture_deduction_expl.json"

REQUIRED_SEVERITY_TIERS = ("CRITICAL", "HIGH", "MODERATE", "LOW")
REQUIRED_MODIFIERS = (
    "RECENCY",
    "REPEAT_VIOLATIONS",
    "UNRESOLVED_VIOLATIONS",
    "MULTIPLE_PRODUCT_LINES",
)


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Metadata invariants
# ---------------------------------------------------------------------------


def test_total_entries_tracks_top_level_section_count(blob):
    """``_metadata.total_entries`` tracks the count of top-level
    non-``_metadata`` sub-sections — meta=5 today (total_deduction_cap,
    violation_categories, modifiers, calculation_rules, score_thresholds).
    Adding or removing a top-level section is a schema change."""
    non_meta = [k for k in blob.keys() if k != "_metadata"]
    expected = len(non_meta)
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but there are {expected} "
        f"top-level non-_metadata sub-sections: {non_meta}. "
        f"Bump total_entries to {expected}."
    )


def test_required_top_level_sections_are_present(blob):
    """Defensive: the scoring engine reads each of these by name. If one
    disappears, manufacturer deduction breaks at runtime."""
    required = {
        "total_deduction_cap",
        "violation_categories",
        "modifiers",
        "calculation_rules",
        "score_thresholds",
    }
    missing = required - set(blob.keys())
    assert not missing, f"required top-level sections missing: {missing}"


# ---------------------------------------------------------------------------
# Runtime-config invariants (live values consumed by the deduction sync)
# ---------------------------------------------------------------------------


def test_total_deduction_cap_is_negative_number(blob):
    """The cap is the lower bound on total deduction; must be a negative
    number so it bounds the sum of negative deductions."""
    cap = blob["total_deduction_cap"]
    assert isinstance(cap, (int, float)), f"total_deduction_cap must be numeric, got {type(cap).__name__}"
    assert cap < 0, f"total_deduction_cap must be negative (it's a floor on deductions), got {cap}"


def test_all_four_severity_tiers_present(blob):
    """The deduction model has 4 severity tiers — adding a 5th or removing
    one is a schema change that requires every consumer to update."""
    vc = blob["violation_categories"]
    missing = [t for t in REQUIRED_SEVERITY_TIERS if t not in vc]
    assert not missing, f"missing severity tiers: {missing}"


def test_every_subcategory_has_code_and_base_deduction(blob):
    """``lookup_base_deduction(code)`` in fda_manufacturer_violations_sync.py
    walks ``violation_categories.*.subcategories.*`` looking for matching
    ``code`` then returns ``base_deduction``. Either field missing means a
    silent fallback to the Python-side VIOLATION_CODE_MAP default of -10."""
    problems = []
    for sev, body in blob["violation_categories"].items():
        if not isinstance(body, dict):
            problems.append(f"{sev}: not a dict")
            continue
        subs = body.get("subcategories", {})
        for sub_id, sub in subs.items():
            if not isinstance(sub, dict):
                problems.append(f"{sev}.{sub_id}: not a dict")
                continue
            if "code" not in sub or not isinstance(sub["code"], str):
                problems.append(f"{sev}.{sub_id}: missing or non-string 'code'")
            base = sub.get("base_deduction")
            if not isinstance(base, (int, float)):
                problems.append(
                    f"{sev}.{sub_id}: missing or non-numeric 'base_deduction' "
                    f"(got {type(base).__name__})"
                )
            elif base > 0:
                problems.append(
                    f"{sev}.{sub_id}: base_deduction must be ≤ 0 "
                    f"(it's a deduction), got {base}"
                )
    assert not problems, "subcategory schema violations:\n  " + "\n  ".join(problems[:10])


def test_violation_codes_are_unique(blob):
    """``code`` is the lookup key — duplicates would cause
    lookup_base_deduction to return whichever subcategory the dict iteration
    happens to hit first. Duplicates are a bug."""
    seen: dict[str, str] = {}
    dupes: list[tuple[str, str, str]] = []
    for sev, body in blob["violation_categories"].items():
        subs = body.get("subcategories", {}) if isinstance(body, dict) else {}
        for sub_id, sub in subs.items():
            code = sub.get("code") if isinstance(sub, dict) else None
            if not code:
                continue
            if code in seen:
                dupes.append((code, seen[code], f"{sev}.{sub_id}"))
            else:
                seen[code] = f"{sev}.{sub_id}"
    assert not dupes, f"duplicate violation codes: {dupes}"


def test_all_four_required_modifiers_present_with_expected_shape(blob):
    """Each modifier carries a different sub-shape but the consumer code in
    fda_manufacturer_violations_sync.py reads specific sub-keys from each."""
    mods = blob["modifiers"]
    missing = [m for m in REQUIRED_MODIFIERS if m not in mods]
    assert not missing, f"missing required modifiers: {missing}"

    # RECENCY needs `ranges` (recency_multiplier reads it)
    assert isinstance(mods["RECENCY"].get("ranges"), dict), (
        "modifiers.RECENCY.ranges must be a dict — recency_multiplier reads it"
    )
    # REPEAT_VIOLATIONS needs `trigger` (build_repeat_violation_lookup reads it)
    assert isinstance(mods["REPEAT_VIOLATIONS"].get("trigger"), str), (
        "modifiers.REPEAT_VIOLATIONS.trigger must be a string — "
        "build_repeat_violation_lookup parses it for lookback windows"
    )
    # UNRESOLVED_VIOLATIONS needs `additional_deduction` (compute_modifier_extras reads it)
    assert isinstance(mods["UNRESOLVED_VIOLATIONS"].get("additional_deduction"), (int, float)), (
        "modifiers.UNRESOLVED_VIOLATIONS.additional_deduction must be numeric"
    )


# ---------------------------------------------------------------------------
# v2.1 additions (Phase 1 of 2026-05-13 deduction-expl proposal, 2026-05-14)
# Pin the new CRITICAL codes + PEDIATRIC_SUPPLEMENT modifier so a future
# refactor can't drop them silently.
# ---------------------------------------------------------------------------


# Code → (severity tier, expected base_deduction). The base_deduction values
# are scoring decisions; pinning them here makes accidental tuning visible.
V2_1_NEW_CODES = {
    "CRI_GLP1":     ("CRITICAL", -18),
    "CRI_ANABOLIC": ("CRITICAL", -18),
    "CRI_BOT_SUB":  ("CRITICAL", -20),
}


def _find_code(blob, target_code):
    """Return the subcategory dict for ``target_code``, or None."""
    for sev, body in blob["violation_categories"].items():
        for sub_id, sub in (body.get("subcategories") or {}).items():
            if isinstance(sub, dict) and sub.get("code") == target_code:
                return sev, sub_id, sub
    return None


@pytest.mark.parametrize("code,expected", list(V2_1_NEW_CODES.items()))
def test_v2_1_new_critical_codes_present(blob, code, expected):
    """v2.1 added 3 new CRITICAL subcategories. Each must be present under
    the expected severity tier with the expected base_deduction. If you
    change either, that's a deliberate scoring change — bump version and
    document in the proposal handoff doc."""
    expected_tier, expected_base = expected
    found = _find_code(blob, code)
    assert found is not None, (
        f"v2.1 violation code {code!r} missing from violation_categories. "
        f"See docs/handoff/2026-05-13_deduction_expl_proposal.md Phase 1."
    )
    tier, sub_id, sub = found
    assert tier == expected_tier, (
        f"{code!r} found under tier {tier!r}, expected {expected_tier!r}"
    )
    assert sub.get("base_deduction") == expected_base, (
        f"{code!r}: base_deduction={sub.get('base_deduction')}, "
        f"expected {expected_base}"
    )


def test_pediatric_supplement_modifier_present(blob):
    """v2.1 added the PEDIATRIC_SUPPLEMENT modifier (-3) for products
    targeting children, infants, or prenatal use. Required shape:
    `additional_deduction` numeric, `trigger` string."""
    mods = blob["modifiers"]
    assert "PEDIATRIC_SUPPLEMENT" in mods, (
        "v2.1 added PEDIATRIC_SUPPLEMENT modifier — must be present. "
        "See docs/handoff/2026-05-13_deduction_expl_proposal.md Phase 1."
    )
    m = mods["PEDIATRIC_SUPPLEMENT"]
    assert isinstance(m.get("additional_deduction"), (int, float)), (
        "PEDIATRIC_SUPPLEMENT.additional_deduction must be numeric"
    )
    assert m["additional_deduction"] == -3, (
        f"PEDIATRIC_SUPPLEMENT.additional_deduction expected -3, "
        f"got {m['additional_deduction']}. Change is a deliberate "
        f"scoring decision — bump version + document."
    )
    assert isinstance(m.get("trigger"), str) and m["trigger"], (
        "PEDIATRIC_SUPPLEMENT.trigger must be a non-empty string"
    )


def test_version_at_or_above_2_1(blob):
    """v2.1 is the minimum version that includes the proposal-Phase-1 codes.
    Older versions are missing CRI_GLP1/CRI_ANABOLIC/CRI_BOT_SUB and the
    pediatric modifier."""
    ver = blob["_metadata"].get("version", "0.0")
    parts = tuple(int(p) for p in ver.split("."))
    assert parts >= (2, 1), (
        f"_metadata.version is {ver!r}; expected ≥ 2.1 since v2.1 added "
        f"the CRI_GLP1 / CRI_ANABOLIC / CRI_BOT_SUB codes and "
        f"PEDIATRIC_SUPPLEMENT modifier."
    )


def test_total_deduction_cap_default_unchanged(blob):
    """The default total_deduction_cap stays at -25 (the floor for
    manufacturers with 0 or 1 Class-I in 3yr). v2.2 adds a graduated
    cap on top — see test_v2_2_graduated_cap_structure below."""
    assert blob["total_deduction_cap"] == -25, (
        f"total_deduction_cap (default) changed to {blob['total_deduction_cap']}. "
        f"The default cap is preserved at -25 by the v2.2 design — only "
        f"repeat Class-I actors hit the graduated tiers (-35 / -50)."
    )


# ---------------------------------------------------------------------------
# v2.2 additions (Phase 2 of 2026-05-13 deduction-expl proposal, 2026-05-14)
# Pin the graduated total_deduction_cap structure introduced for repeat
# Class-I drug-spike actors.
# ---------------------------------------------------------------------------


def test_v2_2_graduated_cap_structure(blob):
    """v2.2 added `total_deduction_cap_graduated` carrying default + two
    threshold tiers. The Python-side mirror in
    scripts/score_supplements.py::SupplementScorer (constants
    _MFG_CAP_DEFAULT / _TWO_CLASS_I / _THREE_OR_MORE_CLASS_I) MUST match.

    Drift between this JSON and the Python code is caught by
    test_graduated_cap_score_movements.py::test_python_cap_constants_match_json_source_of_truth."""
    graduated = blob.get("total_deduction_cap_graduated")
    assert isinstance(graduated, dict), (
        "v2.2 added total_deduction_cap_graduated. Missing block means "
        "the file regressed or was downgraded. See "
        "docs/handoff/2026-05-14_phase2_graduated_cap_impact.md."
    )
    assert graduated.get("default") == -25, (
        f"graduated.default expected -25 (matches top-level total_deduction_cap), "
        f"got {graduated.get('default')}"
    )
    assert graduated.get("two_class_i_in_3_years") == -35, (
        f"graduated.two_class_i_in_3_years expected -35, "
        f"got {graduated.get('two_class_i_in_3_years')}"
    )
    assert graduated.get("three_or_more_class_i_in_3_years") == -50, (
        f"graduated.three_or_more_class_i_in_3_years expected -50, "
        f"got {graduated.get('three_or_more_class_i_in_3_years')}"
    )


def test_v2_2_version_at_or_above_2_2(blob):
    """v2.2 is the minimum version that includes the graduated cap.
    Older versions silently default to a static -25 cap, which produces
    different scores for repeat Class-I actors. Version must reflect that."""
    ver = blob["_metadata"].get("version", "0.0")
    parts = tuple(int(p) for p in ver.split("."))
    assert parts >= (2, 2), (
        f"_metadata.version is {ver!r}; expected ≥ 2.2 since v2.2 added "
        f"the total_deduction_cap_graduated block."
    )


def test_v2_2_calculation_rules_step_7_describes_graduated_cap(blob):
    """`step_7` in calculation_rules is the canonical natural-language
    description of the cap step. Since v2.2 made the cap graduated, the
    description must mention the graduated structure — not the old static
    -25 wording (which incorrectly called 75 a "Trusted score floor"
    when it's actually Acceptable per score_thresholds)."""
    step_7 = blob.get("calculation_rules", {}).get("step_7", "")
    assert "graduated" in step_7.lower(), (
        f"step_7 must reference the graduated cap structure (v2.2). "
        f"Got: {step_7!r}"
    )
    # Wording correction: 75 is the Acceptable band, not Trusted.
    # Existing step_7 text should NOT have the old misleading phrase
    # "never goes below 75 score" without qualifier, since under graduated
    # caps repeat actors DO go below 75.
    assert "Acceptable score floor" in step_7 or "Acceptable" in step_7, (
        f"step_7 must clarify that 75 is the Acceptable score floor "
        f"(not Trusted). Got: {step_7!r}"
    )
