"""Rows whose own label prints Clarinol reach the existing Clarinol form.

Each row was read against its NIH-hosted label PDF. DSLD keeps Clarinol only as
an alternate name on these rows, so they scored as an unspecified form. The fix
is one exact product correction per label. Nothing may read alternate names, and
the Clarinol grade and evidence stay as they are.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "data"

# id, source path, row name, printed amount, unit, DSLD source form kept
PRINTED_CLARINOL = [
    ("228934", "ingredientRows[4]", "CLA", 500, "mg", "Safflower Oil"),
    ("183546", "ingredientRows[2]", "CLA", 4000, "mg", "Safflower Oil"),
    ("213306", "ingredientRows[4]", "CLA", 3.4, "Gram(s)", "Safflower Oil"),
    ("176175", "ingredientRows[2]", "Conjugated Linoleic Acid", 4000, "mg", "Safflower Oil"),
    ("70326", "ingredientRows[2]", "Conjugated Linoleic Acid", 4000, "mg", "Safflower Oil"),
    ("1059", "ingredientRows[3]", "Conjugated Linoleic Acid", 1300, "mg", None),
    ("4259", "ingredientRows[3]", "Conjugated Linoleic Acid", 1000, "mg", None),
    ("26318", "ingredientRows[2]", "Conjugated Linoleic Acid", 1000, "mg", None),
    ("65945", "ingredientRows[2]", "Conjugated Linoleic Acid", 1000, "mg", None),
    ("66895", "ingredientRows[2]", "Conjugated Linoleic Acid", 1000, "mg", None),
    ("220140", "ingredientRows[1].nestedRows[1]", "CLA", 1, "Gram(s)", None),
    ("220238", "ingredientRows[1].nestedRows[1]", "CLA", 1, "Gram(s)", None),
    ("220239", "ingredientRows[1].nestedRows[1]", "CLA", 1, "Gram(s)", None),
]

# The one row whose name, not form list, carries Clarinol. A second form would
# turn this row into a blend header and drop it from scoring.
COMPLEX_ROW = ("227855", "ingredientRows[2]", "Clarinol CLA Complex", 1.3, "Gram(s)", "Conjugated Linoleic Acid")


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _raw(pid):
    return json.loads((FIXTURES / f"clarinol_source_{pid}_raw.json").read_text())


def _source_row(raw, path):
    row = None
    rows = raw["ingredientRows"]
    for part in path.replace("ingredientRows", "").split("."):
        if part.startswith("nestedRows"):
            rows = row["nestedRows"]
            part = part.replace("nestedRows", "")
        row = rows[int(part.strip("[]"))]
    return row


def _quality_row(enricher, raw, path):
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = enricher.enrich_product(cleaned)
    rows = enriched["ingredient_quality_data"]["ingredients"]
    [row] = [r for r in rows if r.get("raw_source_path") == path]
    return row


@pytest.mark.parametrize("pid,path,name,amount,unit,source_form", PRINTED_CLARINOL + [COMPLEX_ROW])
def test_printed_clarinol_reaches_the_existing_form(enricher, pid, path, name, amount, unit, source_form):
    row = _quality_row(enricher, _raw(pid), path)
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())
    assert row["canonical_id"] == "cla"
    assert row["form_id"] == "clarinol"
    assert row["bio_score"] == iqm["cla"]["forms"]["clarinol"]["bio_score"]
    assert row["quantity"] == amount and row["unit"] == unit
    assert row["cleaner_row_role"] == "active_scorable"


@pytest.mark.parametrize("pid,path,name,amount,unit,source_form", PRINTED_CLARINOL)
def test_correction_is_bound_to_this_row_and_keeps_the_source_form(pid, path, name, amount, unit, source_form):
    corrections = json.loads((DATA / "curated_overrides" / "product_label_corrections.json").read_text())["corrections"]
    entry = corrections[pid]
    assert entry["raw_ingredient_text"] == name
    assert entry["corrected_ingredient_text"] == name
    assert entry["correction_fields"] == ["forms"]
    assert entry["raw_source_path"] == path
    assert entry["raw_quantity_value"] == amount and entry["raw_quantity_unit"] == unit
    assert f"https://api.ods.od.nih.gov/dsld/s3/pdf/{pid}.pdf" in entry["sources"]
    assert entry["scope"] == "dsld_id_only"
    assert entry["provenance_tag"] == "official_label_form_correction"
    names = [form["name"] for form in entry["corrected_forms"]]
    assert "Clarinol" in names
    assert names == [n for n in [source_form, "Clarinol"] if n]
    assert [form["name"] for form in entry["raw_forms"]] == ([source_form] if source_form else [])
    assert "Clarinol" not in [form["name"] for form in entry["raw_forms"]]


def test_the_complex_row_keeps_its_printed_form_and_share():
    raw = _raw(COMPLEX_ROW[0])
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    [row] = [r for r in cleaned["activeIngredients"] if r["raw_source_path"] == COMPLEX_ROW[1]]
    [form] = row["forms"]
    assert form["name"] == "Conjugated Linoleic Acid"
    assert form["prefix"] == "providing" and form["percent"] == 78
    assert row["quantity"] == 1.3 and row["unit"] == "Gram(s)"
    entry = json.loads((DATA / "curated_overrides" / "product_label_corrections.json").read_text())["corrections"][COMPLEX_ROW[0]]
    assert entry["correction_fields"] == ["name"]
    assert "corrected_forms" not in entry
    assert entry["raw_ingredient_text"] == COMPLEX_ROW[2]


@pytest.mark.parametrize("pid,path", [("228934", "ingredientRows[4]"), ("1059", "ingredientRows[3]"), ("220140", "ingredientRows[1].nestedRows[1]")])
def test_an_alternate_name_alone_never_reaches_clarinol(enricher, pid, path):
    raw = _raw(pid)
    assert any("Clarinol" in alt for alt in _source_row(raw, path)["alternateNames"])
    raw["id"] = 999999999
    assert _quality_row(enricher, raw, path)["form_id"] != "clarinol"


@pytest.mark.parametrize("change", ["amount", "unit", "form"])
@pytest.mark.parametrize("pid,path", [("228934", "ingredientRows[4]"), ("227855", "ingredientRows[2]")])
def test_a_changed_edition_does_not_inherit_the_correction(enricher, change, pid, path):
    raw = _raw(pid)
    row = _source_row(raw, path)
    if change == "amount":
        row["quantity"][0]["quantity"] = 501
    elif change == "unit":
        row["quantity"][0]["unit"] = "IU"
    else:
        row["forms"][0]["name"] = "Sunflower Oil"
    assert _quality_row(enricher, raw, path)["form_id"] != "clarinol"


def test_the_correction_changes_no_other_row_on_the_label(enricher):
    raw = _raw("228934")
    corrected = EnhancedDSLDNormalizer().normalize_product(copy.deepcopy(raw))
    raw["id"] = 999999999
    plain = EnhancedDSLDNormalizer().normalize_product(raw)
    def strip(rows):
        return {r["raw_source_path"]: (r["name"], r.get("quantity"), r.get("unit"), [f.get("name") for f in r.get("forms") or []]) for r in rows}
    before, after = strip(plain["activeIngredients"]), strip(corrected["activeIngredients"])
    assert set(before) == set(after)
    assert {path for path in before if before[path] != after[path]} == {"ingredientRows[4]"}


def test_the_clarinol_form_itself_is_unchanged():
    form = json.loads((DATA / "ingredient_quality_map.json").read_text())["cla"]["forms"]["clarinol"]
    assert form["bio_score"] == 13
    assert "source_form_aliases" not in form
    assert not any("safflower" in alias.lower() for alias in form["aliases"])
