"""Form disclosure has one contract.

- A form the label does not disclose is worth the lowest *eligible* named
  bio_score minus 1 (scoring_reference_resolver.unknown_form_quality). The
  IQM owns eligibility (form field ``unknown_floor``): non-functional
  analogs, degradation products, wrong stereoisomers, different compounds and
  non-nutrient sources never set the floor. An authored unspecified form
  supplies the identity; its value may sit above the floor only with a
  reviewed override, which the integrity gate checks.
- With no authored unspecified form the result is identity-neutral: no
  form_id, so no named form's notes, evidence or copy can attach.
- A form the label names that IQM does not recognize is not nondisclosure:
  the row keeps its identity, gets no form quality, reads
  form_match_status 'unmapped', and the product is held until curated.
- The enricher is the only form matcher; scoring consumes its reading.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

from scoring_reference_resolver import (
    unknown_floor,
    unknown_floor_override,
    unknown_form_quality,
)

FIXTURES = Path(__file__).parent / 'fixtures'
IQM = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())

# parent -> (lowest eligible named bio_score, the named form the old fallback invented)
DERIVED = {
    'hmb': (13, 'hmb calcium salt (hmb-ca)'),
    'l_leucine': (14, 'l-leucine powder'),
    'acacia_catechu': (9, 'acacia catechu wood and bark extract'),
    'chlorophyll': (3, 'natural chlorophyll'),
}


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def _enrich(enricher, label):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


# ── the unknown-form value ────────────────────────────────────────────────────

@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_without_an_authored_unspecified_form_the_unknown_is_lowest_eligible_minus_one(parent):
    lowest, _ = DERIVED[parent]
    assert unknown_form_quality(IQM[parent]) == {
        'form_id': None, 'form': None, 'bio_score': lowest - 1.0,
        'basis': 'derived_lowest_eligible_minus_one'}


def test_an_authored_unspecified_form_is_capped_at_the_floor():
    # calcium (unspecified) was 6; the plainest eligible calcium form is the
    # oxide at 4, so nondisclosure is worth 3.
    unknown = unknown_form_quality(IQM['calcium'])
    assert (unknown['form_id'], unknown['bio_score']) == ('calcium (unspecified)', 3.0)
    assert unknown_floor(IQM['calcium']) == (3.0, 'calcium oxide')


def test_an_ineligible_form_never_sets_the_floor():
    # D-tyrosine (PubChem CID 71098, (2R)) is the enantiomer of L-tyrosine
    # (CID 6057, (2S); parent UNII 42HK56048U Tyrosine). Its typed
    # parent_relationship keeps it from defining what an undisclosed
    # L-tyrosine is worth (N-acetyl L-tyrosine 8 - 1), and a label naming it
    # is held for identity verification, never scored as L-tyrosine.
    tyrosine = IQM['l_tyrosine']
    assert tyrosine['forms']['d-tyrosine']['parent_relationship'] == 'wrong_stereoisomer'
    assert 'unknown_floor' not in tyrosine['forms']['d-tyrosine']
    assert unknown_floor(tyrosine) == (7.0, 'n-acetyl l-tyrosine')
    assert unknown_form_quality(tyrosine)['bio_score'] == 7.0


def test_the_derived_value_never_goes_below_zero():
    assert unknown_form_quality({'forms': {'x': {'bio_score': 0}}})['bio_score'] == 0.0


def test_a_source_preparation_is_not_an_eligible_named_form():
    parent = {'forms': {'plain': {'bio_score': 8},
                        'from shellfish': {'bio_score': 2, 'alias_identity_scope': 'source_preparation'}}}
    assert unknown_form_quality(parent)['bio_score'] == 7.0


def test_nondisclosure_is_never_worth_more_than_the_floor_without_an_override():
    parent = {'forms': {'plain': {'bio_score': 8},
                        'x (unspecified)': {'bio_score': 12}}}
    assert unknown_form_quality(parent)['bio_score'] == 7.0
    reviewed = copy.deepcopy(parent)
    reviewed['forms']['x (unspecified)']['unknown_floor'] = {
        'override': True, 'rationale': 'r', 'reviewed_by': 'b', 'reviewed_on': '2026-09-25'}
    assert unknown_form_quality(reviewed)['bio_score'] == 12.0
    incomplete = copy.deepcopy(reviewed)
    incomplete['forms']['x (unspecified)']['unknown_floor']['reviewed_by'] = ''
    assert unknown_form_quality(incomplete)['bio_score'] == 7.0


def test_every_shipped_override_is_documented_and_every_unspecified_form_is_at_or_below_its_floor():
    from scoring_reference_resolver import authored_unknown_form
    overrides = []
    for key, entry in IQM.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        authored, floor = authored_unknown_form(entry), unknown_floor(entry)
        if not authored or not floor:
            continue
        if unknown_floor_override(authored[1]):
            overrides.append(key)
        else:
            assert authored[1]['bio_score'] <= floor[0], (key, authored[1]['bio_score'], floor)
    assert sorted(overrides) == sorted([
        'magnesium', 'zinc', 'iron', 'vitamin_a', 'beta_carotene', 'bacillus_subtilis',
        'phosphatidylcholine', 'rhodiola', 'ginkgo', 'msm', 'phosphatidylserine',
        'acetyl_l_carnitine', 'creatine_monohydrate', 'vanadyl_sulfate', 'capsaicin'])


def test_the_integrity_gate_rejects_an_undocumented_value_above_the_floor():
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    mutated['calcium']['forms']['calcium (unspecified)']['bio_score'] = 9
    del mutated['magnesium']['forms']['magnesium (unspecified)']['unknown_floor']['reviewed_by']
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    codes = {(f.path, f.issue) for f in findings if f.severity == 'error'}
    assert ('calcium.forms.calcium (unspecified).bio_score', 'unspecified_above_floor') in codes
    assert ('magnesium.forms.magnesium (unspecified).unknown_floor', 'invalid_unknown_floor') in codes


def test_the_integrity_gate_rejects_an_unknown_relationship_and_a_retired_floor_mark():
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    mutated['l_tyrosine']['forms']['d-tyrosine']['parent_relationship'] = 'enantiomer-ish'
    mutated['iron']['forms']['iron oxide']['unknown_floor'] = {'eligible': False, 'reason': 'not_a_nutrient_source'}
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    codes = {(f.path, f.issue) for f in findings if f.severity == 'error'}
    assert ('l_tyrosine.forms.d-tyrosine.parent_relationship', 'enum_value_not_supported') in codes
    assert ('iron.forms.iron oxide.unknown_floor', 'invalid_unknown_floor') in codes


def test_the_per_form_checks_run_on_every_form_not_only_the_last():
    # The floor check once sat between the per-form checks, so absorption,
    # notes and dosage_importance ran only on each parent's last form.
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    names = list(mutated['calcium']['forms'])
    for name in (names[0], names[-1]):
        mutated['calcium']['forms'][name]['notes'] = 5
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    flagged = {f.path for f in findings if f.issue == 'type_mismatch' and f.path.endswith('.notes')}
    assert flagged == {f'calcium.forms.{names[0]}.notes', f'calcium.forms.{names[-1]}.notes'}


# ── the enricher's reading ────────────────────────────────────────────────────

@pytest.mark.parametrize('parent', sorted(DERIVED))
@pytest.mark.parametrize('label', ['Zqx Blend', 'Zqx Powder'])
def test_the_enricher_fallback_names_no_form(enricher, parent, label):
    lowest, invented = DERIVED[parent]
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert match['match_tier'] == 'cleaner_canonical_parent'
    assert match['form_id'] is None and match['fallback_form_name'] is None
    assert match['form_name'] == 'unspecified' != invented
    assert (match['notes'], match['absorption']) == (None, None)
    assert match['bio_score'] == lowest - 1.0


@pytest.mark.parametrize('label', ['HMB', 'HMB Powder', 'beta-hydroxy beta-methylbutyrate'])
def test_a_bare_hmb_label_names_no_salt(enricher, label):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'])
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('hmb', None, 12.0)


def test_the_parents_generic_form_is_not_a_reading_of_a_named_token(enricher):
    # "taurine (generic)" is taurine's authored unspecified form; before, it was
    # accepted as the form "Magnesium Taurate" named.
    from enrich_supplements_v3 import SupplementEnricherV3
    quality_map = enricher.databases['ingredient_quality_map']
    default = enricher._match_quality_map('Zqx', 'Zqx', quality_map, _form_extraction_attempt=True,
                                          preferred_parent='taurine', cleaner_canonical_id='taurine')
    assert default['form_id'] == 'taurine (generic)'
    assert not SupplementEnricherV3._is_specific_form_match(default, quality_map)


@pytest.mark.parametrize('parent, label, token, form', [
    ('phosphorus', 'Phosphorus', 'Dicalcium Phosphate', 'dicalcium phosphate (as phosphorus source)'),
    ('magnesium', 'Magnesium', 'Magnesium Ascorbate', 'magnesium ascorbate (as magnesium source)'),
    ('zinc', 'Zinc', 'Zinc Ascorbate', 'zinc ascorbate (as zinc source)'),
    ('taurine', 'Taurine', 'Magnesium Taurate', 'magnesium taurate (as taurine source)'),
])
def test_a_compound_filed_under_another_parent_reads_as_this_parents_counter_ion_form(
        enricher, parent, label, token, form):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[{'name': token}], cleaner_canonical_id=parent)
    assert (match['canonical_id'], match['form_id']) == (parent, form)
    assert not match.get('unmapped_forms')


def test_a_disclosed_form_the_iqm_lacks_is_unmapped_and_held(enricher):
    # 59086 "L-Glutamine (as L-Glutamine Alpha-Ketoglutarate)": the identity is
    # L-glutamine, the salt is not in the IQM. It once shipped as
    # l-glutamine powder, bio 11, mapped, form_unmapped false.
    from score_supplements_v4 import score_product_v4
    enriched = _enrich(enricher, 'form_association_59086_raw.json')
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r['name'] == 'L-Glutamine')
    assert (row['canonical_id'], row['mapped']) == ('l_glutamine', True)
    assert (row['form_id'], row['matched_form'], row['bio_score']) == (None, None, None)
    assert row['form_match_status'] == 'unmapped'
    assert row['unmapped_forms'] == ['L-Glutamine Alpha-Ketoglutarate']
    assert row['identity_decision_reason'] == 'disclosed_form_unmapped'
    readiness = score_product_v4(enriched)['v4_breakdown']['assessment_readiness']
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']


@pytest.mark.parametrize('token', ['L-Glutamine HCl', 'L-Glutamine Hydrochloride'])
def test_glutamine_hydrochloride_is_not_free_glutamine(enricher, token):
    # PubChem: the hydrochloride is its own salt (CID 57364844, C5H11ClN2O3);
    # free L-glutamine is CID 5961. No GSRS UNII and no bio_score evidence,
    # so it is a disclosed unmapped form until curated.
    match = enricher._match_quality_map('L-Glutamine', 'L-Glutamine', enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[{'name': token}], cleaner_canonical_id='l_glutamine')
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('l_glutamine', None, None)
    assert match['match_status'] == 'FORM_DISCLOSED_UNMAPPED'
    assert match['unmapped_forms'] == [token]


@pytest.mark.parametrize('label', ['L-Glutamine', 'L-Glutamine Powder', 'Glutamine'])
def test_plain_glutamine_is_the_free_form(enricher, label):
    # Plain L-glutamine and its powder are one identity (GSRS 0RH81L854J).
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'])
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('l_glutamine', 'l-glutamine powder', 11)


@pytest.mark.parametrize('label, parent, form', [
    ('D-Tyrosine', 'l_tyrosine', 'd-tyrosine'),
    ('D-Carnitine', 'l_carnitine', 'd-carnitine'),
    ('Siberian Ginseng', 'ginseng', 'siberian ginseng (eleuthero)'),
    ('Hydroxyproline', 'l_proline', 'hydroxyproline'),
])
def test_a_form_that_is_not_the_parents_identity_never_inherits_its_scoring(enricher, label, parent, form):
    from scoring_reference_resolver import IDENTITY_MISMATCH_RELATIONSHIPS, parent_relationship
    assert parent_relationship(IQM[parent]['forms'][form]) in IDENTITY_MISMATCH_RELATIONSHIPS
    row = {'canonical_id': parent, 'form_id': form, 'matched_forms': []}
    assert enricher._identity_mismatch_forms(row) == [form]


def test_a_same_nutrient_degraded_form_is_not_an_identity_mismatch(enricher):
    # Iron oxide is iron, poorly delivered: its own low bio_score, not a hold.
    assert enricher._identity_mismatch_forms({'canonical_id': 'iron', 'form_id': 'iron oxide'}) == []


def test_a_packaging_word_never_picks_a_form_the_label_does_not_state(enricher):
    # "Ginseng, Powder" once took 'siberian ginseng (eleuthero)' because an
    # eleuthero alias contains "powder".
    quality_map = enricher.databases['ingredient_quality_map']
    match = enricher._match_quality_map('Ginseng, Powder', 'Ginseng, Powder', quality_map,
                                        cleaner_canonical_id='ginseng')
    assert (match['canonical_id'], match['form_id']) == ('ginseng', 'ginseng (unspecified)')


def test_the_contradictory_wild_cherry_label_is_held(enricher):
    # 311881 "Wild Cherry Fruit Extract" (black cherry, Prunus serotina) as
    # "Cerasus avium Fruit Extract" (sweet cherry): out of scoring until the
    # identity is resolved.
    from score_supplements_v4 import score_product_v4
    enriched = _enrich(enricher, 'form_association_311881_raw.json')
    readiness = score_product_v4(enriched)['v4_breakdown']['assessment_readiness']
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']
    unmapped = [r['unmapped_forms'] for r in enriched['ingredient_quality_data']['ingredients']
                if r.get('form_match_status') == 'unmapped']
    unmapped += [e['unmapped_forms'] for e in enriched['product_scoring_evidence']
                 if e.get('form_match_status') == 'unmapped']
    assert unmapped == [['Cerasus avium Fruit Extract']]


def test_a_disclosed_form_is_read_not_replaced_by_a_default(enricher):
    # 318107 "L-Tyrosine (as N-Acetyl-L-Tyrosine)", UNII DA8G610ZO5 (GSRS:
    # Acetyl L-tyrosine). NALT is 8.
    enriched = _enrich(enricher, 'form_association_318107_raw.json')
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('name') == 'L-Tyrosine')
    assert [m['form_key'] for m in row['matched_forms']] == ['n-acetyl l-tyrosine']
    assert row['bio_score'] == 8.0 and row['form_match_status'] == 'mapped'


@pytest.mark.parametrize('token, parent, form', [('N-Acetyl-L-Tyrosine', 'l_tyrosine', 'n-acetyl l-tyrosine'),
                                                 ('N-Acetyl-L-Cysteine', 'nac', 'nac powder')])
def test_hyphenated_acetyl_forms_resolve_by_alias(enricher, token, parent, form):
    match = enricher._match_quality_map(token, token, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert (match['form_id'], match['match_tier']) == (form, 'exact')


# ── one matcher: scoring and export consume the reading ───────────────────────

def test_the_scoring_contract_has_no_form_matcher():
    import scoring_input_contract
    assert not hasattr(scoring_input_contract, '_form_quality_from_iqm')
    assert 'iqm_reference_index' not in vars(scoring_input_contract)


@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_the_export_attaches_no_form_copy_to_a_derived_unknown(parent):
    from build_final_db import _derive_form_evidence, _derive_form_note
    lowest, _ = DERIVED[parent]
    row = {'canonical_id': parent, 'matched_form': 'unspecified', 'matched_forms': [],
           'bio_score': lowest - 1.0}
    iqm_index = {k: v for k, v in IQM.items() if k != '_metadata'}
    assert _derive_form_note(row, iqm_index) == (None, None)
    assert _derive_form_evidence(row, iqm_index) is None
