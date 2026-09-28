"""A row's panel note names its form only through its parent's source_form_aliases.

DSLD sometimes keeps part of a Supplement Facts row apart from the row name:
"BCAA" with notes "2:1:1", "Iodine" (form "Sea Kelp") with notes "organic sea
kelp". The matcher reads the note after the name and forms, only under the parent
the cleaner or a reviewer established, and only as a whole source_form_aliases
clue of that parent (scripts/GLOSSARY.md). Any other note changes nothing and is
never a held form; a disclosed form the reading dropped outranks the note.
"""
import ast
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'
BCAA = 'branched_chain_amino_acids'


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


@pytest.fixture(scope='module')
def iqm(enricher):
    return enricher.databases['ingredient_quality_map']


def _iodine_row(enricher, raw):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    rows = (enriched.get('ingredient_quality_data') or {}).get('ingredients') or []
    return next(row for row in rows if row.get('canonical_id') == 'iodine')


def test_an_iodine_row_whose_panel_note_names_kelp_reads_kelp_iodine(enricher):
    """Garden of Life 50 & Wiser Women (297614): Iodine 75 mcg, form "Sea Kelp",
    notes "organic sea kelp", a batch-11 kelp iodine clue. Without the note the
    row reads iodine's unspecified form, unheld."""
    raw = json.loads((FIXTURES / 'iodine_kelp_note_297614_raw.json').read_text())
    row = _iodine_row(enricher, raw)
    assert (row['matched_form'], row['bio_score'], row['form_source'], row['form_match_status']) == (
        'kelp iodine', 11.0, 'row_notes', 'mapped')

    silent = copy.deepcopy(raw)
    next(r for r in silent['ingredientRows'] if r['name'] == 'Iodine')['notes'] = ''
    row = _iodine_row(enricher, silent)
    assert (row['matched_form'], row['form_match_status']) == ('iodine (unspecified)', 'n/a')


@pytest.mark.parametrize('notes, established_parent', [
    ('organic sea kelp', BCAA),   # another parent's clue
    ('2:1:1 ratio', BCAA),        # not the whole clue
    ('2:1:1', None),              # no parent the cleaner or a reviewer established
])
def test_a_note_that_is_not_a_whole_clue_of_the_established_parent_changes_nothing(
        enricher, iqm, notes, established_parent):
    match = enricher._match_quality_map('BCAA', 'BCAA', iqm, cleaner_canonical_id=established_parent,
                                        row_notes=notes)
    assert match['form_id'] == 'branched chain amino acids (unspecified)'
    assert match.get('form_source') != 'row_notes'


def test_a_held_row_stays_held_whatever_its_note_says(enricher, iqm):
    match = enricher._match_quality_map('BCAA', 'BCAA', iqm, cleaned_forms=[{'name': 'Zorblaxate'}],
                                        cleaner_canonical_id=BCAA, row_notes='2:1:1')
    assert match['match_status'] == 'FORM_DISCLOSED_UNMAPPED'


def test_a_disclosed_form_the_reading_dropped_outranks_the_note(enricher, iqm):
    """Some match paths never consult the row's forms; the dropped-form check then
    holds the row. A note must not turn that row into a mapped reading."""
    unspecified = enricher._match_quality_map('Iodine', 'Iodine', iqm, cleaner_canonical_id='iodine')
    dropped = [{'name': 'Potassium Iodide'}]
    assert enricher._dropped_label_forms('Iodine', 'iodine', dropped) == ['Potassium Iodide']

    kept = enricher._read_form_in_row_notes(unspecified, 'organic sea kelp', iqm, 'Iodine', dropped, 'iodine')
    read = enricher._read_form_in_row_notes(unspecified, 'organic sea kelp', iqm, 'Iodine', [], 'iodine')
    assert (kept['form_id'], read['form_id']) == ('iodine (unspecified)', 'kelp iodine')


def test_every_matcher_call_that_reads_a_rows_forms_also_reads_its_panel_note():
    """One reading per row: a caller that passed a row's forms but not its notes
    would read the same row a second way. Calls inside the matcher itself are
    re-reads whose result returns through the outer call, which reads the note."""
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'enrich_supplements_v3.py').read_text())
    inside_matcher = {id(inner) for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name in ('_match_quality_map', '_match_quality_map_impl')
                      for inner in ast.walk(node)}
    row_calls = [call for call in ast.walk(tree)
                 if isinstance(call, ast.Call) and getattr(call.func, 'attr', None) == '_match_quality_map'
                 and id(call) not in inside_matcher
                 and 'cleaned_forms' in {kw.arg for kw in call.keywords}]
    notes = {id(call): next((kw.value for kw in call.keywords if kw.arg == 'row_notes'), None)
             for call in row_calls}

    assert len(row_calls) >= 7
    assert [call.lineno for call in row_calls
            if notes[id(call)] is None
            or (isinstance(notes[id(call)], ast.Constant) and notes[id(call)].value is None)] == []
