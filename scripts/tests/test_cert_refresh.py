"""Candidate refresh preserves failed snapshots and reviewed record identities."""
import copy
from pathlib import Path

import pytest
from api_audit import verify_certifications as vc


def record(name="Magnesium", rid="OLD", listing="123"):
    return {"record_id": rid, "program": "NSF Sport", "brand": "Brand", "product": name,
            "scope": "sku", "verified_at": "2026-09-01", "listing_id": listing,
            "source_url": "https://example.org/product?id=" + listing, "lot_numbers_tested": ["old"]}


def baseline():
    return {"_metadata": {"registry_sources": [{"program": "NSF Sport", "url": "old", "snapshot_date": "2026-09-01"}]},
            "verified_records": [record()]}


def source(rows):
    return {"program": "NSF Sport", "url": "https://example.org", "snapshot_date": "2026-09-01", "records": rows}


def test_refresh_preserves_id_for_listing_rename_and_lot_update():
    updated = record("Renamed magnesium", "NEW")
    updated.update(lot_numbers_tested=["new"])
    candidate, report = vc.build_refresh_candidate(baseline(), [source([updated])], [], [])
    assert candidate["verified_records"][0]["record_id"] == "OLD"
    assert report["programs"][0]["removed"] == []
    assert report["programs"][0]["changed"] == ["OLD"]


@pytest.mark.parametrize("rows", [[], [record(rid="DUP"), record(rid="DUP")], [dict(record(), brand="")]])
def test_malformed_or_empty_snapshot_keeps_old_dates(rows):
    old = baseline()
    candidate, report = vc.build_refresh_candidate(old, [source(rows)], [], [])
    assert candidate["verified_records"] == old["verified_records"]
    assert candidate["_metadata"]["registry_sources"][0]["snapshot_date"] == "2026-09-01"
    assert report["programs"][0]["status"] == "failed_preserved"


def test_failed_source_preserved_while_other_source_updates():
    old = baseline()
    candidate, report = vc.build_refresh_candidate(old, [], [{"program": "NSF Sport", "error": "403"}], [])
    assert candidate["verified_records"] == old["verified_records"]
    assert report["programs"][0]["status"] == "failed_preserved"


def test_removed_override_reference_reported_for_review():
    candidate, report = vc.build_refresh_candidate(baseline(), [source([record(rid="NEW", listing="456")])], [],
                                                    [{"record_id": "OLD", "status": "verified"}])
    assert report["programs"][0]["removed"] == ["OLD"]
    assert report["missing_override_references"] == ["OLD"]
    assert report["review_required"]


def test_refresh_does_not_mutate_baseline():
    old = baseline()
    frozen = copy.deepcopy(old)
    vc.build_refresh_candidate(old, [source([record("Updated", "NEW")])], [], [])
    assert old == frozen


def test_facility_snapshot_retains_audit_scope_without_product_credit():
    row = dict(record(), program="NSF/ANSI 455", product="", scope="facility", company_id="C123")
    src = dict(source([row]), program="NSF/ANSI 455")
    candidate, report = vc.build_refresh_candidate(baseline(), [src], [], [])
    assert report["programs"][0]["status"] == "candidate_complete"
    meta = next(s for s in candidate["_metadata"]["registry_sources"] if s["program"] == "NSF/ANSI 455")
    assert meta["audit_scope"] == "gmp_facility"
    assert candidate["verified_records"][-1]["scope"] == "facility"


def test_untouched_source_preserved_when_another_source_refreshes():
    row = dict(record(), program="USP Verified", record_id="USP_NEW")
    candidate, report = vc.build_refresh_candidate(baseline(), [dict(source([row]), program="USP Verified")], [], [])
    assert candidate["verified_records"][0] == baseline()["verified_records"][0]


def test_response_receipt_retains_http_failure_bytes(tmp_path, monkeypatch):
    import requests
    response = requests.Response()
    response.url, response.status_code, response._content = "https://example.org", 403, b"blocked"
    monkeypatch.setattr(vc, "_RECEIPT_DIR", tmp_path)
    monkeypatch.setattr(vc, "_RECEIPTS", [])
    vc._capture_response(response)
    assert vc._RECEIPTS[0]["status"] == 403
    assert Path(vc._RECEIPTS[0]["path"]).read_bytes() == b"blocked"


