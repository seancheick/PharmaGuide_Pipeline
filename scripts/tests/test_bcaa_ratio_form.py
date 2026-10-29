"""A BCAA row reads a ratio form only when its own panel text states the ratio.

IQM `branched_chain_amino_acids`: a ratio form (2:1:1, 4:1:1) needs the label to
state the ratio. A generic name ("BCAA", "Branched-Chain Amino Acids", "BCAA
Blend") reads `branched chain amino acids (unspecified)`, whose own consumer note
says the listing does not state the ratio. Until 2026-09-28 the generic names sat
on the 2:1:1 form (bio 15), so the hyphenated spelling read 2:1:1 and the
unhyphenated one read unspecified (bio 10).

The ratio counts when the Supplement Facts row prints it, in the row name ("2:1:1
BCAA") or in the text DSLD keeps as that row's `notes` ("BCAA" + "2:1:1"). A ratio
stated only in a label statement, or computable from the leucine, isoleucine and
valine amounts, does not count (register Q36).

The ratio names the row's form; it does not change form quality. Every disclosed
BCAA form absorbs to the same extent, so each scores 15 and the unspecified form is
the lowest eligible named score minus 1 (IQM unknown-form rule), 14.
"""
import json
from copy import deepcopy
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'
BCAA = 'branched_chain_amino_acids'
UNSPECIFIED = 'branched chain amino acids (unspecified)'


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


def _bcaa_readings(enriched):
    rows = (enriched.get('ingredient_quality_data') or {}).get('ingredients') or []
    rows = rows + (enriched.get('product_scoring_evidence') or [])
    return {(r.get('matched_form'), r.get('bio_score')) for r in rows if r.get('canonical_id') == BCAA}


def _scored_bcaa_bio(enriched):
    """The BCAA form quality the scorer is given (scoring_input_contract rows read
    through generic_helpers.bio_score_of, the one form-quality reader)."""
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.modules.generic_helpers import bio_score_of
    return {bio_score_of(r) for r in get_scoring_ingredients(enriched, strict=True).rows
            if r.get('canonical_id') == BCAA}


def test_a_bcaa_label_without_a_ratio_gives_the_scorer_the_unspecified_form(enricher):
    """GNC Ultra Mega Green Active (31148) lists "Branched-Chain Amino Acids 100 mg"
    with leucine, isoleucine and valine undisclosed, and states no ratio anywhere.
    Its blend-anchor evidence row is the BCAA row the scorer reads; on the
    multi/prenatal route that reading enters Formulation."""
    from scoring_v4.scored_artifact import build_scored_artifact
    enriched = _enrich(enricher, 'bcaa_31148_raw.json')
    readings = _bcaa_readings(enriched)

    assert (UNSPECIFIED, 14.0) in readings
    assert not {form for form, _ in readings} & {'bcaa 2:1:1', 'bcaa 4:1:1', 'bcaa peptides'}
    assert _scored_bcaa_bio(enriched) == {14.0}
    assert build_scored_artifact(enriched)['quality_score_status'] == 'scored'


def test_a_ratio_printed_on_the_panel_row_reads_the_ratio_form(enricher):
    """Nutricost Intra (311733) prints "BCAA 2:1:1 ... 5,000mg" on its Supplement
    Facts panel; DSLD keeps "BCAA" as the row name and "2:1:1" as the row's notes."""
    enriched = _enrich(enricher, 'bcaa_311733_raw.json')
    readings = _bcaa_readings(enriched)

    assert ('bcaa 2:1:1', 15.0) in readings
    assert UNSPECIFIED not in {form for form, _ in readings}
    assert _scored_bcaa_bio(enriched) == {15.0}


def test_a_label_that_states_2_1_1_keeps_the_ratio_form(enricher):
    """Nutricost BCAA 6 g (270253) lists "2:1:1 BCAA 6000 mg" with leucine 3000 mg,
    isoleucine 1500 mg and valine 1500 mg."""
    enriched = _enrich(enricher, 'bcaa_270253_raw.json')

    assert ('bcaa 2:1:1', 15.0) in _bcaa_readings(enriched)
    assert _scored_bcaa_bio(enriched) == {15.0}


