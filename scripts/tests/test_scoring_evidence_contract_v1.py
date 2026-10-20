from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_input_contract import get_scoring_ingredients  # noqa: E402


def _load_product(dsld_id: str) -> dict:
    needle = re.escape(dsld_id.encode())
    id_pattern = re.compile(rb'"(?:dsld_id|id)"\s*:\s*(?:"' + needle + rb'"|' + needle + rb'(?=\s*[,}]))')
    for path in (SCRIPTS_ROOT / "products").glob("output_*_enriched/enriched/*.json"):
        raw = path.read_bytes()
        if not id_pattern.search(raw):
            continue
        payload = json.loads(raw)
        products = payload if isinstance(payload, list) else payload.get("products", [])
        for product in products:
            if str(product.get("dsld_id") or product.get("id")) == dsld_id:
                return product
    raise AssertionError(f"Could not find enriched product {dsld_id}")


def _evidence_rows(product: dict, evidence_type: str) -> list[dict]:
    result = get_scoring_ingredients(product, strict=True)
    return [
        row for row in result.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
        and row.get("evidence_type") == evidence_type
    ]


def _assert_module_aggregate_evidence(out: dict, canonical_id: str) -> None:
    """A product-level total is answered by its module, not by a clinical record.

    `protein` and `digestive_enzymes` name how much the product declares, not
    which ingredient it is, so they raise no individual evidence question and
    cannot be a curation gap.
    """
    assert out["v4_verdict"] != "NOT_SCORED"
    assert out["raw_score_v4_100"] is not None

    evidence = out["v4_breakdown"]["assessment_readiness"]["evidence"]
    # Material product projections belong to their module assessment rather
    # than an individual-ingredient clinical question.
    rows = [
        row for row in evidence["ingredient_assessments"]
        if row.get("canonical_id") == canonical_id
        and row.get("material") is True
        and row.get("scoring_input_kind") == "product_level_evidence"
    ]
    assert rows, f"{canonical_id} produced no material product projection"
    assert all(
        row["evidence_applicability"] == "module_aggregate"
        and row["state"] == "not_applicable"
        and row["reason_code"] == "module_scoped_product_projection"
        for row in rows
    )


def test_protein_macro_reaches_v4_as_sports_primary_dose_evidence() -> None:
    product = _load_product("180692")

    rows = _evidence_rows(product, "sports_primary_dose")
    assert rows, "Protein macro dose must be normalized into ScoringEvidence v1"
    assert max(float(row["quantity"]) for row in rows) >= 19.0

    out = score_product_v4(product)
    _assert_module_aggregate_evidence(out, "protein")


def test_omega_aggregate_and_forms_reach_v4_as_epa_dha_evidence() -> None:
    for dsld_id, minimum in (("13801", 750.0), ("26691", 500.0)):
        product = _load_product(dsld_id)

        rows = _evidence_rows(product, "omega_epa_dha_aggregate")
        assert rows, f"{dsld_id} must emit omega EPA/DHA aggregate evidence"
        assert max(float(row["quantity"]) for row in rows) >= minimum

        out = score_product_v4(product)
        assert out["v4_verdict"] != "NOT_SCORED"


def test_printed_epa_dha_members_own_their_doses_under_a_blend_total() -> None:
    """259484 prints "DHA, EPA 2 g Total" with EPA 1.5 g and DHA 500 mg under it.
    The members own the dose (EPA/DHA label ownership, 25610891); the old pin
    here expected an aggregate built from the 4.5 g fish-oil mass."""
    rows = get_scoring_ingredients(_load_product("259484"), strict=True).rows
    doses = {r.get("canonical_id"): (float(r.get("quantity") or 0), r.get("unit")) for r in rows
             if r.get("canonical_id") in ("epa", "dha")}
    assert doses == {"epa": (1.5, "Gram(s)"), "dha": (500.0, "mg")}


def test_enzyme_activity_reaches_v4_as_non_mass_dose_evidence() -> None:
    product = _load_product("293966")

    rows = _evidence_rows(product, "enzyme_activity")
    assert rows, "PPI/ALU/BLGU activity units must be scoring evidence"
    assert any(str(row.get("unit")).lower() == "ppi" for row in rows)

    out = score_product_v4(product)
    # Activities retain their named enzyme identities; a synthetic generic
    # digestive_enzymes row would erase the preparation and activity owner.
    for canonical_id in ("protease", "lactase"):
        _assert_module_aggregate_evidence(out, canonical_id)


