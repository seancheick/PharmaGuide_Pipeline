"""Vitamin A/provitamin carotenoid IQM reconciliation.

This locks the 2026-06-02 Vitamin A policy:
- direct Vitamin A forms keep absorption-only bio_score semantics
- delivery-tech claims are not premium without direct human PK evidence
- provitamin A carotenoids are tied to vitamin_a without duplicating exact IDs
"""

import json
from pathlib import Path


IQM_PATH = Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json"


def load_iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def assert_score_formula(form: dict) -> None:
    expected = min(18, form["bio_score"] + (3 if form.get("natural") else 0))
    assert form["score"] == expected


def test_vitamin_a_direct_forms_use_absorption_only_scores() -> None:
    iqm = load_iqm()
    forms = iqm["vitamin_a"]["forms"]

    expected = {
        "retinol": 15,
        "retinyl palmitate": 14,
        "retinyl acetate": 14,
        "vitamin A from cod liver oil": 11,
        "micellized vitamin A": 12,
        "liposomal vitamin A": 12,
        "beta-carotene synthetic": 6,
        "beta-carotene from mixed carotenoids": 7,
        "vitamin a (unspecified)": 6,
    }

    for form_name, bio_score in expected.items():
        form = forms[form_name]
        assert form["bio_score"] == bio_score
        assert_score_formula(form)


def test_delivery_tech_forms_are_evidence_thin_not_top_tier() -> None:
    iqm = load_iqm()
    forms = iqm["vitamin_a"]["forms"]

    for form_name in ("micellized vitamin A", "liposomal vitamin A"):
        form = forms[form_name]
        assert form["bio_score"] == 12
        notes = form.get("notes", "").lower()
        assert "evidence-thin" in notes
        assert "mechanistic" in notes
        assert "direct human" in notes


def test_provitamin_a_carotenoids_belong_to_vitamin_a_family() -> None:
    iqm = load_iqm()

    for parent in ("beta_carotene", "alpha_carotene", "cryptoxanthin"):
        assert iqm[parent]["match_rules"]["parent_id"] == "vitamin_a"


def test_standalone_carotenoid_forms_use_conservative_provitamin_a_scores() -> None:
    iqm = load_iqm()

    expected = {
        ("beta_carotene", "natural beta-carotene (from dunaliella salina)"): 7,
        ("beta_carotene", "beta-carotene beadlet"): 6,
        ("beta_carotene", "beta-carotene (unspecified)"): 6,
        ("alpha_carotene", "alpha-carotene (unspecified)"): 5,
        ("cryptoxanthin", "beta-cryptoxanthin"): 5,
    }

    for (parent, form_name), bio_score in expected.items():
        form = iqm[parent]["forms"][form_name]
        assert form["bio_score"] == bio_score
        assert_score_formula(form)


def test_vitamin_a_context_forms_do_not_duplicate_exact_carotenoid_identity_ids() -> None:
    iqm = load_iqm()
    vitamin_a_forms = iqm["vitamin_a"]["forms"]

    expected_forms = {
        "alpha-carotene (provitamin A activity)": "alpha_carotene",
        "beta-cryptoxanthin (provitamin A activity)": "cryptoxanthin",
    }

    for form_name, exact_parent in expected_forms.items():
        form = vitamin_a_forms[form_name]
        assert form["bio_score"] == 5
        assert form["natural"] is True
        assert_score_formula(form)
        assert "external_ids" not in form or not form["external_ids"].get("unii")
        assert form["api_verification"]["exact_identity_parent"] == exact_parent
        for alias in form["aliases"]:
            normalized = alias.lower()
            assert "vitamin a" in normalized or "provitamin a" in normalized

    assert iqm["alpha_carotene"]["cui"] == "C0051336"
    assert iqm["cryptoxanthin"]["external_ids"]["unii"] == "6ZIB13GI33"
