"""Structural source totals must not compete with their own evidenced active."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scoring_input_contract import get_scoring_ingredients
from scoring_v4.modules.generic_evidence import score_evidence


def _ps_complex_product():
    # DSLD 213475 declares 100 mg PS within a 500 mg SerinAid complex.
    # Use the existing evidence record unchanged: this tests ownership, not
    # its clinical classification, score magnitudes, or a new dose threshold.
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "data/backed_clinical_studies.json")
        .read_text()
    )
    evidence = deepcopy(next(
        entry for entry in registry["backed_clinical_studies"]
        if entry["id"] == "BRAND_PHOSPHATIDYLSERINE"
    ))
    child_ref = "ingredientRows[1].nestedRows[0]"
    evidence.update(
        ingredient="Phosphatidylserine",
        matched_source_row_refs=[child_ref],
        matched_canonical_ids=["phosphatidylserine"],
    )
    child = {
        "name": "Phosphatidylserine",
        "standard_name": "Phosphatidylserine",
        "canonical_id": "phosphatidylserine",
        "canonical_source_db": "ingredient_quality_map",
        "quantity": 100.0,
        "unit": "mg",
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "canonical_id_before": "phosphatidylserine",
        "canonical_id_after": "phosphatidylserine",
        "source_section": "active",
        "raw_source_path": child_ref,
        "raw_source_text": "Phosphatidylserine",
        "dose_class": "therapeutic_mass",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    complex_total = {
        "name": "SerinAid Phosphatidylserine complex",
        "canonical_id": "phosphatidylserine",
        "clean_identity_id": "phosphatidylserine",
        "scoring_parent_id": "phosphatidylserine",
        "evidence_canonical_id": "phosphatidylserine",
        "canonical_source_db": "ingredient_quality_map",
        "evidence_origin": "compatibility_derived",
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": 500.0,
        "dose_unit": "mg",
        "source": "activeIngredients",
        "raw_source_path": "ingredientRows[1]",
        "evidence_scope": "blend_level",
        "linked_rows": ["ingredientRows[1]"],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
    }
    return {
        "id": "213475-source-owner-regression",
        "product_name": "Phosphatidylserine 100 mg",
        "ingredient_quality_data": {
            "ingredients": [child],
            "ingredients_scorable": [child],
        },
        "product_scoring_evidence": [complex_total],
        "evidence_data": {"clinical_matches": [evidence]},
    }


def test_ps_complex_total_does_not_dilute_its_only_evidenced_active():
    product = _ps_complex_product()
    child_ref = "ingredientRows[1].nestedRows[0]"
    original = deepcopy(product)
    rows = get_scoring_ingredients(product, strict=True).rows
    by_ref = {row["raw_source_path"]: row for row in rows}
    assert set(by_ref) == {"ingredientRows[1]", child_ref}
    assert by_ref[child_ref]["quantity"] == 100.0
    assert by_ref[child_ref].get("scoring_input_kind") != "product_level_evidence"
    assert by_ref["ingredientRows[1]"]["quantity"] == 500.0
    assert by_ref["ingredientRows[1]"]["scoring_input_kind"] == "product_level_evidence"
    assert {row["canonical_id"] for row in rows} == {"phosphatidylserine"}

    without_total = deepcopy(product)
    without_total["product_scoring_evidence"] = []
    control = score_evidence(without_total, apply_primary_floor=True)
    actual = score_evidence(product, apply_primary_floor=True)
    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )
    assert actual["score"] == control["score"]


@pytest.mark.parametrize("canonical,quantity", [
    ("phosphatidylserine", 500.0),
    ("phosphatidylserine", 5000.0),
    ("protein", 25000.0),
])
def test_unrelated_aggregate_still_competes_with_trace_active(canonical, quantity):
    product = _ps_complex_product()
    aggregate = product["product_scoring_evidence"][0]
    aggregate.update(
        name="Unrelated complex",
        raw_source_path="ingredientRows[2]",
        linked_rows=["ingredientRows[2]"],
        dose_value=quantity,
    )
    for field in ("canonical_id", "clean_identity_id", "scoring_parent_id",
                  "evidence_canonical_id"):
        aggregate[field] = canonical

    result = score_evidence(product, apply_primary_floor=True)

    assert result["metadata"]["primary_evidence_floor"] == 0.0


# --- Real-label lineage (public DSLD fixtures, hash-verified) ----------------

import hashlib

from scoring_input_contract import primary_mass_competitor_rows

_FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "audits/probiotic_rubric_review_2026_09_04/cloud_source_lineage_fixtures.json"
)


def _fixture_label(dsld_id: str) -> dict:
    payload = json.loads(_FIXTURES.read_text())
    record = next(p for p in payload["products"] if p["dsld_id"] == dsld_id)
    projection = record["cleaned_label_projection"]
    digest = hashlib.sha256(
        json.dumps(projection, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert digest == record["projection_sha256"], dsld_id
    return deepcopy(projection)


def _tree_nodes(nodes):
    for node in nodes:
        yield node
        yield from _tree_nodes(node.get("nestedIngredients") or [])


def _node_at(label: dict, path: str) -> dict:
    return next(n for n in _tree_nodes(label["activeIngredients"])
                if n["raw_source_path"] == path)


def _ledger_row(node: dict) -> dict:
    # Mirror the cleaner's IQD row for a projected label node (real shape from
    # the enriched corpus: headers are non-scorable structural rows).
    scorable = node.get("cleaner_row_role") == "active_scorable"
    return {
        "name": node["name"],
        "standard_name": node.get("standardName") or node["name"],
        "canonical_id": node["canonical_id"],
        "canonical_source_db": node.get("canonical_source_db") or "ingredient_quality_map",
        "quantity": node.get("quantity"),
        "unit": node.get("unit"),
        "mapped": scorable,
        "mapped_identity": scorable,
        "scoreable_identity": scorable,
        "identity_disposition": "clean",
        "canonical_id_before": node["canonical_id"],
        "canonical_id_after": node["canonical_id"],
        "source_section": "active",
        "raw_source_path": node["raw_source_path"],
        "raw_source_text": node["raw_source_text"],
        "dose_class": node.get("dose_class"),
        "cleaner_row_role": node.get("cleaner_row_role"),
        "score_eligible_by_cleaner": bool(node.get("score_eligible_by_cleaner")),
        "role_classification": "active_scorable" if scorable else "inactive_non_scorable",
        "is_proprietary_blend": (not scorable) and node.get("hierarchyType") == "blend_header",
        "blend_total_weight_only": not scorable,
        "is_parent_total": False,
    }


def _structural_total(node: dict, **overrides) -> dict:
    # Real observed product_scoring_evidence shape for an identity-bearing
    # blend header (see the enriched corpus for 213475 / 218600 / 218838).
    path = overrides.pop("raw_source_path", node["raw_source_path"])
    item = {
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": node["quantity"],
        "dose_unit": node["unit"],
        "source": "active",
        "raw_source_path": path,
        "evidence_scope": "blend_level",
        "linked_rows": [path],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
        "name": node["name"],
        "canonical_id": "phosphatidylserine",
        "clean_identity_id": "phosphatidylserine",
        "scoring_parent_id": "phosphatidylserine",
        "evidence_canonical_id": "phosphatidylserine",
        "canonical_source_db": "ingredient_quality_map",
        "evidence_origin": "compatibility_derived",
        "source_section": "product",
        "raw_source_text": node["raw_source_text"],
        "identity_contract_required": True,
        "identity_disposition": "clean",
    }
    item.update(overrides)
    return item


def _synthetic_blend_projection(node: dict, index: int = 0) -> dict:
    # The enricher's proprietary-blend projection links only its synthetic
    # ``activeIngredients[i]`` path; lineage must resolve through the tree.
    return _structural_total(
        node,
        raw_source_path=f"activeIngredients[{index}]",
        source="proprietary_blends",
        confidence="low",
        reason="proprietary_blend_total_from_botanical_child",
        canonical_source_db="botanical_ingredients",
        identity_disposition=None,
    )


def _ps_evidence(child_ref: str) -> dict:
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "data/backed_clinical_studies.json")
        .read_text()
    )
    evidence = deepcopy(next(
        entry for entry in registry["backed_clinical_studies"]
        if entry["id"] == "BRAND_PHOSPHATIDYLSERINE"
    ))
    evidence.update(
        ingredient="Phosphatidylserine",
        matched_source_row_refs=[child_ref],
        matched_canonical_ids=["phosphatidylserine"],
    )
    return evidence


def _real_label_product(label: dict, *, evidence_ref: str, structural: list) -> dict:
    ledger = [
        _ledger_row(node)
        for node in _tree_nodes(label["activeIngredients"])
        if node.get("canonical_id")
        and node.get("cleaner_row_role") in {"active_scorable", "blend_header_total"}
    ]
    scorable = [row for row in ledger if row["cleaner_row_role"] == "active_scorable"]
    skipped = [row for row in ledger if row["cleaner_row_role"] != "active_scorable"]
    return {
        "id": f"{label['id']}-source-owner",
        "product_name": label["fullName"],
        "activeIngredients": label["activeIngredients"],
        "ingredient_quality_data": {
            "ingredients": ledger,
            "ingredients_scorable": scorable,
            "ingredients_skipped": skipped,
        },
        "product_scoring_evidence": structural,
        "evidence_data": {"clinical_matches": [_ps_evidence(evidence_ref)]},
    }


def _floors(product: dict) -> tuple[dict, dict]:
    # Control = the same label with no structural mass. The contract derives a
    # header projection from the source tree itself, so every header keeps its
    # place (and its nested children) but loses its printed total.
    without_total = deepcopy(product)
    without_total["product_scoring_evidence"] = []
    iqd = without_total["ingredient_quality_data"]
    for row in (*_tree_nodes(without_total["activeIngredients"]),
                *iqd.get("ingredients", []), *iqd.get("ingredients_skipped", [])):
        if row.get("cleaner_row_role") == "blend_header_total":
            row["quantity"] = None
    control = score_evidence(without_total, apply_primary_floor=True)
    actual = score_evidence(product, apply_primary_floor=True)
    return control, actual


def test_real_213475_parent_total_and_synthetic_projection_are_owned_by_child():
    label = _fixture_label("213475")
    complex_node = _node_at(label, "ingredientRows[1]")
    child = complex_node["nestedIngredients"][0]
    assert child["raw_source_path"] == "ingredientRows[1].nestedRows[0]"
    assert label["activeIngredients"][0] is complex_node
    product = _real_label_product(
        label,
        evidence_ref=child["raw_source_path"],
        structural=[_structural_total(complex_node), _synthetic_blend_projection(complex_node)],
    )
    original = deepcopy(product)
    rows = get_scoring_ingredients(product, strict=True).rows
    assert {row["raw_source_path"] for row in rows} == {
        "ingredientRows[1].nestedRows[0]", "ingredientRows[1]", "activeIngredients[0]",
    }
    control, actual = _floors(product)
    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )
    assert actual["score"] == control["score"]


def test_real_218600_active_owns_its_supplying_complex():
    label = _fixture_label("218600")
    # The cleaned label keeps the supplying complex as a flat row whose source
    # path and parentBlend record its nesting under the 200 mg active.
    complex_node = _node_at(label, "ingredientRows[2].nestedRows[0]")
    assert complex_node["parentBlend"] == _node_at(label, "ingredientRows[2]")["name"]
    assert complex_node["cleaner_row_role"] == "blend_header_total"
    product = _real_label_product(
        label, evidence_ref="ingredientRows[2]", structural=[_structural_total(complex_node)],
    )
    original = deepcopy(product)
    rows = get_scoring_ingredients(product, strict=True).rows
    assert {row["raw_source_path"] for row in rows} == {
        "ingredientRows[2]", "ingredientRows[2].nestedRows[0]",
    }
    control, actual = _floors(product)
    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )


def test_real_218838_sibling_rows_without_owner_links_stay_unresolved():
    """Solgar 218838 lists the 500 mg complex, 100 mg PS and 60 mg PC as flat
    siblings. The source proves no ownership, so none is inferred from shared
    canonical identity: the total still competes and the case remains an
    explicit unresolved source-lineage item, not a scoring correction."""
    label = _fixture_label("218838")
    header = _node_at(label, "ingredientRows[2]")
    assert not header["nestedIngredients"]
    product = _real_label_product(
        label, evidence_ref="ingredientRows[3]", structural=[_structural_total(header)],
    )
    rows = get_scoring_ingredients(product, strict=True).rows
    assert {row["raw_source_path"] for row in rows} == {
        "ingredientRows[2]", "ingredientRows[3]", "ingredientRows[4]",
    }
    control, actual = _floors(product)
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == 0.0


def test_synthetic_projection_resolves_through_the_product_tree_not_identity():
    label = _fixture_label("213475")
    complex_node = _node_at(label, "ingredientRows[1]")
    child = complex_node["nestedIngredients"][0]
    owned = _real_label_product(
        label, evidence_ref=child["raw_source_path"],
        structural=[_synthetic_blend_projection(complex_node)],
    )
    control, actual = _floors(owned)
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )

    # Same canonical, same mass, same synthetic path — but the tree slot now
    # holds an unrelated complex with no lineage to the evidenced child, while
    # the real complex (and its child) moves to the next slot.
    unrelated = deepcopy(owned)
    stranger = deepcopy(complex_node)
    stranger.update(raw_source_path="ingredientRows[7]", nestedIngredients=[])
    unrelated["activeIngredients"] = [stranger, *unrelated["activeIngredients"]]
    result = score_evidence(unrelated, apply_primary_floor=True)
    assert result["metadata"]["primary_evidence_floor"] == 0.0


def test_partially_disclosed_blend_total_still_competes():
    """A blend that names an undisclosed member is an opaque aggregate: its
    total keeps competing, and no remainder is assigned to any child."""
    label = _fixture_label("213475")
    complex_node = _node_at(label, "ingredientRows[1]")
    complex_node["quantity"] = 2000.0
    child = complex_node["nestedIngredients"][0]

    def build(label):
        node = _node_at(label, "ingredientRows[1]")
        return _real_label_product(
            label, evidence_ref=child["raw_source_path"],
            structural=[_structural_total(node), _synthetic_blend_projection(node)],
        )

    disclosed = score_evidence(build(deepcopy(label)), apply_primary_floor=True)
    assert disclosed["metadata"]["primary_evidence_floor"] > 0

    # Real cleaner shape for an undisclosed blend member (nested_display_only,
    # quantity 0 / NP), e.g. DSLD 175375 "Functional Flavor System".
    hidden = deepcopy(child)
    hidden.update(
        name="Bacopa", standardName="Bacopa", raw_source_text="Bacopa",
        raw_source_path="ingredientRows[1].nestedRows[1]", quantity=0.0, unit="NP",
        quantityProvided=False, canonical_id="bacopa",
        cleaner_row_role="nested_display_only", score_eligible_by_cleaner=False,
        score_exclusion_reason="nested_display_only", dose_class="zero_or_np",
    )
    complex_node["nestedIngredients"].append(hidden)
    partial = score_evidence(build(label), apply_primary_floor=True)
    assert partial["metadata"]["primary_evidence_floor"] == 0.0


def test_competitor_rows_drop_only_lineage_owned_structural_totals():
    product = _ps_complex_product()
    rows = get_scoring_ingredients(product, strict=True).rows
    before = deepcopy(rows)
    competitors = primary_mass_competitor_rows(product, rows)
    assert [row["raw_source_path"] for row in competitors] == [
        "ingredientRows[1].nestedRows[0]",
    ]
    assert rows == before

    unrelated = _ps_complex_product()
    unrelated["product_scoring_evidence"][0].update(
        raw_source_path="ingredientRows[2]", linked_rows=["ingredientRows[2]"],
    )
    rows = get_scoring_ingredients(unrelated, strict=True).rows
    assert {row["raw_source_path"] for row in primary_mass_competitor_rows(unrelated, rows)} == {
        "ingredientRows[1].nestedRows[0]", "ingredientRows[2]",
    }

    # Row-level label projections and undosed-child blends are never dropped.
    child = product["ingredient_quality_data"]["ingredients"][0]
    projection = {
        "scoring_input_kind": "label_active_projection",
        "raw_source_path": "ingredientRows[1]",
        "linked_rows": ["ingredientRows[1]"],
        "quantity": 500.0,
        "unit": "mg",
    }
    standalone = {
        "scoring_input_kind": "product_level_evidence",
        "raw_source_path": "ingredientRows[3]",
        "linked_rows": ["ingredientRows[3]"],
        "quantity": 250.0,
        "unit": "mg",
    }
    kept = primary_mass_competitor_rows(product, [child, projection, standalone])
    assert kept == [child, projection, standalone]


def test_activity_unit_child_cannot_stand_in_for_its_mass_total():
    """Wobenzym-style row: "Pancreatin 300 mg" whose only nested member is an
    activity-unit specification (56,000 USP). Nothing mass-comparable stands
    in for the 300 mg, so the total keeps competing with a 135 mg sibling."""
    label = _fixture_label("213475")
    pancreatin = _node_at(label, "ingredientRows[1]")
    pancreatin.update(name="Pancreatin", standardName="Pancreatin",
                      raw_source_text="Pancreatin", quantity=300.0, canonical_id="digestive_enzymes")
    spec = pancreatin["nestedIngredients"][0]
    spec.update(name="Protease", standardName="Protease", raw_source_text="Protease",
                quantity=56000.0, unit="USP", canonical_id="digestive_enzymes")
    bromelain = deepcopy(spec)
    bromelain.update(name="Bromelain", standardName="Bromelain", raw_source_text="Bromelain",
                     raw_source_path="ingredientRows[2]", quantity=135.0, unit="mg",
                     canonical_id="bromelain", parentBlend=None, isNestedIngredient=False)
    label["activeIngredients"].append(bromelain)
    product = _real_label_product(
        label, evidence_ref="ingredientRows[2]", structural=[_structural_total(
            pancreatin, canonical_id="digestive_enzymes", clean_identity_id="digestive_enzymes",
            scoring_parent_id="digestive_enzymes", evidence_canonical_id="digestive_enzymes")],
    )
    match = product["evidence_data"]["clinical_matches"][0]
    match.update(ingredient="Bromelain", matched_canonical_ids=["bromelain"])
    rows = get_scoring_ingredients(product, strict=True).rows
    assert {row["raw_source_path"] for row in rows} >= {"ingredientRows[1]", "ingredientRows[2]"}
    competitors = primary_mass_competitor_rows(product, rows)
    assert "ingredientRows[1]" in {row["raw_source_path"] for row in competitors}
    result = score_evidence(product, apply_primary_floor=True)
    assert result["metadata"]["primary_evidence_floor"] == 0.0
