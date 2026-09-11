"""Preparing evidence for a provider: identity first, then hard limits.

A submission photo is attacker-influenced input on its way to a third party.
These tests hold the three rules that make that safe: content is identity, the
decode is bounded, and nothing beyond the lease leaves.
"""
from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from submission_review.extraction.extractor import (
    EvidenceBundle,
    EvidencePhoto,
    ExtractionError,
)
from submission_review.extraction.photo_prep import prepare_bundle

_PHOTO_A = "10000000-0000-0000-0000-000000000001"
_PHOTO_B = "10000000-0000-0000-0000-000000000002"


def _jpeg(width: int = 64, height: int = 48, colour=(120, 160, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="JPEG")
    return buffer.getvalue()


def _bundle(*photos: EvidencePhoto, revision: int = 1) -> EvidenceBundle:
    return EvidenceBundle(
        submission_id="018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
        evidence_revision=revision,
        photos=tuple(photos),
    )


def _photo(photo_id: str, data: bytes) -> EvidencePhoto:
    return EvidencePhoto(photo_id=photo_id, sha256=hashlib.sha256(data).hexdigest())


def _reader(mapping):
    def read(photo: EvidencePhoto) -> bytes:
        return mapping[photo.photo_id]

    return read


def test_prepared_input_records_both_hashes() -> None:
    source = _jpeg()
    bundle = _bundle(_photo(_PHOTO_A, source))

    prepared = prepare_bundle(bundle, reader=_reader({_PHOTO_A: source}))

    assert len(prepared.photos) == 1
    entry = prepared.photos[0]
    assert entry.original_sha256 == hashlib.sha256(source).hexdigest()
    # Re-encoding changes the bytes, so what was sent is hashed separately
    # rather than assumed equal to what was stored.
    assert entry.sent_sha256 == hashlib.sha256(entry.data).hexdigest()
    assert entry.content_type == "image/jpeg"
    assert entry.as_sent_input()["photo_id"] == _PHOTO_A


def test_bytes_that_do_not_match_the_manifest_are_never_decoded() -> None:
    bundle = _bundle(EvidencePhoto(photo_id=_PHOTO_A, sha256="a" * 64))

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(bundle, reader=_reader({_PHOTO_A: _jpeg()}))

    assert error.value.code == "preparation_failed"
    assert "manifest hash" in error.value.detail


def test_a_decompression_bomb_fails_as_a_typed_error() -> None:
    # A small file whose header claims an enormous canvas. Refused from the
    # header, before any allocation.
    bomb = io.BytesIO()
    Image.new("RGB", (12000, 12000), (255, 255, 255)).save(bomb, format="PNG")
    data = bomb.getvalue()
    bundle = _bundle(_photo(_PHOTO_A, data))

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(bundle, reader=_reader({_PHOTO_A: data}))

    assert error.value.code == "unsupported_evidence"
    assert "pixel limit" in error.value.detail


def test_something_that_is_not_an_image_is_refused() -> None:
    data = b"not an image at all"
    bundle = _bundle(_photo(_PHOTO_A, data))

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(bundle, reader=_reader({_PHOTO_A: data}))

    assert error.value.code == "unsupported_evidence"


def test_empty_evidence_is_refused() -> None:
    bundle = _bundle(_photo(_PHOTO_A, b""))

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(bundle, reader=_reader({_PHOTO_A: b""}))

    assert error.value.code == "preparation_failed"


def test_a_read_failure_becomes_a_typed_failure_not_a_crash() -> None:
    def explode(photo):
        raise OSError("storage unavailable")

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(_bundle(_photo(_PHOTO_A, _jpeg())), reader=explode)

    assert error.value.code == "preparation_failed"
    # The provider's or storage's own message must not travel with the failure.
    assert "storage unavailable" not in error.value.detail


def test_prepared_bytes_over_the_send_ceiling_are_refused() -> None:
    source = _jpeg(800, 800)
    bundle = _bundle(_photo(_PHOTO_A, source))

    with pytest.raises(ExtractionError) as error:
        prepare_bundle(
            bundle, reader=_reader({_PHOTO_A: source}), max_sent_bytes=64
        )

    assert error.value.code == "unsupported_evidence"
    assert "too large to send" in error.value.detail


def test_only_the_leased_photos_are_prepared() -> None:
    first, second = _jpeg(colour=(10, 20, 30)), _jpeg(colour=(200, 100, 50))
    bundle = _bundle(_photo(_PHOTO_A, first))
    seen: list[str] = []

    def read(photo):
        seen.append(photo.photo_id)
        return {_PHOTO_A: first, _PHOTO_B: second}[photo.photo_id]

    prepared = prepare_bundle(bundle, reader=read)

    assert seen == [_PHOTO_A]
    assert [entry.photo_id for entry in prepared.photos] == [_PHOTO_A]


def test_input_ids_are_stable_and_positional() -> None:
    first, second = _jpeg(colour=(10, 20, 30)), _jpeg(colour=(200, 100, 50))
    bundle = _bundle(_photo(_PHOTO_A, first), _photo(_PHOTO_B, second))

    prepared = prepare_bundle(
        bundle, reader=_reader({_PHOTO_A: first, _PHOTO_B: second})
    )

    assert [entry.input_id for entry in prepared.photos] == ["i0", "i1"]


def test_orientation_is_applied_before_metadata_is_removed() -> None:
    source = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (80, 40), "white").save(source, format="JPEG", exif=exif)
    data = source.getvalue()
    prepared = prepare_bundle(_bundle(_photo(_PHOTO_A, data)), reader=_reader({_PHOTO_A: data}))
    with Image.open(io.BytesIO(prepared.photos[0].data)) as result:
        assert result.size == (40, 80)
        assert not result.getexif()


