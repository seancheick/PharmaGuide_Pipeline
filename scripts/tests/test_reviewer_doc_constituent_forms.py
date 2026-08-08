"""Total-vs-constituent-forms notes must rest on label nesting, not arithmetic.

A reviewer told "**Leucine 3000** is the TOTAL, do NOT add the entries after it"
scores that product against 3000 mg of BCAA instead of 6000 mg. The benchmark is
the human oracle the v4 dose pillar is calibrated against, so a wrong note does
not just mislead a reader -- it moves the ground truth.

The rule that produced those notes had no identity signal at all: it asked only
whether the next 2-3 amounts summed to the current one. On the shipped corpus it
fired on 806 products, 639 of them (79%) pairing chemically unrelated actives,
because a 2:1:1 BCAA ratio makes `Leucine == Isoleucine + Valine` arithmetically
true by construction.

The relationship is now resolved once, in the freeze, from the label's own row
nesting; build_review_doc only renders it. These tests pin both halves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audits" / "v4_reviewer_benchmark"))
sys.path.insert(0, str(ROOT / "audits"))

from build_review_doc import facts, rollup  # noqa: E402
from v4_reviewer_benchmark_freeze import (  # noqa: E402
    _direct_child_path,
    _reviewer_packet_row,
    _resolve_constituent_rollups,
    _rollup_unit,
)

BLOBS = ROOT / "dist" / "detail_blobs"


def _packet_actives(detail):
    """The packet's active list, exactly as the freeze emits it."""
    return json.loads(
        _reviewer_packet_row("PG-TEST", 1, detail)["active_ingredients_json"]
    )


def _resolved(*rows):
    """Run the freeze's resolver over hand-built packet rows."""
    rows = list(rows)
    _resolve_constituent_rollups(rows)
    return rows


def _row(name, quantity, unit, parent_index=None):
    return {"name": name, "quantity": quantity, "unit": unit,
            "parent_index": parent_index}


# --- the shapes the old rule got wrong, as unit cases -----------------------

def test_bcaa_ratio_is_not_a_parent_child_relationship():
    """2:1:1 makes Leucine == Isoleucine + Valine. They are three separate BCAAs."""
    act = _resolved(_row("Leucine", 3000.0, "mg"),
                    _row("Isoleucine", 1500.0, "mg"),
                    _row("Valine", 1500.0, "mg"))
    assert rollup(act) is None


def test_unrelated_compounds_that_happen_to_sum_are_not_forms():
    """GABA 200 == Theanine 100 + Rhodiola 100 (dsld 184853), all top-level rows."""
    act = _resolved(_row("GABA", 200.0, "mg"),
                    _row("Theanine", 100.0, "mg"),
                    _row("Rhodiola", 100.0, "mg"))
    assert rollup(act) is None


def test_sum_across_mixed_units_is_never_a_rollup():
    """Folate 400mcg == B12 50mcg + Biotin 300mcg + Pantothenic Acid 50mg.

    Nested here on purpose: even with structure, mismatched units cannot sum.
    """
    act = _resolved(_row("Folate", 400.0, "mcg"),
                    _row("Vitamin B12", 50.0, "mcg", parent_index=0),
                    _row("Biotin", 300.0, "mcg", parent_index=0),
                    _row("Pantothenic Acid", 50.0, "mg", parent_index=0))
    assert rollup(act) is None


def test_phantom_zero_row_cannot_manufacture_a_two_part_sum():
    """`Isoleucine 4g == Milk Protein 0 + Valine 4g` is just Iso == Val (dsld 243776)."""
    act = _resolved(_row("Isoleucine", 4.0, "g"),
                    _row("Milk Protein", 0.0, "NP", parent_index=0),
                    _row("Valine", 4.0, "g", parent_index=0))
    assert rollup(act) is None


def test_nested_marker_row_that_does_not_sum_is_not_additive():
    """A `standardized to X` child is nested but NOT a part of an additive total."""
    act = _resolved(_row("Turmeric Extract", 500.0, "mg"),
                    _row("Curcuminoids", 95.0, "mg", parent_index=0),
                    _row("Turmerones", 5.0, "mg", parent_index=0))
    assert rollup(act) is None


def test_parent_must_account_for_all_of_its_children_not_a_subset():
    """Source hierarchies are not infallible -- dsld 49236 nests `Vitamin B12`
    under `Vitamin K`. Where the declared children do not reconcile to the
    parent, no claim is made rather than cherry-picking the ones that do."""
    act = _resolved(_row("Vitamin K", 2200.0, "mcg"),
                    _row("Vitamin K (Phylloquinone)", 1000.0, "mcg", parent_index=0),
                    _row("Vitamin K (menaquinone)", 1000.0, "mcg", parent_index=0),
                    _row("Vitamin K (menaquinone)", 200.0, "mcg", parent_index=0),
                    _row("Vitamin B12", 300.0, "mcg", parent_index=0))
    assert rollup(act) is None


