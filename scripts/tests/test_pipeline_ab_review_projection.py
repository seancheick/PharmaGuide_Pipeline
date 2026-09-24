"""The production A/B harness records route, live eligibility, Dose exposure
provenance and every ingredient identity, and its comparator reports each kind
of change (scripts/audits/quarantine_triage_20260919)."""
import importlib.util
import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1] / 'audits' / 'quarantine_triage_20260919'


def _load(name):
    spec = importlib.util.spec_from_file_location(name, AUDIT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drive = _load('drive_pipeline_ab')
compare = _load('compare_scored_arms')


def _scored(module='fiber_digestive', eligible=True, missing=(), exposure=1.0):
    return {
        'dsld_id': '1', '_v4_module': module, 'route_decision': {'module': module},
        '_v4_completeness_gate': {'is_live_eligible': eligible, 'missing_fields': list(missing), 'soft_missing': []},
        '_v4_module_breakdown': {'dimensions': {'dose': {'metadata': {'benchmark_exposures': [
            {'basis': 'daily', 'unit': 'g', 'benchmark_amount': exposure, 'quantity_operator': '=',
             'uncertainty': None, 'frequency_defaulted': False, 'source_path': 'ingredientRows[1]', 'extra': 'dropped'}]}}}},
    }


def test_review_projection_keeps_route_eligibility_and_exposure():
    projection = drive.review_projection(_scored(missing=['unresolved_source_quantity'], eligible=False))
    assert projection['module'] == projection['route'] == 'fiber_digestive'
    assert projection['is_live_eligible'] is False
    assert projection['missing_fields'] == ['unresolved_source_quantity']
    assert projection['exposures'][0]['benchmark_amount'] == 1.0
    assert 'extra' not in projection['exposures'][0]


def test_identity_projection_includes_nested_display_rows():
    product = {'ingredient_quality_data': {'ingredients': [
        {'raw_source_path': 'ingredientRows[2].nestedRows[0]', 'name': 'Oat Bran', 'canonical_id': 'oat_bran',
         'identity_disposition': 'clean', 'scoreable_identity': False, 'cleaner_row_role': 'nested_display_only'}]}}
    assert drive.identity_projection(product) == [
        ['ingredientRows[2].nestedRows[0]', 'Oat Bran', 'oat_bran', 'clean', None, False, None]]


def test_comparator_reports_each_kind_of_change():
    left = {'_review': drive.review_projection(_scored()),
            '_identities': [['p', 'Oat Bran', 'oat_generic', 'repaired', 'oat_bran', False, None]]}
    right = {'_review': drive.review_projection(_scored(module='generic', eligible=False, missing=['x'], exposure=2.0)),
             '_identities': [['p', 'Oat Bran', 'oat_bran', 'clean', None, False, None]]}
    changes = compare.review_changes(left, right)
    assert set(changes) == {'route', 'eligibility', 'exposure', 'identity'}
    assert changes['identity'] == {'only_before': [['p', 'Oat Bran', 'oat_generic', 'repaired']],
                                   'only_after': [['p', 'Oat Bran', 'oat_bran', 'clean']]}
    assert compare.review_changes(left, left) == {}


def test_duplicate_source_rows_cannot_hide_an_identity_change():
    # Two rows share a source path and name; only one of them moves.
    row = lambda cid: ['p', 'Fiber', cid, 'clean', None, False, None]
    left = {'_identities': [row('fiber'), row('fiber')]}
    right = {'_identities': [row('fiber'), row('psyllium')]}
    assert compare.review_changes(left, right)['identity'] == {
        'only_before': [['p', 'Fiber', 'fiber', 'clean']], 'only_after': [['p', 'Fiber', 'psyllium', 'clean']]}


def test_soft_missing_and_disposition_are_eligibility_changes():
    left = {'_review': drive.review_projection(_scored())}
    right = {'_review': dict(drive.review_projection(_scored()), soft_missing=['x'], catalog_disposition='held')}
    assert set(compare.review_changes(left, right)) == {'eligibility'}


def test_semantic_changes_never_land_in_bookkeeping(tmp_path, monkeypatch):
    base = {'dsld_id': '1', 'quality_score_v4_100': 50.0, '_review': drive.review_projection(_scored()),
            '_identities': [['p', 'Oat Bran', 'oat_generic', 'repaired', 'oat_bran', False, None]]}
    moved = dict(base, _review=drive.review_projection(_scored(module='generic')),
                 _identities=[['p', 'Oat Bran', 'oat_bran', 'clean', None, False, None]])
    before, after, out = tmp_path / 'b.jsonl', tmp_path / 'a.jsonl', tmp_path / 'diff.json'
    before.write_text(json.dumps(base) + '\n')
    after.write_text(json.dumps(moved) + '\n')
    import sys
    monkeypatch.setattr(sys, 'argv', ['x', '--before', str(before), '--after', str(after), '--out', str(out)])
    compare.main()
    report = json.loads(out.read_text())
    assert report['summary']['route_changes'] == report['summary']['identity_changes'] == 1
    assert report['bookkeeping_only_changes'] == []


def test_collect_writes_the_projections(tmp_path):
    batch = tmp_path / 'scored.json'
    batch.write_text(json.dumps([_scored()]))
    out = tmp_path / 'records.jsonl'
    drive.collect([batch], out, {'1': [['p', 'Oat Bran', 'oat_bran', 'clean', None, False, None]]})
    record = json.loads(out.read_text())
    assert record['_review']['route'] == 'fiber_digestive'
    assert record['_identities'][0][2] == 'oat_bran'


def test_projection_on_a_real_label():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'oat_bran_293400_raw.json').read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    projection = drive.review_projection(build_scored_artifact(enriched))
    assert projection['route'] == 'fiber_digestive' and projection['is_live_eligible'] is True
    assert projection['exposures'] and projection['exposures'][0]['basis'] == 'daily'
    assert ['Oat Bran', 'oat_bran'] in [row[1:3] for row in drive.identity_projection(enriched)]
