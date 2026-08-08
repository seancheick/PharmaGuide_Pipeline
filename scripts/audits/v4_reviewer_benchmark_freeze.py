#!/usr/bin/env python3
"""Freeze a blinded, archetype-balanced V4 reviewer benchmark.

The reviewer packet contains label facts only. Engine outputs and source IDs
live in a separate baseline key that must not be distributed to reviewers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable


EXPECTED_ARCHETYPES = (
    "b_complex",
    "fiber_digestive",
    "generic_botanical_branded",
    "generic_single_molecule",
    "immune_support",
    "omega",
    "prenatal_multi",
    "probiotic",
    "sports_bcaa_eaa",
    "sports_pre_workout",
    "sports_protein",
    "sports_single",
)
TIER_ORDER = (
    "Poor",
    "Weak",
    "Acceptable",
    "Strong",
    "Excellent",
    "Elite",
)
FORBIDDEN_REVIEWER_FIELDS = frozenset({
    "dsld_id",
    "archetype",
    "v4_module",
    "quality_score_v4_100",
    "quality_tier",
    "quality_score_status",
    "product_safety_status",
    "quality_assessment_status",
    "v4_confidence",
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
    "verdict",
    "safety_verdict",
    "sample_cohort",
    "analysis_split",
    "challenge_flags",
})
# Reviewer-packet schema note, for defending the study later. These two fields
# are NOT peer sources of truth -- one is observed, one is derived from it:
#
#   parent_index
#       SOURCE FACT. The label's own row nesting (`raw_source_path`), nothing
#       else. If the source and this field disagree, the source wins.
#
#   constituent_child_indexes
#       BENCHMARK-ONLY DERIVED ANNOTATION, computed from parent_index plus the
#       unit / positive-amount / sum checks in _resolve_constituent_rollups.
#       Never author it directly and never infer it downstream: re-deriving this
#       relationship in a second place, from arithmetic, is exactly what put 23
#       false dose instructions into the v6 packets.
#
# Neither carries scoring, safety, evidence, dose-adequacy or any other
# engine-derived judgment, so both are label provenance rather than blinded
# engine output — which is why they may sit in a blinded reviewer packet.
BASELINE_FIELDS = (
    "benchmark_id",
    "review_sequence",
    "dsld_id",
    "archetype",
    "sample_cohort",
    "analysis_split",
    "challenge_flags",
    "quality_score_v4_100",
    "quality_tier",
    "quality_score_status",
    "product_safety_status",
    "quality_assessment_status",
    "v4_confidence",
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
    "pillar_sum_v4",
    "score_cap_id",
    "score_cap_value",
    "score_cap_applied",
    "score_cap_adjustment",
    "score_model_version",
    "quality_score_version",
    "scoring_engine_version",
    "classification_schema_version",
    "v4_config_fingerprint",
)
REVIEWER_REGISTRY_FIELDS = (
    "reviewer_slot",
    "reviewer_id",
    "panel_role",
    "credential_type",
    "credential_detail",
    "license_jurisdiction",
    "license_status",
    "license_verification_source",
    "supplement_experience_years",
    "evidence_appraisal_experience_years",
    "conflicts_json",
    "training_completed_on",
    "training_assessment_score",
    "protocol_version",
    "independence_attested_on",
    "data_use_attested_on",
    "registered_on",
)


def build_benchmark_freeze(
    catalog_products: Iterable[dict[str, Any]],
    detail_products: Mapping[str, dict[str, Any]],
    *,
    seed: str,
    freeze_id: str,
    per_archetype: int,
    core_per_archetype: int,
    tier_thresholds: Iterable[float],
) -> dict[str, list[dict[str, Any]]]:
    """Select and split a deterministic blinded benchmark."""
    if not seed.strip() or not freeze_id.strip():
        raise ValueError("seed and freeze_id are required")
    if not 0 < core_per_archetype < per_archetype:
        raise ValueError("core_per_archetype must be between 1 and quota - 1")

    thresholds = sorted({
        float(value)
        for value in tier_thresholds
        if _as_float(value) is not None and float(value) > 0.0
    })
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for original in catalog_products:
        row = dict(original)
        dsld_id = _dsld_id(row)
        if not dsld_id or dsld_id in seen_ids:
            raise ValueError(f"duplicate or empty catalog dsld_id: {dsld_id!r}")
        seen_ids.add(dsld_id)
        if row.get("quality_score_status") != "scored":
            continue
        archetype = str(row.get("archetype") or "").strip()
        if not archetype:
            raise ValueError(f"{dsld_id} has no scoring archetype")
        if dsld_id not in detail_products:
            raise ValueError(f"{dsld_id} has no product detail")
        row["dsld_id"] = dsld_id
        row["archetype"] = archetype
        row["challenge_flags"] = _challenge_flags(row, thresholds)
        candidates[archetype].append(row)

    selected: list[dict[str, Any]] = []
    for archetype in sorted(candidates):
        rows = candidates[archetype]
        if len(rows) < per_archetype:
            raise ValueError(
                f"{archetype} has {len(rows)} eligible products; "
                f"{per_archetype} required"
            )
        core = _select_core(
            rows,
            core_per_archetype,
            seed=seed,
            archetype=archetype,
        )
        core_ids = {_dsld_id(row) for row in core}
        challenge = _select_challenge(
            [row for row in rows if _dsld_id(row) not in core_ids],
            per_archetype - core_per_archetype,
            seed=seed,
            archetype=archetype,
        )
        for row in core:
            selected.append({**row, "sample_cohort": "core"})
        for row in challenge:
            selected.append({**row, "sample_cohort": "challenge"})

    _assign_holdout_splits(
        selected,
        seed=seed,
        per_archetype=per_archetype,
    )
    selected.sort(
        key=lambda row: _stable_hash(
            seed,
            "review-order",
            _dsld_id(row),
        )
    )

    reviewer_packet: list[dict[str, Any]] = []
    baseline_key: list[dict[str, Any]] = []
    for sequence, row in enumerate(selected, start=1):
        dsld_id = _dsld_id(row)
        benchmark_id = "PG-" + _stable_hash(
            freeze_id,
            seed,
            dsld_id,
        )[:12].upper()
        detail = detail_products[dsld_id]
        reviewer_packet.append(
            _reviewer_packet_row(
                benchmark_id,
                sequence,
                detail,
            )
        )
        baseline_row = {
            field: (
                benchmark_id
                if field == "benchmark_id"
                else sequence
                if field == "review_sequence"
                else row.get(field)
            )
            for field in BASELINE_FIELDS
        }
        baseline_row.update(_score_adjustment_fields(row, detail))
        baseline_key.append(baseline_row)

    if len({row["benchmark_id"] for row in baseline_key}) != len(
        baseline_key
    ):
        raise ValueError("benchmark ID collision")
    return {
        "reviewer_packet": reviewer_packet,
        "baseline_key": baseline_key,
    }


def reconciled_public_score(
    pillar_scores: Iterable[Any],
    score_cap: dict[str, Any] | None,
) -> int:
    """Return the exported half-up integer after any explicit score cap."""
    numeric_scores = [_as_float(value) for value in pillar_scores]
    if not numeric_scores or any(value is None for value in numeric_scores):
        raise ValueError("all pillar scores must be numeric")
    score = sum(
        value for value in numeric_scores
        if value is not None
    )
    if isinstance(score_cap, dict) and score_cap.get("applied") is True:
        cap_value = _as_float(score_cap.get("cap"))
        if cap_value is None:
            raise ValueError("applied score cap has no numeric cap")
        score = min(score, cap_value)
    return math.floor(score + 0.5)


def _score_adjustment_fields(
    row: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    pillar_fields = (
        "pillar_formulation_v4",
        "pillar_dose_v4",
        "pillar_evidence_v4",
        "pillar_transparency_v4",
        "pillar_verification_v4",
        "pillar_safety_hygiene_v4",
    )
    pillar_values = [_as_float(row.get(field)) for field in pillar_fields]
    if any(value is None for value in pillar_values):
        raise ValueError(f"{_dsld_id(row)} has a non-numeric pillar")
    cap = detail.get("quality_score_cap_v4")
    if not isinstance(cap, dict):
        cap = {}
    return {
        "pillar_sum_v4": round(sum(
            value for value in pillar_values
            if value is not None
        ), 4),
        "score_cap_id": cap.get("id"),
        "score_cap_value": cap.get("cap"),
        "score_cap_applied": cap.get("applied") is True,
        "score_cap_adjustment": cap.get("adjustment"),
    }


def _select_core(
    rows: list[dict[str, Any]],
    quota: int,
    *,
    seed: str,
    archetype: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_tier[str(row.get("quality_tier") or "")].append(row)

    high_confidence = [
        row for row in rows
        if row.get("v4_confidence") == "high"
    ]
    if high_confidence:
        choice = min(
            high_confidence,
            key=lambda row: _stable_hash(
                seed,
                archetype,
                "core-high-confidence",
                _dsld_id(row),
            ),
        )
        selected.append(choice)
        selected_ids.add(_dsld_id(choice))

    for tier in TIER_ORDER:
        choices = [
            row
            for row in by_tier[tier]
            if _dsld_id(row) not in selected_ids
        ]
        if len(selected) >= quota or not choices:
            continue
        choice = min(
            choices,
            key=lambda row: _stable_hash(
                seed,
                archetype,
                "core",
                tier,
                _dsld_id(row),
            ),
        )
        selected.append(choice)
        selected_ids.add(_dsld_id(choice))

    remaining = sorted(
        (row for row in rows if _dsld_id(row) not in selected_ids),
        key=lambda row: _stable_hash(
            seed,
            archetype,
            "core-fill",
            _dsld_id(row),
        ),
    )
    selected.extend(remaining[: quota - len(selected)])
    return selected


def _select_challenge(
    rows: list[dict[str, Any]],
    quota: int,
    *,
    seed: str,
    archetype: str,
) -> list[dict[str, Any]]:
    challenge_rows = [row for row in rows if row["challenge_flags"]]
    if len(challenge_rows) < quota:
        raise ValueError(
            f"{archetype} has {len(challenge_rows)} challenge products; "
            f"{quota} required"
        )

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for flag in (
        "catalog_safety_caution",
        "zero_evidence",
        "low_confidence",
        "near_tier_boundary",
    ):
        choices = [
            row
            for row in challenge_rows
            if flag in row["challenge_flags"]
            and _dsld_id(row) not in selected_ids
        ]
        if len(selected) >= quota or not choices:
            continue
        choice = min(
            choices,
            key=lambda row: _stable_hash(
                seed,
                archetype,
                "challenge",
                flag,
                _dsld_id(row),
            ),
        )
        selected.append(choice)
        selected_ids.add(_dsld_id(choice))

    remaining = sorted(
        (
            row
            for row in challenge_rows
            if _dsld_id(row) not in selected_ids
        ),
        key=lambda row: (
            -len(row["challenge_flags"]),
            _stable_hash(
                seed,
                archetype,
                "challenge-fill",
                _dsld_id(row),
            ),
        ),
    )
    selected.extend(remaining[: quota - len(selected)])
    return selected


def _assign_holdout_splits(
    rows: list[dict[str, Any]],
    *,
    seed: str,
    per_archetype: int,
) -> None:
    holdout_count = max(2, round(per_archetype * 0.2))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["archetype"]].append(row)

    for archetype, archetype_rows in grouped.items():
        holdout: list[dict[str, Any]] = []
        for cohort in ("core", "challenge"):
            choices = [
                row
                for row in archetype_rows
                if row["sample_cohort"] == cohort
            ]
            holdout.append(min(
                choices,
                key=lambda row: _stable_hash(
                    seed,
                    archetype,
                    "holdout",
                    cohort,
                    _dsld_id(row),
                ),
            ))
        holdout_ids = {_dsld_id(row) for row in holdout}
        remaining = sorted(
            (
                row
                for row in archetype_rows
                if _dsld_id(row) not in holdout_ids
            ),
            key=lambda row: _stable_hash(
                seed,
                archetype,
                "holdout-fill",
                _dsld_id(row),
            ),
        )
        holdout_ids.update(
            _dsld_id(row)
            for row in remaining[: holdout_count - len(holdout_ids)]
        )
        for row in archetype_rows:
            row["analysis_split"] = (
                "holdout"
                if _dsld_id(row) in holdout_ids
                else "development"
            )


def _challenge_flags(
    row: dict[str, Any],
    tier_thresholds: list[float],
) -> list[str]:
    flags: list[str] = []
    if row.get("product_safety_status") == "caution":
        flags.append("catalog_safety_caution")
    if _as_float(row.get("pillar_evidence_v4")) == 0.0:
        flags.append("zero_evidence")
    if row.get("v4_confidence") == "low":
        flags.append("low_confidence")
    score = _as_float(row.get("quality_score_v4_100"))
    if (
        score is not None
        and tier_thresholds
        and min(abs(score - value) for value in tier_thresholds) <= 2.0
    ):
        flags.append("near_tier_boundary")
    return flags


def _direct_child_path(child_path: str, parent_path: str) -> bool:
    """True iff child_path is a DIRECT nested row of parent_path on the label.

    The label's own row nesting -- e.g. `Omega-3` carrying `nestedRows[EPA, DHA]`
    -- is the only trustworthy declaration that one row is a constituent form of
    another. Grandchildren are excluded: they are parts-of-parts and would double
    count against the parent total.
    """
    if not child_path or not parent_path:
        return False
    prefix = f"{parent_path}.nestedRows["
    if not child_path.startswith(prefix):
        return False
    return ".nestedRows[" not in child_path[len(prefix):]


_ROLLUP_UNIT_ALIAS = {
    "gram(s)": "g", "grams": "g", "gram": "g",
    "milligram(s)": "mg", "milligrams": "mg", "milligram": "mg",
    "microgram(s)": "mcg",
    "micrograms": "mcg", "microgram": "mcg", "ug": "mcg", "µg": "mcg",
    "np": "", "unspecified": "",
}


def _rollup_unit(unit: Any) -> str:
    key = str(unit or "").strip().lower()
    return _ROLLUP_UNIT_ALIAS.get(key, key)


def _positive_amount(row: Mapping[str, Any]) -> bool:
    quantity = row.get("quantity")
    return (
        isinstance(quantity, (int, float))
        and not isinstance(quantity, bool)
        and quantity > 0
    )


def _resolve_constituent_rollups(actives: list[dict[str, Any]]) -> None:
    """Mark every row the label declares as a total over its own nested forms.

    Resolved here, once, so the reviewer document only has to *render* the
    relationship. It previously re-derived one, and derived it from arithmetic
    coincidence -- "do the next 2-3 amounts sum to this one?" -- which on the
    shipped corpus paired Leucine with Isoleucine+Valine (a 2:1:1 BCAA ratio
    makes the sum match by construction) and GABA with Theanine+Rhodiola.

    A parent must account for **all** of its direct children, not a positional
    window over some of them. That is what makes the claim checkable rather than
    cherry-picked, and it fails closed exactly where the source hierarchy is
    itself unreliable: four products nest an unrelated row under a nutrient
    (`Vitamin B12 300mcg` under `Vitamin K`), and there the totals no longer
    reconcile, so no claim is made.
    """
    for index, parent in enumerate(actives):
        unit = _rollup_unit(parent.get("unit"))
        if not unit or not _positive_amount(parent):
            continue
        children = [
            position for position, row in enumerate(actives)
            if row.get("parent_index") == index
        ]
        if len(children) < 2:
            continue
        rows = [actives[position] for position in children]
        if not all(_positive_amount(row) for row in rows):
            continue
        if any(_rollup_unit(row.get("unit")) != unit for row in rows):
            continue
        if not math.isclose(
            sum(row["quantity"] for row in rows),
            parent["quantity"],
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            continue
        parent["constituent_child_indexes"] = children


def _reviewer_packet_row(
    benchmark_id: str,
    sequence: int,
    detail: dict[str, Any],
) -> dict[str, Any]:
    active_rows = []
    for ingredient in detail.get("ingredients") or []:
        if not isinstance(ingredient, dict):
            continue
        role = str(ingredient.get("role") or "").strip().lower()
        if role and role != "active":
            continue
        active_rows.append(ingredient)
    # Carry the label's structural parent/child nesting into the packet. It is a
    # label fact, not an engine output, and it is the only evidence a downstream
    # reader has for "this row is a constituent form of that one". Dropping it
    # forced build_review_doc.py to infer the relationship from arithmetic
    # coincidence, which paired Leucine with Isoleucine+Valine (a 2:1:1 BCAA
    # ratio makes the sum match) and GABA with Theanine+Rhodiola.
    paths = [str(row.get("raw_source_path") or "") for row in active_rows]
    active_ingredients = []
    for index, ingredient in enumerate(active_rows):
        parent_index = next(
            (
                other
                for other, parent_path in enumerate(paths)
                if other != index and _direct_child_path(paths[index], parent_path)
            ),
            None,
        )
        active_ingredients.append({
            "name": (
                ingredient.get("source_label_name")
                or ingredient.get("label_display_name")
                or ingredient.get("name")
            ),
            "quantity": ingredient.get("quantity"),
            "unit": ingredient.get("unit"),
            "daily_value_percent": ingredient.get("dailyValue"),
            "parent_index": parent_index,
        })
    _resolve_constituent_rollups(active_ingredients)
    inactive_ingredients = [
        ingredient.get("name")
        for ingredient in detail.get("inactive_ingredients") or []
        if isinstance(ingredient, dict) and ingredient.get("name")
    ]
    certification = detail.get("certification_detail")
    if not isinstance(certification, dict):
        certification = {}
    certification_facts = {
        "third_party_programs": (
            certification.get("third_party_programs") or {}
        ).get("programs", []),
        "gmp": certification.get("gmp") or {},
        "purity_verified": certification.get("purity_verified"),
        "heavy_metal_tested": certification.get("heavy_metal_tested"),
        "label_accuracy_verified": certification.get(
            "label_accuracy_verified"
        ),
    }
    row = {
        "benchmark_id": benchmark_id,
        "review_sequence": sequence,
        "product_name": detail.get("product_name"),
        "brand_name": detail.get("brand_name"),
        "serving_info_json": _compact_json(detail.get("serving_info") or {}),
        "active_ingredients_json": _compact_json(active_ingredients),
        "inactive_ingredients_json": _compact_json(inactive_ingredients),
        "certification_facts_json": _compact_json(certification_facts),
        "proprietary_blend_facts_json": _compact_json(
            _proprietary_blend_facts(detail)
        ),
    }
    leaked = set(row) & FORBIDDEN_REVIEWER_FIELDS
    if leaked:
        raise ValueError(f"reviewer packet contains engine fields: {leaked}")
    return row


def _proprietary_blend_facts(
    detail: dict[str, Any],
) -> dict[str, Any]:
    source = detail.get("proprietary_blend_detail")
    if not isinstance(source, dict):
        return {
            "has_proprietary_blends": False,
            "blends": [],
        }
    blends = []
    for blend in source.get("blends") or []:
        if not isinstance(blend, dict):
            continue
        children = [
            {
                "name": child.get("name"),
                "amount": child.get("amount"),
                "unit": child.get("unit"),
            }
            for child in blend.get("child_ingredients") or []
            if isinstance(child, dict)
        ]
        blends.append({
            "name": blend.get("name"),
            "disclosure_level": blend.get("disclosure_level"),
            "total_weight": blend.get("total_weight"),
            "unit": blend.get("unit"),
            "hidden_count": blend.get("hidden_count"),
            "child_ingredients": children,
        })
    return {
        "has_proprietary_blends": bool(
            source.get("has_proprietary_blends")
        ),
        "blends": blends,
    }


def _compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _stable_hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _dsld_id(row: dict[str, Any]) -> str:
    value = row.get("dsld_id")
    return str(value).strip() if value is not None else ""


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DetailBlobStore(Mapping[str, dict[str, Any]]):
    """Lazy read-only access to product detail blobs."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def __getitem__(self, dsld_id: str) -> dict[str, Any]:
        path = self.root / f"{dsld_id}.json"
        if not path.is_file():
            raise KeyError(dsld_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path} is not a product detail object")
        return payload

    def __iter__(self):
        return (
            path.stem
            for path in sorted(self.root.glob("*.json"))
            if path.is_file()
        )

    def __len__(self) -> int:
        return sum(1 for _ in self.__iter__())

    def __contains__(self, dsld_id: object) -> bool:
        return (
            isinstance(dsld_id, str)
            and (self.root / f"{dsld_id}.json").is_file()
        )


