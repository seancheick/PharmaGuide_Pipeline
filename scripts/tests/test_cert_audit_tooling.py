from __future__ import annotations

import sys


def test_cert_provenance_audit_uses_dynamic_registry_coverage() -> None:
    from scripts.api_audit import cert_claim_provenance_audit as audit

    summary = audit.summarize(
        [
            {
                "dsld_id": "1",
                "brand_name": "Example",
                "product_name": "Example Product",
                "provenance": {
                    "label_certifications": ["USP"],
                    "manufacturer_evidence": [],
                    "either_or_unknown": [],
                },
            }
        ],
        covered_programs={"USP Verified"},
    )

    assert summary["products_with_any_unsupported_program"] == 0
    assert summary["by_program"][0]["program"] == "USP Verified"
    assert summary["by_program"][0]["covered_by_live_registry"] is True


def test_cert_label_registry_audit_passes_dsld_id_to_resolver(monkeypatch, tmp_path) -> None:
    from scripts.api_audit import cert_label_registry_audit as audit

    class FakeRegistry:
        metadata = {"registry_sources": [{"program": "USP Verified"}]}
        records_by_program = {"USP Verified": [{"program": "USP Verified"}]}

    class FakeResolution:
        def to_dict(self) -> dict:
            return {"program": "USP Verified", "scope": "sku"}

    seen_dsld_ids: list[str | None] = []

    def fake_resolve(*, brand, product, claimed_programs, registry, dsld_id=None):
        seen_dsld_ids.append(dsld_id)
        return [FakeResolution()]

    monkeypatch.setattr(audit.CertRegistry, "load", staticmethod(lambda **kwargs: FakeRegistry()))
    monkeypatch.setattr(
        audit,
        "load_catalog",
        lambda: [
            {
                "dsld_id": "12345",
                "brand_name": "Example",
                "product_name": "Example Product",
                "primary_category": "vitamin",
                "supplement_type": "vitamin",
                "verdict": "SAFE",
                "score_100_equivalent": 80.0,
            }
        ],
    )
    monkeypatch.setattr(
        audit,
        "load_blob",
        lambda _dsld_id: {
            "certification_detail": {
                "third_party_programs": {
                    "programs": [{"name": "USP Verified"}]
                }
            }
        },
    )
    monkeypatch.setattr(audit, "resolve", fake_resolve)
    monkeypatch.setattr(sys, "argv", ["cert_label_registry_audit.py", "--out-dir", str(tmp_path)])

    audit.main()

    assert seen_dsld_ids == ["12345"]


