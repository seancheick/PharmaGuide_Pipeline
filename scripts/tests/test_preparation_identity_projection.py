"""Project one verified preparation identity without altering label evidence."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from scoring_input_contract import derive_product_scoring_evidence, get_scoring_ingredients
from test_jarrow_yeast_extract_identity import EXTRACT_ID, _jarrow_product

if TYPE_CHECKING:
    from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.fixture(scope="module", params=[
    ("264610", 250.0, EXTRACT_ID, "other_ingredients", "Saccharomyces cerevisiae Extract"),
    ("307558", 250.0, EXTRACT_ID, "other_ingredients", "Saccharomyces cerevisiae Extract"),
    ("dried Yeast Fermentate", 500.0, "NHA_YEAST_FERMENTATE_DRIED",
     "other_ingredients", "Yeast Fermentate (Dried)"),
    ("EpiCor dried Yeast Fermentate", 250.0, "epicor", "standardized_botanicals", "EpiCor"),
    ("EpiCor dried Yeast Fermentate", 500.0, "epicor", "standardized_botanicals", "EpiCor"),
])
def preparation_case(
    request: pytest.FixtureRequest, enricher: SupplementEnricherV3,
) -> tuple[dict, dict, tuple[str, str, str]]:
    label, quantity, canonical, source_db, standard_name = request.param
    source = _jarrow_product(label if label in {"264610", "307558"} else "264610")
    if label not in {"264610", "307558"}:
        source.update(id=f"preparation-{label}-{quantity}", fullName=label)
        active = source["activeIngredients"][0]
        active.update({
            "name": label, "raw_source_text": label, "quantity": quantity,
            "canonical_id": "yeast_fermentate" if canonical != "epicor"
            else "NHA_YEAST_FERMENTATE_DRIED",
            "canonical_source_db": "ingredient_quality_map" if canonical != "epicor"
            else "other_ingredients",
            "standardName": "Yeast Fermentate", "forms": [],
            "ingredientGroup": "Saccharomyces cerevisiae",
        })
        active["raw_taxonomy"].update({
            "forms": [], "ingredientGroup": "Saccharomyces cerevisiae",
        })
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    return source, product, (canonical, source_db, standard_name)


def test_preparation_identity_is_coherent_on_active_and_iqd_rows(
    preparation_case: tuple[dict, dict, tuple[str, str, str]],
) -> None:
    source, product, expected = preparation_case
    active = product["activeIngredients"][0]
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert (active.get("canonical_id"), active.get("canonical_source_db"),
            active.get("standardName")) == expected
    assert (quality.get("canonical_id"), quality.get("canonical_source_db"),
            quality.get("standard_name")) == expected
    for row in (active, quality):
        assert row["canonical_id_after"] == expected[0]
        assert row["canonical_id_before"] == source["activeIngredients"][0]["canonical_id"]
        assert row["identity_disposition"] == "repaired"
        assert row["scoreable_identity"] is False


def test_preparation_has_no_borrowed_iqm_quality_or_live_organism_evidence(
    preparation_case: tuple[dict, dict, tuple[str, str, str]],
) -> None:
    _, product, _ = preparation_case
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["recognized_non_scorable"] is True
    for field in ("bio_score", "score", "natural", "form_id", "matched_form",
                  "final_form_bio_score"):
        assert quality.get(field) is None, (field, quality.get(field))
    assert quality.get("matched_forms") == []
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    assert product["evidence_data"]["clinical_matches"] == []


def test_preparation_projection_preserves_material_rows_and_literal_lineage(
    preparation_case: tuple[dict, dict, tuple[str, str, str]],
) -> None:
    source, product, (canonical, source_db, standard_name) = preparation_case
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.unmapped_count == 0
    assert scoring.mapped_coverage == 1.0
    assert len(scoring.rows) == len(source["activeIngredients"])
    projected = next(row for row in scoring.rows if row["raw_source_path"] == "ingredientRows[0]")
    assert projected["canonical_id"] == canonical.lower()
    assert projected["canonical_source_db"] == source_db
    assert projected["standardName"] == standard_name
    assert projected["scoring_input_kind"] == "label_active_projection"
    assert projected["generic_form_quality_credit"] is False
    assert projected["quantity"] == source["activeIngredients"][0]["quantity"]
    assert projected["unit"] == "mg"
    for before, after in zip(source["activeIngredients"], product["activeIngredients"], strict=True):
        for field in ("name", "raw_source_text", "raw_source_path", "forms", "raw_taxonomy",
                      "quantity", "unit", "parentBlend", "isNestedIngredient"):
            assert after[field] == before[field], field
    if len(scoring.rows) == 2:
        constituent = next(row for row in scoring.rows if row["canonical_id"] == "beta_glucan")
        assert constituent["quantity"] == 188.0
        assert constituent["raw_source_path"] == "ingredientRows[0].nestedRows[0]"


def test_old_artifact_identity_join_copies_registry_and_standard_name_together(
    preparation_case: tuple[dict, dict, tuple[str, str, str]],
) -> None:
    source, enriched, (canonical, source_db, standard_name) = preparation_case
    old_artifact = deepcopy(enriched)
    old_artifact["activeIngredients"] = deepcopy(source["activeIngredients"])
    old_artifact.pop("product_scoring_evidence", None)
    # Model an authoritative IQD ledger beside stale cleaner identity fields.
    quality = old_artifact["ingredient_quality_data"]["ingredients"][0]
    quality.update(canonical_id=canonical, canonical_id_after=canonical,
                   canonical_source_db=source_db, standard_name=standard_name)
    projected = next(row for row in get_scoring_ingredients(old_artifact, strict=True).rows
                     if row["raw_source_path"] == "ingredientRows[0]")
    assert projected["canonical_id"] == canonical.lower()
    assert projected["canonical_source_db"] == source_db
    assert projected["standardName"] == standard_name
    assert old_artifact["activeIngredients"] == source["activeIngredients"]


def test_unknown_extract_stays_conflicted_without_fallback_quality(
    enricher: SupplementEnricherV3,
) -> None:
    source = _jarrow_product("264610")
    source["activeIngredients"][0].update(
        name="unverified yeast extract", raw_source_text="unverified yeast extract",
    )
    original = deepcopy(source["activeIngredients"])
    product, issues = enricher.enrich_product(source)
    assert product.get("enrichment_status") != "validation_failed", issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["identity_disposition"] == "identity_conflict"
    assert quality["canonical_id"] is None
    assert quality["scoreable_identity"] is False
    assert not quality.get("recognized_non_scorable")
    assert quality["score"] is None
    active = product["activeIngredients"][0]
    for field, value in original[0].items():
        assert active[field] == value, field
    assert active.get("identity_disposition") != "repaired"
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.rows == []
    assert scoring.unmapped_count == 1


@pytest.mark.parametrize("missing_field", [
    "canonical_id_after", "canonical_source_db", "standard_name",
])
def test_incomplete_identity_join_cannot_project_a_repaired_id_alone(missing_field: str) -> None:
    product = _jarrow_product("264610")
    quality = {
        "raw_source_path": "ingredientRows[0]", "identity_disposition": "repaired",
        "canonical_id_after": EXTRACT_ID, "canonical_source_db": "other_ingredients",
        "standard_name": "Saccharomyces cerevisiae Extract",
    }
    quality.pop(missing_field)
    product["ingredient_quality_data"] = {"ingredients": [quality]}
    assert derive_product_scoring_evidence(product) == []


def test_identity_join_does_not_replace_a_primary_identity_with_a_safety_record(
    enricher: SupplementEnricherV3,
) -> None:
    recognition = enricher._is_recognized_non_scorable(
        "3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol",
        "3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol",
    )
    assert recognition["recognition_source"] == "banned_recalled_ingredients"
    product = _jarrow_product("264610")
    product["ingredient_quality_data"] = {"ingredients": [{
        "raw_source_path": "ingredientRows[0]", "identity_disposition": "repaired",
        "canonical_id_after": recognition["matched_entry_id"],
        "canonical_source_db": recognition["recognition_source"],
        "standard_name": recognition["matched_entry_name"],
    }]}
    assert derive_product_scoring_evidence(product) == []


@pytest.mark.parametrize("invalid_identity", [
    {"identity_disposition": "identity_conflict"},
    {"canonical_source_db": None},
    {"standard_name": None},
    {"canonical_id_after": "brewers_yeast"},
    {"recognized_entry_id": "brewers_yeast"},
    {"source_label_name": "unverified yeast extract"},
    {"canonical_source_db": "banned_recalled_ingredients",
     "recognition_source": "banned_recalled_ingredients"},
    {"canonical_source_db": "banned_recalled_ingredients", "scoreable_identity": True},
])
def test_incomplete_or_nonprimary_identity_is_not_projected_to_active(
    enricher: SupplementEnricherV3, invalid_identity: dict,
) -> None:
    source = _jarrow_product("264610")
    quality = enricher._collect_ingredient_quality_data(deepcopy(source))["ingredients"][0]
    quality.update(invalid_identity)
    active = deepcopy(source["activeIngredients"][0])
    enricher._project_repaired_identity_to_active_row(active, quality)
    assert active == source["activeIngredients"][0]


@pytest.mark.parametrize("quantity", [360.0, 0.0])
def test_genuine_iqm_repair_retains_its_form_rating(
    enricher: SupplementEnricherV3, quantity: float,
) -> None:
    source = _jarrow_product("264610")
    active = source["activeIngredients"][0]
    active.update({
        "name": "EPA", "raw_source_text": "EPA", "standardName": "DHA",
        "canonical_id": "dha", "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
        "quantity": quantity, "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
        "raw_taxonomy": {},
    })
    result = enricher._collect_ingredient_quality_data(source)
    quality = result["ingredients"][0]
    assert quality["canonical_id"] == active["canonical_id"] == "epa"
    assert active["canonical_source_db"] == "ingredient_quality_map"
    assert active["form_id"] == quality["form_id"] == "EPA fish oil ethyl ester"
    assert quality["bio_score"] == quality["score"] == 9
    assert active["canonical_id_before"] == "dha"
    if quantity == 0.0:
        assert result["ingredients_scorable"] == []
        assert quality["scoreable_identity"] is False


@pytest.fixture(scope="module")
def preparation_with_peer(enricher: SupplementEnricherV3) -> tuple[dict, dict]:
    source = _jarrow_product("307558")
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    return source, product


def _damage_parent_identity(product: dict, defect: str) -> None:
    """Corrupt only the known parent ledger, retaining its valid child."""
    for collection in product["ingredient_quality_data"].values():
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict) or row.get("raw_source_path") != "ingredientRows[0]":
                continue
            if defect in {"canonical_id_after", "canonical_source_db", "standard_name"}:
                row.pop(defect, None)
            elif defect == "mismatched_owner":
                row["canonical_source_db"] = "ingredient_quality_map"
            elif defect == "mismatched_name":
                row["standard_name"] = "Brewer's Yeast"
            elif defect == "safety_substitution":
                row.update({
                    "canonical_id": "SPIKE_ANABOLIC_STEROIDS",
                    "canonical_id_after": "SPIKE_ANABOLIC_STEROIDS",
                    "canonical_source_db": "banned_recalled_ingredients",
                })
            elif defect == "harmful_substitution":
                row.update({
                    "canonical_id": "ADD_NICKEL",
                    "canonical_id_after": "ADD_NICKEL",
                    "canonical_source_db": "harmful_additives",
                })


@pytest.mark.parametrize("defect", [
    "canonical_id_after", "canonical_source_db", "standard_name",
    "mismatched_owner", "mismatched_name", "safety_substitution", "harmful_substitution",
])
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("restore_raw_identity", [True, False])
def test_rejected_parent_stays_in_coverage_and_blocks_scoring_with_valid_peer(
    preparation_with_peer: tuple[dict, dict], defect: str, strict: bool,
    restore_raw_identity: bool,
) -> None:
    from assessment_readiness import evaluate_assessment_readiness
    from scoring_v4.scored_artifact import build_scored_artifact

    source, enriched = preparation_with_peer
    product = deepcopy(enriched)
    if restore_raw_identity:
        product["activeIngredients"] = deepcopy(source["activeIngredients"])
    product.pop("product_scoring_evidence", None)
    if not strict:
        product.pop("assessment_readiness_contract_version", None)
    _damage_parent_identity(product, defect)
    before = deepcopy(product)

    scoring = get_scoring_ingredients(product, strict=strict, allow_legacy_fallback=not strict)
    assert scoring.unmapped_count == 1
    assert scoring.mapped_count == 1
    assert scoring.mapped_coverage == 0.5
    assert [row["canonical_id"] for row in scoring.rows] == ["beta_glucan"]
    rejected_parent = [row for row in scoring.rejected_rows
                       if row.row.get("raw_source_path") == "ingredientRows[0]"]
    assert len(rejected_parent) == 1
    assert rejected_parent[0].reason.startswith("identity_projection_")
    assert any(finding.startswith("identity_projection_") for finding in scoring.contract_findings)
    assert "projection" in rejected_parent[0].row["identity_resolution_rationale"].lower()
    identity = evaluate_assessment_readiness(product, module="generic")["identity"]
    assert identity["readiness"] == "incomplete"
    assert identity["source_unmapped_count"] == 1
    assert identity["source_mapped_coverage"] == 0.5
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["assessment_readiness"]["identity"]["readiness"] == "incomplete"
    assert product == before


@pytest.mark.parametrize("exclusion", [
    {"score_eligible_by_cleaner": False},
    {"cleaner_row_role": "blend_header_total", "is_blend_header": True},
    {"cleaner_row_role": "source_descriptor"},
    {"cleaner_row_role": "inactive", "source_section": "inactive"},
    {"cleaner_row_role": "excipient", "is_excipient": True},
])
@pytest.mark.parametrize("strict", [True, False])
def test_rejected_tuple_does_not_make_an_intentionally_excluded_parent_required(
    preparation_with_peer: tuple[dict, dict], exclusion: dict, strict: bool,
) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    source, enriched = preparation_with_peer
    product = deepcopy(enriched)
    product["activeIngredients"] = deepcopy(source["activeIngredients"])
    product.pop("product_scoring_evidence", None)
    _damage_parent_identity(product, "canonical_source_db")
    product["activeIngredients"][0].update(exclusion)
    for collection in product["ingredient_quality_data"].values():
        if isinstance(collection, list):
            for row in collection:
                if isinstance(row, dict) and row.get("raw_source_path") == "ingredientRows[0]":
                    row.update(exclusion)
    before = deepcopy(product)

    scoring = get_scoring_ingredients(product, strict=strict, allow_legacy_fallback=not strict)
    assert scoring.unmapped_count == 0
    assert scoring.mapped_count >= 1  # Structural headers may project their valid child.
    assert scoring.mapped_coverage == 1.0
    assert not any(finding.startswith("identity_projection_") for finding in scoring.contract_findings)
    assert evaluate_assessment_readiness(product, module="generic")["identity"]["readiness"] == "complete"
    assert product == before


@pytest.mark.parametrize("strict", [True, False])
def test_unclaimed_legacy_tuple_does_not_create_a_new_repair_requirement(
    preparation_with_peer: tuple[dict, dict], strict: bool,
) -> None:
    _, enriched = preparation_with_peer
    product = deepcopy(enriched)
    product.pop("product_scoring_evidence", None)
    for collection in product["ingredient_quality_data"].values():
        if isinstance(collection, list):
            for row in collection:
                if isinstance(row, dict) and row.get("raw_source_path") == "ingredientRows[0]":
                    for field in ("identity_disposition", "canonical_id_after",
                                  "canonical_source_db", "standard_name"):
                        row.pop(field, None)
    before = deepcopy(product)
    scoring = get_scoring_ingredients(product, strict=strict, allow_legacy_fallback=not strict)
    assert scoring.unmapped_count == 0
    assert scoring.mapped_count == 2
    assert not any(finding.startswith("identity_projection_") for finding in scoring.contract_findings)
    assert product == before


def _safety_identity_product(label: str, quantity: float, unit: str) -> dict:
    """A real safety-recognized label beside one independently mapped active."""
    source = _jarrow_product("264610")
    source.update(id="safety-primary-identity", fullName="Identity boundary fixture")
    active = source["activeIngredients"][0]
    active.update({
        "name": label, "raw_source_text": label, "standardName": label,
        "canonical_id": None, "canonical_source_db": "unmapped",
        "ingredientGroup": label, "quantity": quantity, "unit": unit,
        "forms": [], "uniiCode": None,
        "raw_taxonomy": {"ingredientGroup": label, "forms": []},
    })
    peer = deepcopy(active)
    peer.update({
        "name": "Vitamin C", "raw_source_text": "Vitamin C", "standardName": "Vitamin C",
        "canonical_id": "vitamin_c", "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": "Vitamin C", "quantity": 100.0, "unit": "mg",
        "raw_source_path": "ingredientRows[1]",
        "raw_taxonomy": {"ingredientGroup": "Vitamin C", "forms": []},
    })
    source["activeIngredients"].append(peer)
    return source


@pytest.mark.parametrize("label,quantity,unit,safety_source,safety_id", [
    ("Nickel", 5.0, "mcg", "harmful_additives", "ADD_NICKEL"),
    ("Vinpocetine", 20.0, "mg", "banned_recalled_ingredients", "NOOTROPIC_VINPOCETINE"),
])
@pytest.mark.parametrize("supplied_canonical", [None, "vitamin_c"])
def test_safety_only_recognition_keeps_required_primary_identity_unresolved(
    enricher: SupplementEnricherV3, label: str, quantity: float, unit: str,
    safety_source: str, safety_id: str, supplied_canonical: str | None,
) -> None:
    from scoring_v4.scored_artifact import build_scored_artifact

    source = _safety_identity_product(label, quantity, unit)
    if supplied_canonical:
        source["activeIngredients"][0].update(
            canonical_id=supplied_canonical, canonical_source_db="ingredient_quality_map",
        )
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["canonical_id"] is None
    assert quality["canonical_id_after"] is None
    assert quality["canonical_id_before"] == supplied_canonical
    assert quality["canonical_source_db"] == "unmapped"
    assert quality["standard_name"] == label
    assert quality["safety_identity_id"] == quality["recognized_entry_id"] == safety_id
    assert quality["recognition_source"] == safety_source
    assert quality["recognized_non_scorable"] is True
    assert quality["mapped"] is quality["mapped_identity"] is False
    assert quality["identity_disposition"] == "identity_conflict"
    assert quality["role_classification"] == "active_unmapped"
    assert "primary identity" in quality["identity_resolution_rationale"].lower()
    assert quality["identity_decision_reason"] == "safety_recognition_without_primary_identity"
    assert quality["scoreable_identity"] is False
    assert quality["score"] is quality["bio_score"] is quality["form_id"] is None
    assert product["activeIngredients"][0]["canonical_id"] == supplied_canonical

    scoring = get_scoring_ingredients(product)
    assert scoring.mapped_count == scoring.unmapped_count == 1
    assert scoring.mapped_coverage == 0.5
    assert [row["canonical_id"] for row in scoring.rows] == ["vitamin_c"]
    rejected = next(row for row in scoring.rejected_rows
                    if row.row["raw_source_path"] == "ingredientRows[0]")
    assert rejected.reason == "identity_disposition_not_scoreable:identity_conflict"
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "not_scored"
    identity = artifact["assessment_readiness"]["identity"]
    assert identity["source_unmapped_count"] == 1
    assert identity["source_mapped_coverage"] == 0.5
    assert identity["readiness"] == "incomplete"

    # Reconstruct the former safety-primary tuple to pin the independent
    # safety decision: only ingredient identity/readiness is being corrected.
    legacy = deepcopy(product)
    for collection in legacy["ingredient_quality_data"].values():
        if isinstance(collection, list):
            for row in collection:
                if isinstance(row, dict) and row.get("raw_source_path") == "ingredientRows[0]":
                    row.update(
                        canonical_id=safety_id, canonical_id_after=safety_id,
                        canonical_source_db=safety_source, mapped=True, mapped_identity=True,
                        identity_disposition="taxonomy_only", role_classification="recognized_non_scorable",
                    )
    legacy_artifact = build_scored_artifact(legacy)
    assert artifact["_v4_safety_gate"] == legacy_artifact["_v4_safety_gate"]


@pytest.mark.parametrize("label,canonical,safety_source,safety_id", [
    ("Isomaltooligosaccharides", "NHA_ISOMALTOOLIGOSACCHARIDES",
     "harmful_additives", "ADD_ISOMALTOOLIGOSACCHARIDE"),
    ("Adipic Acid", "OI_ADIPIC_ACID",
     "banned_recalled_ingredients", "BANNED_ADD_SYNTHETIC_FOOD_ACIDS"),
])
def test_safety_recognition_preserves_a_validated_primary_without_form_credit(
    enricher: SupplementEnricherV3, label: str, canonical: str,
    safety_source: str, safety_id: str,
) -> None:
    source = _safety_identity_product(label, 500.0, "mg")
    source["activeIngredients"][0].update(
        canonical_id=canonical, canonical_source_db="other_ingredients",
    )
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["canonical_id"] == quality["canonical_id_after"] == canonical
    assert quality["canonical_id_before"] == canonical
    assert quality["canonical_source_db"] == "other_ingredients"
    assert quality["standard_name"] == label
    assert quality["safety_identity_id"] == quality["recognized_entry_id"] == safety_id
    assert quality["recognition_source"] == safety_source
    assert quality["identity_disposition"] in {"clean", "taxonomy_only"}
    assert quality["mapped_identity"] is True
    assert quality["scoreable_identity"] is False
    assert quality["bio_score"] is quality["score"] is quality["form_id"] is None
    assert quality["matched_forms"] == []
    assert product["activeIngredients"][0]["canonical_id"] == canonical


def test_classification_keeps_a_safety_only_conflict_in_the_required_role(
    enricher: SupplementEnricherV3,
) -> None:
    source = _safety_identity_product("Nickel", 5.0, "mcg")
    product, issues = enricher.enrich_product(source)
    assert product.get("enrichment_status") != "validation_failed", issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    # The same final classification boundary also handles rows that reach
    # recognition after quality matching, rather than through an early skip.
    skipped, recognized = [], []
    enricher._route_non_scorable_iqd_row(
        quality, skipped, recognized, skip_reason="recognized_non_scorable",
    )
    assert quality in skipped and quality in recognized
    assert quality["identity_disposition"] == "identity_conflict"
    assert quality["role_classification"] == "active_unmapped"
    assert quality["canonical_id"] is None
    assert quality["safety_identity_id"] == "ADD_NICKEL"
    assert quality["bio_score"] is quality["score"] is None
    scoring = get_scoring_ingredients(product)
    assert scoring.mapped_count == scoring.unmapped_count == 1
    assert scoring.mapped_coverage == 0.5


@pytest.mark.parametrize("label", ["Nickel", "Vinpocetine"])
@pytest.mark.parametrize("exclusion", ["inactive", "excipient"])
def test_safety_recognition_does_not_make_an_excluded_source_required(
    enricher: SupplementEnricherV3, label: str, exclusion: str,
) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    source = _safety_identity_product(label, 5.0, "mg")
    row = source["activeIngredients"][0]
    row.update(cleaner_row_role=exclusion, score_eligible_by_cleaner=False)
    if exclusion == "inactive":
        row["source_section"] = "inactive"
        source["inactiveIngredients"] = [source["activeIngredients"].pop(0)]
    else:
        row["isAdditive"] = True
    product, issues = enricher.enrich_product(source)
    assert product.get("enrichment_status") != "validation_failed", issues
    scoring = get_scoring_ingredients(product)
    assert scoring.mapped_count == 1
    assert scoring.unmapped_count == 0
    assert scoring.mapped_coverage == 1.0
    assert not scoring.contract_findings
    assert evaluate_assessment_readiness(product, module="generic")["identity"]["readiness"] == "complete"


@pytest.mark.parametrize("label", ["Mannitol", "EDTA Disodium", "Calcium Disodium EDTA"])
def test_recognized_excipient_does_not_widen_the_required_primary_denominator(
    enricher: SupplementEnricherV3, label: str,
) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    source = _safety_identity_product(label, 500.0, "mg")
    product, issues = enricher.enrich_product(source)
    assert product.get("enrichment_status") != "validation_failed", issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["is_excipient"] is True
    assert quality["canonical_id"] is None
    assert quality["recognition_source"] == "harmful_additives"
    assert quality["safety_identity_id"] == quality["recognized_entry_id"]
    scoring = get_scoring_ingredients(product)
    assert scoring.mapped_count == 1
    assert scoring.unmapped_count == 0
    assert scoring.mapped_coverage == 1.0
    assert not scoring.contract_findings
    identity = evaluate_assessment_readiness(product, module="generic")["identity"]
    assert identity["readiness"] == "complete"
    assert identity["source_score_eligible_active_count"] == 1
    assert identity["source_unmapped_count"] == 0
