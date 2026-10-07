"""One provider of Evidence subjects (evidence_zero_rootcause_20260929, lane 1).

The scoring contract decides which rows own a product's Evidence
(``evidence_owner_canonicals``); the scorer scores only the enricher's clinical
matches. The enricher used to match over its own row list, which drops
label-level projections (``product_level_evidence``), so 489 products had
owners the matcher never visited. Both sides now read
``scoring_input_contract.get_evidence_subject_rows``.

Fixtures are real DSLD labels from the 2026-09-29 corpus:
- 251549 DIM-plus: DIM 100 mg exists only as a blend projection.
- 54775 Sytrinol: the branded total exists only as a projection.
- 278019 Pancreatic Enzyme Formula: every enzyme row is a projection.
- 321604 Ultra Triple Action Joint Health: "UC-II Proprietary Cartilage
  Blend" (forms: Cartilage, Potassium Chloride) projects UC-II.
- 176055 Amplified Creatine XXX: creatine owns Evidence; the amino-acid blend
  and L-glutamine projections do not.
- 19505 Rebel Fruit Blast: D-aspartic acid sits undosed in a blend total.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from evidence_resolver import evidence_owner_canonicals  # noqa: E402
from scoring_input_contract import get_evidence_subject_rows  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def enriched(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    normalizer = EnhancedDSLDNormalizer()
    out = {}
    for dsld_id in ("251549", "54775", "278019", "321604", "176055", "19505", "251338"):
        raw = json.loads((FIXTURES / f"evidence_subject_{dsld_id}_raw.json").read_text())
        out[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


def _canonicals(rows):
    return {str(r.get("canonical_id") or "").strip().lower() for r in rows} - {""}


def _matches(product):
    return {
        m.get("id"): set(m.get("matched_canonical_ids") or [])
        for m in product["evidence_data"]["clinical_matches"]
    }


@pytest.mark.parametrize("dsld_id", ["251549", "54775", "278019"])
def test_every_evidence_owner_comes_from_the_one_provider(enriched, dsld_id):
    product = enriched[dsld_id]
    owners = evidence_owner_canonicals(product)
    assert owners
    assert owners <= _canonicals(get_evidence_subject_rows(product))


@pytest.mark.parametrize("dsld_id", ["251549", "54775", "278019"])
def test_the_enricher_matches_over_every_evidence_owner(enricher, enriched, dsld_id):
    product = enriched[dsld_id]
    visited = _canonicals(
        enricher._evidence_subject_ingredients_for_enrichment(
            product, ingredient_quality_data=product["ingredient_quality_data"],
        )
    )
    assert evidence_owner_canonicals(product) <= visited


def test_dim_projection_reaches_its_reviewed_record(enriched):
    assert "diindolylmethane" in _matches(enriched["251549"]).get("PRECLIN_DIM", set())


def test_branded_projection_reaches_its_branded_record(enriched):
    assert "sytrinol" in _matches(enriched["54775"]).get("BRAND_SYTRINOL", set())


def test_a_branded_blend_reaches_its_record_through_the_member(enriched):
    """The UC-II blend's name is not an identity; its disclosed member,
    undenatured type II collagen (IQM collagen, form alias "uc-ii"), is."""
    assert "collagen" in _matches(enriched["321604"]).get("BRAND_UCII", set())


def test_a_carrier_form_on_a_blend_earns_no_evidence(enriched):
    """The blend name no longer carries its DSLD forms (Cartilage, Potassium
    Chloride) into matching, so the carrier matches nothing."""
    assert "INGR_POTASSIUM" not in _matches(enriched["321604"])


def test_only_evidence_owners_are_added_beyond_the_label_actives(enricher, enriched):
    product = enriched["176055"]
    iqd = product["ingredient_quality_data"]
    label_actives = _canonicals(
        enricher._primary_active_ingredients_for_enrichment(product, ingredient_quality_data=iqd)
    )
    visited = _canonicals(
        enricher._evidence_subject_ingredients_for_enrichment(product, ingredient_quality_data=iqd)
    )
    assert "creatine_monohydrate" in visited
    assert visited <= label_actives | evidence_owner_canonicals(product)
    assert "l_glutamine" not in visited


def test_a_blend_total_is_not_a_member_dose_for_applicability(enriched):
    """The blend total lent to D-aspartic acid is not its amount, so it cannot
    satisfy the reviewed 3 g/day minimum."""
    for match in enriched["19505"]["evidence_data"]["clinical_matches"]:
        if match["id"] == "INGR_D_ASPARTIC_ACID":
            assert (match.get("applicability_assessment") or {}).get("status") != "applicable"


_INELIGIBLE = [
    {"canonical_id": "protectamins_vegetable_blend", "identity_kind": "label_taxonomy_anchor",
     "name": "Protectamins Vegetable Blend", "raw_source_path": "ingredientRows[1]"},
    {"canonical_id": "piperine", "demotion_reason": "absorption_enhancer_sub_threshold",
     "name": "BioPerine", "raw_source_path": "ingredientRows[2]"},
    {"canonical_id": "vegetable_source_descriptor", "name": "from vegetables",
     "raw_source_path": "ingredientRows[3]"},
]


@pytest.mark.parametrize("path", ["strict", "label_rows", "both"])
def test_one_eligibility_decision_on_every_provider_path(monkeypatch, path):
    """A blend name, a demoted aid and a descriptor are refused whether they
    arrive as strict scoring rows, as label rows (the mirror, or its
    pre-enrichment fallback), or both; an all-ineligible label stays empty."""
    import scoring_input_contract as sic
    from types import SimpleNamespace

    strict = [dict(r) for r in _INELIGIBLE] if path in ("strict", "both") else []
    label = [dict(r) for r in _INELIGIBLE] if path in ("label_rows", "both") else []
    monkeypatch.setattr(sic, "get_scoring_ingredients", lambda product, **_: SimpleNamespace(rows=strict))
    monkeypatch.setattr(sic, "get_assessable_evidence_ingredients", lambda product: label)
    assert sic.get_evidence_subject_rows({}) == []

    real = {"canonical_id": "diindolylmethane", "name": "DIM", "raw_source_path": "ingredientRows[0]"}
    (strict if path != "label_rows" else label).append(real)
    assert _canonicals(sic.get_evidence_subject_rows({})) == {"diindolylmethane"}


def test_the_minted_blend_name_is_not_a_subject_on_a_real_label(enriched):
    assert "protectamins_vegetable_blend" not in _canonicals(get_evidence_subject_rows(enriched["251549"]))


def test_enrichment_keeps_undosed_reviewed_match_without_promising_a_member_dose(enriched):
    product = enriched['176055']
    row = next(r for r in get_evidence_subject_rows(product) if r.get('canonical_id') == 'l_arginine')
    matches = [m for m in product['evidence_data']['clinical_matches'] if m.get('id') == 'INGR_L_ARGININE']
    assert matches
    assert row['raw_source_path'] in matches[0]['matched_source_row_refs']
    from dose_assessment import positive_clinical_benchmark
    assert positive_clinical_benchmark(product, row) is None


def test_printed_inulin_child_supports_anchor_without_borrowing_blend_mass(enriched):
    from clinical_applicability import assess_clinical_applicability
    from dose_assessment import positive_clinical_benchmark
    product = enriched["251338"]
    match = next(m for m in product["evidence_data"]["clinical_matches"] if m["id"] == "INGR_INULIN")
    result = assess_clinical_applicability(product, match, assess_amount=False)
    assert result["status"] == "applicable"
    assert result["source_row_ref"] == "ingredientRows[7].nestedRows[0]"
    row = next(r for r in get_evidence_subject_rows(product) if r.get("canonical_id") == "inulin")
    assert positive_clinical_benchmark(product, row) is None


def test_strict_subject_merge_respects_accepted_marker_role():
    from scoring_input_contract import _is_ineligible_evidence_subject
    marker = {'name': 'Terpene Lactone', 'canonical_id': 'nha_total_terpene_lactones',
              'cleaner_row_role': 'standardization_marker', 'quantity': 7.2, 'unit': 'mg'}
    assert _is_ineligible_evidence_subject(marker)
    # The same named material without an accepted marker role is not globally excluded.
    assert not _is_ineligible_evidence_subject({**marker, 'cleaner_row_role': 'active_scorable'})



@pytest.mark.parametrize('dsld_id, ref', [('175375', 'ingredientRows[11]'), ('175409', 'ingredientRows[13]')])
def test_source_flavor_heading_keeps_disclosure_without_therapeutic_projection(enricher, dsld_id, ref):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / f'functional_flavor_{dsld_id}_raw.json').read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    header = next(r for r in cleaned['activeIngredients'] if r['raw_source_path'] == ref)
    assert header['cleaner_row_role'] == 'source_descriptor'
    assert header['quantity'] > 0
    display = next(r for r in cleaned['display_ingredients'] if r.get('raw_source_path') == ref)
    assert display['score_included'] is False
    assert display['is_label_context'] is True
    children = header['nestedIngredients']
    source_children = raw['ingredientRows'][int(ref.split('[')[1].split(']')[0])]['nestedRows']
    assert [r['raw_source_text'] for r in children] == [r['name'] for r in source_children]
    assert all(r['raw_source_path'].startswith(ref + '.nestedRows[') for r in children)
    product, _ = enricher.enrich_product(cleaned)
    assert not any(r.get('canonical_id') == 'oi_generic_flavor' for r in get_evidence_subject_rows(product))
