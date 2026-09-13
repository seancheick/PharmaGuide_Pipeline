"""Bind RapidOCR to the reader protocol, and nothing else.

Kept apart from the adapter on purpose: the assembly rules are the thing under
benchmark, and they must stay testable without an engine installed. Swapping
engines changes this file only.

RapidOCR is ONNX Runtime under the hood, Apache-2.0, and runs entirely on this
machine. No photograph leaves the host, which is the same promise the local
model adapter makes.
"""

from __future__ import annotations

import io
import math
from typing import Any

from ..extractor import ExtractionError, Usage
from .ocr_adapter import OcrLine, OcrPage

#: Below this the engine is guessing at shapes rather than reading characters,
#: and a guessed digit in a dose is the most expensive error on this label.
MIN_LINE_CONFIDENCE = 0.5


class RapidOcrReader:
    """Reads printed text and its geometry from prepared image bytes."""

    def __init__(self, engine: Any | None = None,
                 min_confidence: float = MIN_LINE_CONFIDENCE) -> None:
        self._engine = engine
        self._min_confidence = min_confidence

    def _resolve(self) -> Any:
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:  # pragma: no cover - environment shape
            raise ExtractionError(
                "provider_unavailable",
                "the local OCR engine is not installed",
                usage=Usage(),
            ) from error
        # Per-line 180-degree repair hides which way the page reads. Read
        # upright candidates instead, so amount columns keep their direction.
        self._engine = RapidOCR(use_angle_cls=False)
        return self._engine

    def read(self, data: bytes, *, photo_id: str, input_id: str) -> OcrPage:
        try:
            import numpy
            from PIL import Image
        except ImportError as error:  # pragma: no cover - environment shape
            raise ExtractionError(
                "provider_unavailable", "image support is unavailable", usage=Usage(),
            ) from error
        with Image.open(io.BytesIO(data)) as image:
            # Decoded in memory: the prepared bytes are a user's photograph and
            # do not get a second copy on disk for an engine's convenience.
            frame = numpy.asarray(image.convert("RGB"))
        engine = self._resolve()

        def read_frame(pixels: Any, rotation: int) -> OcrPage:
            result, _ = engine(pixels)
            return OcrPage(photo_id, input_id, self._lines(result), rotation,
                           (pixels.shape[1], pixels.shape[0]))

        initial = read_frame(frame, 0)
        vertical = sum(line.height > (line.right - line.left) * 1.5 for line in initial.lines)
        if initial.lines and vertical <= len(initial.lines) / 2:
            return initial
        # At most four reads. A tie is unresolved, not permission to reverse
        # row ownership. Confidence selects orientation only, never approval.
        candidates = [read_frame(numpy.ascontiguousarray(numpy.rot90(frame, -turn)), turn * 90)
                      for turn in (1, 2, 3)]
        def readability(page: OcrPage) -> float:
            return sum(min(len(line.text), 80) * (line.confidence or 0) for line in page.lines
                       if line.right - line.left >= line.height)
        candidates.sort(key=readability, reverse=True)
        best, runner_up = candidates[:2]
        if readability(best) > 0 and readability(best) > readability(runner_up) * 1.1:
            return best
        return OcrPage(photo_id, input_id, image_size=(frame.shape[1], frame.shape[0]))

    def _lines(self, result: Any) -> tuple[OcrLine, ...]:
        lines: list[OcrLine] = []
        for box, text, confidence in result or ():
            value = str(text).strip()
            if not value:
                continue
            try:
                score = float(confidence)
            except (TypeError, ValueError):
                score = 0.0
            if not math.isfinite(score) or not self._min_confidence <= score <= 1:
                # Dropped rather than passed on: a low-confidence line is the
                # engine guessing, and the reviewer sees a missing row, which
                # is honest, instead of a plausible wrong one.
                continue
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            lines.append(OcrLine(
                text=value, left=min(xs), top=min(ys),
                right=max(xs), bottom=max(ys), confidence=score,
            ))
        return tuple(lines)
