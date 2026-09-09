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
from dataclasses import dataclass
from pathlib import Path

from .extractor import EvidenceBundle, EvidencePhoto, ExtractionError

#: Matches the app's own upload ceiling. A larger file never came from us.
MAX_SOURCE_BYTES = 15 * 1024 * 1024
#: A supplement label needs detail, not a poster. Above this the pixels are
#: cost and risk, not information.
MAX_PIXELS = 40_000_000
MAX_EDGE = 4096
#: What an adapter is allowed to transmit per photo after preparation.
MAX_SENT_BYTES = 4 * 1024 * 1024
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "HEIF", "HEIC"})


@dataclass(frozen=True)
class PreparedInput:
    """One photo as it will actually be sent, and what it came from."""

    input_id: str
    photo_id: str
    #: Hash of the bytes as stored, which the manifest also carries.
    original_sha256: str
    #: Hash of the bytes actually transmitted. Different when re-encoded, and
    #: recorded separately so provenance is not a guess.
    sent_sha256: str
    content_type: str
    byte_size: int
    data: bytes = b""

    def as_sent_input(self) -> dict[str, object]:
        return {
            "input_id": self.input_id,
            "photo_id": self.photo_id,
            "original_sha256": self.original_sha256,
            "sent_sha256": self.sent_sha256,
        }


def prepare_bundle(
    bundle: EvidenceBundle,
    *,
    reader=None,
    max_sent_bytes: int = MAX_SENT_BYTES,
) -> list[PreparedInput]:
    """Prepare every leased photo, or raise a typed failure.

    `reader` returns the stored bytes for one photo; the default reads the
    local path the worker fetched to. It is injected so tests never need a
    network and so the fetch policy stays the caller's decision.
    """
    read = reader or _read_local
    prepared: list[PreparedInput] = []
    for index, photo in enumerate(bundle.photos):
        prepared.append(
            _prepare_photo(photo, f"i{index}", read, max_sent_bytes=max_sent_bytes)
        )
    return prepared


def _prepare_photo(
    photo: EvidencePhoto,
    input_id: str,
    read,
    *,
    max_sent_bytes: int,
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

    data, content_type = _bounded_reencode(raw, max_sent_bytes=max_sent_bytes)
    return PreparedInput(
        input_id=input_id,
        photo_id=photo.photo_id,
        original_sha256=actual,
        sent_sha256=hashlib.sha256(data).hexdigest(),
        content_type=content_type,
        byte_size=len(data),
        data=data,
    )


def _bounded_reencode(raw: bytes, *, max_sent_bytes: int) -> tuple[bytes, str]:
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - environment guard
        raise ExtractionError("preparation_failed", "imaging support is unavailable") from error

    # Refuse the bomb before allocating for it. `open` is lazy, so the header
    # is available without decoding the pixels.
    try:
        probe = Image.open(io.BytesIO(raw))
        image_format = (probe.format or "").upper()
        width, height = probe.size
    except Exception as error:  # noqa: BLE001
        raise ExtractionError("unsupported_evidence", "evidence is not a readable image") from error
    if image_format not in ALLOWED_FORMATS:
        raise ExtractionError("unsupported_evidence", "unsupported image format")
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ExtractionError("unsupported_evidence", "evidence exceeds the pixel limit")

    try:
        probe.load()
        prepared = probe.convert("RGB")
        prepared.thumbnail((MAX_EDGE, MAX_EDGE))
        buffer = io.BytesIO()
        # A fresh RGB save carries no EXIF, so location and device metadata do
        # not travel to a provider even though the app already stripped them.
        prepared.save(buffer, format="JPEG", quality=88, optimize=True)
    except ExtractionError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ExtractionError("preparation_failed", "evidence could not be prepared") from error

    data = buffer.getvalue()
    if len(data) > max_sent_bytes:
        raise ExtractionError("unsupported_evidence", "prepared evidence is too large to send")
    return data, "image/jpeg"


def _read_local(photo: EvidencePhoto) -> bytes:
    if not photo.path:
        raise ExtractionError("preparation_failed", "no local path for leased evidence")
    return Path(photo.path).read_bytes()
