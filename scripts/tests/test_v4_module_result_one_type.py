"""One module-result type behind the public v4_breakdown["module"] shape.

GenericModuleResult, OmegaModuleResult, ProbioticModuleResult and
MultiPrenatalModuleResult had the same 11 fields and the same to_breakdown
(architecture audit 2026-10-17, AUDIT.md H #4, R4). One ModuleResult in
scoring_v4.modules.generic now carries every route; each route still stamps its
own module name and phase marker.
"""

from __future__ import annotations

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules import (
    b_complex,
    fiber_digestive,
    generic,
    multi_prenatal,
    omega,
    probiotic,
    sports,
)

FIELDS = [
    "module", "dimensions", "verification_bonus", "manufacturer_trust",
    "manufacturer_violations", "safety_hygiene_base", "botanical_dose_deferred",
    "raw_score_100", "score_100", "phase", "metadata",
]
BREAKDOWN_KEYS = [
    "module", "dimensions", "verification_bonus", "manufacturer_trust",
    "manufacturer_violations", "safety_hygiene_base", "raw_score_100",
    "score_100", "phase", "metadata",
]

ROUTES = [
    (generic.score_generic, "generic", generic.PHASE_MARKER),
    (omega.score_omega, "omega", omega.PHASE_MARKER),
    (probiotic.score_probiotic, "probiotic", probiotic.PHASE_MARKER),
    (multi_prenatal.score_multi_prenatal, "multi_or_prenatal", multi_prenatal.PHASE_MARKER),
    (b_complex.score_b_complex, "b_complex", b_complex.PHASE_MARKER),
    (fiber_digestive.score_fiber_digestive, "fiber_digestive", fiber_digestive.PHASE_MARKER),
    (sports.score_sports, "sports", sports.PHASE_MARKER),
]


def test_module_result_keeps_the_eleven_fields():
    assert [f.name for f in dataclasses.fields(generic.ModuleResult)] == FIELDS


@pytest.mark.parametrize("score, module, phase", ROUTES)
def test_every_route_returns_the_one_type_with_its_own_stamp(score, module, phase):
    result = score({})
    assert type(result) is generic.ModuleResult
    breakdown = result.to_breakdown()
    assert list(breakdown) == BREAKDOWN_KEYS
    assert breakdown["module"] == module
    assert breakdown["phase"] == phase


@pytest.mark.parametrize("module, name", [
    (generic, "GenericModuleResult"),
    (omega, "OmegaModuleResult"),
    (probiotic, "ProbioticModuleResult"),
    (multi_prenatal, "MultiPrenatalModuleResult"),
])
def test_route_modules_do_not_carry_their_own_result_type(module, name):
    assert not hasattr(module, name)
