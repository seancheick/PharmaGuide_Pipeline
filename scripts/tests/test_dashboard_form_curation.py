"""The dashboard reads the latest enrichment run and renders the form
curation queue it writes (reports/runs/<run_id>/form_fallback_audit_report.json).
Before, it globbed only flat reports/*.json, so it showed July reports, and it
loaded the form queue without ever rendering it."""
import json
import os

from scripts.dashboard.data_loader import _latest_report_dir
from scripts.dashboard.views.quality import build_form_curation_rows, build_parent_fallback_rows


def _write(path, payload, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    os.utime(path, (mtime, mtime))


def test_the_newest_run_directory_wins_over_stale_flat_reports(tmp_path):
    reports = tmp_path / 'reports'
    _write(reports / 'form_fallback_audit_report.json', {'form_fallbacks': []}, 1_000)
    _write(reports / 'runs' / 'old' / 'form_fallback_audit_report.json', {}, 2_000)
    _write(reports / 'runs' / 'new' / 'form_fallback_audit_report.json', {}, 3_000)
    _write(reports / 'runs' / 'new' / 'parent_fallback_report.json', {}, 3_000)
    assert _latest_report_dir(reports) == reports / 'runs' / 'new'


def test_flat_reports_still_load_when_no_run_directory_exists(tmp_path):
    reports = tmp_path / 'reports'
    _write(reports / 'enrichment_summary.json', {}, 1_000)
    assert _latest_report_dir(reports) == reports


def test_form_curation_rows_merge_datasets_and_rank_by_held_products():
    def entry(token, ids, brands, occurrences):
        return {'gap_type': 'disclosed_form_unmapped', 'canonical_id': 'calcium', 'parent_name': 'Calcium',
                'unmapped_form_text': token, 'occurrence_count': occurrences, 'dsld_ids': ids,
                'brands': brands, 'examples': [{'dsld_id': ids[0], 'raw_source_text': f'Calcium ({token})'}]}
    reports = {
        'A enriched': {'form_fallbacks': [entry('Calcium Zqxate', ['1', '2'], ['Acme'], 3),
                                          entry('Calcium Qqxate', ['9'], ['Acme'], 9)]},
        'B enriched': {'form_fallbacks': [entry('calcium zqxate', ['2', '3'], ['Brandy'], 2)]},
    }
    rows = build_form_curation_rows(reports)
    assert [(r['unmapped_form'], r['held_products'], r['occurrences']) for r in rows] == [
        ('Calcium Zqxate', 3, 5), ('Calcium Qqxate', 1, 9)]
    top = rows[0]
    assert (top['brands'], top['datasets'], top['dsld_ids']) == ('Acme, Brandy', 'A enriched, B enriched', '1, 2, 3')
    assert top['example'] == '1: Calcium (Calcium Zqxate)'


def test_pipeline_losses_stay_a_separate_row_from_unmapped_forms():
    reports = {'A': {'form_fallbacks': [
        {'gap_type': 'disclosed_form_unmapped', 'canonical_id': 'vitamin_c', 'unmapped_form_text': 'X',
         'occurrence_count': 1, 'dsld_ids': ['1']},
        {'gap_type': 'pipeline_form_loss', 'canonical_id': 'vitamin_c', 'unmapped_form_text': 'X',
         'occurrence_count': 1, 'dsld_ids': ['2']},
    ]}}
    assert sorted(r['gap_type'] for r in build_form_curation_rows(reports)) == [
        'disclosed_form_unmapped', 'pipeline_form_loss']


def test_parent_fallback_rows_rank_undisclosed_forms_by_occurrence():
    reports = {'A': {'fallbacks': [
        {'ingredient_raw': 'Boron', 'ingredient_normalized': 'boron', 'canonical_id': 'boron',
         'fallback_form_name': 'boron (unspecified)', 'occurrence_count': 2},
        {'ingredient_raw': 'Zinc', 'ingredient_normalized': 'zinc', 'canonical_id': 'zinc',
         'fallback_form_name': 'zinc (unspecified)', 'occurrence_count': 7},
    ]}}
    assert [(r['canonical_id'], r['occurrences']) for r in build_parent_fallback_rows(reports)] == [
        ('zinc', 7), ('boron', 2)]