@pytest.mark.parametrize('current_notes', [None, 'Supports muscle recovery'])
def test_cached_ratio_from_panel_notes_cannot_outlive_its_same_source_notes(enricher, current_notes):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / 'bcaa_270253_raw.json').read_text())
    raw['ingredientRows'][0].update(name='Branched-Chain Amino Acids', notes='2:1:1')
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert _scored_bcaa_bio(product) == {15.0}
    assert next(row for row in product['product_scoring_evidence']
                if row.get('canonical_id') == BCAA)['notes'] == '2:1:1'
    for row in [*product['activeIngredients'], *product['ingredient_quality_data']['ingredients'],
                *product['ingredient_quality_data']['ingredients_scorable']]:
        if row.get('raw_source_path') == 'ingredientRows[0]':
            if current_notes is None:
                row.pop('notes', None)
            else:
                row['notes'] = current_notes
    # A retained old reading cannot name a ratio after its matcher input changed.
    assert _scored_bcaa_bio(product) == {None}
    if current_notes is None:
        raw['ingredientRows'][0].pop('notes')
    else:
        raw['ingredientRows'][0]['notes'] = current_notes
    fresh, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert _scored_bcaa_bio(fresh) == {14.0}
    assert (UNSPECIFIED, 14.0) in _bcaa_readings(fresh)


@pytest.fixture(scope='module')
def ratio_bcaa_product(enricher):
    return _enrich(enricher, 'bcaa_270253_raw.json')


@pytest.mark.parametrize('mutation, expected', [
    ('none', 15.0), ('foreign_ref', None), ('foreign_source_text', None),
    ('foreign_forms', None), ('foreign_standard_name', None),
    ('stale_composition', None), ('conflicting_readings', None),
    ('legacy_missing_notes', None),
])
def test_fresh_composition_retains_only_its_exact_source_form_reading(ratio_bcaa_product, mutation, expected):
    from scoring_input_contract import get_scoring_ingredients
    product = deepcopy(ratio_bcaa_product)
    native = next(row for row in product['product_scoring_evidence']
                  if row.get('canonical_id') == BCAA)
    if mutation == 'foreign_ref':
        native['raw_source_path'] = 'ingredientRows[99]'
    elif mutation == 'foreign_source_text':
        native['raw_source_text'] = '4:1:1 BCAA'
    elif mutation == 'foreign_forms':
        native['forms'] = [{'name': 'BCAA Peptides'}]
    elif mutation == 'foreign_standard_name':
        native['standardName'] = 'Different material reading'
    elif mutation == 'stale_composition':
        native['verified_child_canonicals'].remove('l_valine')
    elif mutation == 'legacy_missing_notes':
        native.pop('notes', None)
    elif mutation == 'conflicting_readings':
        other = deepcopy(native)
        other['matched_form'] = 'bcaa 4:1:1'
        product['product_scoring_evidence'].append(other)
    rows = [row for row in get_scoring_ingredients(product, strict=True).rows
            if row.get('canonical_id') == BCAA]
    assert len(rows) == 1
    assert _scored_bcaa_bio(product) == {expected}
    assert rows[0].get('matched_form') == ('bcaa 2:1:1' if expected else None)
    # The fresh composition/amount/ref owner survives; a stale cached form
    # cannot replace that source or supply a new ratio reading in Score.
    assert rows[0]['raw_source_path'] == 'ingredientRows[0]'
    assert rows[0]['quantity'] == 6000
    assert rows[0]['unit'] == 'mg'
    assert set(rows[0]['verified_child_canonicals']) == {'l_leucine', 'l_isoleucine', 'l_valine'}
    assert rows[0]['linked_rows'] == ['ingredientRows[0]', *[
        f'ingredientRows[0].nestedRows[{index}]' for index in range(3)]]


@pytest.mark.parametrize('name', [
    'BCAA', 'BCAAs', 'BCAA Powder', 'BCAA Supplement', 'BCAA Blend',
    'Branched-Chain Amino Acids', 'Branched Chain Amino Acids',
    # "High leucine" states no ratio: 2:1:1 is leucine-dominant too.
    'High Leucine BCAA', 'Leucine Dominant BCAA',
])
def test_a_generic_bcaa_name_reads_one_unspecified_form_whatever_its_punctuation(enricher, name):
    match = enricher._match_quality_map(name, name, enricher.databases['ingredient_quality_map'],
                                        cleaner_canonical_id=BCAA)
    assert (match['canonical_id'], match['form_id']) == (BCAA, UNSPECIFIED)


@pytest.mark.parametrize('name, form', [
    ('2:1:1 BCAA', 'bcaa 2:1:1'),
    ('Leucine:Isoleucine:Valine 2:1:1', 'bcaa 2:1:1'),
    ('Leucine:Isoleucine:Valine 4:1:1', 'bcaa 4:1:1'),
    ('Branched-Chain Amino Acids, Instantized', 'instantized bcaas'),
    ('BCAA Peptides', 'bcaa peptides'),
])
def test_a_named_ratio_or_process_keeps_its_form(enricher, name, form):
    match = enricher._match_quality_map(name, name, enricher.databases['ingredient_quality_map'],
                                        cleaner_canonical_id=BCAA)
    assert (match['canonical_id'], match['form_id']) == (BCAA, form)