def _load_catalog_products(path: Path) -> list[dict[str, Any]]:
    columns = (
        "dsld_id",
        "product_name",
        "brand_name",
        "quality_score_v4_100",
        "quality_tier",
        "quality_score_status",
        "product_safety_status",
        "quality_assessment_status",
        "v4_confidence",
        "pillar_formulation_v4",
        "pillar_dose_v4",
        "pillar_evidence_v4",
        "pillar_transparency_v4",
        "pillar_verification_v4",
        "pillar_safety_hygiene_v4",
        "score_model_version",
        "quality_score_version",
        "scoring_engine_version",
        "classification_schema_version",
        "v4_config_fingerprint",
    )
    with sqlite3.connect(str(path)) as connection:
        connection.row_factory = sqlite3.Row
        available = {
            row[1]
            for row in connection.execute("PRAGMA table_info(products_core)")
        }
        missing = sorted(set(columns) - available)
        if missing:
            raise ValueError(
                f"products_core missing benchmark columns: {missing}"
            )
        rows = connection.execute(
            f"SELECT {', '.join(columns)} FROM products_core "
            "WHERE quality_score_status = 'scored'"
        ).fetchall()
    return [dict(row) for row in rows]


def _load_archetypes(
    scored_root: Path,
    released_ids: set[str],
) -> tuple[dict[str, str], list[Path]]:
    files = sorted(
        path
        for path in scored_root.glob("**/scored/scored_*.json")
        if path.is_file()
    )
    if not files:
        raise FileNotFoundError(
            f"no Stage-3 scored JSON files found under {scored_root}"
        )
    archetypes: dict[str, str] = {}
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path} is not a Stage-3 product array")
        for product in payload:
            if not isinstance(product, dict):
                raise ValueError(f"{path} contains a non-product row")
            dsld_id = _dsld_id(product)
            if dsld_id not in released_ids:
                continue
            archetype = _artifact_archetype(product)
            if not archetype:
                raise ValueError(
                    f"released scored product {dsld_id} has no archetype"
                )
            existing = archetypes.get(dsld_id)
            if existing is not None and existing != archetype:
                raise ValueError(
                    f"{dsld_id} has conflicting archetypes: "
                    f"{existing} vs {archetype}"
                )
            archetypes[dsld_id] = archetype
    missing = sorted(released_ids - set(archetypes))
    if missing:
        raise ValueError(
            f"{len(missing)} released scored products lack Stage-3 context"
        )
    return archetypes, files


