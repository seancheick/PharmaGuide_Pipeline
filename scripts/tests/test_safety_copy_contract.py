"""
Sprint E1.0.2 — safety-copy contract tests (5 invariants).

These tests encode the "what the app tells the user about safety must be
medically honest and profile-appropriate" guarantees identified in the
2026-04-21 Flutter device-testing handoff. They are the permanent CI
floor that prevents regression once Phase E1.1 (safety-copy integrity)
and E1.2.3 (warning dedup) fixes ship.

Each test auto-skips until its target pipeline change lands. Activation
style is chosen per invariant:

  - Invariants 1 and 4 auto-gate on the appearance of a new structural
    field (``decision_highlights.danger`` / banned-substance preflight
    copy propagation). They activate with zero code change here the
    moment the matching phase lands.

  - Invariants 2, 3, and 5 have no clean structural signal (copy
    rewrites, validator additions, dedup collapse). They gate on a
    module-level constant flipped to ``True`` when the phase lands.
    One-line toggle, co-located so nothing is forgotten.

Invariants (sprint doc §E1.0.2):

| # | Invariant | Fix task |
|---|---|---|
| 1 | no_danger_in_positives               | E1.1.1 |
| 2 | critical_warnings_are_profile_agnostic | E1.1.2 |
| 3 | no_raw_enum_leaks                    | E1.1.3 |
| 4 | banned_substance_has_preflight_copy  | E1.1.4 |
| 5 | no_duplicate_warnings                | E1.2.3 |
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Phase-landed toggles — flip to True as each task ships.
# ---------------------------------------------------------------------------

SPRINT_E1_1_2_LANDED = False  # Warning copy rewrite (critical → profile-agnostic)
SPRINT_E1_1_3_LANDED = False  # Build-time raw-enum-leak validator
SPRINT_E1_2_3_LANDED = False  # Build-time warning dedup

# ---------------------------------------------------------------------------
# Deny-lists / regex — medical/UX justification in each invariant docstring.
# ---------------------------------------------------------------------------

# Any of these tokens appearing in decision_highlights.positive[] indicates
# the "bad news pretending to be good news" UX bug from the Flutter handoff.
DANGER_DENY_LIST = re.compile(
    r"(not lawful|banned|talk to your doctor|arsenic|trace metals|"
    r"undisclosed|high glycemic|contraindicated)",
    re.IGNORECASE,
)

# Condition-specific phrases that must not appear in a critical-mode
# (profile-unaware) warning. Critical-mode warnings show to EVERY user
# regardless of profile, so naming a specific condition is medically wrong.
CONDITION_SPECIFIC_RE = re.compile(
    r"(during pregnancy|for liver disease|breastfeeding|kidney disease|"
    r"heart disease|while nursing)",
    re.IGNORECASE,
)

# Five authored-copy fields; ≥ 1 must be populated on every warning.
AUTHORED_COPY_FIELDS = (
    "alert_headline",
    "alert_body",
    "safety_warning",
    "safety_warning_one_liner",
    "detail",
)


def _find_blob_dir() -> Path | None:
    candidates = [
        Path("/tmp/pharmaguide_release_build/detail_blobs"),
        Path("/tmp/pharmaguide_build/detail_blobs"),
    ]
    for c in candidates:
        if c.is_dir() and any(c.glob("*.json")):
            return c
    return None


@pytest.fixture(scope="module")
def sample_blobs():
    blob_dir = _find_blob_dir()
    if blob_dir is None:
        pytest.skip(
            "No build artifact found under /tmp/pharmaguide_release_build — "
            "run build_final_db.py first to exercise this contract test."
        )
    sample_paths = sorted(blob_dir.glob("*.json"))[:200]
    if not sample_paths:
        pytest.skip("No detail blobs to sample.")
    return [json.loads(p.read_text()) for p in sample_paths]


def _iter_warnings(blob: dict):
    """Yield (warning, source_list_name) for every warning across the two
    warning lists Flutter consumes."""
    for key in ("warnings", "warnings_profile_gated"):
        for w in blob.get(key) or []:
            if isinstance(w, dict):
                yield w, key


def _as_string_list(value) -> list[str]:
    """Decision-highlight buckets are a single string pre-E1.1.1 and a
    list[str] post-E1.1.1. Normalize so the test body is shape-agnostic."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


# ---------------------------------------------------------------------------
# Invariant 1 — no_danger_in_positives (E1.1.1)
# ---------------------------------------------------------------------------