def test_transparent_label_is_composited_on_white() -> None:
    source = io.BytesIO()
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(source, format="PNG")
    data = source.getvalue()
    prepared = prepare_bundle(_bundle(_photo(_PHOTO_A, data)), reader=_reader({_PHOTO_A: data}))
    with Image.open(io.BytesIO(prepared.photos[0].data)) as result:
        assert min(result.getpixel((8, 8))) > 245


def test_multiframe_image_is_not_silently_reduced_to_one_label() -> None:
    source = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(source, format="PNG", save_all=True,
        append_images=[Image.new("RGB", (16, 16), "blue")])
    data = source.getvalue()
    with pytest.raises(ExtractionError):
        prepare_bundle(_bundle(_photo(_PHOTO_A, data)), reader=_reader({_PHOTO_A: data}))


def test_close_up_uses_the_same_preparation_and_keeps_original_provenance() -> None:
    source = _jpeg(200, 100)
    crop = {'x': 0.5, 'y': 0.0, 'w': 0.5, 'h': 1.0}
    bundle = _bundle(_photo(_PHOTO_A, source))
    prepared = prepare_bundle(bundle, reader=_reader({_PHOTO_A: source}), crops={_PHOTO_A: crop})
    entry = prepared.photos[0]
    assert entry.original_sha256 == hashlib.sha256(source).hexdigest()
    assert entry.sent_sha256 == hashlib.sha256(entry.data).hexdigest()
    assert entry.as_sent_input()['crop'] == crop
    with Image.open(io.BytesIO(entry.data)) as result:
        assert result.size == (100, 100)
        assert not result.getexif()
    # Provenance must not follow later mutation of a caller's request or receipt.
    crop['x'] = 0
    entry.as_sent_input()['crop']['x'] = 0
    assert entry.as_sent_input()['crop']['x'] == 0.5


@pytest.mark.parametrize('crop', [
    {'x': 0.8, 'y': 0, 'w': 0.3, 'h': 1},
    {'x': 0, 'y': 0, 'w': 0, 'h': 1},
    {'x': True, 'y': 0, 'w': 0.5, 'h': 1},
    {'x': float('nan'), 'y': 0, 'w': 0.5, 'h': 1},
])
def test_invalid_close_up_is_refused_before_reading(crop) -> None:
    source = _jpeg()
    seen = []
    with pytest.raises(ExtractionError):
        prepare_bundle(_bundle(_photo(_PHOTO_A, source)),
                       reader=lambda photo: seen.append(photo), crops={_PHOTO_A: crop})
    assert seen == []


def test_close_up_cannot_request_an_unleased_photo() -> None:
    source = _jpeg()
    with pytest.raises(ExtractionError):
        prepare_bundle(_bundle(_photo(_PHOTO_A, source)),
                       crops={_PHOTO_B: {'x': 0, 'y': 0, 'w': 1, 'h': 1}})


def test_close_up_coordinates_are_applied_after_orientation() -> None:
    image = Image.new('RGB', (80, 40), 'red')
    image.paste(Image.new('RGB', (40, 40), 'blue'), (40, 0))
    exif = Image.Exif()
    exif[274] = 6  # Clockwise: the blue right half becomes the bottom half.
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', exif=exif)
    raw = buffer.getvalue()
    prepared = prepare_bundle(_bundle(_photo(_PHOTO_A, raw)), reader=_reader({_PHOTO_A: raw}),
                              crops={_PHOTO_A: {'x': 0, 'y': .5, 'w': 1, 'h': .5}})
    with Image.open(io.BytesIO(prepared.photos[0].data)) as result:
        assert result.size == (40, 40)
        red, green, blue = result.getpixel((20, 20))
        assert blue > 240 and red < 10 and green < 10
        assert not result.getexif()