def test_label_nested_forms_are_still_recognised():
    """The real relationship -- Magnesium 135 mg over its two forms (dsld 328832)."""
    act = _resolved(_row("Magnesium", 135.0, "mg"),
                    _row("Magnesium", 55.0, "mg", parent_index=0),
                    _row("Magnesium", 80.0, "mg", parent_index=0))
    got = rollup(act)
    assert got is not None
    parent, kids = got
    assert parent["quantity"] == 135.0
    assert [k["quantity"] for k in kids] == [55.0, 80.0]


def test_float_sum_tolerance_is_unit_aware_not_absolute():
    """Riboflavin 28.6 == 25.0 + 3.6 survives binary floating point (dsld packet)."""
    act = _resolved(_row("Riboflavin", 28.6, "mg"),
                    _row("Riboflavin", 25.0, "mg", parent_index=0),
                    _row("Riboflavin", 3.6, "mg", parent_index=0))
    assert rollup(act) is not None


def test_unit_aliases_do_not_silently_merge_distinct_scales():
    assert _rollup_unit("Gram(s)") == _rollup_unit("g") == "g"
    assert _rollup_unit("microgram(s)") == _rollup_unit("mcg") == "mcg"
    assert _rollup_unit("mcg DFE") == "mcg dfe"
    assert _rollup_unit("mcg RAE") == "mcg rae"
    assert _rollup_unit("mg NE") == "mg ne"
    assert _rollup_unit("mcg DFE") != _rollup_unit("mcg")
    assert _rollup_unit("mcg RAE") != _rollup_unit("mcg")
    assert _rollup_unit("mg") != _rollup_unit("mcg")
    # unusable units normalise to empty and disqualify a parent outright
    assert _rollup_unit("NP") == "" and _rollup_unit("unspecified") == ""


def test_semantic_dose_bases_never_reconcile_with_plain_mass():
    """Folate DFE and vitamin-A RAE are not aliases for literal micrograms."""
    folate = _resolved(
        _row("Folate", 400.0, "mcg DFE"),
        _row("Folic acid", 200.0, "mcg", parent_index=0),
        _row("Methylfolate", 200.0, "mcg", parent_index=0),
    )
    vitamin_a = _resolved(
        _row("Vitamin A", 900.0, "mcg RAE"),
        _row("Retinol", 450.0, "mcg", parent_index=0),
        _row("Beta-carotene", 450.0, "mcg", parent_index=0),
    )

    assert rollup(folate) is None
    assert rollup(vitamin_a) is None


def test_grandchildren_are_not_counted_as_direct_parts():
    assert _direct_child_path("ingredientRows[0].nestedRows[1]", "ingredientRows[0]")
    assert not _direct_child_path(
        "ingredientRows[0].nestedRows[1].nestedRows[0]", "ingredientRows[0]")


def test_siblings_under_a_shared_blend_header_are_not_parent_and_child():
    """The BCAA case as the source actually shapes it (dsld 211337): Leucine is
    `nestedRows[0]`, Isoleucine `nestedRows[1]` -- siblings, not parent/child."""
    assert not _direct_child_path(
        "ingredientRows[7].nestedRows[1]", "ingredientRows[7].nestedRows[0]")


def test_row_index_prefix_is_not_mistaken_for_nesting():
    assert not _direct_child_path("ingredientRows[10]", "ingredientRows[1]")


def test_doc_builder_renders_only_and_infers_nothing():
    """Arithmetic that sums perfectly is inert without the resolved relationship."""
    act = [_row("Leucine", 3000.0, "mg"),
           _row("Isoleucine", 1500.0, "mg"),
           _row("Valine", 1500.0, "mg")]
    assert rollup(act) is None, "doc builder must not re-derive the relationship"


def test_doc_builder_rejects_out_of_range_child_indexes():
    act = [_row("Magnesium", 135.0, "mg"), _row("Magnesium", 135.0, "mg", 0)]
    act[0]["constituent_child_indexes"] = [1, 99]
    assert rollup(act) is None


def _reviewer_row(serving_info):
    return {
        "serving_info_json": json.dumps(serving_info),
        "active_ingredients_json": "[]",
        "inactive_ingredients_json": "[]",
        "certification_facts_json": "{}",
        "proprietary_blend_facts_json": "{}",
    }


def test_reviewer_doc_accepts_a_direction_sourced_weekly_regimen():
    rendered, notes = facts(_reviewer_row({
        "min_servings_per_day": 1 / 7,
        "max_servings_per_day": 1 / 7,
        "servings_per_day_source": "directions",
    }))

    assert "**Servings/day:** 0.143" in rendered
    assert not any("defect" in note or "implausible" in note for note in notes)