def test_nsf_uses_current_official_directory_and_declared_brand(monkeypatch):
    class Response:
        text = '''<a href="/certified-products/listing-detail.php?id=123"><p class="results__product-name">Magnesium</p><p class="results__company-name">Declared Brand</p><img src="https://example.org/A/Wrong%20Brand/Line/123/Product.png"></a>'''
        def raise_for_status(self):
            pass
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        return Response()
    monkeypatch.setattr(vc.requests, "get", get)
    rows, _ = vc.fetch_nsf_sport_live()
    assert urls[0].startswith("https://www.nsfsport.com/")
    assert rows[0]["brand"] == "Declared Brand"
    assert rows[0]["source_url"] == "https://www.nsfsport.com/certified-products/listing-detail.php?id=123"


@pytest.mark.parametrize("program", ["IKOS", "IAOS", "IPRO"])
def test_additional_nutrasource_adapters_are_program_specific(program):
    payload = {"success": True, "totalCount": 1, "list": [
        {"ProductNum": "X123", "ProductName": "Supplement", "Is" + program.capitalize(): True},
        {"ProductNum": "WRONG", "ProductName": "Other", "IsIfos": True}]}
    rows, count = vc.parse_nutrasource_products_payload(payload, program=program)
    assert [r["product_num"] for r in rows] == ["X123"]
    assert count == 1
    detail = vc.parse_nutrasource_product_detail_page(f'<title>Supplement | Brand | Certifications by Nutrasource</title><h2 class="h2--lg">{program}&trade; Testing Results</h2>', "X123")
    assert detail["certifications"] == [program]


@pytest.mark.parametrize("payload", [{"success": False, "list": []}, {"success": True, "list": "broken"}])
def test_nutrasource_rejects_failed_or_malformed_payload(payload):
    with pytest.raises(ValueError):
        vc.parse_nutrasource_products_payload(payload)


def test_cli_stages_candidate_without_touching_live_registry(tmp_path, monkeypatch):
    import json
    import sys
    registry = tmp_path / "live" / "cert_registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(baseline()))
    overrides_dir = tmp_path / "scripts" / "data" / "curated_overrides"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "cert_verification_overrides.json").write_text('{"overrides": []}')
    monkeypatch.setattr(vc, "REGISTRY_PATH", registry)
    monkeypatch.setattr(vc, "SCRIPTS_ROOT", tmp_path / "scripts")
    monkeypatch.setattr(vc, "fetch_nsf_sport_live", lambda **kwargs: ([record()], "2026-09-01"))
    out = tmp_path / "candidate"
    before = registry.read_bytes()
    monkeypatch.setattr(sys, "argv", ["verify_certifications", "--source", "live-nsf-sport", "--output-dir", str(out)])
    vc.main()
    assert registry.read_bytes() == before
    assert (out / "cert_registry.candidate.json").exists()
    assert json.loads((out / "refresh_report.json").read_text())["review_required"]
    assert json.loads((out / "source_snapshots.json").read_text())[0]["program"] == "NSF Sport"


@pytest.mark.parametrize("program", ["IKOS", "IAOS", "IPRO"])
def test_cli_additional_programs_never_enter_production_candidate(tmp_path, monkeypatch, program):
    import json
    import sys
    registry = tmp_path / "live" / "cert_registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(baseline()))
    overrides_dir = tmp_path / "scripts" / "data" / "curated_overrides"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "cert_verification_overrides.json").write_text('{"overrides": []}')
    monkeypatch.setattr(vc, "REGISTRY_PATH", registry)
    monkeypatch.setattr(vc, "SCRIPTS_ROOT", tmp_path / "scripts")
    monkeypatch.setattr(vc, "fetch_ifos_live", lambda **kwargs: ([dict(record(), program=program)], "2026-09-01"))
    out = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", ["verify_certifications", "--source", "live-" + program.lower(), "--output-dir", str(out)])
    vc.main()
    candidate = json.loads((out / "cert_registry.candidate.json").read_text())
    assert candidate == baseline()
    assert json.loads((out / "refresh_report.json").read_text())["pending_policy_programs"] == [program]
    assert (out / "additional_programs.pending_policy.json").exists()


