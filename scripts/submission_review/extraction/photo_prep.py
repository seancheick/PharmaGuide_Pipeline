"""Turn leased evidence into bytes an adapter may see, or refuse.

Everything here is a limit. A submission photo is attacker-influenced input:
it arrives from a phone we do not control, it is decoded by a library with a
long history of decompression bombs, and it is about to be sent to a third
party. So this module verifies identity first, bounds the work second, and
never widens what the queue leased.

Three rules it exists to keep:

* Content is identity. A photo whose bytes do not hash to the manifest value
  is not the evidence the reviewer will see, and is refused rather than read.
* Bounded decode. Byte size, pixel count and dimensions are capped before the
  image is materialised, so a small file that expands to gigabytes fails as a
  typed error instead of taking the worker down.
* Nothing extra leaves. Only the leased photos are prepared, re-encoded
  without metadata, and the exact bytes sent are hashed so a draft can be
  bound to what the provider actually received.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from collections.abc import Mapping

from .extractor import EvidenceBundle, EvidencePhoto, ExtractionError, PreparedBundle, PreparedInput
from .envelope import LabelDraftError, _region

#: Worker-side input ceiling, also enforced by the bounded local reader.
MAX_SOURCE_BYTES = 15 * 1024 * 1024
#: A supplement label needs detail, not a poster. Above this the pixels are
#: cost and risk, not information.
MAX_PIXELS = 40_000_000
MAX_SOURCE_EDGE = 16_384
MAX_EDGE = 4096
#: What an adapter is allowed to transmit per photo after preparation.
MAX_SENT_BYTES = 4 * 1024 * 1024
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


def prepare_bundle(
    bundle: EvidenceBundle,
    *,
    reader=None,
    max_sent_bytes: int = MAX_SENT_BYTES,
    crops: Mapping[str, Mapping[str, float]] | None = None,
) -> PreparedBundle:
    """Prepare every leased photo, or raise a typed failure.

    `reader` returns the stored bytes for one photo; the default reads the
    local path the worker fetched to. It is injected so tests never need a
    network and so the fetch policy stays the caller's decision. Optional crops
    select one view per leased photo; they never add evidence or upscale it.
    Coordinates refer to the orientation-corrected original, before thumbnailing.
    """
    read = reader or _read_local
    if not bundle.photos or len(bundle.snapshot) != len(bundle.photos):
        raise ExtractionError("unsupported_evidence", "empty or duplicate evidence")
    validated_crops: dict[str, tuple[float, float, float, float]] = {}
    if crops is not None:
        if not isinstance(crops, Mapping) or set(crops) - set(bundle.snapshot):
            raise ExtractionError("unsupported_evidence", "crop must reference leased evidence")
        for photo_id, region in crops.items():
            try:
                value = dict(region)
                _region(value, "$.crop")  # The envelope owns coordinate validity.
                if value['w'] <= 0 or value['h'] <= 0:
                    raise ValueError('empty crop')
                validated_crops[photo_id] = tuple(value[key] for key in ('x', 'y', 'w', 'h'))
            except (LabelDraftError, ValueError, TypeError):
                raise ExtractionError("unsupported_evidence", "invalid crop region") from None
    prepared: list[PreparedInput] = []
    for index, photo in enumerate(bundle.photos):
        prepared.append(
            _prepare_photo(photo, f"i{index}", read, max_sent_bytes=max_sent_bytes,
                           crop=validated_crops.get(photo.photo_id))
        )
    return PreparedBundle(bundle.submission_id, bundle.evidence_revision, tuple(prepared))


def _prepare_photo(
    photo: EvidencePhoto,
    input_id: str,
    read,
    *,
    max_sent_bytes: int,
    crop: tuple[float, float, float, float] | None = None,
) -> PreparedInput:
    try:
        raw = read(photo)
    except ExtractionError:
        raise
    except Exception as error:  # noqa: BLE001 - the boundary types everything
        raise ExtractionError("preparation_failed", "evidence could not be read") from error
    if not raw:
        raise ExtractionError("preparation_failed", "evidence is empty")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ExtractionError("unsupported_evidence", "evidence exceeds the size limit")

    # Identity before anything else: never decode bytes we cannot attribute.
    actual = hashlib.sha256(raw).hexdigest()
    if actual != photo.sha256:
        raise ExtractionError(
            "preparation_failed", "evidence does not match its manifest hash"
        )

    geometry = {}
    data, content_type = _bounded_reencode(raw, max_sent_bytes=max_sent_bytes, crop=crop, geometry=geometry)
    return PreparedInput(
        input_id=input_id,
        photo_id=photo.photo_id,
        original_sha256=actual,
        sent_sha256=hashlib.sha256(data).hexdigest(),
        content_type=content_type,
        byte_size=len(data),
        data=data,
        categories=photo.categories,
        crop=crop,
        **geometry,
    )


def _bounded_reencode(raw: bytes, *, max_sent_bytes: int,
                      crop: tuple[float, float, float, float] | None = None,
                      geometry: dict | None = None) -> tuple[bytes, str]:
    try:
        from PIL import Image, ImageOps
    except ImportError as error:  # pragma: no cover - environment guard
        raise ExtractionError("preparation_failed", "imaging support is unavailable") from error

    # Refuse the bomb before allocating for it. `open` is lazy, so the header
    # is available without decoding the pixels.
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            if image_format not in ALLOWED_FORMATS:
                raise ExtractionError("unsupported_evidence", "unsupported image format")
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise ExtractionError("unsupported_evidence", "evidence exceeds the pixel limit")
            if max(width, height) > MAX_SOURCE_EDGE:
                raise ExtractionError("unsupported_evidence", "evidence exceeds the dimension limit")
            if getattr(probe, "n_frames", 1) != 1:
                raise ExtractionError("unsupported_evidence", "multi-frame evidence requires separate photos")
            probe.load()
            oriented = ImageOps.exif_transpose(probe)
            rgba = oriented.convert("RGBA")
            prepared = Image.new("RGB", rgba.size, "white")
            prepared.paste(rgba, mask=rgba.getchannel("A"))
            original_size = prepared.size
            pixel_crop = (0, 0, *original_size)
            if crop is not None:
                x, y, w, h = crop
                width, height = prepared.size
                pixel_crop = (round(x * width), round(y * height),
                              round((x + w) * width), round((y + h) * height))
                prepared = prepared.crop(pixel_crop)
            prepared.thumbnail((MAX_EDGE, MAX_EDGE))
            if geometry is not None:
                geometry.update(original_size=original_size, pixel_crop=pixel_crop, prepared_size=prepared.size)
            buffer = io.BytesIO()
            # Apply orientation before stripping EXIF; composite transparency
            # so black label text remains readable on a transparent background.
            prepared.save(buffer, format="JPEG", quality=88, optimize=True)
    except ExtractionError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ExtractionError("unsupported_evidence", "evidence is not a readable image") from error

    data = buffer.getvalue()
    if len(data) > max_sent_bytes:
        raise ExtractionError("unsupported_evidence", "prepared evidence is too large to send")
    return data, "image/jpeg"


def _read_local(photo: EvidencePhoto) -> bytes:
    if not photo.path:
        raise ExtractionError("preparation_failed", "no local path for leased evidence")
    with Path(photo.path).open("rb") as source:
        return source.read(MAX_SOURCE_BYTES + 1)
