"""
Review follow-up — the pipeline coverage gate must not fail OPEN on a
transitive ImportError raised *during* gate execution.

run_coverage_gate wrapped the whole body (import + load + check + report) in one
`try` with `except ImportError: return True`. That catch was meant for "the
coverage_gate module isn't installed → skip", but it also swallowed ANY
ImportError raised transitively while running the gate (a broken dependency of a
checker) and silently PROCEEDED to scoring. Narrow the ImportError catch to the
import line only; anything else falls to `except Exception` which fails closed.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import coverage_gate
from run_pipeline import PipelineRunner


def test_transitive_importerror_during_gate_fails_closed(tmp_path, monkeypatch):
    enr = tmp_path / "enr"
    enr.mkdir()
    (enr / "p.json").write_text(json.dumps([{"id": "1"}]), encoding="utf-8")

    class BoomGate:
        def check_batch(self, products):
            raise ImportError("transitive import failure during gate execution")

    monkeypatch.setattr(coverage_gate, "CoverageGate", BoomGate)

    runner = PipelineRunner()
    can_proceed, _summary = runner.run_coverage_gate(
        str(enr), str(tmp_path), block_on_failure=True
    )

    assert can_proceed is False, (
        "A transitive ImportError during coverage checking must fail CLOSED "
        "(block scoring), not be swallowed by the module-missing ImportError catch"
    )


def test_gate_execution_failure_cannot_be_downgraded_to_warn_only(
    tmp_path, monkeypatch
):
    enr = tmp_path / "enr"
    enr.mkdir()
    (enr / "p.json").write_text(json.dumps([{"id": "1"}]), encoding="utf-8")

    class BoomGate:
        def __init__(self, strict_mode=False):
            pass

        def check_batch(self, products):
            raise RuntimeError("required gate crashed")

    monkeypatch.setattr(coverage_gate, "CoverageGate", BoomGate)

    can_proceed, summary = PipelineRunner().run_coverage_gate(
        str(enr), str(tmp_path), block_on_failure=False
    )

    assert can_proceed is False
    assert summary["error"] == "gate_execution_failed"