def test_smoke_limit_cannot_write_candidate(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(sys, "argv", ["verify_certifications", "--source", "all", "--max-pages", "1", "--output-dir", str(tmp_path / "output")])
    with pytest.raises(SystemExit):
        vc.main()
    assert not (tmp_path / "output").exists()


def test_ifos_truncated_pagination_rejected(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"success": True, "totalCount": 2, "list": []}
    monkeypatch.setattr(vc.requests, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="Incomplete IFOS pagination"):
        vc.fetch_ifos_live()


def test_shared_company_id_does_not_collapse_different_facilities_or_products():
    one = dict(record(), program="NSF/ANSI 455", product="", scope="facility", company_id="C123", listing_id=None)
    two = dict(one, record_id="OTHER", brand="Other Division")
    candidate, report = vc.build_refresh_candidate(baseline(), [dict(source([one, two]), program="NSF/ANSI 455")], [], [])
    assert report["programs"][0]["status"] == "candidate_complete"
    assert len([r for r in candidate["verified_records"] if r["program"] == "NSF/ANSI 455"]) == 2


def test_ifos_required_detail_failure_is_not_a_partial_success(monkeypatch):
    import requests
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"success": True, "totalCount": 1, "list": [{"ProductNum": "X1", "ProductName": "Oil", "IsIfos": True}]}
    def get(url, **kwargs):
        if "product?id=" in url:
            raise requests.HTTPError("detail unavailable")
        return Response()
    monkeypatch.setattr(vc.requests, "get", get)
    with pytest.raises(ValueError, match="required detail failed"):
        vc.fetch_ifos_live()


def test_cli_baseline_change_withholds_candidate(tmp_path, monkeypatch):
    import json
    import sys
    registry = tmp_path / "live" / "cert_registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(baseline()))
    overrides_dir = tmp_path / "scripts" / "data" / "curated_overrides"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "cert_verification_overrides.json").write_text('{"overrides": []}')
    monkeypatch.setattr(vc, "REGISTRY_PATH", registry)
    monkeypatch.setattr(vc, "SCRIPTS_ROOT", tmp_path / "scripts")
    def fetch(**kwargs):
        registry.write_text(json.dumps(dict(baseline(), concurrent_update=True)))
        return [record()], "2026-09-01"
    monkeypatch.setattr(vc, "fetch_nsf_sport_live", fetch)
    out = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", ["verify_certifications", "--source", "live-nsf-sport", "--output-dir", str(out)])
    with pytest.raises(SystemExit, match="changed during retrieval"):
        vc.main()
    assert not (out / "cert_registry.candidate.json").exists()
    assert json.loads((out / "baseline_registry.json").read_text()) == baseline()


def test_ifos_keeps_distinct_authoritative_ids_with_similar_strength_names(monkeypatch):
    class Response:
        def __init__(self, url):
            self.url = url
            self.text = ('<title>Fish Oil ' + ('1000' if url.endswith('X1') else '2000') + ' mg | Brand | Certifications by Nutrasource</title><h2 class="h2--lg">IFOS Testing Results</h2>')
        def raise_for_status(self):
            pass
        def json(self):
            return {"success": True, "totalCount": 2, "list": [
                {"ProductNum": "X1", "ProductName": "Fish Oil 1000 mg", "IsIfos": True},
                {"ProductNum": "X2", "ProductName": "Fish Oil 2000 mg", "IsIfos": True}]}
    monkeypatch.setattr(vc.requests, "get", lambda url, **kwargs: Response(url))
    monkeypatch.setattr(vc.time, "sleep", lambda seconds: None)
    rows, _ = vc.fetch_ifos_live()
    assert [r["product_num"] for r in rows] == ["X1", "X2"]


def test_informed_keeps_different_strengths_and_forms(monkeypatch):
    class Response:
        text = '''<div class="grid-3-column-product-list"><div class="grid-item-wrapper"><h3><h4 class="small-bottom-margin">Brand</h4></h3><div class="views-field views-field-title"><span class="field-content">Vitamin D 1000 IU Capsules</span></div><div class="views-field views-field-title"><span class="field-content">Vitamin D 2000 IU Gummies</span></div></div></div>'''
        def raise_for_status(self): pass
    monkeypatch.setattr(vc.requests, "get", lambda *args, **kwargs: Response())
    rows, _ = vc.fetch_informed_live("Informed Sport")
    assert len(rows) == 2
    assert len({r["record_id"] for r in rows}) == 2