def test_cert_census_discovers_no_claim_held_product(monkeypatch, tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    import json
    from cert_resolver import CertRegistry, CertResolution
    directory = tmp_path / 'output_Example_enriched' / 'enriched'
    directory.mkdir(parents=True)
    product = {'dsld_id': '1', 'brandName': 'Example', 'fullName': 'Capsules',
               'form_factor_canonical': 'capsule', 'quality_score_status': 'not_scored'}
    (directory / 'enriched_cleaned_batch_1.json').write_text(json.dumps([product]))
    seen = []
    registry = CertRegistry(records_by_program={'USP Verified': []})
    def discover(brand, product, registry, dsld_id=None, *, label_context=None):
        seen.append((dsld_id, label_context))
        return [CertResolution(program='USP Verified', scope='sku', record_id='current', source_url='https://example.org', snapshot_date='2026-10-04', recency_status='fresh')]
    monkeypatch.setattr(audit, 'discover_verified_programs', discover)
    monkeypatch.setattr(audit, 'resolve', lambda *a, **kw: [])
    result = audit.census(tmp_path, registry)
    assert result['_metadata']['total_products_scanned'] == 1
    assert result['products'][0]['cause'] == 'verified_match'
    assert result['products'][0]['has_claim'] is False
    assert seen == [('1', {'form_factor_canonical': 'capsule', 'form_factor': None, 'netContents': None})]


def test_cert_census_accounts_for_malformed_and_clean_only(tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry
    import json
    directory = tmp_path / 'output_Example' / 'cleaned'
    directory.mkdir(parents=True)
    (directory / 'cleaned_batch_1.json').write_text(json.dumps([
        {'dsld_id': '2', 'brandName': 'Unknown', 'fullName': 'Product'}, None,
        {'dsld_id': '3', 'brandName': 'Unknown'}]))
    (directory / 'cleaned_batch_2.json').write_text('{broken')
    result = audit.census(tmp_path, CertRegistry())
    assert len(result['products']) == 3
    assert result['_metadata']['input_error_count'] == 3
    assert len(result['input_errors']) == 3
    assert result['_metadata']['complete'] is False


def test_cert_census_override_dangling_record(tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry
    registry = CertRegistry(overrides_by_brand_product={('example', 'product'): [
        {'status': 'verified', 'program': 'USP Verified', 'record_id': 'gone'}]})
    assert audit.audit_overrides(registry)[0]['cause'] == 'missing_registry_record'


def test_cert_census_duplicate_identity_cannot_silently_disappear(tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry
    import json
    directory = tmp_path / 'output_Example' / 'cleaned'
    directory.mkdir(parents=True)
    (directory / 'cleaned_batch_1.json').write_text(json.dumps([
        {'dsld_id': '2', 'brandName': 'Unknown', 'fullName': 'First'},
        {'dsld_id': '2', 'brandName': 'Unknown', 'fullName': 'Conflicting'}]))
    result = audit.census(tmp_path, CertRegistry())
    assert result['_metadata']['stage_duplicates'] == 1
    assert result['_metadata']['complete'] is False
    assert result['input_errors'][0]['error'] == 'duplicate label ID has conflicting identity'


def test_census_optimized_discovery_equals_production(tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry, discover_verified_programs, normalize_brand, normalize_product
    from datetime import datetime, timezone
    date = datetime.now(timezone.utc).date().isoformat()
    def record(identifier, product):
        return {'program': 'USP Verified', 'scope': 'sku', 'brand': 'Example',
                'product': product, 'record_id': identifier, 'source_url': 'https://example.org',
                'verified_at': date, '_snapshot_date': date, '_recency_status': 'fresh'}
    cases = [
        ('Magnesium 200 mg Capsules', [record('exact', 'Magnesium 200 mg Capsules')], False),
        ('Magnesium 200 mg Gummies', [record('form', 'Magnesium 200 mg Capsules')], False),
        ('Magnesium 200 mg Capsules', [record('dose', 'Magnesium 100 mg Capsules')], False),
        ('Vitamin D 1000 IU Capsules', [record('strengthless', 'Vitamin D Capsules')], False),
        ('Magnesium 200 mg Capsules', [record('reject', 'Magnesium 200 mg Capsules')], True),
        ('Magnesium Capsules', [record('a', 'Magnesium 100 mg Capsules'), record('b', 'Magnesium 200 mg Capsules')], False),
    ]
    observed_positive = False
    for title, records, rejected in cases:
        registry = CertRegistry(records_by_program={'USP Verified': records, 'NSF Sport': []})
        if rejected:
            registry.overrides_by_brand_product[(normalize_brand('Example'), normalize_product(title))] = [
                {'program': 'USP Verified', 'status': 'rejected', 'record_id': records[0]['record_id']}]
        product = {'dsld_id': '1', 'brandName': 'Example', 'fullName': title,
                   'form_factor_canonical': 'gummy' if 'Gummies' in title else 'capsule'}
        context = {key: product.get(key) for key in ('form_factor_canonical', 'form_factor', 'netContents')}
        expected = [row.to_dict() for row in discover_verified_programs('Example', title, registry, dsld_id='1', label_context=context)]
        result = audit._census_resolution(product, registry)
        assert result['discovered'] == expected
        observed_positive |= bool(expected)
    assert observed_positive


def test_census_cli_fails_after_writing_explicit_input_errors(monkeypatch, tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    import json
    import pytest
    products = tmp_path / 'products'
    products.mkdir()
    output = tmp_path / 'reports'
    monkeypatch.setattr(sys, 'argv', ['cert_label_registry_audit.py', '--products-root', str(products), '--out-dir', str(output)])
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 1
    receipt = json.loads((output / 'certification_census.json').read_text())
    assert receipt['_metadata']['complete'] is False
    assert receipt['input_errors'][0]['error'] == 'no product batches found'
    assert len(receipt['_metadata']['source_sha256']) == 4


def test_census_rejects_registry_changed_during_walk(monkeypatch, tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    import json
    import pytest
    registry = tmp_path / 'registry.json'
    overrides = tmp_path / 'overrides.json'
    registry.write_text('{}')
    overrides.write_text('{}')
    def changing_census(*args, **kwargs):
        registry.write_text('{"changed":true}')
        return {'_metadata': {'complete': True}, 'summary': {}, 'input_errors': []}
    monkeypatch.setattr(audit, 'census', changing_census)
    monkeypatch.setattr(sys, 'argv', ['audit', '--products-root', str(tmp_path), '--registry', str(registry),
                                    '--overrides', str(overrides), '--out-dir', str(tmp_path / 'out')])
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 1
    receipt = json.loads((tmp_path / 'out/certification_census.json').read_text())
    assert receipt['_metadata']['source_unchanged'] is False
    assert receipt['_metadata']['complete'] is False
    assert receipt['input_errors'] == [{'error': 'source or registry changed during census'}]


def test_override_audit_distinguishes_conflicts_from_disjoint_reviews():
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry
    import copy
    records = [
        {'record_id': 'a', 'brand': 'Example', 'product': 'Magnesium 100 mg Capsules', 'program': 'USP Verified', '_recency_status': 'fresh'},
        {'record_id': 'b', 'brand': 'Example', 'product': 'Magnesium 200 mg Capsules', 'program': 'USP Verified', '_recency_status': 'fresh'}]
    entries = [
        {'status': 'verified', 'program': 'USP Verified', 'brand': 'Example', 'product': 'Magnesium Capsules', 'matched_brand': 'Example', 'matched_product': r['product'], 'record_id': r['record_id']}
        for r in records]
    registry = CertRegistry(records_by_program={'USP Verified': records}, overrides_by_brand_product={('example', 'magnesium'): entries})
    assert any(issue['cause'] == 'conflicting_reviewed_overrides' for issue in audit.audit_overrides(registry))
    disjoint = copy.deepcopy(entries)
    disjoint[0]['dsld_id'] = '1'
    disjoint[1]['dsld_id'] = '2'
    registry.overrides_by_brand_product = {('example', 'magnesium'): disjoint}
    assert audit.audit_overrides(registry) == []
    for entry, record in zip(disjoint, records):
        entry.pop('dsld_id')
        entry['product'] = record['product']
    assert audit.audit_overrides(registry) == []
    registry.overrides_by_brand_product = {('example', 'magnesium'): [entries[0], {'program': 'USP Verified', 'status': 'rejected', 'record_id': 'b'}]}
    assert audit.audit_overrides(registry) == []


def test_exported_claim_audit_honors_candidate_inputs(monkeypatch, tmp_path):
    from scripts.api_audit import cert_label_registry_audit as audit
    from cert_resolver import CertRegistry
    seen = []
    def load(**kwargs):
        seen.append(kwargs)
        return CertRegistry()
    monkeypatch.setattr(audit.CertRegistry, 'load', staticmethod(load))
    monkeypatch.setattr(audit, 'load_catalog', lambda: [])
    monkeypatch.setattr(sys, 'argv', ['audit', '--registry', str(tmp_path / 'candidate.json'),
                                    '--overrides', str(tmp_path / 'reviews.json'), '--out-dir', str(tmp_path)])
    audit.main()
    assert seen == [{'registry_path': tmp_path / 'candidate.json', 'overrides_path': tmp_path / 'reviews.json'}]
