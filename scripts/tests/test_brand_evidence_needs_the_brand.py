"""A brand's clinical record reaches a label only when the label names the brand.

`enrich_supplements_v3._brand_mentioned` confirms an alias-only BRAND_ match in the
product text, using the entry's curated `brand_tokens` when present; aliases stay the
discovery surface and may be generic. BioPerine and Zynamite had no brand_tokens, so
a generic alias ("piperine", "mangiferin") confirmed itself, and HMB and OptiFerrin
were ingredient evidence filed as brands: 81 raw labels in the corpus census of
2026-09-29 took a brand's Evidence floor without naming a brand. Receipts:
scripts/audits/rr_correctness_20260928/research.md.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"


def _entries():
    rows = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    return {e["id"]: e for e in rows}


def test_brands_with_generic_aliases_confirm_on_their_brand_token():
    entries = _entries()
    assert entries["BRAND_ZYNAMITE"]["brand_tokens"] == ["zynamite"]
    assert entries["BRAND_SUNTHEANINE"]["brand_tokens"] == ["suntheanine"]


def test_ingredient_evidence_is_filed_as_ingredient_evidence():
    entries = _entries()
    assert "BRAND_HMB" not in entries and "BRAND_OPTIFERRIN" not in entries
    hmb, lactoferrin = entries["INGR_HMB"], entries["INGR_LACTOFERRIN"]
    assert lactoferrin["evidence_level"] == "ingredient-human"
    # Dr. Pham, 2026-10-28: HMB's restrictive conclusion is a completed
    # no-credit decision on the reference-only path, still under its INGR_ id.
    assert hmb["evidence_level"] == hmb["study_type"] == "reference"
    assert {"hmb", "calcium hmb"} <= set(hmb["aliases"])
    assert "lactoferrin" in lactoferrin["aliases"]
    assert (lactoferrin["min_clinical_dose"], lactoferrin["dose_unit"]) == (200, "mg")


def test_bioperine_is_an_absorption_aid_not_an_efficacy_record():
    """BRAND_BIOPERINE (removed 2026-09-29, Sean) filed pharmacokinetic evidence
    (piperine raising curcumin exposure) as Energy / Healthy Aging efficacy. The
    absorption-aid role stays with its owner, absorption_enhancers.json."""
    assert "BRAND_BIOPERINE" not in _entries()
    enhancers = json.loads((DATA / "absorption_enhancers.json").read_text())["absorption_enhancers"]
    pepper = next(e for e in enhancers if e["id"] == "ENHANCER_BLACK_PEPPER")
    assert "bioperine" in pepper["aliases"]


def _matches(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"brand_generic_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    evidence = enriched.get("evidence_data") or {}
    accepted = {m.get("id") for m in evidence.get("clinical_matches") or []}
    rejected = {m.get("id"): m.get("reason_code") for m in evidence.get("rejected_clinical_matches") or []}
    return accepted, rejected


# Discovery remains separate from eligibility: completed reference-only and
# held-source records retain their exact rejection reason. Routing is asserted
# without restoring affirmative credit to the held lactoferrin source.
@pytest.mark.parametrize("pid, absent, present, reference_only", [
    ("233404", "BRAND_ZYNAMITE", None, False),          # mangiferin, Zynamite not named
    ("18416", "BRAND_HMB", "INGR_HMB", True),           # plain HMB
    ("267894", "BRAND_OPTIFERRIN", "INGR_LACTOFERRIN", False),  # plain lactoferrin
    ("182824", "BRAND_BIOPERINE", None, False),        # "Curcumin 500 with Bioperine": no efficacy record
    ("214982", None, "BRAND_SUNTHEANINE", True),       # names Suntheanine
])
def test_real_labels_reach_the_right_record(pid, absent, present, reference_only):
    accepted, rejected = _matches(pid)
    if absent:
        assert absent not in accepted and absent not in rejected
    if present and reference_only:
        assert present not in accepted
        assert rejected.get(present) == "reference_only_clinical_record"
    elif present == "INGR_LACTOFERRIN":
        from clinical_applicability import assess_clinical_source_review
        assert present not in accepted
        assert rejected.get(present) == "clinical_sources_ineligible"
        assert assess_clinical_source_review({"id": present})["is_complete"] is False
    elif present:
        assert present in accepted



@pytest.mark.parametrize('record_id,canonical,generic,branded', [
    ('BRAND_UCII', 'collagen_type_ii', 'Undenatured Collagen II', 'UC-II Undenatured Type II Collagen'),
    ('BRAND_MAGTEIN', 'magnesium', 'Magnesium L-Threonate', 'Magtein Magnesium L-Threonate'),
])
def test_generic_identity_or_another_row_cannot_supply_exact_brand_scope(record_id, canonical, generic, branded):
    from copy import deepcopy
    from clinical_applicability import assess_clinical_applicability
    from test_green_tea_evidence_identity import _source_product
    product = _source_product(generic)
    row = product['activeIngredients'][0]
    row.update(name=generic, raw_source_text=generic, standardName=generic, canonical_id=canonical,
               ingredientGroup=canonical, matched_form=branded, forms=[])
    row['raw_taxonomy'].update(category='non-nutrient/non-botanical', ingredientGroup=canonical, forms=[])
    entry = {'id': record_id, 'matched_source_row_refs': ['ingredientRows[0]'],
             'matched_canonical_ids': [canonical]}
    decision = assess_clinical_applicability(product, entry, assess_amount=False)
    assert decision['status'] == 'not_applicable'
    assert decision['reason_code'] == 'clinical_form_mismatch'
    sibling = deepcopy(row)
    sibling.update(name=branded, raw_source_text=branded, raw_source_path='ingredientRows[1]')
    product['activeIngredients'].append(sibling)
    assert assess_clinical_applicability(product, entry, assess_amount=False)['reason_code'] == 'clinical_form_mismatch'
    exact = {**entry, 'matched_source_row_refs': ['ingredientRows[1]']}
    assert assess_clinical_applicability(product, exact, assess_amount=False)['status'] == 'applicable'


@pytest.mark.parametrize('case, expected', [
    ('exact_heading', True),
    ('generic_heading', False),
    ('negated_heading', False),
    ('unrelated_brand_row', False),
    ('quantified_child', False),
])
def test_ucii_source_preparation_heading_is_bound_to_its_undosed_member(case, expected):
    """The physical owner may name its child; another row cannot lend that name."""
    import copy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from clinical_applicability import assess_clinical_applicability

    raw = json.loads((FIXTURES / 'evidence_subject_321604_raw.json').read_text())
    heading = raw['ingredientRows'][0]
    if case in {'generic_heading', 'unrelated_brand_row'}:
        heading['name'] = 'Proprietary Cartilage Blend'
    if case == 'negated_heading':
        heading['name'] = 'Proprietary Cartilage Blend, not UC-II'
    if case == 'unrelated_brand_row':
        unrelated = copy.deepcopy(raw['ingredientRows'][1])
        unrelated.update(name='UC-II', forms=[], ingredientGroup='Other')
        raw['ingredientRows'].append(unrelated)
    if case == 'quantified_child':
        heading['nestedRows'][0]['quantity'][0].update(quantity=10, unit='mg')
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    matches = [m for m in product['evidence_data']['clinical_matches'] if m.get('id') == 'BRAND_UCII']
    # An unrelated explicit UC-II row may qualify itself, never the generic member.
    member_matches = [m for m in matches if 'ingredientRows[0]' in m.get('matched_source_row_refs', [])]
    assert bool(member_matches) is expected
    if case in {'generic_heading', 'negated_heading', 'quantified_child'}:
        assert matches == []
    if expected:
        match = member_matches[0]
        assessment = match['applicability_assessment']
        assert assessment['source_row_ref'] == 'ingredientRows[0].nestedRows[0]'
        assert assessment.get('daily_dose') is None
        foreign = {**match, 'matched_source_row_refs': ['ingredientRows[99]']}
        assert assess_clinical_applicability(product, foreign, assess_amount=False)['status'] != 'applicable'


@pytest.mark.parametrize('record_id, canonical, label', [
    ('BRAND_UCII', 'collagen_type_ii', 'Undenatured collagen, not UC-II'),
    ('BRAND_MAGTEIN', 'magnesium', 'Magnesium L-Threonate, not Magtein'),
])
def test_negated_exact_brand_does_not_establish_source_preparation(record_id, canonical, label):
    from clinical_applicability import assess_clinical_applicability
    from test_green_tea_evidence_identity import _source_product
    product = _source_product(label)
    row = product['activeIngredients'][0]
    row.update(canonical_id=canonical, raw_source_text=label, forms=[])
    row['raw_taxonomy']['forms'] = []
    entry = {'id': record_id, 'matched_source_row_refs': ['ingredientRows[0]'],
             'matched_canonical_ids': [canonical]}
    decision = assess_clinical_applicability(product, entry, assess_amount=False)
    assert decision['status'] == 'not_applicable'
    assert decision['reason_code'] == 'clinical_form_mismatch'


@pytest.mark.parametrize('reverse_rows', [False, True])
def test_ucii_clinical_source_cannot_be_attributed_to_leucine(reverse_rows):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((FIXTURES / 'brand_generic_76848_raw.json').read_text())
    if reverse_rows:
        raw['ingredientRows'].reverse()
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    match = next(m for m in product['evidence_data']['clinical_matches'] if m.get('id') == 'BRAND_UCII')
    assert match['ingredient'] == 'UC-II standardized Cartilage'
    assert match['matched_canonical_ids'] == ['collagen']
    assert match['applicability_assessment']['matched_canonical_ids'] == ['collagen']
    artifact = build_scored_artifact(product)
    evidence = artifact['_v4_module_breakdown']['dimensions']['evidence']
    assert 'l_leucine' not in evidence['metadata'].get('ingredient_points', {})
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0.0


@pytest.mark.parametrize('canon_index, expected', [
    ({'beta alanine': 'beta-alanine'}, 'beta-alanine'),
    ({'unknown': 'taurine'}, ''),
    ({'beta alanine': 'beta-alanine', 'beta alanine alias': 'beta_alanine'}, ''),
])
def test_reviewed_source_identity_matches_only_a_unique_actual_canonical(canon_index, expected):
    from scoring_v4.modules.generic_evidence import _matched_active_canonical
    entry = {'ingredient': 'Taurine', 'matched_canonical_ids': ['beta-alanine'],
             'applicability_assessment': {'matched_canonical_ids': ['beta-alanine']}}
    assert _matched_active_canonical(entry, canon_index, owner_canonicals=set(canon_index.values())) == expected


@pytest.mark.parametrize('dsld_id', ['220215', '221166', '224676', '295064', '310967', '71680'])
def test_complete_material_evidence_never_belongs_to_one_constituent(dsld_id):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    raw = json.loads((FIXTURES / f'brand_generic_{dsld_id}_raw.json').read_text())
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    matches, _ = resolved_clinical_matches(product, owner_scoped=True)
    if dsld_id in {'220215', '221166'}:
        # Source whey alongside amino-acid forms cannot make free leucine the
        # whole-protein trial material. The mixed-source macro is not all whey.
        assert not any(m.get('id') == 'INGR_WHEY_PROTEIN' for m in matches)
    else:
        match = next(m for m in matches if m.get('id') == 'INGR_BRANCHED_CHAIN_AMINO_ACIDS')
        assert match['matched_canonical_ids'] == ['branched_chain_amino_acids']
        assert 'leucine' not in match['ingredient'].lower()
        from scoring_v4.scored_artifact import build_scored_artifact
        artifact = build_scored_artifact(product)
        points = artifact['_v4_module_breakdown']['dimensions']['evidence']['metadata'].get('ingredient_points', {})
        assert 'l_leucine' not in points


@pytest.mark.parametrize('shape, aggregate, dose_known', [
    ('complete', True, True), ('isolated', False, False), ('partial', False, False),
    ('duplicate', False, False), ('foreign', False, False), ('unknown', True, False),
    ('mixed_units', True, True),
])
def test_bcaa_composition_owner_keeps_complete_source_identity_separate_from_amount(shape, aggregate, dose_known):
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence
    rows = [dict(name=name, canonical_id=name, raw_category='amino acid', ingredientGroup='Amino Acid',
                 raw_source_path=f'ingredientRows[{index}]', quantity=amount, unit='mg',
                 identity_disposition='clean')
            for index, (name, amount) in enumerate([('l_leucine', 1000), ('l_isoleucine', 500), ('l_valine', 500)])]
    if shape == 'isolated': rows = rows[:1]
    if shape == 'partial': rows = rows[:2]
    if shape == 'duplicate': rows.append({**rows[0], 'raw_source_path': 'ingredientRows[3]'})
    if shape == 'foreign': rows[-1]['parent_source_path'] = 'ingredientRows[99]'
    if shape == 'unknown': rows[-1].update(quantity=None, unit='NP')
    if shape == 'mixed_units': rows[0].update(quantity=1, unit='g')
    items = [item for item in _derive_explicit_eaa_aggregate_evidence(rows, {'product_name': 'BCAA'})
             if item['canonical_id'] == 'branched_chain_amino_acids']
    assert bool(items) is aggregate
    if aggregate:
        assert set(items[0]['verified_child_canonicals']) == {'l_leucine', 'l_isoleucine', 'l_valine'}
        assert set(items[0]['linked_rows']) == {row['raw_source_path'] for row in rows}
        if dose_known:
            assert items[0]['dose_value'] == 2.0
            assert items[0]['dose_unit'] == 'g'
        else:
            assert items[0]['scoreable'] is False
            assert items[0]['dose_value'] == 0


def test_raw_complete_bcaa_unknown_member_amounts_keep_identity_without_borrowed_dose():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_evidence_subject_rows
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    raw = json.loads((FIXTURES / 'brand_generic_295064_raw.json').read_text())
    for member in raw['ingredientRows'][0]['nestedRows']:
        member['quantity'][0].update(quantity=0, unit='NP')
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    groups = [r for r in get_evidence_subject_rows(product) if r.get('canonical_id') == 'branched_chain_amino_acids']
    assert len(groups) == 1
    assert groups[0]['scoreable'] is False
    assert groups[0]['dose_value'] == 0
    assert set(groups[0]['verified_child_canonicals']) == {'l_leucine', 'l_isoleucine', 'l_valine'}
    matches, _ = resolved_clinical_matches(product, owner_scoped=True)
    match = next(m for m in matches if m.get('id') == 'INGR_BRANCHED_CHAIN_AMINO_ACIDS')
    assert match['matched_canonical_ids'] == ['branched_chain_amino_acids']


def test_complete_bcaa_parent_owns_its_printed_mass_without_member_fractions():
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence
    parent = {'name': 'BCAA', 'canonical_id': 'branched_chain_amino_acids',
              'raw_source_path': 'ingredientRows[0]', 'quantity': 5, 'unit': 'g',
              'cleaner_row_role': 'blend_header_total'}
    children = [{'name': canonical, 'canonical_id': canonical, 'identity_disposition': 'clean',
                 'raw_category': 'amino acid', 'quantity': 0, 'unit': 'NP',
                 'raw_source_path': f'ingredientRows[0].nestedRows[{index}]',
                 'parent_source_path': 'ingredientRows[0]'}
                for index, canonical in enumerate(['l_leucine', 'l_isoleucine', 'l_valine'])]
    items = _derive_explicit_eaa_aggregate_evidence([parent, *children], {'product_name': 'BCAA'})
    assert len(items) == 1
    assert items[0]['dose_value'] == 5
    assert items[0]['dose_unit'] == 'g'
    assert items[0]['raw_source_path'] == parent['raw_source_path']
    assert items[0]['linked_rows'] == [parent['raw_source_path'], *(row['raw_source_path'] for row in children)]
    # An undisclosed other member prevents transferring the parent's total.
    other = {**children[0], 'name': 'Other material', 'canonical_id': 'unknown',
             'raw_source_path': 'ingredientRows[0].nestedRows[3]'}
    uncertain = _derive_explicit_eaa_aggregate_evidence([parent, *children, other], {'product_name': 'BCAA'})
    assert uncertain[0]['scoreable'] is False
    assert uncertain[0]['dose_value'] == 0


def test_complete_eaa_does_not_infer_bcaa_without_a_separately_quantified_preparation():
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence, EAA_CANONICALS
    parent = {'name': 'Amino complex', 'canonical_id': 'essential_amino_acids',
              'raw_source_path': 'ingredientRows[0]', 'quantity': 10, 'unit': 'g',
              'cleaner_row_role': 'blend_header_total'}
    bcaa = {'name': 'BCAA', 'canonical_id': 'branched_chain_amino_acids',
            'raw_source_path': 'ingredientRows[0].nestedRows[0]',
            'parent_source_path': 'ingredientRows[0]', 'quantity': 0, 'unit': 'NP'}
    rows = [parent, bcaa]
    for index, canonical in enumerate(sorted(EAA_CANONICALS)):
        base = bcaa['raw_source_path'] if canonical in {'l_leucine', 'l_isoleucine', 'l_valine'} else parent['raw_source_path']
        rows.append({'name': canonical, 'canonical_id': canonical, 'identity_disposition': 'clean',
                     'quantity': 0, 'unit': 'NP', 'raw_category': 'amino acid',
                     'raw_source_path': base + f'.nestedRows[{index + 1}]', 'parent_source_path': base})
    groups = _derive_explicit_eaa_aggregate_evidence(rows, {'product_name': 'Amino complex'})
    assert [row['canonical_id'] for row in groups] == ['essential_amino_acids']


def test_explicit_zero_bcaa_member_cannot_use_unknown_identity_fallback():
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence
    rows = [{'name': canonical, 'canonical_id': canonical, 'identity_disposition': 'clean',
             'raw_category': 'amino acid', 'quantity': amount, 'unit': 'mg',
             'raw_source_path': f'ingredientRows[{index}]',
             'raw_taxonomy': {'quantityVariants': [{'quantity': amount, 'unit': 'mg',
                    'selected_for_analysis': True, 'quantity_parsed': True, 'operator': '='}]}}
            for index, (canonical, amount) in enumerate([('l_leucine', 1000), ('l_isoleucine', 500), ('l_valine', 0)])]
    assert _derive_explicit_eaa_aggregate_evidence(rows, {'product_name': 'BCAA'}) == []


@pytest.mark.parametrize('category, source, compatible', [
    ('amino acid', 'Whey Protein Isolate', False),
    ('amino acid', 'hydrolyzed Whey Protein', False),
    ('amino acid', 'Whey Protein, Hydrolyzed', False),
    ('amino acid', 'Casein', True),
    ('protein', 'Whey Protein Isolate', True),
])
def test_protein_source_form_cannot_replace_its_amino_acid_material(category, source, compatible):
    from scoring_input_contract import declared_source_form_matches_material
    row = {'name': 'L-Leucine' if category == 'amino acid' else 'Whey Protein',
           'raw_taxonomy': {'category': category, 'forms': [{'category': 'protein', 'name': source}]}}
    assert declared_source_form_matches_material(row, ['Whey Protein', 'whey protein isolate']) is compatible


def test_bounded_bcaa_member_is_not_zero_or_an_exact_aggregate_dose():
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence
    rows = [{'name': canonical, 'canonical_id': canonical, 'identity_disposition': 'clean',
             'raw_category': 'amino acid', 'quantity': amount, 'unit': 'mg',
             'raw_source_path': f'ingredientRows[{index}]',
             'raw_taxonomy': {'quantityVariants': [{'quantity': amount, 'unit': 'mg',
                    'selected_for_analysis': True, 'quantity_parsed': True,
                    'operator': '<' if canonical == 'l_valine' else '='}]}}
            for index, (canonical, amount) in enumerate([('l_leucine', 1000), ('l_isoleucine', 500), ('l_valine', 1)])]
    groups = _derive_explicit_eaa_aggregate_evidence(rows, {'product_name': 'BCAA'})
    assert len(groups) == 1
    assert groups[0]['scoreable'] is False
    assert groups[0]['dose_value'] == 0


def test_bounded_bcaa_parent_keeps_complete_identity_without_exact_mass():
    from scoring_input_contract import _derive_explicit_eaa_aggregate_evidence
    parent = {'name': 'BCAA', 'canonical_id': 'branched_chain_amino_acids',
              'raw_source_path': 'ingredientRows[0]', 'quantity': 5, 'unit': 'g',
              'raw_taxonomy': {'quantityVariants': [{'quantity': 5, 'unit': 'g', 'operator': '<',
                          'selected_for_analysis': True, 'quantity_parsed': True}]}}
    children = [{'name': canonical, 'canonical_id': canonical, 'identity_disposition': 'clean',
                 'raw_category': 'amino acid', 'quantity': 0, 'unit': 'NP',
                 'raw_source_path': f'ingredientRows[0].nestedRows[{index}]',
                 'parent_source_path': 'ingredientRows[0]'}
                for index, canonical in enumerate(['l_leucine', 'l_isoleucine', 'l_valine'])]
    groups = _derive_explicit_eaa_aggregate_evidence([parent, *children], {'product_name': 'BCAA'})
    assert len(groups) == 1
    assert groups[0]['scoreable'] is False
    assert groups[0]['dose_value'] == 0
    assert set(groups[0]['verified_child_canonicals']) == {'l_leucine', 'l_isoleucine', 'l_valine'}
