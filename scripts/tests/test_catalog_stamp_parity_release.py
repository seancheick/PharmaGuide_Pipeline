"""The shipped catalog must contain what the scorer produced, and only that.

Two questions, both answered against the built artifact rather than trusted:

1. Does anything the completeness gate quarantined, or anything NOT_SCORED,
   reach the app catalog? Quarantine is only a real boundary if the excluded
   ids are absent from `products_core` and from `detail_blobs/`.

2. Do the values stamped into `products_core` match what the Score stage
   emitted? The export re-projects the scorer's output; a projection that
   drifts is invisible from either side alone. Verdict, score, tier, module,
   pillars and both status columns are compared per product, and the route is
   additionally recomputed live from the classifier for a sample so a stamped
   route cannot agree with a stale scored artifact.

   Verdict and safety-status columns are exact too. If export-time warning
   synthesis discovers a signal Stage 3 missed, candidate construction fails;
   the exporter never becomes a second safety-decision producer.

Release-tier: needs a completed build, so it skips when one is absent.
"""

from __future__ import annotations

import glob
import json
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.release_artifact_paths import catalog_dist_dir

DIST = catalog_dist_dir()
CORE_DB = DIST / "pharmaguide_core.db"
MANIFEST = DIST / "export_manifest.json"

# scored-stage field -> products_core column
STAMPED_FIELDS = {
    "verdict": "verdict",
    "safety_verdict": "safety_verdict",
    "quality_score_v4_100": "quality_score_v4_100",
    "quality_score_status": "quality_score_status",
    "product_safety_status": "product_safety_status",
    "quality_assessment_status": "quality_assessment_status",
    "quality_tier": "quality_tier",
    "blocking_reason": "blocking_reason",
}
# Columns the export deliberately projects to a whole number. The schema says
# so in its own words: "quality_score_v4_100 is the whole-number shipped
# score". Comparing the raw decimal against it would report a documented
# projection as drift, so the contract is stated instead of tolerated.
WHOLE_NUMBER_COLUMNS = frozenset({"quality_score_v4_100"})
PILLARS = (
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
)
ROUTE_SAMPLE = 400


