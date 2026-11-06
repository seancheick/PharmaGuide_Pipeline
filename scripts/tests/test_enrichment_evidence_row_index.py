"""Evidence discovery prepares row identity keys once without changing joins."""

from collections import Counter

import pytest

import enrich_supplements_v3 as enrichment


@pytest.fixture
def discovery(monkeypatch):
    enricher = enrichment.SupplementEnricherV3.__new__(enrichment.SupplementEnricherV3)
    enricher.databases = {}
    candidates = []
    monkeypatch.setattr(enricher, "_get_all_product_text", lambda _: "")
    monkeypatch.setattr(enricher, "_check_unsubstantiated_claims", lambda _: {})
    monkeypatch.setattr(enricher, "_has_bcaa_mixture_evidence_identity", lambda *_: False)
    monkeypatch.setattr(enricher, "_product_context_branded_token_for_ingredient", lambda *_: None)
    monkeypatch.setattr(enrichment, "delivers_parent_nutrient", lambda *_: True)
    monkeypatch.setattr("clinical_applicability.filter_clinical_matches", lambda _, matches, **kw: (matches, []))

    def collect(product, rows):
        candidates.clear()
        monkeypatch.setattr(enricher, "_evidence_subject_ingredients_for_enrichment",
                            lambda *args, **kwargs: product["activeIngredients"])
        monkeypatch.setattr(enricher, "_candidate_clinical_studies",
                            lambda names, _: candidates.append(names) or [])
        enricher._collect_evidence_data(product, {"ingredients_scorable": rows})
        return list(candidates)

    return collect


def test_quality_identity_preparation_is_linear(discovery, monkeypatch):
    count = 40
    rows = [{"name": f"quality-row-{i}", "matched_form": f"prepared-{i}"}
            for i in range(count)]
    ingredients = [{"name": row["name"]} for row in rows]
    calls = Counter()
    original = enrichment.norm_module.make_normalized_key

    def counted(value):
        if str(value).startswith("quality-row-"):
            calls[value] += 1
        return original(value)

    monkeypatch.setattr(enrichment.norm_module, "make_normalized_key", counted)
    found = discovery({"activeIngredients": ingredients}, rows)

    assert len(found) == count
    assert [next(value for value in names if value.startswith("prepared-"))
            for names in found] == [f"prepared-{i}" for i in range(count)]
    assert sum(calls.values()) == 2 * count


@pytest.mark.parametrize("quantity,unit,expected", [
    (10, "mg", ["prepared-first", "prepared-unknown", "prepared-last"]),
    (20, "mg", ["prepared-other-dose", "prepared-unknown"]),
    (10, "g", ["prepared-unknown"]),
    (None, "g", ["prepared-first", "prepared-other-dose", "prepared-unknown", "prepared-last"]),
])
def test_quality_join_preserves_quantity_unknowns_and_original_order(discovery, quantity, unit, expected):
    rows = [
        {"name": "Vitamin-C", "raw_source_text": "vitamin c", "quantity": 10,
         "unit": "mg", "matched_form": "prepared-first"},
        {"name": "Vitamin C", "quantity": 20, "unit": "mg", "matched_form": "prepared-other-dose"},
        {"original_label": "Vitamin C", "matched_form": "prepared-unknown"},
        {"name": "Vitamin C", "quantity": 10, "unit": "mg", "matched_form": "prepared-last"},
        {"name": "Vitamin C", "source_section": "inactive", "matched_form": "prepared-inactive"},
        {"name": "Other", "matched_form": "prepared-other"},
    ]
    product = {"activeIngredients": [{"name": "Vitamin C", "standardName": "Vitamin-C",
                                      "quantity": quantity, "unit": unit}]}

    found = discovery(product, rows)

    assert [value for value in found[0] if value.startswith("prepared-")] == expected
