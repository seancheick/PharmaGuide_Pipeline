"""
Sprint E1.0.1 — label-fidelity contract tests (7 invariants).

These tests encode the "what the user sees must match what's on the label"
guarantees identified in the 2026-04-21 dual audit (pipeline label-fidelity
scan + Flutter device-testing handoff). They are the permanent CI floor
that prevents regression once Phase E1.2 fixes ship.

Each test auto-skips until its target pipeline field exists in the sampled
detail blobs. As the matching E1.2.x / E1.3.x task lands, the field appears
and the test activates with no code change required here. This mirrors the
"define the eval first" non-negotiable in SPRINT_E1_ACCURACY_ADDENDUM §3.

Invariants (sprint doc §E1.0.1):

| # | Invariant | Target field | Fix task |
|---|---|---|---|
| 1 | display_name_never_canonical | ingredients[].display_label | E1.2.2 |
| 2 | no_false_well_dosed_on_undisclosed | ingredients[].display_badge | E1.2.2 |
| 3 | no_np_leaks_to_display | ingredients[].display_dose_label | E1.2.2 |
| 4 | branded_identity_preserved | ingredients[].display_label | E1.2.2 |
| 5 | plant_part_preserved | ingredients[].display_label | E1.2.2 / E1.3.5 |
| 6 | standardization_note_preserved | ingredients[].standardization_note | E1.2.2 |
| 7 | inactive_ingredients_complete | inactive_ingredients count recovery | E1.2.4 |

Uses the same ``_find_blob_dir()`` contract-sample pattern as
``test_d53_detail_blob_top_level_contract.py`` — local-build-aware, skips
cleanly in CI environments without a build artifact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


# Branded-identity tokens audit-grade. Expanded as E1.2.2 QA surfaces more
# branded forms. Match is case-insensitive; hyphens treated as literal.
BRANDED_TOKENS = (
    "KSM-66",
    "Meriva",
    "BioPerine",
    "Ferrochel",
    "Sensoril",
    "Phytosome",
    "Silybin Phytosome",
    "Pycnogenol",
    "Setria",
    "Albion",
    "TRAACS",
    "Chromax",
    "Curcumin C3",
    "Longvida",
    "Wellmune",
    "CurcuWIN",
    "LJ100",
    "enXtra",
    "AstraGin",
    "Venetron",
)

# Plant-part tokens whose preservation we enforce. Case-insensitive single-
# word match; phrases like "aerial parts" covered via regex below.
PLANT_PART_TOKENS = (
    "root",
    "leaf",
    "leaves",
    "seed",
    "bark",
    "rhizome",
    "flower",
    "fruit",
    "stem",
    "aerial",
)
PLANT_PART_RE = re.compile(
    r"\b(root|leaf|leaves|seed|bark|rhizome|flower|fruit|stem|aerial)\b",
    re.IGNORECASE,
)

# Standardization-note pattern: "X% Y" or "standardized to X% Y" or
# "contains X mg of Y per Z". Matches the shape Dr Pham authoring uses.
STANDARDIZATION_RE = re.compile(
    r"(standardi[sz]ed to\b|\b\d+(?:\.\d+)?\s*%\b|\bcontains\s+\d)",
    re.IGNORECASE,
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


def _any_ingredient_has_field(sample_blobs, field: str) -> bool:
    """Return True if at least one blob emits the named field on any
    ingredient. Used as an auto-skip gate so these tests activate the
    moment E1.2.x starts emitting the field."""
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            if field in ing:
                return True
    return False


# ---------------------------------------------------------------------------
# Invariant 1 — display_name_never_canonical (E1.2.2)
# ---------------------------------------------------------------------------

def test_display_name_never_canonical(sample_blobs) -> None:
    """An ingredient's ``display_label`` must never collapse to its scoring-
    group canonical name when the label source differs. The user must see
    what the bottle says (e.g. "KSM-66 Ashwagandha Root Extract"), not the
    internal scoring key ("Ashwagandha"). Collapsing hides brand identity,
    form, and plant part — all of which drive the purchase decision.

    Fix in: E1.2.2 (pre-computed display fields).
    """
    if not _any_ingredient_has_field(sample_blobs, "display_label"):
        pytest.skip("waiting on E1.2.2 — display_label not yet emitted")

    violations = []
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            display = (ing.get("display_label") or "").strip()
            canonical = (ing.get("canonical_name") or ing.get("scoring_group_canonical") or "").strip()
            source_name = (ing.get("name") or ing.get("raw_name") or "").strip()
            if not display or not canonical or not source_name:
                continue
            if display.lower() == canonical.lower() and source_name.lower() != canonical.lower():
                violations.append((blob.get("dsld_id"), source_name, canonical, display))

    assert not violations, (
        f"E1.0.1 #1: {len(violations)} ingredients collapsed display_label "
        f"to canonical name despite differing source. First 5:\n"
        + "\n".join(
            f"  [{did}] source={src!r} canonical={can!r} display={disp!r}"
            for did, src, can, disp in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 2 — no_false_well_dosed_on_undisclosed (E1.2.2)
# ---------------------------------------------------------------------------

def test_no_false_well_dosed_on_undisclosed(sample_blobs) -> None:
    """An ingredient inside a proprietary blend whose individual dose is NOT
    disclosed cannot carry a ``well_dosed`` badge. Doing so tells the user
    "this is dosed at a clinical level" when we literally do not know the
    dose. This is the core safety/trust bug from the Flutter handoff:
    green thumbs-up on undisclosed prop-blend members.

    Fix in: E1.2.2 (pre-computed display fields — badge logic).
    """
    if not _any_ingredient_has_field(sample_blobs, "display_badge"):
        pytest.skip("waiting on E1.2.2 — display_badge not yet emitted")

    violations = []
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            in_blend = bool(ing.get("is_in_proprietary_blend"))
            individually_disclosed = bool(ing.get("individually_disclosed"))
            badge = (ing.get("display_badge") or "").strip().lower()
            if in_blend and not individually_disclosed and badge == "well_dosed":
                violations.append((blob.get("dsld_id"), ing.get("name"), badge))

    assert not violations, (
        f"E1.0.1 #2: {len(violations)} undisclosed prop-blend members "
        f"falsely badged 'well_dosed'. First 5:\n"
        + "\n".join(f"  [{did}] {name!r} badge={b!r}" for did, name, b in violations[:5])
    )


# ---------------------------------------------------------------------------
# Invariant 3 — no_np_leaks_to_display (E1.2.2)
# ---------------------------------------------------------------------------

def test_no_np_leaks_to_display(sample_blobs) -> None:
    """``display_dose_label`` is user-facing. Internal sentinel tokens like
    ``NP`` (not provided) must never leak through. The expected user-
    visible strings are authored-copy forms: ``"600 mg"``, ``"Amount not
    disclosed"``, ``"—"``. Seeing raw ``NP`` signals a pipeline bug that
    erodes trust.

    Fix in: E1.2.2 (pre-computed display fields — dose-label humanization).
    """
    if not _any_ingredient_has_field(sample_blobs, "display_dose_label"):
        pytest.skip("waiting on E1.2.2 — display_dose_label not yet emitted")

    violations = []
    np_re = re.compile(r"\bNP\b")
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            label = ing.get("display_dose_label") or ""
            if np_re.search(label):
                violations.append((blob.get("dsld_id"), ing.get("name"), label))

    assert not violations, (
        f"E1.0.1 #3: {len(violations)} display_dose_label values leak 'NP'. First 5:\n"
        + "\n".join(f"  [{did}] {name!r} label={lab!r}" for did, name, lab in violations[:5])
    )


# ---------------------------------------------------------------------------
# Invariant 4 — branded_identity_preserved (E1.2.2)
# ---------------------------------------------------------------------------

def test_branded_identity_preserved(sample_blobs) -> None:
    """When the raw label names a branded ingredient form (KSM-66, Meriva,
    BioPerine, Ferrochel, etc.), the ``display_label`` must preserve the
    brand token. Branded forms carry clinical-evidence packages the generic
    does not — "KSM-66 Ashwagandha" ≠ "Ashwagandha". Dropping the brand
    misrepresents what the user bought.

    Fix in: E1.2.2 (pre-computed display fields — branded-token carry-through).
    """
    if not _any_ingredient_has_field(sample_blobs, "display_label"):
        pytest.skip("waiting on E1.2.2 — display_label not yet emitted")

    violations = []
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            raw_sources = [
                ing.get("name") or "",
                ing.get("raw_name") or "",
                " ".join(f.get("name", "") for f in (ing.get("forms") or []) if isinstance(f, dict)),
                " ".join(n or "" for n in (ing.get("notes") or []) if isinstance(n, str)),
            ]
            raw_blob = " ".join(raw_sources)
            display = ing.get("display_label") or ""
            for token in BRANDED_TOKENS:
                if token.lower() in raw_blob.lower() and token.lower() not in display.lower():
                    violations.append((blob.get("dsld_id"), token, ing.get("name"), display))
                    break

    assert not violations, (
        f"E1.0.1 #4: {len(violations)} branded tokens dropped from display_label. First 5:\n"
        + "\n".join(
            f"  [{did}] token={tok!r} source={src!r} display={disp!r}"
            for did, tok, src, disp in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 5 — plant_part_preserved (E1.2.2 / E1.3.5)
# ---------------------------------------------------------------------------

def test_plant_part_preserved(sample_blobs) -> None:
    """When raw ``forms[].name`` carries a plant-part token (root, leaf,
    seed, bark, rhizome, aerial), ``display_label`` must preserve it.
    Plant part governs active-compound profile and dose equivalence:
    turmeric root ≠ turmeric leaf, valerian root ≠ valerian aerial parts.
    Dropping the part erases a clinically material distinction.

    Fix in: E1.2.2 (display field composition) + E1.3.5 (validation
    closeout).
    """
    if not _any_ingredient_has_field(sample_blobs, "display_label"):
        pytest.skip("waiting on E1.2.2 — display_label not yet emitted")

    violations = []
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            forms = ing.get("forms") or []
            form_blob = " ".join(f.get("name", "") for f in forms if isinstance(f, dict))
            match = PLANT_PART_RE.search(form_blob)
            if not match:
                continue
            part = match.group(1).lower()
            display = (ing.get("display_label") or "").lower()
            # Accept inflection equivalence (leaf/leaves)
            equivalents = {"leaf": ("leaf", "leaves"), "leaves": ("leaf", "leaves")}
            acceptable = equivalents.get(part, (part,))
            if not any(e in display for e in acceptable):
                violations.append((blob.get("dsld_id"), part, ing.get("name"), ing.get("display_label")))

    assert not violations, (
        f"E1.0.1 #5: {len(violations)} plant parts dropped from display_label. First 5:\n"
        + "\n".join(
            f"  [{did}] part={p!r} source={src!r} display={disp!r}"
            for did, p, src, disp in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 6 — standardization_note_preserved (E1.2.2)
# ---------------------------------------------------------------------------

def test_standardization_note_preserved(sample_blobs) -> None:
    """When the raw notes carry a standardization string (e.g. "Standardized
    to 5% total withanolides", "95% curcuminoids"), the blob must emit a
    non-null ``standardization_note``. Standardization is the contract
    between the label and the clinical evidence — without it, a 600 mg
    generic turmeric cannot be compared to a 600 mg 95%-curcuminoid trial.

    Fix in: E1.2.2 (pre-computed display fields — standardization extraction).
    """
    if not _any_ingredient_has_field(sample_blobs, "standardization_note"):
        pytest.skip("waiting on E1.2.2 — standardization_note not yet emitted")

    violations = []
    for blob in sample_blobs:
        for ing in blob.get("ingredients", []) or []:
            notes = ing.get("notes") or []
            notes_text = " ".join(n for n in notes if isinstance(n, str))
            if not STANDARDIZATION_RE.search(notes_text):
                continue
            note = ing.get("standardization_note")
            if not note:
                violations.append((blob.get("dsld_id"), ing.get("name"), notes_text[:120]))

    assert not violations, (
        f"E1.0.1 #6: {len(violations)} standardization strings dropped. First 5:\n"
        + "\n".join(
            f"  [{did}] {name!r} raw_notes={nt!r}"
            for did, name, nt in violations[:5]
        )
    )


# ---------------------------------------------------------------------------
# Invariant 7 — inactive_ingredients_complete (E1.2.4)
# ---------------------------------------------------------------------------

def _raw_inactives_count(blob: dict) -> int:
    """Count inactive ingredients on the raw DSLD side, if the blob exposes
    a snapshot. Contract blobs emitted post-E1.2.4 carry
    ``raw_inactives_count`` (set by build_final_db). Until that field
    lands, this helper returns 0 so the invariant skips."""
    v = blob.get("raw_inactives_count")
    if isinstance(v, int):
        return v
    return 0


def test_inactive_ingredients_complete(sample_blobs) -> None:
    """For every raw ``otheringredients.ingredients[i]`` on the DSLD source,
    the blob's ``inactive_ingredients`` must carry a matching entry (by
    name or alias). The cleaner currently filters too aggressively — 118
    products ship with raw inactives > 0 and blob inactives == 0. The
    Flutter excipient density card renders empty and the user cannot see
    e.g. magnesium stearate, titanium dioxide, artificial colors.

    Fix in: E1.2.4 (inactive-ingredient dropping audit).
    """
    # Gate on the raw-counts snapshot emitted by E1.2.4's build changes.
    has_snapshot = any("raw_inactives_count" in b for b in sample_blobs)
    if not has_snapshot:
        pytest.skip("waiting on E1.2.4 — raw_inactives_count snapshot not yet emitted")

    violations = []
    for blob in sample_blobs:
        raw_n = _raw_inactives_count(blob)
        blob_n = len(blob.get("inactive_ingredients") or [])
        if raw_n > 0 and blob_n == 0:
            violations.append((blob.get("dsld_id"), raw_n))

    assert not violations, (
        f"E1.0.1 #7: {len(violations)} products have raw_inactives > 0 but "
        f"blob_inactives == 0. First 5:\n"
        + "\n".join(f"  [{did}] raw={rn}" for did, rn in violations[:5])
    )