def _artifact_archetype(product: dict[str, Any]) -> str:
    pillars = product.get("quality_pillars_v4") or product.get("_v4_pillars")
    if not isinstance(pillars, dict):
        return ""
    formulation = pillars.get("formulation")
    if not isinstance(formulation, dict):
        return ""
    components = formulation.get("components")
    if not isinstance(components, dict):
        return ""
    return str(components.get("archetype") or "").strip()


def _load_tier_thresholds(path: Path) -> list[float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tiers = payload.get("tiers") if isinstance(payload, dict) else None
    if not isinstance(tiers, list):
        raise ValueError(f"{path} has no tiers array")
    values: list[float] = []
    for tier in tiers:
        if not isinstance(tier, dict):
            raise ValueError(f"{path} contains a malformed tier")
        minimum = _as_float(tier.get("min"))
        if minimum is None:
            raise ValueError(f"{path} contains a non-numeric tier minimum")
        values.append(minimum)
    return values


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
    *,
    json_fields: frozenset[str] = frozenset(),
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for original in rows:
            row = {field: original.get(field) for field in fields}
            for field in json_fields:
                row[field] = _compact_json(row[field])
            row = {
                field: safe_csv_cell(value)
                for field, value in row.items()
            }
            writer.writerow(row)


def safe_csv_cell(value: Any) -> Any:
    """Prevent untrusted label text from becoming a spreadsheet formula."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip(" \t\r\n")
    if stripped.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _response_template_rows(
    reviewer_packet: list[dict[str, Any]],
    reviewers_per_product: int,
    *,
    seed: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reviewer_slot in range(1, reviewers_per_product + 1):
        reviewer_products = sorted(
            reviewer_packet,
            key=lambda product: _stable_hash(
                seed,
                "reviewer-order",
                str(reviewer_slot),
                str(product["benchmark_id"]),
            ),
        )
        for reviewer_order, product in enumerate(
            reviewer_products,
            start=1,
        ):
            rows.append({
                "benchmark_id": product["benchmark_id"],
                "review_sequence": product["review_sequence"],
                "reviewer_slot": reviewer_slot,
                "reviewer_id": "",
                "reviewer_order": reviewer_order,
                "review_round": 1,
                "correction_reason": "",
                "formulation_0_20": "",
                "dose_0_20": "",
                "evidence_0_20": "",
                "transparency_0_15": "",
                "verification_0_15": "",
                "formula_quality_checks_0_10": "",
                "overall_0_100": "",
                "product_safety_status": "",
                "safety_concern_driver": "",
                "assessment_confidence": "",
                "label_facts_sufficient": "",
                "source_citations_json": "[]",
                "rationale": "",
                "protocol_deviation": "",
            })
    return rows


def _validate_baseline_reconciliation(
    rows: list[dict[str, Any]],
) -> None:
    pillar_fields = (
        "pillar_formulation_v4",
        "pillar_dose_v4",
        "pillar_evidence_v4",
        "pillar_transparency_v4",
        "pillar_verification_v4",
        "pillar_safety_hygiene_v4",
    )
    for row in rows:
        expected = reconciled_public_score(
            (row.get(field) for field in pillar_fields),
            {
                "applied": row.get("score_cap_applied"),
                "cap": row.get("score_cap_value"),
            },
        )
        actual = int(row["quality_score_v4_100"])
        if actual != expected:
            raise ValueError(
                f"{row['dsld_id']} baseline does not reconcile: "
                f"public={actual}, expected={expected}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aggregate_fingerprint(
    files: Iterable[Path],
    root: Path,
) -> dict[str, Any]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(files):
        relative = str(path.relative_to(root))
        content_hash = _sha256(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_hash.encode("ascii"))
        digest.update(b"\n")
        count += 1
    return {
        "file_count": count,
        "aggregate_sha256": digest.hexdigest(),
    }


def _count_by(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, int]:
    return dict(sorted(
        Counter(str(row.get(field)) for row in rows).items()
    ))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the blinded V4 reviewer benchmark"
    )
    parser.add_argument("--catalog-db", required=True, type=Path)
    parser.add_argument("--scored-root", required=True, type=Path)
    parser.add_argument("--detail-blobs-dir", required=True, type=Path)
    parser.add_argument("--scoring-config", required=True, type=Path)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--analysis-spec", required=True, type=Path)
    parser.add_argument("--analysis-script", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--freeze-id", required=True)
    parser.add_argument("--frozen-on", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--per-archetype", type=int, default=10)
    parser.add_argument("--core-per-archetype", type=int, default=6)
    parser.add_argument("--reviewers-per-product", type=int, default=3)
    return parser.parse_args(argv)


def prepare_benchmark_output_dir(path: Path) -> None:
    """Create a new freeze directory without permitting replacement."""
    if path.exists():
        raise FileExistsError(
            f"benchmark freeze is immutable; output already exists: {path}"
        )
    path.mkdir(parents=True)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.reviewers_per_product < 3:
        raise ValueError("at least three independent reviewers are required")
    analysis_spec = json.loads(
        args.analysis_spec.read_text(encoding="utf-8")
    )
    if not isinstance(analysis_spec, dict):
        raise ValueError("analysis spec is not a JSON object")
    if analysis_spec.get("freeze_id") != args.freeze_id:
        raise ValueError(
            "analysis spec freeze_id does not match requested freeze"
        )
    if (
        analysis_spec.get("primary_design", {}).get("panel_size")
        != args.reviewers_per_product
    ):
        raise ValueError(
            "analysis spec panel size does not match reviewer count"
        )

    catalog = _load_catalog_products(args.catalog_db)
    released_ids = {_dsld_id(row) for row in catalog}
    archetypes, scored_files = _load_archetypes(
        args.scored_root,
        released_ids,
    )
    for row in catalog:
        row["archetype"] = archetypes[_dsld_id(row)]
    actual_archetypes = set(archetypes.values())
    if actual_archetypes != set(EXPECTED_ARCHETYPES):
        raise ValueError(
            "released archetypes differ from the frozen contract: "
            f"{sorted(actual_archetypes)}"
        )

    details = DetailBlobStore(args.detail_blobs_dir)
    freeze = build_benchmark_freeze(
        catalog,
        details,
        seed=args.seed,
        freeze_id=args.freeze_id,
        per_archetype=args.per_archetype,
        core_per_archetype=args.core_per_archetype,
        tier_thresholds=_load_tier_thresholds(args.scoring_config),
    )
    baseline = freeze["baseline_key"]
    reviewer_packet = freeze["reviewer_packet"]
    expected_reviews = len(baseline) * args.reviewers_per_product
    if (
        analysis_spec.get("primary_design", {}).get("required_ratings")
        != expected_reviews
    ):
        raise ValueError(
            "analysis spec required_ratings does not match frozen sample"
        )
    _validate_baseline_reconciliation(baseline)
    selected_detail_files = [
        args.detail_blobs_dir / f"{row['dsld_id']}.json"
        for row in baseline
    ]
    release_manifest = json.loads(
        args.release_manifest.read_text(encoding="utf-8")
    )
    if not isinstance(release_manifest, dict):
        raise ValueError("release manifest is not a JSON object")

    prepare_benchmark_output_dir(args.output_dir)
    reviewer_fields = tuple(reviewer_packet[0])
    _write_csv(
        args.output_dir / "reviewer_packet.csv",
        reviewer_packet,
        reviewer_fields,
    )
    development_baseline = [
        row for row in baseline
        if row["analysis_split"] == "development"
    ]
    holdout_baseline = [
        row for row in baseline
        if row["analysis_split"] == "holdout"
    ]
    _write_csv(
        args.output_dir / "development_baseline_key.csv",
        development_baseline,
        BASELINE_FIELDS,
        json_fields=frozenset({"challenge_flags"}),
    )
    _write_csv(
        args.output_dir / "SEALED_HOLDOUT_KEY.csv",
        holdout_baseline,
        BASELINE_FIELDS,
        json_fields=frozenset({"challenge_flags"}),
    )
    response_rows = _response_template_rows(
        reviewer_packet,
        args.reviewers_per_product,
        seed=args.seed,
    )
    response_fields = tuple(response_rows[0])
    _write_csv(
        args.output_dir / "reviewer_response_template.csv",
        response_rows,
        response_fields,
    )
    _write_csv(
        args.output_dir / "reviewer_registry_template.csv",
        [],
        REVIEWER_REGISTRY_FIELDS,
    )
    protocol_target = args.output_dir / "PROTOCOL.md"
    protocol_target.write_text(
        args.protocol.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    analysis_spec_target = args.output_dir / "ANALYSIS_SPEC.json"
    analysis_spec_target.write_text(
        args.analysis_spec.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    artifact_paths = (
        args.output_dir / "reviewer_packet.csv",
        args.output_dir / "development_baseline_key.csv",
        args.output_dir / "SEALED_HOLDOUT_KEY.csv",
        args.output_dir / "reviewer_response_template.csv",
        args.output_dir / "reviewer_registry_template.csv",
        protocol_target,
        analysis_spec_target,
    )
    manifest = {
        "schema_version": "1.0.0",
        "freeze_id": args.freeze_id,
        "frozen_on": args.frozen_on,
        "source_revision": {
            "commit": args.source_commit,
            "basis": (
                "last committed revision preceding release generation; "
                "content fingerprints are authoritative if the release "
                "worktree contained uncommitted changes"
            ),
        },
        "release": {
            "db_version": release_manifest.get("db_version"),
            "schema_version": release_manifest.get("schema_version"),
            "product_count": release_manifest.get("product_count"),
            "generated_at": release_manifest.get("generated_at"),
        },
        "selection": {
            "seed": args.seed,
            "sample_size": len(baseline),
            "per_archetype": args.per_archetype,
            "core_per_archetype": args.core_per_archetype,
            "challenge_per_archetype": (
                args.per_archetype - args.core_per_archetype
            ),
            "reviewers_per_product": args.reviewers_per_product,
            "required_reviews": expected_reviews,
            "archetype_counts": _count_by(baseline, "archetype"),
            "cohort_counts": _count_by(baseline, "sample_cohort"),
            "analysis_split_counts": _count_by(
                baseline,
                "analysis_split",
            ),
            "tier_counts": _count_by(baseline, "quality_tier"),
            "safety_counts": _count_by(
                baseline,
                "product_safety_status",
            ),
            "confidence_counts": _count_by(baseline, "v4_confidence"),
            "evidence_band_counts": dict(sorted(Counter(
                (
                    "zero"
                    if _as_float(row.get("pillar_evidence_v4")) == 0.0
                    else "nonzero"
                )
                for row in baseline
            ).items())),
        },
        "engine_contract": {
            field: sorted({
                str(row.get(field))
                for row in baseline
            })
            for field in (
                "score_model_version",
                "quality_score_version",
                "scoring_engine_version",
                "classification_schema_version",
                "v4_config_fingerprint",
            )
        },
        "inputs": {
            "catalog_db": {
                "path": str(args.catalog_db),
                "sha256": _sha256(args.catalog_db),
            },
            "scored_artifacts": _aggregate_fingerprint(
                scored_files,
                args.scored_root,
            ),
            "selected_detail_blobs": _aggregate_fingerprint(
                selected_detail_files,
                args.detail_blobs_dir,
            ),
            "scoring_config": {
                "path": str(args.scoring_config),
                "sha256": _sha256(args.scoring_config),
            },
            "release_manifest": {
                "path": str(args.release_manifest),
                "sha256": _sha256(args.release_manifest),
            },
        },
        "analysis_contract": {
            "analysis_version": analysis_spec.get("analysis_version"),
            "protocol_version": analysis_spec.get("protocol_version"),
            "analysis_spec_sha256": _sha256(args.analysis_spec),
            "analysis_script_path": str(args.analysis_script),
            "analysis_script_sha256": _sha256(args.analysis_script),
            "development_key_opening": (
                "only after reviewer registry and append-only responses "
                "are content-locked"
            ),
            "holdout_key_opening": (
                "only after candidate lock and unchanged analysis hashes"
            ),
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path)}
            for path in artifact_paths
        },
        "blinding": {
            "reviewer_packet_forbidden_fields": sorted(
                FORBIDDEN_REVIEWER_FIELDS
            ),
            "baseline_key_distribution": (
                "hold both keys back from reviewers; restrict the sealed "
                "holdout key from the calibration analyst until candidates "
                "and analysis code are locked"
            ),
            "holdout_opening": (
                "after calibration candidates and analysis code are locked"
            ),
        },
        "status": (
            "sample_protocol_and_analysis_frozen_reviewers_not_yet_registered"
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "freeze_id": args.freeze_id,
        "sample_size": len(baseline),
        "required_reviews": len(response_rows),
        "archetype_counts": manifest["selection"]["archetype_counts"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