def test_nsf173_preserves_distinct_forms_and_aggregates_duplicate_rows(monkeypatch):
    class Response:
        text = '''<font size="+2">Brand</font><table><tr><td>Trade Designation</td><td>Product ID</td><td>Product Form</td><td>Daily Serving Size</td></tr><tr><td>Magnesium</td><td>All</td><td>Tablet</td><td>1 tablet</td></tr><tr><td>Magnesium</td><td>All</td><td>Tablets</td><td>1 tablet</td></tr><tr><td>Magnesium</td><td>All</td><td>Capsule</td><td>1 capsule</td></tr></table>'''
        def raise_for_status(self): pass
    monkeypatch.setattr(vc.requests, "get", lambda *args, **kwargs: Response())
    rows, _ = vc.fetch_nsf_173_live()
    assert len(rows) == 2
    assert len({r["record_id"] for r in rows}) == 2
    assert {r["product_form"] for r in rows} == {"Tablet", "Capsule"}
    assert sum(len(r["source_listing_rows"]) for r in rows) == 3


def test_nsf173_unique_legacy_id_survives_equivalent_plural_rows():
    old = dict(record(), program="NSF Certified", product_form="Tablet", listing_id=None)
    old_plural = dict(old, product_form="Tablets")
    incoming = dict(old, record_id="GENERATED", product_id="All", source_listing_rows=[{"product_form": "Tablet"}, {"product_form": "Tablets"}])
    previous = {"_metadata": {"registry_sources": []}, "verified_records": [old, old_plural]}
    candidate, report = vc.build_refresh_candidate(previous, [dict(source([incoming]), program="NSF Certified")], [], [])
    assert candidate["verified_records"][0]["record_id"] == "OLD"
    assert report["programs"][0]["split_previous_record_ids"] == []


def test_nsf173_ambiguous_legacy_id_splits_without_auto_rebinding_override():
    tablet = dict(record(), program="NSF Certified", product_form="Tablet", listing_id=None)
    capsule = dict(tablet, product_form="Capsule")
    incoming = [dict(tablet, record_id="TABLET", product_id="All"), dict(capsule, record_id="CAPSULE", product_id="All")]
    previous = {"_metadata": {"registry_sources": []}, "verified_records": [tablet, capsule]}
    candidate, report = vc.build_refresh_candidate(previous, [dict(source(incoming), program="NSF Certified")], [], [{"record_id": "OLD", "status": "verified"}])
    assert {r["record_id"] for r in candidate["verified_records"]} == {"TABLET", "CAPSULE"}
    assert report["programs"][0]["split_previous_record_ids"] == ["OLD"]
    assert report["new_missing_override_references"] == ["OLD"]


def test_list_only_refresh_cannot_erase_existing_lot_evidence():
    old = baseline()
    incoming = record(rid='NEW')
    incoming['lot_numbers_tested'] = []
    candidate, report = vc.build_refresh_candidate(old, [source([incoming])], [], [])
    assert report['programs'][0]['status'] == 'failed_preserved'
    assert candidate['verified_records'] == old['verified_records']
    assert candidate['_metadata']['registry_sources'] == old['_metadata']['registry_sources']


@pytest.mark.parametrize('html', ['<html>Login</html>', '<table><tr><th>Error</th><td>Unavailable</td></tr></table>'])
def test_required_nsf_detail_rejects_unrecognized_success_response(html, monkeypatch):
    import requests
    response = requests.Response()
    response.status_code, response._content = 200, html.encode()
    response.url = 'https://www.nsfsport.com/certified-products/listing-detail.php?id=123'
    monkeypatch.setattr(vc.requests, 'get', lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match='Unrecognized NSF Sport detail'):
        vc._fetch_nsf_sport_detail('123')


def test_nsf_source_with_unparsed_listing_is_not_complete(monkeypatch):
    import requests
    response = requests.Response()
    response.status_code = 200
    response._content = b'''<a href="listing-detail.php?id=1"><span class="results__product-name">Product</span><span class="results__company-name">Brand</span></a><a href="listing-detail.php?id=2"><span class="changed-name-hook">Lost product</span></a>'''
    response.url = vc.NSF_SPORT_SEARCH_URL
    monkeypatch.setattr(vc.requests, 'get', lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match='Missing NSF Sport product identity'):
        vc.fetch_nsf_sport_live()