def test_reviewer_doc_does_not_override_a_high_label_frequency():
    rendered, notes = facts(_reviewer_row({
        "min_servings_per_day": 6,
        "max_servings_per_day": 6,
        "servings_per_day_source": "directions",
    }))

    assert "**Servings/day:** 6" in rendered
    assert not any("implausible" in note for note in notes)


def test_reviewer_doc_fails_closed_on_an_untrusted_fraction():
    rendered, notes = facts(_reviewer_row({
        "min_servings_per_day": 0.044,
        "max_servings_per_day": 0.044,
        "servings_per_day_source": "servingSizes",
    }))

    assert "**Servings/day:** 1" in rendered
    assert notes == [
        "servings-per-day provenance is not trustworthy — verify the labeled directions"
    ]


# --- the real corpus --------------------------------------------------------

@pytest.mark.skipif(not BLOBS.is_dir(), reason="shipped detail blobs not built")
def test_no_chemically_unrelated_rollup_survives_on_the_shipped_corpus():
    """Every note emitted across the catalog must be structurally evidenced.

    Guards the regression directly: re-introducing arithmetic-only matching puts
    the BCAA, GABA and Folate shapes straight back into this count.
    """
    blobs = sorted(BLOBS.glob("*.json"))
    assert len(blobs) > 1000, f"corpus too small to be meaningful: {len(blobs)}"

    emitted = 0
    offenders = []
    for path in blobs:
        act = _packet_actives(json.loads(path.read_text()))
        got = rollup(act)
        if not got:
            continue
        emitted += 1
        parent, kids = got
        index = next(i for i, row in enumerate(act) if row is parent)
        unit = _rollup_unit(parent["unit"])
        declared = [i for i, row in enumerate(act) if row.get("parent_index") == index]

        why = []
        if any(kid.get("parent_index") != index for kid in kids):
            why.append("child is not a declared direct child of the parent")
        if len(kids) != len(declared):
            why.append("parent's other declared children are unaccounted for")
        if any(_rollup_unit(kid["unit"]) != unit for kid in kids):
            why.append("child unit differs from the parent's")
        if any(not isinstance(k["quantity"], (int, float)) or k["quantity"] <= 0
               for k in kids):
            why.append("non-positive child amount")
        if abs(sum(k["quantity"] for k in kids) - parent["quantity"]) > 1e-6:
            why.append("children do not sum to the parent")
        if why:
            offenders.append((path.stem, parent["name"], why))

    assert not offenders, (
        f"{len(offenders)} rollups lack parent/child evidence: {offenders[:10]}")
    # Arithmetic-only matching fired on 806 products; label nesting fires on 171.
    assert 100 <= emitted <= 300, (
        f"{emitted} products emit a total-vs-forms note; expected ~171. A large "
        "jump means the identity gate regressed back toward arithmetic matching."
    )


@pytest.mark.skipif(not BLOBS.is_dir(), reason="shipped detail blobs not built")
def test_parent_index_encoding_is_acyclic_and_well_formed():
    """A row cannot be its own parent, point out of range, or form a cycle."""
    for path in sorted(BLOBS.glob("*.json")):
        act = _packet_actives(json.loads(path.read_text()))
        for index, row in enumerate(act):
            parent = row.get("parent_index")
            if parent is None:
                continue
            assert isinstance(parent, int) and 0 <= parent < len(act), path.stem
            assert parent != index, f"{path.stem}: row {index} is its own parent"
            seen, cursor = {index}, parent
            while cursor is not None:
                assert cursor not in seen, f"{path.stem}: parent_index cycle"
                seen.add(cursor)
                cursor = act[cursor].get("parent_index")


@pytest.mark.skipif(not BLOBS.is_dir(), reason="shipped detail blobs not built")
def test_known_false_pairs_are_gone_from_the_corpus():
    """The exact products a reviewer flagged must no longer carry a note."""
    flagged = {
        "184853": ("GABA", {"Theanine", "Rhodiola"}),
        "211337": ("Leucine", {"Isoleucine", "Valine"}),
    }
    for dsld_id, (parent_name, kid_names) in flagged.items():
        blob = BLOBS / f"{dsld_id}.json"
        if not blob.is_file():
            pytest.skip(f"{dsld_id} not in this catalog build")
        got = rollup(_packet_actives(json.loads(blob.read_text())))
        if got is None:
            continue
        parent, kids = got
        assert not (parent["name"] == parent_name
                    and {k["name"] for k in kids} & kid_names), (
            f"dsld {dsld_id}: {parent_name} still claimed as the total of {kid_names}")
