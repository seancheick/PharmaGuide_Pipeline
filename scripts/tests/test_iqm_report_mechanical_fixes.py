"""Regression locks for IQM v4 defensibility-audit mechanical fixes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


IQM_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def test_bcaa_211_does_not_hijack_generic_amino_acid_labels(iqm: dict) -> None:
    aliases = {
        str(a).strip().lower()
        for a in iqm["branched_chain_amino_acids"]["forms"]["bcaa 2:1:1"]["aliases"]
    }
    forbidden = {
        "amino acids",
        "essential amino acids",
        "amino acids supplement",
        "essential amino acids supplement",
    }
    assert aliases.isdisjoint(forbidden), (
        "Generic amino-acid/EAA labels must not resolve to premium BCAA 2:1:1."
    )


def test_generic_bcaa_standard_does_not_receive_natural_bonus(iqm: dict) -> None:
    form = iqm["branched_chain_amino_acids"]["forms"]["branched chain amino acids (standard)"]
    assert form["natural"] is False
    assert form["score"] == form["bio_score"]


@pytest.mark.parametrize(
    "parent,form_name",
    [
        ("pine_bark_extract", "generic pine bark extract"),
        ("lactobacillus_salivarius", "generic lactobacillus salivarius"),
    ],
)
def test_generic_catch_all_forms_do_not_receive_natural_bonus(
    iqm: dict,
    parent: str,
    form_name: str,
) -> None:
    form = iqm[parent]["forms"][form_name]
    assert form["natural"] is False
    assert form["score"] == form["bio_score"]


@pytest.mark.parametrize(
    "parent,form_name",
    [
        ("saw_palmetto", "liposomal saw palmetto"),
        ("quercetin", "quercetin phytosome"),
        ("probiotics", "liposomal probiotics"),
        ("milk_thistle", "silymarin phytosome"),
        ("vitamin_k1", "micellized k1"),
    ],
)
def test_manufactured_delivery_forms_do_not_receive_natural_bonus(
    iqm: dict,
    parent: str,
    form_name: str,
) -> None:
    form = iqm[parent]["forms"][form_name]
    assert form["natural"] is False
    assert form["score"] == form["bio_score"]


def test_manuka_unspecified_does_not_outrank_disclosed_ungraded_form(iqm: dict) -> None:
    forms = iqm["manuka_honey"]["forms"]
    unspecified = forms["manuka honey (unspecified)"]
    ungraded = forms["ungraded manuka"]

    assert unspecified["natural"] is False
    assert unspecified["score"] == unspecified["bio_score"]
    assert unspecified["score"] < ungraded["score"]


@pytest.mark.parametrize(
    "parent,unspecified,specific_forms",
    [
        ("dha", "dha (unspecified)", ["DHA fish oil ethyl ester"]),
        ("epa", "epa (unspecified)", ["EPA fish oil ethyl ester"]),
        ("fish_oil", "fish oil (unspecified)", ["ethyl ester"]),
        ("ceramides", "ceramides (unspecified)", ["synthetic"]),
        ("hemp_seed_oil", "hemp seed oil (unspecified)", ["refined"]),
    ],
)
def test_unspecified_form_does_not_outrank_lowest_specific_form(
    iqm: dict,
    parent: str,
    unspecified: str,
    specific_forms: list[str],
) -> None:
    forms = iqm[parent]["forms"]
    unspecified_form = forms[unspecified]
    specific_scores = [forms[name]["score"] for name in specific_forms]
    assert unspecified_form["score"] <= min(specific_scores), (
        f"{parent}::{unspecified} should not outscore a disclosed lower-quality form."
    )
    assert unspecified_form["natural"] is False


def test_acetyl_l_carnitine_aliases_route_to_l_carnitine_alcar_form(iqm: dict) -> None:
    form = iqm["l_carnitine"]["forms"]["acetyl-l-carnitine (alcar)"]
    aliases = {str(a).strip().lower() for a in form["aliases"]}

    expected_aliases = {
        "acetyl-l-carnitine",
        "acetyl l-carnitine",
        "acetyl l carnitine",
        "acetyl-l-carnitine hcl",
        "acetyl l carnitine hcl",
        "acetyl l-carnitine hcl",
        "n-acetyl-l-carnitine hcl",
        "n-acetyl-l-carnitine hydrochloride",
        "alcar",
        "alcar hcl",
    }
    assert expected_aliases <= aliases
    assert form["bio_score"] == 11
    assert form["score"] == 11
    assert form["external_ids"]["unii"] == "6DH1W9VH8Q"


def test_acetyl_l_carnitine_duplicate_parent_is_deprecated_compat_only(iqm: dict) -> None:
    canonical = iqm["l_carnitine"]["forms"]["acetyl-l-carnitine (alcar)"]
    duplicate = iqm["acetyl_l_carnitine"]

    assert duplicate["match_rules"]["parent_id"] == "l_carnitine"
    assert duplicate["match_rules"]["deprecated_in_favor_of"] == "l_carnitine"

    canonical_aliases = {str(a).strip().lower() for a in canonical["aliases"]}
    for form_name, form in duplicate["forms"].items():
        aliases = {str(a).strip().lower() for a in form["aliases"]}
        assert aliases
        assert aliases.isdisjoint(canonical_aliases), (
            f"Deprecated acetyl_l_carnitine::{form_name} must not keep real "
            "ALCAR routing aliases that compete with l_carnitine."
        )
        assert form["bio_score"] == canonical["bio_score"]
        assert form["score"] == canonical["score"]
        assert "deprecated compatibility form" in form["notes"]


@pytest.mark.parametrize(
    "parent,form_name,required_aliases",
    [
        (
            "lions_mane",
            "lions mane standardized extract",
            {"lion's mane mushroom extract", "lions mane mushroom extract"},
        ),
        ("reishi", "reishi standardized extract", {"reishi mushroom extract"}),
        ("maitake", "maitake d-fraction", {"maitake mushroom extract"}),
        ("turkey_tail", "turkey tail standardized extract", {"turkey tail mushroom extract"}),
        ("cordyceps", "cordyceps militaris", {"cordyceps mushroom extract"}),
    ],
)
def test_common_mushroom_extract_labels_stay_scorable(
    iqm: dict,
    parent: str,
    form_name: str,
    required_aliases: set[str],
) -> None:
    aliases = {
        str(alias).strip().lower()
        for alias in iqm[parent]["forms"][form_name]["aliases"]
    }
    assert required_aliases <= aliases
