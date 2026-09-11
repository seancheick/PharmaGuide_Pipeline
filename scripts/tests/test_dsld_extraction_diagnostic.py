"""The real image experiment must not become a second qualification route."""
import hashlib
import io
import json

import pytest
from PIL import Image

from diagnose_dsld_extraction import run_diagnostic, selected_images
from submission_review.extraction.adapters.fake_adapter import FakeAdapter
from submission_review.extraction.extractor import ExtractionConfig, LabelDraftExtractor


def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    buffer = io.BytesIO()
    Image.new("RGB", (80, 100), (200, 100, 10)).save(buffer, format="WEBP")
    data = buffer.getvalue()
    (root / "7.webp").write_bytes(data)
    (root / "unselected.webp").write_bytes(b"not selected")
    payload = {"schema_version": "dsld_image_diagnostic_v1", "products": [{
        "dsld_id": "7", "path": "7.webp", "status": "ok",
        "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
    }]}
    manifest = root / "diagnostic_manifest.json"
    manifest.write_text(json.dumps(payload))
    return manifest, payload


@pytest.mark.parametrize("path", ["../outside.webp", "/tmp/outside.webp"])
def test_manifest_path_cannot_escape(tmp_path, path):
    manifest, payload = source(tmp_path)
    payload["products"][0]["path"] = path
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        selected_images(manifest)


def test_changed_image_refused_before_any_output(tmp_path):
    manifest, _ = source(tmp_path)
    (manifest.parent / "7.webp").write_bytes(b"changed")
    output = tmp_path / "experiment"
    with pytest.raises(ValueError, match="differs"):
        run_diagnostic(manifest, output, tmp_path, tmp_path, None, None)
    assert not output.exists()


def test_duplicate_selection_refused(tmp_path):
    manifest, payload = source(tmp_path)
    payload["products"].append(payload["products"][0])
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicate"):
        selected_images(manifest)


def test_invalid_limit_does_not_create_output(tmp_path):
    manifest, _ = source(tmp_path)
    output = tmp_path / "experiment"
    with pytest.raises(ValueError, match="positive"):
        run_diagnostic(manifest, output, tmp_path, tmp_path, None, None, limit=0)
    assert not output.exists()


def test_cloud_enabled_daemon_refused_before_reading_photos(tmp_path, monkeypatch):
    import sys
    from diagnose_dsld_extraction import main
    from submission_review.extraction import bounded_http

    output = tmp_path / "experiment"
    monkeypatch.setattr(sys, "argv", ["diagnose", "--manifest", "missing.json",
        "--output", str(output), "--raw-root", str(tmp_path), "--provider", "ollama",
        "--model", "local-model", "--model-digest", "a" * 64])
    monkeypatch.setattr(bounded_http, "request", lambda *a, **kw:
        bounded_http.Response(200, b'{"cloud":{"disabled":false}}'))
    with pytest.raises(SystemExit) as raised:
        main()
    assert raised.value.code == 2
    assert not output.exists()


def test_experiment_preserves_only_selected_bytes_and_uses_real_boundary(tmp_path):
    manifest, payload = source(tmp_path)
    original = manifest.read_bytes()
    raw_root = tmp_path / "raw"
    (raw_root / "brand").mkdir(parents=True)
    raw = b'{"id": 7, "fullName": "Example"}'
    (raw_root / "brand" / "7.json").write_bytes(raw)
    config = ExtractionConfig(provider="fake", model="fake-1", model_digest="c" * 64,
                              prompt_version="p1", retention_policy_version="local-only-v1")
    output = tmp_path / "experiment"
    result = run_diagnostic(manifest, output, tmp_path / "blobs", raw_root,
                            LabelDraftExtractor(FakeAdapter()), config)
    assert result["qualification"] is False
    assert result["products"] == 1
    assert result["results"][0]["reference_status"] == "unavailable"
    assert (output / "raw" / "7.json").read_bytes() == raw
    assert list((output / "images").iterdir()) == [output / "images" / "7.webp"]
    assert hashlib.sha256((output / "images" / "7.webp").read_bytes()).hexdigest() == payload["products"][0]["sha256"]
    assert (output / "runs" / "7.draft.json").exists()
    assert (output / "runs" / "7-input-0.jpg").exists()
    assert not (output / "gold").exists()
    assert manifest.read_bytes() == original
    with pytest.raises(FileExistsError):
        run_diagnostic(manifest, output, tmp_path, raw_root,
                        LabelDraftExtractor(FakeAdapter()), config)


def test_ocr_invalid_draft_is_model_failure_not_provider_outage(tmp_path):
    from submission_review.extraction.adapters.ocr_adapter import OcrLabelAdapter, OcrLine, OcrPage, RULES_VERSION

    class Reader:
        def read(self, data, *, photo_id, input_id):
            return OcrPage(photo_id, input_id, (
                OcrLine("Supplement Facts", 0, 0, 260, 20),
                OcrLine("A" * 2001, 0, 40, 100, 60),
                OcrLine("10 mg", 200, 40, 260, 60),
            ))

    manifest, _ = source(tmp_path)
    config = ExtractionConfig(provider="ocr", model="fixture", model_digest="a" * 64,
                              prompt_version=RULES_VERSION, retention_policy_version="local-only-v1")
    result = run_diagnostic(manifest, tmp_path / "experiment", tmp_path, tmp_path,
                            LabelDraftExtractor(OcrLabelAdapter(Reader())), config)
    assert result["results"][0]["failure"]["code"] == "model_failure"
    assert "AAAA" not in json.dumps(result)


def test_single_label_close_up_is_recorded_through_the_existing_diagnostic(tmp_path):
    manifest, _ = source(tmp_path)
    config = ExtractionConfig(provider='fake', model='fake-1', model_digest='c' * 64,
                              prompt_version='p1', retention_policy_version='local-only-v1')
    output = tmp_path / 'experiment'
    crop = {'x': .5, 'y': 0, 'w': .5, 'h': 1}
    result = run_diagnostic(manifest, output, tmp_path, tmp_path,
                            LabelDraftExtractor(FakeAdapter()), config, crop_region=crop)
    assert result['results'][0]['sent_inputs'][0]['crop'] == crop
    assert json.loads((output / 'configuration.json').read_text())['crop_region'] == crop
    with Image.open(output / 'runs' / '7-input-0.jpg') as image:
        assert image.size == (40, 100)


def test_close_up_diagnostic_refuses_ambiguous_multiple_labels_before_creating_output(tmp_path):
    manifest, payload = source(tmp_path)
    payload['products'].append({**payload['products'][0], 'dsld_id': '8'})
    manifest.write_text(json.dumps(payload))
    output = tmp_path / 'experiment'
    with pytest.raises(ValueError, match='one selected product'):
        run_diagnostic(manifest, output, tmp_path, tmp_path, None, None,
                       crop_region={'x': .5, 'y': 0, 'w': .5, 'h': 1})
    assert not output.exists()
