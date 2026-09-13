"""Page rotation must not change which original pixels support a row."""
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from submission_review.extraction.adapters.rapidocr_reader import RapidOcrReader
from submission_review.extraction.adapters.ocr_adapter import OcrLine, OcrPage, _largest_text
from submission_review.extraction.grounding import _original_region


def _result(text, box, confidence=.95):
    x, y, right, bottom = box
    return [[[x, y], [right, y], [right, bottom], [x, bottom]], text, confidence]


def test_sideways_page_is_reread_upright_with_rotation_provenance():
    image = Image.new('RGB', (100, 200), 'white')
    image.putpixel((0, 0), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')

    def engine(frame):
        if frame.shape[:2] == (200, 100):
            return [_result('Vitamin C', (10, 10, 20, 100))], None
        # Clockwise rotation puts the original top-left at top-right.
        if tuple(frame[0, -1]) == (255, 0, 0):
            return [_result('Vitamin C 500 mg', (10, 10, 180, 30))], None
        return [], None

    page = RapidOcrReader(engine=engine).read(buffer.getvalue(), photo_id='p1', input_id='i0')
    assert [line.text for line in page.lines] == ['Vitamin C 500 mg']
    assert page.rotation_degrees == 90
    assert page.image_size == (200, 100)


@pytest.mark.parametrize('rotation,expected', [
    (90, {'x': .125, 'y': .3, 'w': .1, 'h': .15}),
    (270, {'x': .575, 'y': .15, 'w': .1, 'h': .15}),
])
def test_rotated_region_returns_to_original_crop(rotation, expected):
    prepared = SimpleNamespace(original_size=(1000, 2000), prepared_size=(600, 800),
                               pixel_crop=(100, 200, 700, 1000))
    page = OcrPage('p1', 'i0', rotation_degrees=rotation, image_size=(800, 600))
    band = [OcrLine('Vitamin C 500 mg', 100, 25, 400, 125)]
    assert _original_region(band, prepared, page) == pytest.approx(expected)


def test_vertical_side_panel_is_not_front_brand():
    page = OcrPage('p1', 'i0', (
        OcrLine('Actual brand', 10, 10, 200, 40),
        OcrLine('Facts', 210, 10, 230, 180),
    ))
    assert _largest_text(page) == ('Actual brand', 'Actual brand')


def test_nan_confidence_never_counts_as_read_text():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 200)).save(buffer, format='PNG')
    reader = RapidOcrReader(engine=lambda _: ([_result('500 mg', (1, 1, 90, 20), float('nan'))], None))
    assert reader.read(buffer.getvalue(), photo_id='p1', input_id='i0').lines == ()


def test_equal_rotation_readings_abstain_instead_of_reversing_columns():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 200)).save(buffer, format='PNG')
    calls = []
    def engine(frame):
        calls.append(frame.shape)
        if frame.shape[:2] == (200, 100):
            return [_result('Vitamin C', (10, 10, 20, 100))], None
        return [_result('Vitamin C 500 mg', (10, 10, 180, 30))], None
    page = RapidOcrReader(engine=engine).read(buffer.getvalue(), photo_id='p1', input_id='i0')
    assert page.lines == ()
    assert len(calls) == 4


def test_upright_page_does_not_trigger_extra_engine_reads():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 200)).save(buffer, format='PNG')
    calls = []
    def engine(frame):
        calls.append(frame.shape)
        return [_result('Vitamin C', (10, 10, 90, 30))], None
    page = RapidOcrReader(engine=engine).read(buffer.getvalue(), photo_id='p1', input_id='i0')
    assert len(calls) == 1
    assert page.rotation_degrees == 0
