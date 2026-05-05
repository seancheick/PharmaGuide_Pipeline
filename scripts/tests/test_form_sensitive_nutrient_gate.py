#!/usr/bin/env python3
"""Form-sensitive nutrient integrity gate — Phase C.

Rule the gate enforces:
  For every active ingredient whose IQM matched_form resolves to a real
  chemical form (i.e. not the '(unspecified)' / 'standard' placeholders),
  the build_final_db blob MUST emit a non-empty display_form_label.

Form-sensitivity matters most for nutrients where bio_score / safety
varies sharply between forms — Vitamin A (palmitate vs beta-carotene),
Vitamin D (D3 vs D2), Vitamin K (MK-7 vs phylloquinone), B12
(methylcobalamin vs cyanocobalamin), folate (L-5-MTHF vs folic acid),
Mg/Fe/Zn salts (chelate vs oxide), CoQ10 (ubiquinol vs ubiquinone),
omega-3 (TG vs EE), curcumin (Theracurmin vs raw).

Two scopes:
  - Unit (always runs): synthetic rows for the user-listed nutrients
    confirm the contract triggers correctly.
  - Integration (skipped if no build output): walks the live
    detail_blobs corpus and reports first-N violations.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_final_db import _compute_form_contract, _is_placeholder_form


# Form-sensitive nutrients — name + a representative real matched_form
# the IQM aliases would resolve to. Sourced from the user's Phase C list.
FORM_SENSITIVE_FIXTURES = [
    # (display name, raw_source_text, matched_form)
    ("Vitamin A",        "Vitamin A Palmitate",          "retinyl palmitate"),
    ("Vitamin A",        "Vitamin A Acetate",            "retinyl acetate"),
    ("Vitamin D",        "Vitamin D3",                   "cholecalciferol"),
    ("Vitamin D",        "Vitamin D2",                   "ergocalciferol"),
    ("Vitamin E",        "d-Alpha Tocopherol",           "d-alpha tocopherol"),
    ("Vitamin K",        "Vitamin K2 MK-7",              "menaquinone-7"),
    ("Vitamin K",        "Vitamin K1 Phylloquinone",     "phylloquinone"),
    ("Vitamin B12",      "Methylcobalamin",              "methylcobalamin"),
    ("Vitamin B12",      "Cyanocobalamin",               "cyanocobalamin"),
    ("Folate",           "Folate as L-5-MTHF",           "5-methyltetrahydrofolate"),
    ("Folate",           "Folic Acid",                   "folic acid"),
    ("Magnesium",        "Magnesium Bisglycinate",       "bisglycinate"),
    ("Magnesium",        "Magnesium L-Threonate",        "threonate"),
    ("Iron",             "Iron Bisglycinate",            "bisglycinate"),
    ("Iron",             "Iron Fumarate",                "fumarate"),
    ("Zinc",             "Zinc Picolinate",              "picolinate"),
    ("Zinc",             "Zinc Gluconate",               "gluconate"),
    ("CoQ10",            "CoQ10 (as Ubiquinol)",         "ubiquinol"),
    ("CoQ10",            "Ubiquinone",                   "ubiquinone"),
    # Omega-3 form is normally on the parent oil, not the EPA/DHA row;
    # IQM stores forms like 'triglyceride' / 'ethyl ester' on the parent.
    ("Omega-3 Fish Oil", "Fish Oil (Triglyceride form)", "triglyceride"),
    # Curcumin — branded forms route via _BRANDED_TOKENS in the cleaner
    # but the IQM matched_form stays canonical.
    ("Curcumin",         "Curcumin (Theracurmin)",       "theracurmin"),
]


@pytest.mark.parametrize("nutrient,raw,matched_form", FORM_SENSITIVE_FIXTURES)
def test_form_contract_emits_label_when_iqm_resolved_form(nutrient, raw, matched_form):
    """When the cleaner misses the inline form (forms=[]) but the
    enricher's matched_form is a real chemical form, the contract must
    populate display_form_label and emit form_status='known'."""
    ing = {"forms": [], "name": raw, "raw_source_text": raw}
    m = {"matched_form": matched_form}
    contract = _compute_form_contract(ing, m)
    assert contract["display_form_label"], (
        f"{nutrient}: display_form_label empty for matched_form={matched_form!r}. "
        f"Flutter would render no form helper line."
    )
    assert contract["form_status"] == "known"
    assert contract["form_match_status"] == "mapped"


def test_placeholder_matched_forms_emit_unknown():
    """Inverse of the gate: an IQM fallback to '(unspecified)' must
    surface as form_status='unknown' rather than a silent empty label."""
    for placeholder in (
        "vitamin a (unspecified)",
        "vitamin d (unspecified)",
        "magnesium (unspecified)",
        "standard",
        "",
    ):
        ing = {"forms": [], "name": "Vitamin A"}
        m = {"matched_form": placeholder}
        contract = _compute_form_contract(ing, m)
        assert contract["form_status"] == "unknown", (
            f"placeholder={placeholder!r} should resolve to unknown"
        )
        assert contract["display_form_label"] is None


# -- Integration: scan real build output if present --------------------------

DETAIL_BLOBS_DIR = REPO_ROOT / "scripts" / "final_db_output" / "detail_blobs"


def _iter_blob_paths(limit: int | None = None):
    if not DETAIL_BLOBS_DIR.is_dir():
        return
    for i, path in enumerate(sorted(DETAIL_BLOBS_DIR.iterdir())):
        if limit is not None and i >= limit:
            return
        if path.suffix == ".json":
            yield path


def _build_carries_contract(blob_path: Path) -> bool:
    """Detect whether a built blob carries the Phase A canonical contract.
    Pre-Phase-A blobs lack the display_form_label key entirely."""
    try:
        b = json.loads(blob_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    for ing in b.get("ingredients", []):
        if isinstance(ing, dict) and ing.get("role") == "active":
            return "display_form_label" in ing
    return False


@pytest.mark.skipif(
    not DETAIL_BLOBS_DIR.is_dir(),
    reason="No build output to scan — run scripts/build_final_db.py first.",
)
def test_no_form_sensitive_violations_in_build_output():
    """Release gate. For any active ingredient whose matched_form is a
    real chemical form, display_form_label MUST be non-empty.

    Skipped on pre-Phase-A build output (rebuild needed first). Once
    the corpus is fresh this gate would have caught the Thorne Basic
    Prenatal regression (DSLD 328830) before Flutter consumed it.
    """
    sample = next(_iter_blob_paths(limit=1), None)
    if sample is None:
        pytest.skip("Empty build output directory.")
    if not _build_carries_contract(sample):
        pytest.skip(
            "Build output predates Phase A canonical contract. "
            "Re-run scripts/build_final_db.py to refresh blobs; "
            "this gate will then enforce display_form_label coverage."
        )

    violations = []
    for blob_path in _iter_blob_paths():
        try:
            blob = json.loads(blob_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        dsld_id = blob.get("dsld_id") or blob_path.stem
        for ing in blob.get("ingredients", []):
            if not isinstance(ing, dict) or ing.get("role") != "active":
                continue
            matched = ing.get("matched_form") or ""
            if _is_placeholder_form(matched):
                continue
            if not ing.get("display_form_label"):
                violations.append({
                    "dsld_id": dsld_id,
                    "name": ing.get("name"),
                    "raw_source_text": ing.get("raw_source_text"),
                    "matched_form": matched,
                })
                if len(violations) >= 20:
                    break
        if len(violations) >= 20:
            break

    assert not violations, (
        f"{len(violations)} active ingredient(s) have a real matched_form "
        f"but empty display_form_label. First few:\n"
        + "\n".join(json.dumps(v, indent=2) for v in violations[:5])
    )