def test_no_danger_in_positives(sample_blobs) -> None:
    """``decision_highlights.positive[]`` is the user-visible "reasons to
    feel good about this product" hero string. It cannot carry danger-
    valence copy like "Not lawful as a US dietary supplement" or "Some
    can carry trace arsenic." Those belong in the new ``danger`` bucket
    added by E1.1.1 and rendered red in Flutter. Putting danger copy
    under a green thumbs-up is actively user-harmful.

    Fix in: E1.1.1 (decision_highlights re-classification + danger bucket).
    """
    has_danger_bucket = any(
        isinstance(b.get("decision_highlights"), dict)
        and "danger" in b["decision_highlights"]
        for b in sample_blobs
    )
    if not has_danger_bucket:
        pytest.skip("waiting on E1.1.1 — decision_highlights.danger bucket not yet emitted")

    violations = []
    for blob in sample_blobs:
        dh = blob.get("decision_highlights")
        if not isinstance(dh, dict):
            continue
        for s in _as_string_list(dh.get("positive")):
            m = DANGER_DENY_LIST.search(s)
            if m:
                violations.append((blob.get("dsld_id"), m.group(0), s[:120]))

    assert not violations, (
        f"E1.0.2 #1: {len(violations)} decision_highlights.positive strings "
        f"match the danger deny-list. First 5:\n"
        + "\n".join(f"  [{did}] tok={tok!r} text={s!r}" for did, tok, s in violations[:5])
    )


# ---------------------------------------------------------------------------
# Invariant 2 — critical_warnings_are_profile_agnostic (E1.1.2)
# ---------------------------------------------------------------------------