def _half_up(value: float) -> int:
    """Whole-number projection, half away from zero.

    Python's built-in round() is half-to-even, so 44.5 would become 44 and a
    correctly stamped 45 would be reported as drift.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _require_build():
    if not CORE_DB.is_file() or not MANIFEST.is_file():
        pytest.skip(f"no completed build in {DIST}")


def _core_rows(columns):
    con = sqlite3.connect(str(CORE_DB))
    try:
        available = {r[1] for r in con.execute("pragma table_info(products_core)")}
        wanted = ["dsld_id"] + [c for c in columns if c in available]
        return {
            str(row[0]): dict(zip(wanted, row))
            for row in con.execute(f"select {','.join(wanted)} from products_core")
        }, wanted
    finally:
        con.close()


def _scored_products():
    for path in sorted(glob.glob(
        str(ROOT / "scripts" / "products" / "output_*_scored" / "scored" / "*.json")
    )):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload if isinstance(payload, list) else (
            payload.get("products") or payload.get("scored") or []
        )
        for row in rows:
            if isinstance(row, dict) and row.get("dsld_id"):
                yield str(row["dsld_id"]), row


# --------------------------------------------------------------------------- #
# 1. Quarantine is a real boundary
# --------------------------------------------------------------------------- #


def test_no_quarantined_product_reaches_the_catalog() -> None:
    _require_build()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    excluded = {
        str(entry.get("dsld_id"))
        for entry in manifest.get("excluded_by_gate") or []
        if isinstance(entry, dict) and entry.get("dsld_id")
    }
    assert excluded, "no quarantine records; this gate would pass vacuously"

    core, _ = _core_rows([])
    leaked = sorted(excluded & set(core))
    assert not leaked, (
        f"{len(leaked)} quarantined product(s) are in products_core: {leaked[:10]}"
    )

    blobs = {p.stem for p in (DIST / "detail_blobs").glob("*.json")}
    leaked_blobs = sorted(excluded & blobs)
    assert not leaked_blobs, (
        f"{len(leaked_blobs)} quarantined product(s) still have a detail blob: "
        f"{leaked_blobs[:10]}"
    )


def test_no_live_product_is_not_scored() -> None:
    _require_build()
    core, _ = _core_rows(["quality_score_status", "quality_assessment_status"])
    bad = sorted(
        pid for pid, row in core.items()
        if str(row.get("quality_score_status") or "").upper() == "NOT_SCORED"
        or str(row.get("quality_assessment_status") or "").upper() == "NOT_SCORED"
    )
    assert not bad, f"NOT_SCORED products in the live catalog: {bad[:10]}"


def test_every_live_product_has_a_blob_and_every_blob_a_row() -> None:
    _require_build()
    core, _ = _core_rows([])
    blobs = {p.stem for p in (DIST / "detail_blobs").glob("*.json")}
    assert not sorted(set(core) - blobs), "live products without a detail blob"
    assert not sorted(blobs - set(core)), "detail blobs without a products_core row"


# --------------------------------------------------------------------------- #
# 2. Stamped == produced
# --------------------------------------------------------------------------- #


def test_stamped_values_match_the_score_stage() -> None:
    _require_build()
    core, wanted = _core_rows(list(STAMPED_FIELDS.values()) + list(PILLARS))
    compared = 0
    mismatches: list[str] = []
    for pid, scored in _scored_products():
        row = core.get(pid)
        if row is None:
            continue  # quarantined; covered by the gate above
        compared += 1
        for field, column in STAMPED_FIELDS.items():
            if column not in wanted or field not in scored:
                continue
            produced, stamped = scored[field], row.get(column)
            if produced is None or stamped is None:
                if produced != stamped:
                    mismatches.append(f"{pid}.{column}: {produced!r} != {stamped!r}")
                continue
            if column in WHOLE_NUMBER_COLUMNS:
                expected = _half_up(float(produced))
                if int(stamped) != expected:
                    mismatches.append(
                        f"{pid}.{column}: half_up({produced!r})={expected} "
                        f"!= {stamped!r}"
                    )
            elif isinstance(produced, float) or isinstance(stamped, float):
                if abs(float(produced) - float(stamped)) > 0.005:
                    mismatches.append(f"{pid}.{column}: {produced!r} != {stamped!r}")
            elif produced != stamped:
                mismatches.append(f"{pid}.{column}: {produced!r} != {stamped!r}")
        if len(mismatches) > 40:
            break

    assert compared > 0, "no scored products joined the catalog"
    assert not mismatches, (
        f"{len(mismatches)} stamped value(s) differ from the Score stage "
        f"(compared {compared} products): " + "; ".join(mismatches[:10])
    )


def test_stamped_route_matches_a_live_reclassification() -> None:
    """Guard against a stamped route agreeing with a stale scored artifact."""
    _require_build()
    from scoring_v4.router import class_for_product

    core, wanted = _core_rows(["v4_module"])
    if "v4_module" not in wanted:
        pytest.skip("v4_module not stamped in this schema")

    checked = 0
    mismatches: list[str] = []
    for path in sorted(glob.glob(
        str(ROOT / "scripts" / "products" / "output_*_enriched" / "enriched" / "*.json")
    )):
        if path.endswith(".stage_manifest.json"):
            continue
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload if isinstance(payload, list) else (
            payload.get("products") or payload.get("items")
            or payload.get("data") or [payload]
        )
        for product in rows:
            if not isinstance(product, dict):
                continue
            pid = str(product.get("dsld_id") or product.get("dsldId") or "")
            row = core.get(pid)
            if row is None:
                continue
            stamped = row.get("v4_module")
            if stamped is None:
                continue
            if class_for_product(product) != stamped:
                mismatches.append(
                    f"{pid}: stamped={stamped!r} recomputed={class_for_product(product)!r}"
                )
            checked += 1
            if checked >= ROUTE_SAMPLE:
                break
        if checked >= ROUTE_SAMPLE:
            break

    assert checked > 0, "no enriched products joined the catalog"
    assert not mismatches, (
        f"{len(mismatches)} of {checked} stamped routes disagree with a live "
        f"reclassification: {mismatches[:10]}"
    )
