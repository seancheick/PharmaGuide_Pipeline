"""End-to-end canonical_id identity chain continuity tests.

Traces canonical_id from cleaner output through enriched output through v4
scored output, validating that the semantic shift is made explicit via the
new identity fields: clean_identity_id, scoring_parent_id,
evidence_canonical_id, canonical_source_db, evidence_origin.
"""
from __future__ import annotations

import copy
import json
import sys
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_input_contract import get_scoring_ingredients  # noqa: E402
from scoring_input_contract import derive_product_scoring_evidence  # noqa: E402

IDENTITY_FIELDS = {
    "clean_identity_id",
    "scoring_parent_id",
    "evidence_canonical_id",
    "canonical_source_db",
    "evidence_origin",
}


@lru_cache(maxsize=1)
def _golden_index() -> dict:
    # Scan the enriched corpus ONCE for every golden product (early-exit once all
    # are found) instead of re-parsing the whole corpus per parametrized call.
    # sorted() makes the scan deterministic (glob order is FS-dependent).
    wanted = set(GOLDEN_IDS)
    index: dict[str, dict] = {}
    for path in sorted((SCRIPTS_ROOT / "products").glob("output_*_enriched/enriched/*.json")):
        payload = json.loads(path.read_text())
        products = payload if isinstance(payload, list) else payload.get("products", [])
        for product in products:
            pid = str(product.get("dsld_id") or product.get("id"))
            if pid in wanted and pid not in index:
                index[pid] = product
        if len(index) == len(wanted):
            break
    return index


def _load_product(dsld_id: str) -> dict:
    product = _golden_index().get(dsld_id)
    if product is None:
        raise AssertionError(f"Could not find enriched product {dsld_id}")
    # Deepcopy so a test mutating the product (e.g. scoring derivation) cannot
    # corrupt the shared cached parse used by the other parametrized tests.
    return copy.deepcopy(product)


def _evidence_rows(product: dict) -> list[dict]:
    result = get_scoring_ingredients(product, strict=True)
    return [
        row for row in result.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
    ]


# --- Golden product IDs ---
PROTEIN_DSLD = "180692"
OMEGA_DSLD = "13801"
ENZYME_DSLD = "293966"
BLEND_DSLD = "309492"

GOLDEN_IDS = [PROTEIN_DSLD, OMEGA_DSLD, ENZYME_DSLD, BLEND_DSLD]


@pytest.mark.parametrize("dsld_id", GOLDEN_IDS)
def test_evidence_rows_carry_identity_chain_fields(dsld_id: str) -> None:
    """Every derived evidence row must carry all five new identity fields."""
    product = _load_product(dsld_id)
    rows = _evidence_rows(product)
    assert rows, f"Product {dsld_id} must produce at least one evidence row"
    for row in rows:
        missing = IDENTITY_FIELDS - set(row.keys())
        assert not missing, (
            f"Evidence row {row.get('evidence_type')} missing fields: {missing}"
        )


@pytest.mark.parametrize("dsld_id", GOLDEN_IDS)
def test_scoring_parent_id_matches_evidence_canonical_id(dsld_id: str) -> None:
    """scoring parent follows the evidence key, not necessarily clean identity."""
    product = _load_product(dsld_id)
    for row in _evidence_rows(product):
        assert row["scoring_parent_id"] == row["evidence_canonical_id"], (
            f"scoring_parent_id={row['scoring_parent_id']} != "
            f"evidence_canonical_id={row['evidence_canonical_id']} "
            f"for {row.get('evidence_type')}"
        )


def test_clean_identity_id_traces_to_row_canonical() -> None:
    """clean_identity_id must come from the source row's canonical_id,
    not be invented by the contract. For protein, the cleaner resolves the
    macro as 'protein' (a real IQM entry), so clean_identity_id == 'protein'
    is correct. The contract distinguishes this from scoring_parent_id which
    is always the synthetic scoring key."""
    product = _load_product(PROTEIN_DSLD)
    protein_rows = [
        r for r in _evidence_rows(product)
        if r.get("evidence_type") == "sports_primary_dose"
    ]
    assert protein_rows, "Must have sports_primary_dose evidence"
    # At least one row must have a real clean_identity_id (from a row where
    # the cleaner resolved a canonical). Others may be None when evidence was
    # derived via text matching on a row with no canonical_id.
    has_real_identity = any(row.get("clean_identity_id") for row in protein_rows)
    assert has_real_identity, (
        "At least one protein evidence row must have a non-None clean_identity_id"
    )
    for row in protein_rows:
        assert row["scoring_parent_id"] == row["evidence_canonical_id"]


def test_identity_chain_can_represent_clean_to_scoring_semantic_shift() -> None:
    """The contract must not collapse clean identity into the scoring key.

    Protein products often clean to a specific source identity such as
    whey_protein while v4 scores the normalized protein macro. That semantic
    shift is expected, but it must be explicit in the evidence row.
    """
    product = {
        "product_name": "Whey Protein",
        "primary_type": "protein_powder",
        "activeIngredients": [
            {
                "name": "Whey Protein Isolate",
                "canonical_id": "whey_protein",
                "quantity": 25,
                "unit": "g",
                "raw_source_path": "activeIngredients[0]",
            }
        ],
        "ingredient_quality_data": {"ingredients_scorable": []},
    }
    shifted_rows = derive_product_scoring_evidence(product)

    assert shifted_rows, "Expected at least one explicit clean->evidence identity shift"
    for row in shifted_rows:
        assert row["clean_identity_id"] == "whey_protein"
        assert row["evidence_canonical_id"] == "protein"
        assert row["scoring_parent_id"] == "protein"


@pytest.mark.parametrize("dsld_id", GOLDEN_IDS)
def test_evidence_origin_is_compatibility_derived(dsld_id: str) -> None:
    """All derived evidence rows carry evidence_origin == 'compatibility_derived'."""
    product = _load_product(dsld_id)
    for row in _evidence_rows(product):
        assert row.get("evidence_origin") == "compatibility_derived", (
            f"evidence_origin should be 'compatibility_derived', "
            f"got {row.get('evidence_origin')!r} for {row.get('evidence_type')}"
        )


@pytest.mark.parametrize("dsld_id", GOLDEN_IDS)
def test_scorable_rows_lack_evidence_origin(dsld_id: str) -> None:
    """Rows from ingredients_scorable (not synthesized) must NOT have evidence_origin."""
    product = _load_product(dsld_id)
    result = get_scoring_ingredients(product, strict=True)
    scorable_rows = [
        r for r in result.rows
        if r.get("scoring_input_kind") != "product_level_evidence"
    ]
    for row in scorable_rows:
        assert row.get("evidence_origin") is None, (
            f"Non-evidence row should not have evidence_origin, "
            f"got {row.get('evidence_origin')!r} for {row.get('name')}"
        )