def test_critical_warnings_are_profile_agnostic(sample_blobs) -> None:
    """If ``display_mode_default == "critical"``, the warning is shown to
    every user regardless of profile. Its copy must therefore be profile-
    agnostic — no "during pregnancy", "for liver disease", etc. The
    condition-specific variants belong under ``display_mode_default ==
    "suppress"`` and are surfaced only when a matching profile attribute
    is set. Showing "during pregnancy" to every user (including men) is
    both confusing and erodes trust in the safety layer.

    Fix in: E1.1.2 (warning copy rewrite — Path A preferred).
    """
    if not SPRINT_E1_1_2_LANDED:
        pytest.skip("waiting on E1.1.2 — critical-copy rewrite not yet landed")

    violations = []
    for blob in sample_blobs:
        for w, source in _iter_warnings(blob):
            if w.get("display_mode_default") != "critical":
                continue
            for field in AUTHORED_COPY_FIELDS:
                text = w.get(field) or ""
                if isinstance(text, str) and CONDITION_SPECIFIC_RE.search(text):
                    violations.append((blob.get("dsld_id"), source, field, text[:120]))
                    break

    assert not violations, (
        f"E1.0.2 #2: {len(violations)} critical-mode warnings reference a "
        f"specific condition. First 5:\n"
        + "\n".join(
            f"  [{did}] {src}[{fld}] text={t!r}" for did, src, fld, t in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 3 — no_raw_enum_leaks (E1.1.3)
# ---------------------------------------------------------------------------

def test_no_raw_enum_leaks(sample_blobs) -> None:
    """No warning may have its enum ``type`` as the only populated field.
    At least one of ``alert_headline``, ``alert_body``, ``safety_warning``,
    ``safety_warning_one_liner``, ``detail`` must be non-empty. A raw-enum-
    only warning (e.g. ``{"type": "ban_ingredient"}``) renders as raw
    machine text in Flutter — the user sees "ban_ingredient" instead of
    authored copy. This is a silent regression path: any future warning-
    emission site that forgets to populate authored copy must fail the
    build.

    Fix in: E1.1.3 (build-time missing-copy validator).
    """
    if not SPRINT_E1_1_3_LANDED:
        pytest.skip("waiting on E1.1.3 — raw-enum-leak validator not yet landed")

    violations = []
    for blob in sample_blobs:
        for w, source in _iter_warnings(blob):
            if not any((w.get(f) or "").strip() for f in AUTHORED_COPY_FIELDS if isinstance(w.get(f), str)):
                violations.append((blob.get("dsld_id"), source, w.get("type")))

    assert not violations, (
        f"E1.0.2 #3: {len(violations)} warnings have no authored copy "
        f"populated. First 5:\n"
        + "\n".join(f"  [{did}] {src} type={t!r}" for did, src, t in violations[:5])
    )


# ---------------------------------------------------------------------------
# Invariant 4 — banned_substance_has_preflight_copy (E1.1.4)
# ---------------------------------------------------------------------------

def _banned_preflight_fields_present(blob: dict) -> bool:
    """E1.1.4 wires Dr Pham's banned-substance authored copy into the
    detail blob. Exact carrier shape is finalized in E1.1.4; we detect
    presence by any of: top-level banned_substance_detail, or any
    ingredient where ``is_banned`` is truthy and either
    ``safety_warning_one_liner`` or ``safety_warning`` is populated."""
    if blob.get("banned_substance_detail"):
        return True
    for ing in blob.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        if ing.get("is_banned") and (
            ing.get("safety_warning_one_liner") or ing.get("safety_warning")
        ):
            return True
    return False


def test_banned_substance_has_preflight_copy(sample_blobs) -> None:
    """Stack-add preflight on banned-substance products (CBD, ephedra,
    DMAA, kratom, higenamine) must render Dr Pham's authored red-banner
    copy. When ``has_banned_substance == 1``, both
    ``safety_warning_one_liner`` (≤80 chars) and ``safety_warning``
    (≤200 chars) must propagate to the detail blob so Flutter Sprint
    27.7's preflight sheet can render the CRITICAL state with honest
    copy rather than generic "banned substance" machine text.

    Fix in: E1.1.4 (wire existing Dr Pham fields through enricher →
    build → blob; no new columns required per 2026-04-21 scope reduction).
    """
    if not any(_banned_preflight_fields_present(b) for b in sample_blobs):
        pytest.skip("waiting on E1.1.4 — banned-substance preflight copy not yet propagated to blob")

    violations = []
    for blob in sample_blobs:
        has_banned = bool(blob.get("has_banned_substance"))
        if not has_banned:
            continue

        # Prefer top-level banned_substance_detail if present; else scan
        # ingredient-level banned markers.
        bsd = blob.get("banned_substance_detail")
        if isinstance(bsd, dict):
            one = (bsd.get("safety_warning_one_liner") or "").strip()
            body = (bsd.get("safety_warning") or "").strip()
            if not (one and body):
                violations.append((blob.get("dsld_id"), "top-level", one[:40], body[:40]))
                continue
        else:
            # Require at least one banned ingredient to carry both fields.
            banned_ings = [
                i for i in (blob.get("ingredients") or [])
                if isinstance(i, dict) and i.get("is_banned")
            ]
            if not banned_ings:
                # has_banned_substance=1 without any marked ingredient is itself a propagation bug.
                violations.append((blob.get("dsld_id"), "no-marked-ingredient", "", ""))
                continue
            carriers = [
                i for i in banned_ings
                if (i.get("safety_warning_one_liner") or "").strip()
                and (i.get("safety_warning") or "").strip()
            ]
            if not carriers:
                violations.append((blob.get("dsld_id"), "ingredient-missing-copy", "", ""))

    assert not violations, (
        f"E1.0.2 #4: {len(violations)} banned-substance products lack "
        f"preflight copy. First 5:\n"
        + "\n".join(
            f"  [{did}] src={src} one={o!r} body={b!r}"
            for did, src, o, b in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 5 — no_duplicate_warnings (E1.2.3)
# ---------------------------------------------------------------------------

def _warning_key(w: dict) -> tuple:
    """Dedup key per sprint §E1.2.3: (severity, canonical_id, condition_id,
    drug_class_id, source_rule). ``condition_id`` and ``drug_class_id`` may
    be singular today and plural post-E1.4.1; normalize to a tuple."""

    def _norm(v) -> tuple:
        if v is None:
            return ()
        if isinstance(v, (list, tuple)):
            return tuple(sorted(str(x) for x in v))
        return (str(v),)

    return (
        w.get("severity"),
        w.get("canonical_id") or w.get("type"),
        _norm(w.get("condition_id") or w.get("condition_ids")),
        _norm(w.get("drug_class_id") or w.get("drug_class_ids")),
        w.get("source_rule"),
    )


def test_no_duplicate_warnings(sample_blobs) -> None:
    """Within ``warnings[]`` and within ``warnings_profile_gated[]``, no
    two entries may share the full dedup key. VitaFusion CBD Mixed Berry
    currently ships with 6 identical pregnancy warnings — the user sees
    six red banners for one medically-distinct rule. Build-time dedup
    in E1.2.3 collapses these, keeping the entry with the most-complete
    authored copy.

    Fix in: E1.2.3 (build-time warning dedup).
    """
    if not SPRINT_E1_2_3_LANDED:
        pytest.skip("waiting on E1.2.3 — warning dedup not yet landed")

    violations = []
    for blob in sample_blobs:
        for key in ("warnings", "warnings_profile_gated"):
            seen: dict[tuple, int] = {}
            for w in blob.get(key) or []:
                if not isinstance(w, dict):
                    continue
                k = _warning_key(w)
                seen[k] = seen.get(k, 0) + 1
            dups = {k: n for k, n in seen.items() if n > 1}
            if dups:
                violations.append((blob.get("dsld_id"), key, dups))

    assert not violations, (
        f"E1.0.2 #5: {len(violations)} warning-list dedup violations. First 5:\n"
        + "\n".join(
            f"  [{did}] {src} dups={dict(list(d.items())[:3])!r}"
            for did, src, d in violations[:5]
        )
    )
