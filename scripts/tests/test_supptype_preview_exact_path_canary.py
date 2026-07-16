"""§8 case 5 — exact-path canary for the TEMPORARY supp-type drift harness.

TEMPORARY — delete with `scripts/audits/supptype_drift_preview.py` at
consolidation cutover (Phase 5).

WHY THIS EXISTS
    The harness previews the shipped score OFF the pipeline. That is only
    evidence if the preview is the same projection the real final build
    produces. This canary proves it against the strongest available oracle:
    the SHIPPED catalog rows in `final_db_output/pharmaguide_core.db`.

    Without this, the harness could be internally consistent and still be
    measuring something the catalog never sees — which is exactly how a
    classifier regression reaches production wearing a green check.

    It is registered in the SLOW profile (test_profiles.py): it loads the real
    enriched corpus and re-scores real products.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
HARNESS_PATH = SCRIPTS_DIR / "audits" / "supptype_drift_preview.py"
CORE_DB = SCRIPTS_DIR / "final_db_output" / "pharmaguide_core.db"
MANIFEST = SCRIPTS_DIR / "tests" / "fixtures" / "contract_snapshots" / "_manifest.json"

_spec = importlib.util.spec_from_file_location("supptype_drift_preview", HARNESS_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["supptype_drift_preview"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
harness = _mod

pytestmark = pytest.mark.skipif(
    not CORE_DB.exists(),
    reason=f"no shipped catalog at {CORE_DB}; canary needs a real final build",
)

# preview score_facts key -> products_core column. Only fields the export
# actually persists per product are comparable; the rest of the preview surface
# is covered by the harness contract tests.
PREVIEW_TO_DB = {
    "_v4_quality_score_100": "quality_score_v4_100",
    "_v4_quality_status": "quality_score_status",
    "_v4_quality_tier": "quality_tier",
    "_v4_suppressed_reason": "quality_score_suppressed_reason",
    "_v4_raw_score_100": "raw_score_v4_100",
    "_v4_module": "v4_module",
    "verdict": "verdict",
    "safety_verdict": "safety_verdict",
    "grade": "grade",
    "blocking_reason": "blocking_reason",
    "mapped_coverage": "mapped_coverage",
    "score_100_equivalent": "score_100_equivalent",
}

PILLAR_TO_DB = {
    "formulation": "pillar_formulation_v4",
    "dose": "pillar_dose_v4",
    "evidence": "pillar_evidence_v4",
    "transparency": "pillar_transparency_v4",
    "verification": "pillar_verification_v4",
    "safety_hygiene": "pillar_safety_hygiene_v4",
}


@pytest.fixture(scope="module")
def manifest_ids() -> list[str]:
    manifest = json.loads(MANIFEST.read_text())
    return [str(entry["dsld_id"]) for entry in manifest["products"]]


@pytest.fixture(scope="module")
def shipped_rows(manifest_ids) -> dict[str, dict]:
    conn = sqlite3.connect(f"file:{CORE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in manifest_ids)
    cur = conn.execute(
        f"SELECT * FROM products_core WHERE dsld_id IN ({placeholders})", manifest_ids
    )
    rows = {str(row["dsld_id"]): dict(row) for row in cur}
    conn.close()
    return rows


@pytest.fixture(scope="module")
def previews(manifest_ids, shipped_rows) -> dict[str, dict]:
    """Project + preview-score exactly the fixture products from the corpus."""
    wanted = set(manifest_ids) & set(shipped_rows)
    rows = harness.run_corpus(do_score=True, only_ids=wanted, workers=1)
    return rows


def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 0.05
    return a == b


def test_fixture_products_are_present_in_the_shipped_catalog(manifest_ids, shipped_rows):
    """A fixture that never shipped cannot canary the shipped projection."""
    missing = sorted(set(manifest_ids) - set(shipped_rows))
    # UPC-dedup legitimately drops some products from the catalog; the canary
    # needs a real majority to be meaningful, not every id.
    assert len(shipped_rows) >= len(manifest_ids) - 5, (
        f"too many fixture products missing from the shipped catalog: {missing}"
    )


def test_preview_matches_the_shipped_final_build_projection(previews, shipped_rows):
    """§8: 'prove the preview equals the real final-build projection on the
    frozen fixture set' — for every captured field."""
    mismatches: list[str] = []
    for pid, row in sorted(previews.items()):
        shipped = shipped_rows.get(pid)
        if shipped is None:
            continue
        preview = row["scores"]
        for preview_key, db_col in PREVIEW_TO_DB.items():
            got, want = preview.get(preview_key), shipped.get(db_col)
            if not _close(got, want):
                mismatches.append(
                    f"{pid}.{db_col}: preview={got!r} shipped={want!r}"
                )
        pillars = preview.get("pillars") or {}
        for pillar_key, db_col in PILLAR_TO_DB.items():
            # The preview carries the full pillar payload ({score, max, reason,
            # components}); products_core persists only the scalar score.
            pillar = pillars.get(pillar_key)
            got = pillar.get("score") if isinstance(pillar, dict) else pillar
            want = shipped.get(db_col)
            if want is None and got is None:
                continue
            if not _close(got, want):
                mismatches.append(
                    f"{pid}.{db_col}: preview={got!r} shipped={want!r}"
                )

    assert not mismatches, (
        "the harness preview does not reproduce the shipped final-build "
        "projection — the harness cannot be used as evidence:\n  "
        + "\n  ".join(mismatches[:40])
    )


def test_preview_reproduces_the_shipped_supplement_type_column(previews, shipped_rows):
    """The DB `supplement_type` column is the compatibility mirror the dashboard
    reads. Pin that the preview's classification reproduces what shipped."""
    mismatches = []
    for pid, row in sorted(previews.items()):
        shipped = shipped_rows.get(pid)
        if shipped is None:
            continue
        got = row["facts"].get("primary_type")
        want = shipped.get("supplement_type")
        if got != want:
            mismatches.append(f"{pid}: preview primary_type={got!r} shipped supplement_type={want!r}")
    assert not mismatches, "\n  ".join(mismatches)


def test_no_decision_field_drifts_from_the_shipped_artifacts(previews):
    """Current code must reproduce every DECISION field embedded in the
    artifacts these fixtures were frozen from; otherwise the baseline mixes
    fresh code with stale enriched taxonomy (plan §8 'baseline parity').

    Cosmetic drift is tolerated and quantified separately: the 2026-07-15
    determinism fix (sorted() in classification_reasons) legitimately changed
    reason *text* on 562/14,193 products without changing a single decision.
    Those artifacts are regenerated by the Phase 5 rebuild.
    """
    offenders = {
        pid: [f for f in row["embedded_drift"] if f in harness._DECISION_FIELDS]
        for pid, row in previews.items()
        if any(f in harness._DECISION_FIELDS for f in row["embedded_drift"])
    }
    assert not offenders, (
        f"decision-field drift between current code and the shipped artifacts: "
        f"{offenders}"
    )
