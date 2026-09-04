"""Synthetic adversarial diagnostics, not clinical references or approved scores.

Reuses label fixtures and actual module functions. Temporary in-memory contexts
test the applicability branch; they are deliberately not treatment claims.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "scripts/tests")]

import studied_formulas
from scoring_v4.modules.probiotic_dose import score_dose
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.modules.probiotic_formulation import score_formulation
from scoring_v4.modules.probiotic_transparency import score_transparency
from test_probiotic_applicability_rubric import strain_product
from test_probiotic_label_dose_independence import owned_label
from test_studied_formula_assessment import seed_label


def run_probes():
    cases = []

    def record(name, product, *, simulated_scope=False):
        cases.append({"name": name, "synthetic": True,
            "simulated_applicability_not_clinical_review": simulated_scope,
            "dimensions": {k: scorer(product) for k, scorer in (
                ("formulation", score_formulation), ("dose", score_dose),
                ("evidence", score_evidence), ("transparency", score_transparency))}})

    for billions in (.1, 1, 10, 50):
        record(f"LGG {billions:g}B", owned_label(billions * 1e9))
    dsm = strain_product(dose=1e8, clinical_id="STRAIN_REUTERI_DSM17938",
                         name="Lactobacillus reuteri DSM 17938")
    dsm["probiotic_data"].update(total_strain_count=1, total_cfu=1e8,
                                  guarantee_type="at_expiration")
    record("DSM 17938 0.1B", dsm)

    two = owned_label()
    other = strain_product(dose=1e10, clinical_id="STRAIN_RHAMNOSUS_HN001",
                           name="Lactobacillus rhamnosus HN001")
    other["activeIngredients"][0]["raw_source_path"] = "ingredientRows[1]"
    other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    other["probiotic_data"]["probiotic_blends"][0]["raw_source_path"] = "ingredientRows[1]"
    other["probiotic_data"]["probiotic_blends"][0]["cfu_data"]["raw_source_path"] = "ingredientRows[1]"
    two["activeIngredients"] += other["activeIngredients"]
    for key in ("clinical_strains", "probiotic_blends"):
        two["probiotic_data"][key] += other["probiotic_data"][key]
    two["probiotic_data"].update(total_strain_count=2, total_billion_count=20)
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    for cid in ("STRAIN_LGG", "STRAIN_RHAMNOSUS_HN001"):
        registry[cid]["applicability"] = {
            "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
            "dosage_forms": ["capsule"], "target_population": "adult",
            "studied_population": "SYNTHETIC CONTRACT TEST ONLY",
            "supported_outcomes": ["synthetic test endpoint"],
            "source_pmids": [registry[cid]["cfu_thresholds"]["evidence"]["pmid"]],
        }
    with patch.object(studied_formulas, "_clinical_strain_registry", return_value=registry):
        record("one rejected legacy-scope fixture", owned_label(), simulated_scope=True)
        record("two rejected legacy-scope fixtures", two, simulated_scope=True)

    for count in (15, 20):
        product = {"probiotic_data": {"total_strain_count": count, "total_cfu": 1e11,
            "guarantee_type": "at_expiration", "clinical_strains": [],
            "probiotic_blends": [{"strains": [f"Synthetic unreviewed strain {i}" for i in range(count)]}]}}
        record(f"{count} unreviewed strains 100B aggregate", product)

    # Isolate strain-count behavior inside the existing exact-formula branch.
    # This is a two-member counterfactual, NOT a second reviewed commercial RCT.
    product = seed_label()
    product["activeIngredients"] = [product["activeIngredients"][0], product["activeIngredients"][-1]]
    product["activeIngredients"][0]["nestedIngredients"] = product["activeIngredients"][0]["nestedIngredients"][:2]
    product["probiotic_data"]["afu_measurements"] = [{
        "source_row_ref": "ingredientRows[0]", "source_value": 53.6,
        "source_unit": "Billion AFU", "normalized_unit": "AFU", "normalized_value": 53.6e9}]
    product["probiotic_data"]["total_strain_count"] = 2
    entries = deepcopy(studied_formulas.reviewed_entries())
    eid = next(k for k, v in entries.items() if v.get("formula_contract"))
    contract = entries[eid]["formula_contract"]
    contract["strain_names"] = contract["strain_names"][:2]
    contract["blend_composition"] = [{"strain_indices": [0, 1], "daily_afu": 53.6e9}]
    with patch.object(studied_formulas, "reviewed_entries", return_value=entries):
        record("two-strain finished-formula fixture", product, simulated_scope=True)
    return {"clinical_approval": False, "production_changes": False,
            "point_scale": "raw module points, NOT public /100 scores",
            "warning": "Synthetic scope fields are test inputs, never evidence curation.", "cases": cases}


if __name__ == "__main__":
    print(json.dumps(run_probes(), indent=2, allow_nan=False))
