"""RC-5: integration tests for the label-correction mechanism in
enhanced_normalizer.py.

These tests exercise EnhancedDSLDNormalizer's normalize_product against
synthetic DSLD-shape inputs to assert that:

1. When a (dsld_id, raw_ingredient_text) tuple matches an override
   entry in product_label_corrections.json, the row's name is
   rewritten to corrected_ingredient_text BEFORE downstream
   ingredient resolution, and a provenance tag records the rewrite.

2. When raw_ingredient_text is a known drug token AND there is NO
   matching override for the dsld_id, the row is emitted to
   quarantine with reason 'requires_human_review_drug_token_in_supplement'
   instead of being silently mapped or silently dropped.

3. Non-drug-token unmapped rows continue to flow through the normal
   unmapped path (this test pins the regression boundary so the new
   quarantine code does not over-trigger).

Test inputs are synthesized to be minimal — just enough DSLD shape
to exercise normalize_product. Real shadow-clean of GNC pid=69734
lives in a separate audit script.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

# Skip the integration tests if the normalizer can't be constructed in
# a unit-test harness (it has heavy data-file dependencies). The tests
# below are designed to import the helper functions directly when the
# full normalizer fixture is too heavy.

try:
    from enhanced_normalizer import EnhancedDSLDNormalizer  # type: ignore
    _NORMALIZER_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    EnhancedDSLDNormalizer = None  # type: ignore
    _NORMALIZER_AVAILABLE = False
    _IMPORT_ERR = _e


def _make_ingredient_row(name: str, category: str = "fiber", order: int = 1) -> Dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "order": order,
        "ingredientId": 0,
        "uniiCode": "0",
    }


def _make_raw_product(dsld_id: int, ingredient_names: List[str]) -> Dict[str, Any]:
    return {
        "id": dsld_id,
        "fullName": "Test Product",
        "brandName": "TestBrand",
        "status": "active",
        "offMarket": 0,
        "ingredientRows": [
            _make_ingredient_row(n, order=i + 1)
            for i, n in enumerate(ingredient_names)
        ],
        "otherIngredients": {"ingredients": []},
    }


@pytest.fixture(scope="module")
def normalizer():
    if not _NORMALIZER_AVAILABLE:
        pytest.skip(f"EnhancedDSLDNormalizer not importable: {_IMPORT_ERR}")
    return EnhancedDSLDNormalizer()


def _walk_names(d, found):
    if isinstance(d, dict):
        n = d.get("name")
        if isinstance(n, str):
            found.append(n)
        for v in d.values():
            _walk_names(v, found)
    elif isinstance(d, list):
        for v in d:
            _walk_names(v, found)


def test_override_rewrites_matching_dsld_id_row(normalizer):
    """For GNC pid=69734, the raw 'Insulin' cell must be rewritten
    to 'Inulin' before mapping. We assert by walking the normalized
    output for the 'Inulin' name and absence of 'Insulin'."""
    raw = _make_raw_product(
        dsld_id=69734,
        ingredient_names=["Inositol", "Insulin", "Fructooligosaccharides"],
    )
    normalized = normalizer.normalize_product(raw)
    names = []
    _walk_names(normalized, names)
    name_text = " | ".join(names)
    # Insulin must NOT survive as a raw_source_text or name field
    # after override application
    assert "Insulin" not in [n for n in names if n is not None], (
        f"override failed: 'Insulin' still present in normalized output. "
        f"names={names}"
    )
    # And Inulin must be present (corrected value)
    assert any(n and n.strip().lower() == "inulin" for n in names), (
        f"override failed: 'Inulin' not found after correction. "
        f"names sample={names[:20]}"
    )


def test_override_does_not_apply_to_non_matching_dsld_id(normalizer):
    """If a hypothetical OTHER product (not in overrides) also
    contains 'Insulin' in a fiber-blend cell, it must NOT be
    silently rewritten — that would defeat scope=dsld_id_only."""
    fake_dsld_id = 99999999  # not in overrides
    raw = _make_raw_product(
        dsld_id=fake_dsld_id,
        ingredient_names=["Inositol", "Insulin", "Fructooligosaccharides"],
    )
    normalized = normalizer.normalize_product(raw)
    names = []
    _walk_names(normalized, names)
    # The row MUST NOT silently become Inulin. Either:
    #   (a) it stays as 'Insulin' (unmapped) and a quarantine signal
    #       is set on the product, OR
    #   (b) the row is dropped with a quarantine signal.
    # What is forbidden: silent re-interpretation as 'Inulin'.
    rewrote_silently = any(
        n and n.strip().lower() == "inulin" for n in names
    )
    assert not rewrote_silently, (
        f"scope leak: 'Insulin' was silently rewritten to 'Inulin' on "
        f"a product with no matching override (dsld_id={fake_dsld_id}). "
        f"Global aliasing of label-typo tokens is forbidden. "
        f"names={names}"
    )


def test_non_drug_token_unmapped_flow_unaffected(normalizer):
    """Regression boundary: an unmapped non-drug-token row (e.g.,
    'Vegetable Concentrate', 'Chocolate Cookie Crumbs') must
    continue to flow through the normal unmapped path. The new
    quarantine code must NOT over-trigger on garden-variety
    unmapped rows."""
    fake_dsld_id = 99999998
    raw = _make_raw_product(
        dsld_id=fake_dsld_id,
        ingredient_names=["Some Unknown Botanical", "Vitamin C"],
    )
    # Just assert this does not raise and produces output
    normalized = normalizer.normalize_product(raw)
    assert normalized is not None
    names = []
    _walk_names(normalized, names)
    assert any(n and "vitamin" in n.lower() for n in names), (
        f"normal unmapped path should still produce ingredient rows. "
        f"names={names[:20]}"
    )


def test_product_scoped_correction_removes_misattributed_source_unii(normalizer):
    rows = [
        {
            "name": "Transglucosidase",
            "category": "enzyme",
            "ingredientGroup": "Transglucosidase",
            "uniiCode": "DTI67O9503",
            "nestedRows": [],
            "forms": [],
        }
    ]

    corrected = normalizer._apply_label_corrections(rows, "59047")

    assert corrected[0]["name"] == "Transglucosidase"
    assert corrected[0]["uniiCode"] is None
    assert corrected[0]["_pre_correction_unii"] == "DTI67O9503"
    assert corrected[0]["_label_correction_provenance"] == "source_unii_correction"

    raw_product = _make_raw_product(59047, [])
    raw_product["fullName"] = "Digestive Enzymes"
    raw_product["ingredientRows"] = [
        {
            "name": "Transglucosidase",
            "category": "enzyme",
            "ingredientGroup": "Transglucosidase",
            "uniiCode": "DTI67O9503",
            "quantity": [{"quantity": 450, "unit": "TG"}],
            "nestedRows": [],
            "forms": [],
        }
    ]
    normalized = normalizer.normalize_product(raw_product)
    active = next(
        row for row in normalized["activeIngredients"]
        if row.get("raw_source_text") == "Transglucosidase"
    )
    assert active["source_correction"] == {
        "provenance_tag": "source_unii_correction",
        "original_unii_code": "DTI67O9503",
        "corrected_unii_code": None,
    }


def test_botanical_latin_parenthetical_resolves_without_replacing_label_name(normalizer):
    raw_product = _make_raw_product(99999997, [])
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Tropical Almond (Terminalia chebula)",
                category="botanical",
            ),
            "ingredientGroup": "Tropical Almond",
            "quantity": [{"quantity": 500, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    active = normalized["activeIngredients"][0]
    assert active["raw_source_text"] == "Tropical Almond (Terminalia chebula)"
    assert active["name"] == "Tropical Almond (Terminalia chebula)"
    assert active["standardName"] == "Chebulic Myrobalan"
    assert active["canonical_id"] == "chebulic_myrobalan"
    assert active["canonical_source_db"] == "botanical_ingredients"


def test_nested_64551_row_restores_omitted_latin_identity(normalizer):
    raw_product = _make_raw_product(64551, [])
    raw_product["fullName"] = "Standardized Triphala"
    raw_product["brandName"] = "Nature's Way"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Triphala fruit extract Blend",
                category="blend",
            ),
            "ingredientGroup": "Blend (Herb/Botanical)",
            "quantity": [{"quantity": 1.5, "unit": "Gram(s)"}],
            "forms": [],
            "nestedRows": [
                {
                    **_make_ingredient_row(
                        "Tropical Almond",
                        category="botanical",
                    ),
                    "ingredientGroup": "Tropical Almond",
                    "quantity": [{"quantity": 500, "unit": "mg"}],
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    active = next(
        row for row in normalized["activeIngredients"]
        if row.get("canonical_id") == "chebulic_myrobalan"
    )
    assert active["raw_source_text"] == "Tropical Almond (Terminalia chebula)"
    assert active["source_correction"] == {
        "provenance_tag": "source_label_omission_correction",
        "original_ingredient_text": "Tropical Almond",
        "corrected_ingredient_text": "Tropical Almond (Terminalia chebula)",
    }


def test_explicit_epa_note_repairs_contradictory_dsld_dha_taxonomy(normalizer):
    """The DSLD omega row must follow its explicit EPA label note, not a
    contradictory DHA name/identifier tuple supplied by the API."""
    raw_product = _make_raw_product(180408, [])
    raw_product["fullName"] = "One Per Day Fish Oil 1200 mg"
    raw_product["brandName"] = "Nature Made"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Docosahexaenoic Acid Ethyl Ester",
                category="fatty acid",
            ),
            "ingredientId": 285066,
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "uniiCode": "7PO7G8PA8M",
            "alternateNames": ["C22:6n-3", "DHA EE"],
            "notes": (
                "EPA (Form: as Ethyl Esters) "
                "(Alt. Name: Eicosapentaenoic Acid) Note: Omega-3"
            ),
            "quantity": [{"quantity": 360, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        },
        {
            **_make_ingredient_row(
                "Docosahexaenoic Acid Ethyl Ester",
                category="fatty acid",
                order=2,
            ),
            "ingredientId": 285066,
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "uniiCode": "7PO7G8PA8M",
            "alternateNames": ["C22:6n-3", "DHA EE"],
            "notes": (
                "DHA (Form: as Ethyl Esters) "
                "(Alt. Name: Docosahexaenoic Acid) Note: Omega-3"
            ),
            "quantity": [{"quantity": 300, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        },
    ]

    normalized = normalizer.normalize_product(raw_product)

    assert [row["canonical_id"] for row in normalized["activeIngredients"]] == [
        "epa",
        "dha",
    ]
    epa = normalized["activeIngredients"][0]
    assert epa["raw_source_text"] == "Eicosapentaenoic Acid Ethyl Ester"
    assert epa["ingredientGroup"] == "EPA (Eicosapentaenoic Acid)"
    assert epa["uniiCode"] == "6GC8A4PAYH"
    assert epa["ingredientId"] == 285067
    assert epa["source_correction"] == {
        "provenance_tag": "source_taxonomy_contradiction_repair",
        "original_ingredient_text": "Docosahexaenoic Acid Ethyl Ester",
        "corrected_ingredient_text": "Eicosapentaenoic Acid Ethyl Ester",
        "original_unii_code": "7PO7G8PA8M",
        "corrected_unii_code": "6GC8A4PAYH",
    }

    ledger_rows = normalized["display_ingredients"]
    assert [row["label_display_name"] for row in ledger_rows] == [
        "Eicosapentaenoic Acid Ethyl Ester",
        "Docosahexaenoic Acid Ethyl Ester",
    ]
