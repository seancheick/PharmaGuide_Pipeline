"""Q40: botanical plant part has one owner, the cleaner, and only label text discloses it.

21 CFR 101.36(d)(1) puts the plant part on the Supplement Facts row. The cleaner records it from
DSLD's PlantPart note, else from the label row's name or its label forms; the enricher carries
it onto the quality row and the botanical Formulation credit reads only that. Before, the scorer
re-derived it with a private word list over text that included IQM form and standard names, so a
"Licorice" row earned the credit from IQM's "licorice root extract" while DSLD's own PlantPart
note (60306, root) earned nothing.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def scored():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.CRITICAL)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for dsld_id in ("60306", "330145", "251625"):
        raw = json.loads((FIXTURES / f"plant_part_{dsld_id}_raw.json").read_text())
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        out[dsld_id] = build_scored_artifact(enriched)
    logging.disable(logging.NOTSET)
    return out


def _botanical_components(artifact):
    formulation = artifact["_v4_module_breakdown"]["dimensions"]["formulation"]
    return (formulation.get("metadata") or {}).get("botanical_formulation") or {}


@pytest.mark.parametrize("dsld_id", ["60306", "330145"])
def test_label_disclosed_plant_part_earns_the_credit(scored, dsld_id):
    # 60306: DSLD note "PlantPart: root". 330145: label row "Okra Pods Extract, Fresh".
    assert _botanical_components(scored[dsld_id]).get("plant_part_disclosed") == 2.0


def test_database_form_name_is_not_label_disclosure(scored):
    # 251625: the Supplement Facts row is "Licorice"; only IQM's form name says root.
    assert "plant_part_disclosed" not in _botanical_components(scored["251625"])


@pytest.mark.parametrize("keep_part", [True, False])
def test_botanical_blend_projection_preserves_only_cleaner_owned_child_part(keep_part):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((FIXTURES / "plant_part_204571_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    if not keep_part:
        # Root wording remains. Neither the bridge nor scorer may reparse it.
        for row in cleaned["activeIngredients"]:
            row.pop("plantPart", None)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    projection = next(row for row in enriched["product_scoring_evidence"]
                      if row.get("canonical_id") == "ashwagandha"
                      and row.get("raw_source_path") == "activeIngredients[6]")
    assert projection.get("plantPart") == ("root" if keep_part else None)
    assert projection["dose_value"] == 850
    assert projection["evidence_scope"] == "blend_level"
    artifact = build_scored_artifact(enriched)
    assert artifact["_v4_provenance"]["module_route"] == "generic"
    # This mixed product uses the generic profile; source disclosure does not
    # independently promote it into botanical Formulation credit.
    assert not _botanical_components(artifact)


@pytest.mark.parametrize("case,expected", [("linked", "root"), ("unrelated", None), ("conflicting", None)])
def test_blend_projection_cannot_borrow_another_childs_plant_part(case, expected):
    from scoring_input_contract import _derive_top_level_botanical_blend_evidence

    name = "organic Ashwagandha root extract"
    active = {"name": name, "plantPart": "root", "raw_source_path": "ingredientRows[0].nestedRows[0]"}
    blend = {"name": "Botanical Blend", "total_weight": 850, "unit": "mg",
             "source_path": "activeIngredients[0]", "source_fields": ["activeIngredients[0]", "activeIngredients[1]"],
             "source_row_ref": "ingredientRows[0]", "child_ingredients": [{"name": name}]}
    if case == "unrelated":
        active["raw_source_path"] = "ingredientRows[3].nestedRows[0]"
        blend["source_fields"] = ["activeIngredients[0]"]
    product = {"activeIngredients": [{"name": "Botanical Blend"}, active], "proprietary_blends": [blend]}
    if case == "conflicting":
        product["activeIngredients"].append({**active, "plantPart": "leaf",
                                            "raw_source_path": "ingredientRows[0].nestedRows[1]"})
    rows = _derive_top_level_botanical_blend_evidence(product, set())
    assert len(rows) == 1
    assert rows[0].get("plantPart") == expected
    assert rows[0]["dose_value"] == 850
    assert rows[0]["evidence_scope"] == "blend_level"
