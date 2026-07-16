"""Phase 0a — the structured taxonomy evidence contract, and the SoT audit's
migration onto it.

WHY THIS EXISTS
    `audit_source_of_truth_contract.py` runs FIRST in release_full.sh and is
    fail-closed. It used to gate on two things it should never have gated on:

      1. a hard-coded PHYSICAL JSON path
         (`classification_input_source == "ingredient_quality_data.ingredients_scorable"`),
         which the consolidation's RC1 fix repopulates — the literal would stop
         matching and block the release for a change that is correct;
      2. rendered PROSE
         (`"omega-3:" in " ".join(classification_reasons)`), which made a
         human-readable sentence a release input. Those sentences were not even
         deterministic until 2026-07-15 (see
         test_supplement_taxonomy_determinism.py).

    These tests pin the contract the gate consumes instead, and pin that the
    producer and the consumer moved together.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import audit_source_of_truth_contract as sot  # noqa: E402
from supplement_taxonomy import (  # noqa: E402
    CLASSIFICATION_CONTRACT_VERSION,
    INPUT_CONTRACT_IQD_ALL_ROWS,
    INPUT_CONTRACT_RAW_LABEL_ACTIVES,
    INPUT_CONTRACT_SCORE_ELIGIBLE_ROWS,
    ROW_ROLE_EXCLUDED_NON_QUANTIFIED,
    ROW_ROLE_EXCLUDED_STRUCTURAL,
    ROW_ROLE_INCLUDED_ACTIVE,
    SCORE_ELIGIBLE_INPUT_CONTRACTS,
    classify_supplement,
)


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "category": category,
        "quantity": qty,
        "unit": unit,
        "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }
    row.update(extra)
    return row


def _product(rows, name="Test Product"):
    return {
        "dsld_id": 980001,
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": copy.deepcopy(rows)},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


@pytest.fixture
def omega_product():
    return _product(
        [
            _row("EPA", "epa", "fatty_acid", 500.0),
            _row("DHA", "dha", "fatty_acid", 250.0),
        ],
        name="Test Fish Oil",
    )


# ---------------------------------------------------------------------------
# The contract itself
# ---------------------------------------------------------------------------


def test_taxonomy_emits_the_contract(omega_product):
    taxonomy = classify_supplement(omega_product)

    assert taxonomy["classification_contract_version"] == CLASSIFICATION_CONTRACT_VERSION
    assert taxonomy["classification_input_contract"] == INPUT_CONTRACT_SCORE_ELIGIBLE_ROWS
    assert isinstance(taxonomy["classification_row_evidence"], list)
    assert taxonomy["unresolved_quantified_active_count"] == 0


def test_input_contract_is_stable_id_not_a_physical_path(omega_product):
    """The policy field must not be a JSON path — that is what made the gate
    brittle in the first place."""
    taxonomy = classify_supplement(omega_product)
    contract = taxonomy["classification_input_contract"]

    assert "." not in contract, f"{contract!r} looks like a physical path"
    assert "ingredient_quality_data" not in contract
    assert contract in {
        INPUT_CONTRACT_SCORE_ELIGIBLE_ROWS,
        INPUT_CONTRACT_IQD_ALL_ROWS,
        INPUT_CONTRACT_RAW_LABEL_ACTIVES,
    }


def test_physical_source_is_still_emitted_for_diagnostics(omega_product):
    """Kept — but as a diagnostic, not policy."""
    taxonomy = classify_supplement(omega_product)
    assert taxonomy["classification_input_source"] == "ingredient_quality_data.ingredients_scorable"


def test_row_evidence_records_every_row_with_an_explicit_role(omega_product):
    product = copy.deepcopy(omega_product)
    product["ingredient_quality_data"]["ingredients_scorable"].append(
        _row("Proprietary Blend", "blend_x", "blend",
             cleaner_row_role="blend_header_total")
    )
    product["ingredient_quality_data"]["ingredients_scorable"].append(
        _row("Rosemary Extract", "rosemary", "botanical", qty=0.0, unit="NP")
    )

    taxonomy = classify_supplement(product)
    evidence = taxonomy["classification_row_evidence"]

    assert len(evidence) == 4, "every input row must be accounted for"
    roles = {item["canonical_id"]: item["role"] for item in evidence}
    assert roles["epa"] == ROW_ROLE_INCLUDED_ACTIVE
    assert roles["dha"] == ROW_ROLE_INCLUDED_ACTIVE
    assert roles["blend_x"] == ROW_ROLE_EXCLUDED_STRUCTURAL
    assert roles["rosemary"] == ROW_ROLE_EXCLUDED_NON_QUANTIFIED

    for item in evidence:
        assert set(item) == {
            "source_path", "row_id", "canonical_id", "category",
            "quantified", "score_eligible", "role",
        }


def test_row_evidence_separates_score_eligibility_from_being_an_active(omega_product):
    """A dose-bearing row with an unresolved identity is a genuine label active
    that the SCORER must still reject. RC1 depends on these staying distinct."""
    product = copy.deepcopy(omega_product)
    product["ingredient_quality_data"]["ingredients_scorable"].append(
        _row("Mystery Herb", "", "botanical", 300.0, mapped=False)
    )

    taxonomy = classify_supplement(product)
    unresolved = [
        item for item in taxonomy["classification_row_evidence"]
        if item["role"] == ROW_ROLE_INCLUDED_ACTIVE and not item["score_eligible"]
    ]
    assert len(unresolved) == 1
    assert unresolved[0]["quantified"] is True
    assert taxonomy["unresolved_quantified_active_count"] == 1


# ---------------------------------------------------------------------------
# The SoT audit consumes the contract, not the path literal or prose
# ---------------------------------------------------------------------------


def test_audit_no_longer_greps_prose_for_omega_evidence(omega_product):
    """The gate must survive reason prose being rewritten entirely."""
    product = copy.deepcopy(omega_product)
    product["supplement_taxonomy"] = classify_supplement(product)
    product["supplement_taxonomy"]["classification_reasons"] = ["totally rewritten prose"]

    assert sot.taxonomy_has_omega_scorable_evidence(product), (
        "the omega gate still depends on rendered prose"
    )


def test_audit_survives_the_physical_source_path_changing(omega_product):
    """RC1 renames the physical row population. The gate must not care."""
    product = copy.deepcopy(omega_product)
    product["supplement_taxonomy"] = classify_supplement(product)
    product["supplement_taxonomy"]["classification_input_source"] = (
        "ingredient_quality_data.quantified_label_active_rows"  # RC1-shaped
    )

    assert sot.taxonomy_has_omega_scorable_evidence(product), (
        "the gate still pins the physical JSON path literal — RC1 would block "
        "the release"
    )


def test_audit_rejects_a_non_score_eligible_population(omega_product):
    product = copy.deepcopy(omega_product)
    product["supplement_taxonomy"] = classify_supplement(product)
    product["supplement_taxonomy"]["classification_input_contract"] = (
        INPUT_CONTRACT_IQD_ALL_ROWS
    )
    product["supplement_taxonomy"]["category_breakdown"] = {}

    assert not sot.taxonomy_has_omega_scorable_evidence(product)


def test_audit_requires_omega_rows_to_be_score_eligible(omega_product):
    product = copy.deepcopy(omega_product)
    taxonomy = classify_supplement(product)
    taxonomy["category_breakdown"] = {}  # force the row-evidence path
    for item in taxonomy["classification_row_evidence"]:
        item["score_eligible"] = False
    product["supplement_taxonomy"] = taxonomy

    assert not sot.taxonomy_has_omega_scorable_evidence(product)


def test_pre_contract_artifacts_still_readable_outside_strict_mode(omega_product):
    """Old blobs have no contract fields; non-release inspection still works."""
    legacy = {
        "classification_input_source": "ingredient_quality_data.ingredients_scorable",
        "classification_reasons": ["omega-3: ids=['epa', 'dha'], name_match=True"],
        "category_breakdown": {},
    }
    assert sot.taxonomy_has_omega_scorable_evidence({"supplement_taxonomy": legacy})


def test_iqd_fallback_detection_uses_the_contract():
    assert sot.taxonomy_used_iqd_fallback(
        {"classification_input_contract": INPUT_CONTRACT_IQD_ALL_ROWS}
    )
    assert not sot.taxonomy_used_iqd_fallback(
        {"classification_input_contract": INPUT_CONTRACT_SCORE_ELIGIBLE_ROWS}
    )
    # pre-contract artifact
    assert sot.taxonomy_used_iqd_fallback(
        {"classification_input_source": "ingredient_quality_data.ingredients_fallback"}
    )


def test_score_eligible_contract_set_is_not_empty():
    assert SCORE_ELIGIBLE_INPUT_CONTRACTS
    assert INPUT_CONTRACT_IQD_ALL_ROWS not in SCORE_ELIGIBLE_INPUT_CONTRACTS
    assert INPUT_CONTRACT_RAW_LABEL_ACTIVES not in SCORE_ELIGIBLE_INPUT_CONTRACTS


# ---------------------------------------------------------------------------
# Strict release mode accepts only the current contract version
# ---------------------------------------------------------------------------


def _clinical_args(tmp_path, product, *, strict):
    import argparse
    import json

    path = tmp_path / "enriched_batch.json"
    path.write_text(json.dumps([product]))
    return argparse.Namespace(
        product_file=[str(path)],
        enriched_file=[],
        enriched_dir=[],
        products_dir=None,
        strict_release=strict,
        matrix=str(sot.DEFAULT_MATRIX),
    )


def _pre_contract_product(omega_product):
    product = copy.deepcopy(omega_product)
    taxonomy = classify_supplement(product)
    taxonomy.pop("classification_contract_version")
    taxonomy.pop("classification_input_contract")
    taxonomy.pop("classification_row_evidence")
    product["supplement_taxonomy"] = taxonomy
    return product


def test_strict_release_rejects_a_pre_contract_artifact(tmp_path, omega_product):
    findings = sot.audit_clinical(
        _clinical_args(tmp_path, _pre_contract_product(omega_product), strict=True)
    )
    codes = [f.code for f in findings]
    assert "CLINICAL_TAXONOMY_CONTRACT_VERSION" in codes, (
        "strict release mode must not accept an artifact written by an older "
        "classifier — its classification cannot be gated on this contract"
    )


def test_non_strict_inspection_tolerates_a_pre_contract_artifact(tmp_path, omega_product):
    findings = sot.audit_clinical(
        _clinical_args(tmp_path, _pre_contract_product(omega_product), strict=False)
    )
    codes = [f.code for f in findings]
    assert "CLINICAL_TAXONOMY_CONTRACT_VERSION" not in codes


def test_strict_release_accepts_a_current_artifact(tmp_path, omega_product):
    product = copy.deepcopy(omega_product)
    product["supplement_taxonomy"] = classify_supplement(product)
    findings = sot.audit_clinical(_clinical_args(tmp_path, product, strict=True))
    codes = [f.code for f in findings]
    assert "CLINICAL_TAXONOMY_CONTRACT_VERSION" not in codes


def test_contract_version_findings_are_aggregated_not_per_product(tmp_path, omega_product):
    """One artifact-wide condition should not emit 14k identical findings and
    bury the per-product findings that actually differ."""
    import argparse
    import json

    products = []
    for index in range(25):
        stale = _pre_contract_product(omega_product)
        stale["dsld_id"] = 970000 + index
        products.append(stale)
    path = tmp_path / "enriched_batch.json"
    path.write_text(json.dumps(products))
    args = argparse.Namespace(
        product_file=[str(path)], enriched_file=[], enriched_dir=[],
        products_dir=None, strict_release=True, matrix=str(sot.DEFAULT_MATRIX),
    )

    findings = sot.audit_clinical(args)
    version_findings = [
        f for f in findings if f.code == "CLINICAL_TAXONOMY_CONTRACT_VERSION"
    ]
    assert len(version_findings) == 1
    assert "25 product(s)" in version_findings[0].message
