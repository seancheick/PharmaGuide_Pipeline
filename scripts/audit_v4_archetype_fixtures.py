#!/usr/bin/env python3
"""Validate synthetic V4 archetypes through the single production scorer.

The fixture suite is deliberately data-only: it contains enriched-product
inputs and reviewed output snapshots, but no scoring formula. Every case is
routed through ``build_scored_artifact`` so this audit exercises the same
router, gates, modules, quality assembler, and Stage-3 projection as a release.
"""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from scoring_v4.scored_artifact import build_scored_artifact


PRODUCTION_ENTRY_POINT = "scoring_v4.scored_artifact.build_scored_artifact"
PROJECTION_KEYS = frozenset(
    {
        "v4_module",
        "archetype",
        "quality_score_status",
        "product_safety_status",
        "quality_score_v4_100",
        "quality_tier",
        "v4_confidence",
        "normalization_references",
        "pillars",
        "raw_dimensions",
    }
)
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "tests"
    / "fixtures"
    / "v4_archetype_decision_suite.json"
)

# Exposed as an explicit architecture lock for tests and reviewers.
scoring_entry_point = build_scored_artifact


@dataclass(frozen=True)
class ArchetypeFixture:
    case_id: str
    archetype: str
    variant: str
    product: dict[str, Any]
    expected: dict[str, Any]


@dataclass(frozen=True)
class ArchetypeFixtureSuite:
    metadata: dict[str, Any]
    cases: tuple[ArchetypeFixture, ...]

    @property
    def archetypes(self) -> set[str]:
        return {case.archetype for case in self.cases}

    def by_id(self, case_id: str) -> ArchetypeFixture:
        matches = [case for case in self.cases if case.case_id == case_id]
        if len(matches) != 1:
            raise KeyError(f"expected one archetype fixture {case_id!r}, found {len(matches)}")
        return matches[0]


@dataclass(frozen=True)
class ArchetypeFixtureResult:
    case_id: str
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    diff: dict[str, Any]


def _require_object(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return dict(value)


def load_fixture_suite(
    path: Path | str = DEFAULT_FIXTURE_PATH,
) -> ArchetypeFixtureSuite:
    """Load and structurally validate the reviewed fixture catalog."""
    fixture_path = Path(path)
    payload = _require_object(
        json.loads(fixture_path.read_text(encoding="utf-8")),
        path="$",
    )
    metadata = _require_object(payload.get("_metadata"), path="$._metadata")
    if metadata.get("schema_version") != "1.0.0":
        raise ValueError("unsupported archetype fixture schema")
    if metadata.get("production_entry_point") != PRODUCTION_ENTRY_POINT:
        raise ValueError("fixture suite does not name the canonical production entry point")

    raw_cases = payload.get("fixtures")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("$.fixtures must be a non-empty array")

    cases: list[ArchetypeFixture] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        case = _require_object(raw_case, path=f"$.fixtures[{index}]")
        case_id = str(case.get("id") or "").strip()
        archetype = str(case.get("archetype") or "").strip()
        variant = str(case.get("variant") or "").strip()
        if not case_id or case_id in seen_ids:
            raise ValueError(f"fixture id must be non-empty and unique: {case_id!r}")
        if variant not in {"ideal", "failure"}:
            raise ValueError(f"{case_id}: variant must be ideal or failure")
        if case_id != f"{archetype}__{variant}":
            raise ValueError(f"{case_id}: id must be <archetype>__<variant>")
        seen_ids.add(case_id)
        expected = _require_object(case.get("expected"), path=f"{case_id}.expected")
        if set(expected) != PROJECTION_KEYS:
            missing = sorted(PROJECTION_KEYS - set(expected))
            extra = sorted(set(expected) - PROJECTION_KEYS)
            raise ValueError(
                f"{case_id}: expected projection keys drifted "
                f"(missing={missing}, extra={extra})"
            )
        cases.append(
            ArchetypeFixture(
                case_id=case_id,
                archetype=archetype,
                variant=variant,
                product=_require_object(case.get("product"), path=f"{case_id}.product"),
                expected=expected,
            )
        )

    variants_by_archetype: dict[str, set[str]] = {}
    for case in cases:
        variants_by_archetype.setdefault(case.archetype, set()).add(case.variant)
    incomplete = {
        archetype: sorted({"ideal", "failure"} - variants)
        for archetype, variants in variants_by_archetype.items()
        if variants != {"ideal", "failure"}
    }
    if incomplete:
        raise ValueError(f"every archetype requires an ideal/failure pair: {incomplete}")

    return ArchetypeFixtureSuite(metadata=metadata, cases=tuple(cases))


def _score_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    pillars = artifact.get("quality_pillars_v4")
    if not isinstance(pillars, dict):
        pillars = {}
    module_breakdown = artifact.get("_v4_module_breakdown")
    if not isinstance(module_breakdown, dict):
        module_breakdown = {}
    dimensions = module_breakdown.get("dimensions")
    if not isinstance(dimensions, dict):
        dimensions = {}

    archetype = None
    normalization_references: dict[str, Any] = {}
    formulation_pillar = pillars.get("formulation")
    if isinstance(formulation_pillar, dict):
        components = formulation_pillar.get("components")
        if isinstance(components, dict):
            archetype = components.get("archetype")
    for name in ("formulation", "dose", "evidence"):
        pillar = pillars.get(name)
        if not isinstance(pillar, dict):
            continue
        components = pillar.get("components")
        if isinstance(components, dict):
            normalization_references[name] = components.get("reference")

    return {
        "v4_module": artifact.get("_v4_module"),
        "archetype": archetype,
        "quality_score_status": artifact.get("quality_score_status"),
        "product_safety_status": artifact.get("product_safety_status"),
        "quality_score_v4_100": artifact.get("quality_score_v4_100"),
        "quality_tier": artifact.get("quality_tier"),
        "v4_confidence": artifact.get("_v4_confidence"),
        "normalization_references": normalization_references,
        "pillars": {
            name: value.get("score")
            for name, value in pillars.items()
            if isinstance(value, dict)
        },
        "raw_dimensions": {
            name: value.get("score")
            for name, value in dimensions.items()
            if isinstance(value, dict)
        },
    }


def evaluate_fixture(case: ArchetypeFixture) -> ArchetypeFixtureResult:
    """Score one fixture once and compare it with its reviewed snapshot."""
    actual = _score_projection(scoring_entry_point(copy.deepcopy(case.product)))
    passed = actual == case.expected
    diff = {} if passed else {"expected": case.expected, "actual": actual}
    return ArchetypeFixtureResult(
        case_id=case.case_id,
        passed=passed,
        expected=case.expected,
        actual=actual,
        diff=diff,
    )


def evaluate_suite(
    suite: ArchetypeFixtureSuite | None = None,
) -> tuple[ArchetypeFixtureResult, ...]:
    selected = suite or load_fixture_suite()
    return tuple(evaluate_fixture(case) for case in selected.cases)


def _report(results: Sequence[ArchetypeFixtureResult]) -> dict[str, Any]:
    failures = [result for result in results if not result.passed]
    return {
        "production_entry_point": PRODUCTION_ENTRY_POINT,
        "fixture_count": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "results": [
            {
                "id": result.case_id,
                "passed": result.passed,
                "actual": result.actual,
                "diff": result.diff,
            }
            for result in results
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="reviewed archetype fixture suite",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON report path; stdout is always emitted",
    )
    args = parser.parse_args(argv)

    results = evaluate_suite(load_fixture_suite(args.fixtures))
    report = _report(results)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
