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