def test_instantized_amino_acids_is_not_a_bcaa_identity(enricher):
    """An instantized amino-acid blend need not be branched-chain (EAA blends are
    instantized too); only BCAA-named instantized forms read the BCAA parent."""
    iqm = enricher.databases['ingredient_quality_map']
    match = enricher._match_quality_map('Instantized Amino Acids', 'Instantized Amino Acids', iqm) or {}
    assert match.get('canonical_id') != BCAA
    assert enricher._match_quality_map('Branched-Chain Amino Acids, Instantized', 'Branched-Chain Amino Acids, Instantized',
                                       iqm)['form_id'] == 'instantized bcaas'


@pytest.mark.parametrize('name, notes, form', [
    ('BCAA', '2:1:1', 'bcaa 2:1:1'),
    ('Branched-Chain Amino Acids', '2:1:1', 'bcaa 2:1:1'),
    ('Branched-Chain Amino Acids', 'BCAA 2:1:1 Blend', 'bcaa 2:1:1'),
    # The row name already names a form, so the note is not consulted.
    ('Branched-Chain Amino Acids, Instantized', '2:1:1', 'instantized bcaas'),
    # Panel text that is not one of the parent's source-form tokens changes nothing.
    ('BCAA', 'Supports muscle recovery', UNSPECIFIED),
])
def test_a_panel_note_names_the_form_only_through_the_parents_source_form_aliases(enricher, name, notes, form):
    match = enricher._match_quality_map(name, name, enricher.databases['ingredient_quality_map'],
                                        cleaner_canonical_id=BCAA, row_notes=notes)

    assert (match['canonical_id'], match['form_id']) == (BCAA, form)
    assert match.get('match_status') not in ('FORM_DISCLOSED_UNMAPPED', 'FORM_UNMAPPED')
    assert (match.get('form_source') == 'row_notes') == (form == 'bcaa 2:1:1')


def test_disclosed_bcaa_forms_share_the_parent_maximum_and_unspecified_is_one_lower(enricher):
    """IQM bio_score for a systemic active follows absorption. A ratio sets how much of
    each amino acid a serving holds, instantizing aids mixing, and peptide-bound BCAAs
    appear faster but to the same ~90% extent (IQM Batch 22), so no disclosed form
    outranks another."""
    from scoring_reference_resolver import unknown_floor
    parent = enricher.databases['ingredient_quality_map'][BCAA]
    forms = parent['forms']
    named = ('bcaa 2:1:1', 'bcaa 4:1:1', 'instantized bcaas', 'bcaa peptides')

    assert {forms[name]['bio_score'] for name in named} == {15}
    assert forms[UNSPECIFIED]['bio_score'] == unknown_floor(parent)[0] == 14

    # The tier rests on a verified free-amino-acid absorption trial; peptides keeps
    # its frozen legacy score until a source for peptide-bound extent is verified.
    from iqm_form_evidence import validate_iqm_form
    for name in ('bcaa 2:1:1', 'bcaa 4:1:1', 'instantized bcaas', UNSPECIFIED):
        assert validate_iqm_form(forms[name], label=name) == []
        assert [ref['pmid'] for ref in forms[name]['form_evidence']['references_structured']] == ['34642762']
    assert 'form_evidence' not in forms['bcaa peptides']

    copy = ' '.join(str(form.get(field) or '').lower() for form in forms.values() for field in ('notes', 'absorption'))
    for unsupported in ('most common and clinically studied', 'maximize muscle protein synthesis',
                        'absorbed even faster', 'superior', 'for accurate scoring'):
        assert unsupported not in copy


def test_pmid_34642762_is_cited_by_its_real_byline(enricher):
    """PMID 34642762 is Weijzen et al., J Nutr 2022 (free amino acids vs intact milk
    protein); the leucine note had it as "Churchward-Venne 2021"."""
    iqm = enricher.databases['ingredient_quality_map']
    notes = iqm['l_leucine']['forms']['l-leucine powder']['notes']
    assert '34642762' in notes
    assert 'free-amino-acid mixture with intact milk protein' in notes
    assert 'not intestinal absorption measurements' in notes
    assert 'Churchward-Venne' not in json.dumps(iqm)
