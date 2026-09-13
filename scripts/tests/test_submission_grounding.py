"""Locating a reading in the photograph it claims to come from.

Every field in a draft cites an image and quotes the text it was read out of,
and until now nothing checked the quote. This is the check, and its whole worth
is that it works on any producer: a vision model's claims can be tested against
a reader that cannot hallucinate.

The two failure modes that matter are opposite. A verifier that misses an
invented dose is worse than none, because it lends false assurance. One that
reports honest readings as ungrounded is worse still, because a reviewer learns
to ignore it.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.adapters.ocr_adapter import (  # noqa: E402
    OcrLine, OcrPage,
)
from submission_review.extraction.grounding import verify_grounding  # noqa: E402

_PHOTO = "11111111-1111-4111-8111-111111111111"


def _page(*texts: str) -> OcrPage:
    lines = tuple(
        OcrLine(text=text, left=10.0, top=20.0 * index,
                right=200.0, bottom=20.0 * index + 18.0)
        for index, text in enumerate(texts)
    )
    return OcrPage(photo_id=_PHOTO, input_id="i1", lines=lines)


def _field(value, supporting, status="read"):
    return {
        "value": value, "status": status, "confidence": None,
        "sources": [{"input_id": "i1", "photo_id": _PHOTO,
                     "supporting_text": supporting}],
    }


def _draft(rows):
    return {
        "identity": {"brand": _field("Northwind", "Northwind"),
                     "product_name": None, "barcode_digits_seen": None},
        "serving": {"size": None, "servings_per_container": None,
                    "basis_text": None, "amount": None},
        "ingredient_rows": rows,
        "other_ingredients": {"text": None, "disclosure_hint": "unknown"},
    }


def _row(name="Vitamin C", amount=None, percent=None):
    return {
        "display_name": _field(name, name),
        "amount": amount, "percent_dv": percent,
        "form_text": None, "parent_index": None,
        "is_blend_header": False, "status": "read",
    }


def test_an_honest_reading_is_fully_grounded() -> None:
    draft = _draft([_row(amount=_field({"value": 500.0, "unit_text": "mg"}, "500 mg"))])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    assert report.ungrounded == ()
    assert report.rate == 1.0


def test_an_invented_dose_is_caught_even_though_its_unit_is_printed() -> None:
    draft = _draft([_row(amount=_field({"value": 5000.0, "unit_text": "mg"}, "500 mg"))])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    # The unit is always printed somewhere, so requiring only that *something*
    # claimed was found lets any fabricated number through. The digits have to
    # be located on their own.
    assert [entry.path for entry in report.ungrounded] == ["ingredient_rows[0].amount"]


def test_an_invented_ingredient_name_is_caught() -> None:
    draft = _draft([_row(name="Vitamin Q")])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    assert [entry.path for entry in report.ungrounded] == ["ingredient_rows[0].display_name"]


def test_a_printed_number_does_not_ground_an_unprinted_unit() -> None:
    draft = _draft([_row(amount=_field({"value": 500.0, "unit_text": "IU"}, "500 mg"))])
    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])
    assert [entry.path for entry in report.ungrounded] == ["ingredient_rows[0].amount"]


def test_collapsed_spacing_does_not_read_as_a_fabrication() -> None:
    draft = _draft([_row(
        name="Proprietary Blend",
        amount=_field({"value": 400.0, "unit_text": "mcg DFE"}, "400 mcg DFE"),
    )])

    # Real OCR returns "400mcgDFE" for the same panel that yields "500 mg".
    # A verifier that flags this teaches reviewers to ignore it.
    report = verify_grounding(
        draft, [_page("Northwind", "ProprietaryBlend", "400mcgDFE")])

    assert report.ungrounded == ()


def test_thousands_separator_does_not_read_as_a_fabrication() -> None:
    draft = _draft([_row(
        amount=_field({"value": 5000.0, "unit_text": "mg"}, "5,000 mg"),
    )])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "5,000 mg")])

    assert report.ungrounded == ()


def test_source_input_must_belong_to_the_cited_photo() -> None:
    draft = _draft([_row()])
    draft["ingredient_rows"][0]["display_name"]["sources"][0]["input_id"] = "wrong-input"

    report = verify_grounding(draft, [_page("Vitamin C")])

    entry = next(item for item in report.fields if item.path == "ingredient_rows[0].display_name")
    assert not entry.grounded
    assert "input" in entry.reason


def test_a_field_citing_a_photograph_nobody_read_is_not_grounded() -> None:
    draft = _draft([_row()])
    other = OcrPage(photo_id="22222222-2222-4222-8222-222222222222",
                    input_id="i2", lines=())

    report = verify_grounding(draft, [other])

    assert all(not entry.grounded for entry in report.fields)
    assert any("not read" in entry.reason for entry in report.fields)


def test_a_reading_with_no_source_is_not_grounded() -> None:
    row = _row()
    row["display_name"]["sources"] = []

    report = verify_grounding(_draft([row]), [_page("Vitamin C")])

    assert any(entry.reason == "no source cited" for entry in report.ungrounded)


def test_unread_fields_are_not_checked_at_all() -> None:
    row = _row()
    row["display_name"] = {"value": None, "status": "unreadable",
                           "confidence": None, "sources": []}

    report = verify_grounding(_draft([row]), [_page("Northwind")])

    # Nothing was claimed, so there is nothing to locate; counting it as a
    # failure would punish the honest answer.
    assert "ingredient_rows[0].display_name" not in [e.path for e in report.fields]


def test_the_report_says_how_much_of_the_reading_is_supported() -> None:
    draft = _draft([_row(), _row(name="Vitamin Q")])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C")])

    assert report.checked == 3 and report.grounded == 2
    payload = report.as_payload()
    assert payload["schema_version"] == "grounding_report_v1"
    assert abs(payload["rate"] - 2 / 3) < 1e-9


def _prepared(data: bytes = b"\xff\xd8fixture"):
    from submission_review.extraction.extractor import PreparedBundle, PreparedInput
    import hashlib
    # The boundary verifies the bytes against their provenance, so a
    # placeholder digest is refused before grounding is ever reached.
    digest = hashlib.sha256(data).hexdigest()
    photo = PreparedInput(
        input_id="i1", photo_id=_PHOTO, original_sha256=digest,
        sent_sha256=digest, content_type="image/jpeg", byte_size=len(data),
        data=data, categories=("supplement_facts",),
    )
    return PreparedBundle(submission_id="s1", evidence_revision=1, photos=(photo,))


def _ocr_config(provider="ollama"):
    from submission_review.extraction.extractor import ExtractionConfig
    return ExtractionConfig(
        provider=provider, model="m", model_digest="c" * 64,
        prompt_version="p1", retention_policy_version="local-only-v1",
    )


class _PageReader:
    """Stands in for an engine: returns whatever the test says was printed."""

    def __init__(self, page=None, boom=False):
        self._page, self._boom = page, boom

    def read(self, data, *, photo_id, input_id):
        if self._boom:
            raise RuntimeError("engine exploded")
        return self._page or _page()


def _run(reader, provider="ollama"):
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter
    from submission_review.extraction.extractor import LabelDraftExtractor
    extractor = LabelDraftExtractor(FakeAdapter(), grounding_reader=reader)
    return extractor.extract(_prepared(), _ocr_config("fake"))


def test_the_worker_boundary_records_a_grounding_report() -> None:
    result = _run(_PageReader(_page("Northwind")))

    report = result.usage.as_payload()["grounding"]
    assert report["status"] == "ok"
    assert report["schema_version"] == "grounding_report_v1"


def test_grounding_never_fails_an_extraction() -> None:
    # A broken verifier is not a broken reading. If the check cannot run, the
    # draft still stands and the absence is stated rather than assumed.
    result = _run(_PageReader(boom=True))

    report = result.usage.as_payload()["grounding"]
    assert report["status"] == "unavailable"
    assert result.draft["schema_version"] == "label_draft_v1"


def test_no_reader_means_no_report_rather_than_a_passing_one() -> None:
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter
    from submission_review.extraction.extractor import LabelDraftExtractor

    result = LabelDraftExtractor(FakeAdapter()).extract(_prepared(), _ocr_config("fake"))

    # Silence must never read as "everything was located".
    assert "grounding" not in result.usage.as_payload()


def test_a_reader_that_produced_the_draft_is_marked_not_independent() -> None:
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter
    from submission_review.extraction.extractor import LabelDraftExtractor
    from submission_review.extraction.extractor import ExtractionConfig

    class _ConfiguredFakeAdapter(FakeAdapter):
        """A fake reading adapter that accepts the producer under test."""

        def extract(self, bundle, config):
            # Reuse the canonical fake draft, then only retag its pinned
            # producer fields. The test is about the grounding seam, not a
            # second adapter implementation.
            result = super().extract(bundle, _ocr_config("fake"))
            result.draft.update(
                provider=config.provider,
                model=config.model,
                prompt_version=config.prompt_version,
            )
            return result

    config = ExtractionConfig(
        provider="ocr", model="rapidocr", model_digest="c" * 64,
        prompt_version="p1", retention_policy_version="local-only-v1",
    )
    extractor = LabelDraftExtractor(_ConfiguredFakeAdapter(), grounding_reader=_PageReader())
    result = extractor.extract(_prepared(), config)

    # Checking a reading against the reader that produced it can only catch an
    # assembly bug, never an invented value, so the benchmark must be told.
    assert result.usage.as_payload()["grounding"]["independent_of_producer"] is False


def _spatial_page(*rows):
    return OcrPage(_PHOTO, 'i1', tuple(OcrLine(text, left, top, right, bottom)
                                     for text, left, top, right, bottom in rows))


def _grounded_row(page, name='Vitamin C', amount=500, unit='mg', **kwargs):
    draft = _draft([_row(name, _field({'value': amount, 'unit_text': unit}, f'{amount} {unit}'))])
    return verify_grounding(draft, [page], **kwargs).as_payload()['rows'][0]


def test_spatial_grounding_keeps_valid_row_and_rejects_swapped_dose():
    page = _spatial_page(('Vitamin C', 10, 10, 150, 25), ('500 mg', 200, 10, 260, 25),
                         ('Calcium', 10, 40, 150, 55), ('250 mg', 200, 40, 260, 55))
    assert _grounded_row(page)['status'] == 'supported'
    assert _grounded_row(page, amount=250)['status'] == 'check_this'
    assert _grounded_row(page, unit='IU')['status'] == 'check_this'


def test_spatial_number_is_not_substring_and_name_is_exact():
    page = _spatial_page(('Vitamin C 1500 mg', 10, 10, 260, 25))
    assert _grounded_row(page, amount=500)['status'] == 'check_this'
    assert _grounded_row(page, name='Vitamin', amount=1500)['status'] == 'check_this'


def test_spatial_wrap_reuses_geometry_grouping():
    page = _spatial_page(('Vitamin', 10, 10, 150, 24), ('C', 10, 26, 150, 40),
                         ('500 mg', 200, 15, 260, 35))
    assert _grounded_row(page)['status'] == 'supported'


def test_spatial_repeated_and_multiple_columns_are_uncertain():
    repeated = _spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25),
                             ('Vitamin C 500 mg', 10, 40, 260, 55))
    columns = _spatial_page(('Vitamin C', 10, 10, 150, 25), ('500 mg', 200, 10, 260, 25),
                           ('500 mg', 300, 10, 360, 25))
    assert _grounded_row(repeated)['status'] == 'check_this'
    assert _grounded_row(columns)['status'] == 'check_this'


def test_spatial_missing_or_invalid_geometry_is_not_checked():
    from types import SimpleNamespace
    for line in (SimpleNamespace(text='Vitamin C 500 mg'),
                 OcrLine('Vitamin C 500 mg', 10, 10, float('nan'), 25),
                 OcrLine('Vitamin C 500 mg', 20, 10, 10, 25)):
        page = OcrPage(_PHOTO, 'i1', (line,))
        assert _grounded_row(page)['status'] == 'not_checked'


def test_spatial_sources_must_agree_and_draft_is_unchanged():
    from copy import deepcopy
    draft = _draft([_row(amount=_field({'value': 500, 'unit_text': 'mg'}, '500 mg'))])
    draft['ingredient_rows'][0]['amount']['sources'][0]['input_id'] = 'i2'
    before = deepcopy(draft)
    report = verify_grounding(draft, [_spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25))])
    assert report.rows[0]['status'] == 'check_this'
    assert draft == before


def test_spatial_blends_are_conservative():
    draft = _draft([_row(amount=_field({'value': 500, 'unit_text': 'mg'}, '500 mg'))])
    draft['ingredient_rows'][0]['parent_index'] = 0
    assert verify_grounding(draft, [_spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25))]).rows[0]['status'] == 'check_this'


def test_region_requires_proven_transform_and_uses_exact_crop_pixels():
    from types import SimpleNamespace
    page = _spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25))
    assert _grounded_row(page)['region'] is None
    prepared = SimpleNamespace(photo_id=_PHOTO, input_id='i1', original_size=(1001, 701),
                               prepared_size=(501, 351), pixel_crop=(100, 70, 601, 421))
    result = _grounded_row(page, prepared_inputs=[prepared])
    assert result['region'] == {'x': 110 / 1001, 'y': 80 / 701, 'w': 250 / 1001, 'h': 15 / 701}
    prepared.prepared_size = (200, 200)
    assert _grounded_row(page, prepared_inputs=[prepared])['status'] == 'not_checked'


def test_rotated_grounding_checks_dimensions_and_maps_back_to_the_photo():
    from dataclasses import replace
    from types import SimpleNamespace
    page = replace(_spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25)),
                   rotation_degrees=90, image_size=(400, 200))
    prepared = SimpleNamespace(photo_id=_PHOTO, input_id='i1', original_size=(200, 400),
                               prepared_size=(200, 400), pixel_crop=(0, 0, 200, 400))
    result = _grounded_row(page, prepared_inputs=[prepared])
    assert result['status'] == 'supported'
    assert result['region'] == {'x': .05, 'y': .35, 'w': .075, 'h': .625}
    assert _grounded_row(replace(page, image_size=(200, 400)),
                         prepared_inputs=[prepared])['status'] == 'not_checked'


def test_preparation_records_orientation_and_exact_pixel_rounding():
    import hashlib
    import io
    from PIL import Image
    from submission_review.extraction.extractor import EvidenceBundle, EvidencePhoto
    from submission_review.extraction.photo_prep import prepare_bundle
    buffer = io.BytesIO()
    image = Image.new('RGB', (701, 1001), 'white')
    exif = Image.Exif()
    exif[274] = 6
    image.save(buffer, format='JPEG', exif=exif)
    raw = buffer.getvalue()
    photo = EvidencePhoto(photo_id=_PHOTO, sha256=hashlib.sha256(raw).hexdigest())
    bundle = EvidenceBundle('s1', 1, (photo,))
    prepared = prepare_bundle(bundle, reader=lambda _: raw,
                              crops={_PHOTO: {'x': .1, 'y': .1, 'w': .5, 'h': .5}}).photos[0]
    assert prepared.original_size == (1001, 701)
    assert prepared.pixel_crop == (100, 70, 601, 421)
    assert prepared.prepared_size == (501, 351)
    # Internal geometry must not expand the label_draft_v1 input schema.
    assert 'pixel_crop' not in prepared.as_sent_input()


def test_new_row_check_retains_page_wide_baseline_for_comparison():
    page = _spatial_page(('Northwind', 10, 1, 150, 8),
                         ('Vitamin C 500 mg', 10, 20, 260, 35),
                         ('Calcium 250 mg', 10, 50, 260, 65))
    draft = _draft([_row(amount=_field({'value': 250, 'unit_text': 'mg'}, '250 mg'))])
    report = verify_grounding(draft, [page])
    assert report.rate == 1.0
    assert report.rows[0]['status'] == 'check_this'


def test_name_spanning_two_amount_rows_has_ambiguous_ownership():
    page = _spatial_page(('Vitamin C', 10, 10, 150, 50),
                         ('500 mg', 200, 10, 260, 25), ('250 mg', 200, 40, 260, 55))
    assert _grounded_row(page)['status'] == 'check_this'


def test_missing_cited_page_is_not_checked_but_duplicates_are_ambiguous():
    draft = _draft([_row(amount=_field({'value': 500, 'unit_text': 'mg'}, '500 mg'))])
    page = _spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25))
    assert verify_grounding(draft, []).rows[0]['status'] == 'not_checked'
    assert verify_grounding(draft, [page, page]).rows[0]['status'] == 'check_this'


def test_name_spanning_unitless_amount_rows_has_ambiguous_ownership():
    page = _spatial_page(('Vitamin C', 10, 10, 150, 50),
                         ('500 mg', 200, 10, 260, 25), ('250', 200, 40, 280, 55))
    assert _grounded_row(page)['status'] == 'check_this'


def test_amount_and_percent_on_same_row_are_one_anchor():
    page = _spatial_page(('Vitamin C', 10, 10, 150, 25),
                         ('500 mg', 200, 10, 260, 25), ('556%', 280, 10, 330, 25))
    assert _grounded_row(page)['status'] == 'supported'


def test_two_machine_rows_cannot_both_claim_one_printed_occurrence():
    import copy
    row = _row(amount=_field({'value': 500, 'unit_text': 'mg'}, '500 mg'))
    draft = _draft([row, copy.deepcopy(row)])
    page = _spatial_page(('Vitamin C 500 mg', 10, 10, 260, 25))
    assert [row['status'] for row in verify_grounding(draft, [page]).rows] == ['check_this', 'check_this']
