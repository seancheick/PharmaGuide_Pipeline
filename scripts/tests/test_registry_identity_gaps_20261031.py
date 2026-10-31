"""Registry identity gaps left by the PR #318 replay (October 31, 2026).

Identity is by chemistry or organism, never by a shared vernacular word:
- L-cystine (PubChem CID 67678, GSRS UNII 48TCX9A1VT) is the disulfide dimer
  of L-cysteine (UNII K848JZ4886); it had no registry owner, so Solgar
  L-Cystine 213846 was unmapped and NOT_SCORED.
- Rows that print the Panax quinquefolius binomial fell to the generic
  "ginseng (unspecified)" form of IQM ginseng instead of its American ginseng
  species form. The IQM canonical stays `ginseng`: Sean's October 29 attested
  Dose scopes are keyed to it (test_attested_botanical_dose_scopes.py).
- A Butcher's Broom leaf/stem row resolved by the cleaner to the part-less
  standardized_botanicals identity was overwritten in enrichment by the root
  entry, because the recognition index reached the root record's alias first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from test_preparation_identity_splits import _raw_product, _raw_row  # noqa: E402

FIXTURES = TESTS / "fixtures"
AMERICAN_FORM = "american ginseng (panax quinquefolius)"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(raw):
        cleaned = normalizer.normalize_product(raw)
        return cleaned, enricher.enrich_product(cleaned)[0]

    return run


def _fixture(pid):
    return json.loads((FIXTURES / f"raw_registry_gap_{pid}.json").read_text())


def _iqd(enriched, name):
    return [row for row in enriched["ingredient_quality_data"].get("ingredients") or []
            if row.get("name") == name]


def _active(cleaned, name):
    return [row for row in cleaned["activeIngredients"] if row.get("name") == name]


# ── L-cystine ────────────────────────────────────────────────────────────────

def test_solgar_l_cystine_label_has_its_own_identity(pipeline):
    cleaned, enriched = pipeline(_fixture("213846"))
    [active] = _active(cleaned, "L-Cystine")
    assert (active["canonical_id"], active["canonical_source_db"]) == (
        "l_cystine", "ingredient_quality_map")
    [row] = _iqd(enriched, "L-Cystine")
    assert row["canonical_id"] == "l_cystine"


@pytest.mark.parametrize("name,group", [
    ("L-Cystine", "Cystine"), ("Cystine", "Cystine"), ("L Cystine", "Cystine"),
])
def test_cystine_rows_resolve_to_cystine_not_cysteine(pipeline, name, group):
    cleaned, enriched = pipeline(_raw_product(990501, [
        _raw_row(1, name, group, category="amino acid", quantity=500, unit="mg")]))
    assert {r["canonical_id"] for r in _active(cleaned, name)} == {"l_cystine"}
    assert {r["canonical_id"] for r in _iqd(enriched, name)} == {"l_cystine"}


@pytest.mark.parametrize("name,group,expected", [
    ("L-Cysteine", "Cysteine", "l_cysteine"),
    ("N-Acetyl-L-Cysteine", "N-Acetyl Cysteine", "nac"),
])
def test_cysteine_and_nac_keep_their_own_identity(pipeline, name, group, expected):
    _, enriched = pipeline(_raw_product(990502, [
        _raw_row(1, name, group, category="amino acid", quantity=500, unit="mg")]))
    assert {r["canonical_id"] for r in _iqd(enriched, name)} == {expected}


def test_acetylated_cystine_misprint_is_not_l_cystine(pipeline):
    # GNC 78327 prints "N-Acetyl-L-Cystine": neither cystine nor, by its own
    # words, NAC. It stays unresolved rather than borrow either identity.
    name = "N-Acetyl-L-Cystine"
    cleaned, enriched = pipeline(_raw_product(990503, [
        _raw_row(1, name, "N-Acetyl Cysteine", category="amino acid", quantity=15, unit="mg")]))
    ids = {r.get("canonical_id") for r in _active(cleaned, name) + _iqd(enriched, name)}
    assert "l_cystine" not in ids and "l_cysteine" not in ids


def test_l_cystine_entry_carries_verified_identifiers():
    entry = json.loads((TESTS.parent / "data" / "ingredient_quality_map.json").read_text())["l_cystine"]
    assert entry["external_ids"] == {"unii": "48TCX9A1VT", "cas": "56-89-3", "pubchem_cid": 67678}
    assert entry["cui"] == "C0010682" and entry["rxcui"] == "3036"
    assert "acetyl" in entry["match_rules"]["negative_match_terms"]


# ── American ginseng ─────────────────────────────────────────────────────────

def test_multi_part_american_ginseng_row_keeps_its_species_form(pipeline):
    name = "American Ginseng Rhizome, Root Extract"
    cleaned, enriched = pipeline(_fixture("330196"))
    [active] = _active(cleaned, name)
    assert active["canonical_id"] == "ginseng"
    [row] = _iqd(enriched, name)
    assert (row["canonical_id"], row["matched_form"]) == ("ginseng", AMERICAN_FORM)


@pytest.mark.parametrize("name,form", [
    ("American Ginseng Rhizome Extract", "Panax quinquefolius Rhizome Extract"),
    ("American Ginseng Rhizome Extract", "Panax quinquefolium L. Rhizome Extract"),
    ("American Ginseng Root Extract", "Panax quinquefolius Root Extract"),
])
def test_binomial_declared_american_rows_use_the_species_form(pipeline, name, form):
    _, enriched = pipeline(_raw_product(990511, [
        _raw_row(1, name, "American Ginseng", quantity=500, unit="mg", forms=[form])]))
    assert {(r["canonical_id"], r["matched_form"]) for r in _iqd(enriched, name)} == {
        ("ginseng", AMERICAN_FORM)}


@pytest.mark.parametrize("name,group", [
    ("Panax Ginseng Root Extract", "Panax Ginseng"),
    ("Asian Ginseng root extract", "Oriental Ginseng"),
    ("Korean Ginseng extract", "Ginseng, Panax"),
])
def test_asian_ginseng_rows_never_take_the_american_form(pipeline, name, group):
    _, enriched = pipeline(_raw_product(990512, [
        _raw_row(1, name, group, quantity=500, unit="mg")]))
    forms = {r["matched_form"] for r in _iqd(enriched, name)}
    assert forms and AMERICAN_FORM not in forms


# ── Butcher's broom ──────────────────────────────────────────────────────────

def test_leaf_stem_butchers_broom_is_not_the_root_identity(pipeline):
    name = "Butcher's Broom Leaf, Stem Extract"
    cleaned, enriched = pipeline(_fixture("311195"))
    [active] = _active(cleaned, name)
    assert (active["canonical_id"], active["canonical_source_db"]) == (
        "butcher_s_broom", "standardized_botanicals")
    [row] = _iqd(enriched, name)
    assert (row["canonical_id"], row["canonical_source_db"]) == (
        "butcher_s_broom", "standardized_botanicals")


@pytest.mark.parametrize("name", ["Butcher's Broom Leaf Extract", "Butcher's Broom Stem Extract"])
def test_single_part_aerial_butchers_broom_is_not_root(pipeline, name):
    _, enriched = pipeline(_raw_product(990521, [
        _raw_row(1, name, "Butcher's Broom", quantity=500, unit="mg")]))
    assert {r["canonical_id"] for r in _iqd(enriched, name)} - {None} <= {"butcher_s_broom"}
    assert "butchers_broom_root" not in {r["canonical_id"] for r in _iqd(enriched, name)}


@pytest.mark.parametrize("name", ["Butcher's Broom root powder", "Butcher's Broom Root Extract"])
def test_root_butchers_broom_keeps_the_root_identity(pipeline, name):
    _, enriched = pipeline(_raw_product(990522, [
        _raw_row(1, name, "Butcher's Broom", quantity=500, unit="mg")]))
    assert {r["canonical_id"] for r in _iqd(enriched, name)} == {"butchers_broom_root"}


def test_partless_butchers_broom_row_on_a_root_product_is_unchanged(pipeline):
    # Nature's Way 251524 prints "Butcher's Broom" with no part on the row; its
    # existing root recognition is a separate question and is not moved here.
    _, enriched = pipeline(_fixture("251524"))
    assert {r["canonical_id"] for r in _iqd(enriched, "Butcher's Broom")} == {"butchers_broom_root"}


@pytest.mark.parametrize("declared,entry_name,expected", [
    ("leaf and stem", "Butcher's Broom Root", True),
    ("leaf", "Butcher's Broom Root", True),
    ("root", "Butcher's Broom Root", False),
    (None, "Butcher's Broom Root", False),           # part-less row: no evidence against
    ("leaf and stem", "Butcher's Broom", False),     # part-less record
    ("leaves", "Ginkgo Biloba Leaf", False),         # plural of the same organ
    ("fruit", "Schisandra Berry", False),            # a berry is the fruit
    ("root and rhizome", "Ginseng Root (Panax)", False),
])
def test_undeclared_part_guard_compares_organs_not_spellings(declared, entry_name, expected):
    from enrich_supplements_v3 import SupplementEnricherV3
    assert SupplementEnricherV3._names_undeclared_plant_part(declared, entry_name) is expected