def test_identity_bearing_preparation_keeps_its_printed_mass_without_a_blend_projection() -> None:
    # The label declares one Quercefit preparation with a Quercetin Phytosome
    # form, not a blend with independently listed constituent ingredients.
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures" / "evidence_readiness_309492_raw.json").read_text())
    product, _ = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))
    rows = get_scoring_ingredients(product, strict=True).rows
    assert len(rows) == 1
    [row] = rows
    assert row["canonical_id"] == "quercetin"
    assert row["matched_form"] == "quercetin phytosome"
    assert row["raw_source_path"] == "ingredientRows[0]"
    assert row["quantity"] == 300.0
    assert row["unit"] == "mg"
    assert row.get("scoring_input_kind") != "product_level_evidence"
    assert not _evidence_rows(product, "blend_anchor_mass")

    out = score_product_v4(product)
    [assessment] = out["v4_breakdown"]["assessment_readiness"]["evidence"]["ingredient_assessments"]
    assert assessment["evidence_applicability"] == "individual_ingredient"
    assert assessment["state"] == "evaluated_supported"
    assert assessment["source_value"] == 300.0
    assert set(assessment["evidence_ids"]) == {"INGR_QUERCETIN", "PRECLIN_QUERCETIN_PHYTOSOME"}
    assert out["v4_verdict"] != "NOT_SCORED"
    assert out["raw_score_v4_100"] is not None
    completeness = out["v4_breakdown"]["completeness_gate"]
    assert "conservative_blend_anchor_mass" not in completeness["soft_missing"]
    assert completeness["score_cap"] is None
    assert completeness["verdict_ceiling"] is None


def test_blend_anchor_cannot_hide_title_material_unresolved_vitamin_dose() -> None:
    # Product 76510 used to carry the source defect this test guarded, but its
    # Vitamin D unit has since been corrected from NP to IU. Keep the canary
    # deterministic by recreating the unresolved label input explicitly.
    product = copy.deepcopy(_load_product("76510"))

    def remove_vitamin_d_dose(node: object) -> None:
        if isinstance(node, dict):
            if (
                node.get("canonical_id") == "vitamin_d"
                or node.get("normalized_key") == "vitamin_d"
            ):
                if "quantity" in node:
                    node["quantity"] = 0.0
                if "unit" in node:
                    node["unit"] = "NP"
                node.pop("source_correction", None)
                raw_taxonomy = node.get("raw_taxonomy")
                if isinstance(raw_taxonomy, dict):
                    for variant in raw_taxonomy.get("quantityVariants") or []:
                        variant["quantity"] = 0.0
                        variant["unit"] = "NP"
            for value in node.values():
                remove_vitamin_d_dose(value)
        elif isinstance(node, list):
            for value in node:
                remove_vitamin_d_dose(value)

    remove_vitamin_d_dose(product)

    out = score_product_v4(product)

    assert out["v4_verdict"] == "NOT_SCORED"
    readiness = out["v4_breakdown"]["assessment_readiness"]
    assert readiness["dose"]["readiness"] == "incomplete"
    assert "ingredientRows[2]" in readiness["dose"]["incomplete_source_row_refs"]
    assert readiness["unavailable_reasons"] == ["dose_assessment_readiness"]


def test_enzyme_evidence_carries_new_identity_fields() -> None:
    """Enzyme evidence rows carry the new identity chain fields."""
    product = _load_product("293966")

    result = get_scoring_ingredients(product, strict=True)
    enzyme_rows = [
        row for row in result.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
        and row.get("evidence_type") == "enzyme_activity"
    ]
    assert enzyme_rows, "Must have enzyme_activity evidence rows"
    for row in enzyme_rows:
        assert row.get("evidence_origin") == "compatibility_derived"
        assert row.get("dose_class") == "enzyme_activity"
        assert "clean_identity_id" in row
        assert "scoring_parent_id" in row
        assert "evidence_canonical_id" in row
