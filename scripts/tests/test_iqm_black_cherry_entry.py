#!/usr/bin/env python3
"""
IQM coverage: Black Cherry (Batch 5 IQM gap fill #6).

Black cherry concentrate (typically Prunus avium fruit) is used in 5+
supplement products for gout/uric-acid management and anthocyanin-mediated
anti-inflammatory effects. Previously skipped as `recognized_non_scorable`
because IQM only had `tart_cherry` (Prunus cerasus — botanically distinct).

Identifiers verified via:
- FDA GSRS: UNII A77056YJ4K ("BLACK CHERRY"), CAS 84604-07-9
- UMLS: CUI C5551209 (Black Cherry, MTH; classification=Food)
- DSLD: 3 product references under "botanical|Black cherry"

Distinct from `tart_cherry` (Prunus cerasus / Montmorency) — same family
(Rosaceae/Prunus genus) but different species with different anthocyanin
levels and different label terminology. The `tart_cherry` IQM entry stays
intact; this entry adds Prunus avium coverage.
"""

import json
import os

import pytest


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def test_black_cherry_iqm_entry_exists(iqm):
    assert "black_cherry" in iqm


def test_black_cherry_identifiers(iqm):
    e = iqm["black_cherry"]
    assert e.get("cui") == "C5551209"
    assert e.get("external_ids", {}).get("unii") == "A77056YJ4K"


def test_black_cherry_score_formula(iqm):
    e = iqm["black_cherry"]
    for form_key, form in e.get("forms", {}).items():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        score = form.get("score")
        natural = bool(form.get("natural", False))
        if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
            assert score == bio + (3 if natural else 0)


def test_black_cherry_aliases(iqm):
    e = iqm["black_cherry"]
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "black cherry",
        "black cherry concentrate",
        "black cherry extract",
        "prunus avium",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"


def test_black_cherry_does_not_collide_with_tart_cherry(iqm):
    """Tart cherry (Prunus cerasus) and black cherry (Prunus avium) are
    botanically distinct species. Their alias lists must not overlap."""
    bc = iqm["black_cherry"]
    tc = iqm.get("tart_cherry", {})

    bc_aliases = set()
    for f in bc.get("forms", {}).values():
        if isinstance(f, dict):
            bc_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    tc_aliases = set()
    for f in tc.get("forms", {}).values():
        if isinstance(f, dict):
            tc_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}

    overlap = bc_aliases & tc_aliases
    assert not overlap, (
        f"black_cherry and tart_cherry aliases must not overlap: {overlap}"
    )


def test_black_cherry_category_matches_tart(iqm):
    """Both cherry entries should sit in the same category for consistency."""
    bc = iqm["black_cherry"]
    tc = iqm.get("tart_cherry", {})
    assert bc.get("category") == tc.get("category")
    assert bc.get("category_enum") == bc.get("category")
