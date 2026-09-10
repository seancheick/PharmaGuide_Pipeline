"""Guards on the preparation surface both extractors share.

`photo_prep` is common mode: every candidate reads the same prepared bytes, so
a loss there is invisible to any comparison between candidates — they fail on
the same rows and their agreement reads as confirmation. These tests pin the
geometry of that surface. The legibility measurement itself needs the OCR
engine and is opted into separately.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("PIL")

from submission_review.extraction import photo_prep  # noqa: E402
from submission_review.extraction.extractor import ExtractionError  # noqa: E402
from submission_review.extraction.print_fidelity import (  # noqa: E402
    DEVICE_SHORT_EDGE,
    FRAMES,
    PANEL_LINES,
    PanelDoesNotFit,
    device_encode,
    panel_ems,
    prepare,
    render_frame,
    score,
)

RUN_OCR = os.environ.get("PG_RUN_OCR_FIDELITY_TESTS") == "1"


def _flat(width: int, height: int) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (240, 240, 236)).save(buffer, format="PNG")
    return buffer.getvalue()


def _edge(data: bytes) -> int:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return max(image.size)


def test_preparation_does_not_shrink_what_the_phone_already_sent():
    """The server's ceiling must sit above the app's, or it silently re-crushes.

    The app caps the short side at DEVICE_SHORT_EDGE before upload, so the
    long side of a 4:3 photograph arrives near 3200. If photo_prep.MAX_EDGE
    ever drops below that, every submission loses resolution twice and the
    fine print pays for it.
    """
    sent = prepare(_flat(DEVICE_SHORT_EDGE, DEVICE_SHORT_EDGE * 4 // 3))
    assert _edge(sent) == DEVICE_SHORT_EDGE * 4 // 3
    assert photo_prep.MAX_EDGE > DEVICE_SHORT_EDGE * 4 // 3


def test_a_sixteen_by_nine_still_is_shrunk_twice():
    """Known and accepted, not a discovery in waiting.

    The phone caps the short side at 2400, which puts a 16:9 long side at
    4267, above MAX_EDGE. The server takes another 4% off the width. If that
    gap ever widens, this figure moves with it and the test says so.
    """
    twice = prepare(device_encode(_flat(3024, 5376)))
    assert _size(twice) == (2304, 4096)


def test_a_sanitized_high_resolution_capture_is_accepted():
    """A 48MP phone is only acceptable because the app shrinks it first."""
    sanitized = device_encode(_flat(*FRAMES["phone-48mp"]))
    assert max(_size(sanitized)) <= photo_prep.MAX_EDGE
    prepare(sanitized)  # must not raise


def test_an_unsanitized_high_resolution_capture_is_refused():
    """Records the coupling: relax the app's sanitizer and the server refuses.

    A 48MP frame is 48.8 million pixels, above MAX_PIXELS. Any client that
    uploads what the camera produced — a future web path, a changed picker —
    gets a typed refusal, not a degraded read.
    """
    with pytest.raises(ExtractionError) as raised:
        prepare(_flat(*FRAMES["phone-48mp"]))
    assert raised.value.code == "unsupported_evidence"


def _size(data: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return image.size


def test_device_encode_only_ever_shrinks():
    small = _flat(1200, 1600)
    assert _size(device_encode(small)) == (1200, 1600)
    assert _size(device_encode(_flat(3024, 4032))) == (DEVICE_SHORT_EDGE, 3200)


def test_the_panel_is_sized_from_its_own_type():
    """A fixed panel width would clip the longest row and blame preparation."""
    assert 2.0 < panel_ems() * 6.0 / 72.0 < 3.0


def test_an_unphotographable_geometry_is_refused_not_cropped():
    # Wide and short: the panel is about 29 ems across and 18 tall, so only
    # a letterbox frame can fail to hold it.
    with pytest.raises(PanelDoesNotFit):
        render_frame((3024, 900), 0.90, point_size=6.0)


def test_scoring_ignores_box_order_but_not_character_order():
    """An engine may return boxes in any order and split them anywhere.

    What it may not do is reorder characters: "mcg 25" is a different reading
    from "25 mcg", and a metric that accepted it would score a wrong dose as
    a right one.
    """
    boxes = list(reversed(PANEL_LINES))
    split = boxes.index("Zinc (as zinc picolinate) 15 mg 136%")
    boxes[split : split + 1] = ["Zinc (as zinc", " picolinate) 15 mg 136%"]
    assert score(tuple(boxes)).line_recall == 1.0

    scrambled = score(tuple(" ".join(reversed(line.split())) for line in PANEL_LINES))
    assert scrambled.digit_recall < 1.0


def test_scoring_refuses_a_line_whose_dose_is_missing():
    lost = score(("Vitamin D3 (as cholecalciferol) mcg (1,000 IU) 125%",))
    assert lost.line_recall == 0.0
    partial = score(("Zinc (as zinc picolinate) 15 mg 136%",))
    assert partial.lines_found == 1
    assert "25mcg" in partial.missing_digits


def test_a_six_point_render_is_rasterised_at_six_points():
    """Rendering large and scaling down would hide the loss under test."""
    from PIL import Image

    raw, ppi = render_frame((3024, 4032), 0.35, point_size=6.0)
    with Image.open(io.BytesIO(raw)) as image:
        assert image.size == (3024, 4032)
    assert abs(6.0 / 72.0 * ppi - round(3024 * 0.35) / panel_ems()) < 0.001


@pytest.mark.skipif(not RUN_OCR, reason="needs PG_RUN_OCR_FIDELITY_TESTS=1 and the OCR engine")
def test_preparation_costs_nothing_at_the_working_operating_point():
    """At a panel filling half the frame, photo_prep must be transparent.

    Measured 2026-09-10: identical readings in and out at 41.6 pixels per em.
    A regression here means the shared surface started eating fine print.
    """
    from submission_review.extraction.adapters.rapidocr_reader import RapidOcrReader
    from submission_review.extraction.print_fidelity import measure

    rung = measure(RapidOcrReader(), frame_name="phone-12mp", fraction=0.50)
    assert rung.refused is None
    assert rung.resized is False
    assert rung.after.line_recall >= rung.before.line_recall
    assert rung.after.digit_recall == 1.0
