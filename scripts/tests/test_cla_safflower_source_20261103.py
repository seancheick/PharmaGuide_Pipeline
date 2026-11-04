"""A bare botanical source under a fatty-acid parent is nondisclosure, not a form.

295001 prints conjugated linoleic acid with safflower as its source. It prints no
80% preparation, brand or standardization, so the row earns exactly what a CLA row
with no form earns, from the existing nondisclosure owner. Disclosed preparations
and tokens that are not a bare source must not reach this path.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import enrich_supplements_v3
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_reference_resolver import unknown_form_quality

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "data"
PATH = "ingredientRows[0]"


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def iqm():
    return json.loads((DATA / "ingredient_quality_map.json").read_text())


def _raw():
    return json.loads((FIXTURES / "cla_safflower_source_295001_raw.json").read_text())


def _form(name, *, group=None, category="botanical", percent=None, prefix=None):
    return {
        "order": 1,
        "ingredientId": 285710,
        "prefix": prefix,
        "percent": percent,
        "name": name,
        "category": category,
        "ingredientGroup": group if group is not None else name,
        "uniiCode": None,
    }


def _row(enricher, forms=None):
    raw = _raw()
    if forms is not None:
        raw["ingredientRows"][0]["forms"] = copy.deepcopy(forms)
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    [row] = [
        r for r in enriched["ingredient_quality_data"]["ingredients"]
        if r.get("raw_source_path") == PATH
    ]
    return row


def test_fixture_is_the_printed_source_row():
    [row] = _raw()["ingredientRows"]
    [form] = row["forms"]
    assert row["name"] == "Conjugated Linoleic Acid" and row["category"] == "fatty acid"
    assert form["name"] == "Safflower" and form["category"] == "botanical"
    assert form["ingredientGroup"] == "Safflower"
    assert form["percent"] is None


def test_safflower_source_scores_exactly_like_no_form_at_all(enricher):
    source, none = _row(enricher), _row(enricher, [])
    for field in ("canonical_id", "form_id", "matched_form", "bio_score",
                  "absorption", "natural", "cleaner_row_role"):
        assert source.get(field) == none.get(field), field
    assert source["canonical_id"] == "cla"
    assert source["form_id"] is None
    assert source["matched_form"] == "unspecified"
    assert source["form_match_status"] != "unmapped"
    assert source["source_label_form"] == "Safflower"


def test_the_floor_comes_from_the_nondisclosure_owner(enricher, iqm, monkeypatch):
    owner = unknown_form_quality(iqm["cla"])
    assert owner["form_id"] is None
    assert owner["basis"] == "derived_lowest_eligible_minus_one"
    named = [form["bio_score"] for form in iqm["cla"]["forms"].values()]
    assert owner["bio_score"] == min(named) - 1
    assert _row(enricher)["bio_score"] == owner["bio_score"]

    # Move the owner: the row follows, so no value is hard-coded on this path.
    def moved(parent):
        result = dict(unknown_form_quality(parent) or {})
        result["bio_score"] = 7.0
        return result

    monkeypatch.setattr(enrich_supplements_v3, "unknown_form_quality", moved)
    # A fresh enricher: the shared one has already cached this row's match.
    assert _row(SupplementEnricherV3())["bio_score"] == 7.0


def test_no_preparation_brand_or_absorption_credit_attaches(enricher, iqm):
    row = _row(enricher)
    assert row["matched_form"] not in iqm["cla"]["forms"]
    assert row["form_id"] not in iqm["cla"]["forms"]
    assert row.get("absorption") is None
    assert row.get("natural") is None
    for form in iqm["cla"]["forms"].values():
        assert form.get("consumer_note") not in {row.get("notes"), row.get("consumer_note")}
    text = json.dumps(row, ensure_ascii=False, default=str).lower()
    assert "80%" not in text
    assert "tonalin" not in text and "clarinol" not in text


def test_no_safflower_alias_reaches_a_named_cla_form(iqm):
    for form in iqm["cla"]["forms"].values():
        aliases = {str(alias).strip().lower() for alias in form.get("aliases") or []}
        assert not aliases & {"safflower", "safflower oil", "cla (safflower)"}


@pytest.mark.parametrize(
    "form",
    [
        pytest.param(_form("SafflowerMax CLA", group="Safflower"), id="branded-token"),
        pytest.param(_form("Safflower 80%", group="Safflower"), id="percent-in-name"),
        pytest.param(_form("Safflower 80%"), id="percent-in-name-and-group"),
        pytest.param(_form("Safflower 80"), id="digit-in-name-and-group"),
        pytest.param(_form("Safflower Extract", group="Safflower"), id="extract"),
        pytest.param(_form("Safflower", percent=80), id="printed-percent"),
        pytest.param(_form("Safflower", category="non-nutrient/non-botanical"), id="not-botanical"),
        pytest.param(_form("Safflower", category="protein"), id="protein-class"),
        pytest.param(_form("Xanthoplex", group="Safflower"), id="unknown-preparation"),
    ],
)
def test_anything_but_a_bare_source_stays_unmapped_for_curation(enricher, form):
    row = _row(enricher, [form])
    assert row["form_match_status"] == "unmapped"
    assert row["bio_score"] is None
    assert row["matched_form"] is None


@pytest.mark.parametrize(
    "name,form_id",
    [("Clarinol", "clarinol"), ("Tonalin", "tonalin"), ("CLA Safflower Oil", "cla 80%")],
)
def test_disclosed_forms_still_win(enricher, iqm, name, form_id):
    row = _row(enricher, [_form(name, group="Conjugated Linoleic Acid", category="fatty acid")])
    assert row["form_id"] == form_id
    assert row["bio_score"] == iqm["cla"]["forms"][form_id]["bio_score"]


def test_a_fatty_acid_source_needs_no_printed_percentage():
    assert SupplementEnricherV3._is_cross_class_source_form(
        {"raw_form_text": "Safflower", "dsld_category": "botanical",
         "dsld_ingredient_group": "Safflower", "percent_share": 1.0},
        "fatty_acids",
    )
    assert not SupplementEnricherV3._is_cross_class_source_form(
        {"raw_form_text": "Safflower", "dsld_category": "botanical",
         "dsld_ingredient_group": "Safflower", "percent_share": 0.8},
        "fatty_acids",
    )


@pytest.mark.parametrize("parent", ["vitamins", "minerals", "amino_acids", "enzymes"])
def test_defined_nutrient_parents_keep_their_wider_rule(parent):
    assert SupplementEnricherV3._is_cross_class_source_form(
        {"raw_form_text": "Acerola Extract", "dsld_category": "botanical",
         "dsld_ingredient_group": "Acerola", "percent_share": 0.5},
        parent,
    )


@pytest.mark.parametrize("parent", ["botanicals", "other", "proteins", "", None])
def test_other_parents_do_not_gain_the_rule(parent):
    assert not SupplementEnricherV3._is_cross_class_source_form(
        {"raw_form_text": "Safflower", "dsld_category": "botanical",
         "dsld_ingredient_group": "Safflower", "percent_share": 1.0},
        parent,
    )
