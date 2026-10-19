"""Hermetic builders for dashboard index tests: tiny scored batches and a release dist."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

PILLAR_MAX = {"formulation": 20, "dose": 20, "evidence": 20, "transparency": 15, "verification": 15, "safety_hygiene": 10}
CONFIG = json.dumps({"quality_score": {"fingerprint": "abc123", "version": "1.29.1-test"}})


def receipt(points: list[tuple[str, str, float]], score: float, max_: float, *, nominal: float = 0.0,
            realized: float | None = None, basis: str | None = None) -> dict:
    entries = []
    for entry_id, kind, value in points:
        entry = {"id": entry_id, "kind": kind, "source": f"x.{entry_id}", "points": value}
        if basis and kind == "neutral":
            entry["basis"] = basis
        entries.append(entry)
    realized = nominal if realized is None else realized
    without = score - realized
    return {"entries": entries, "nominal_deductions": nominal, "realized_deductions": realized,
            "unawarded": round(max_ - without, 4)}


def scored_product(pid: str, *, brand: str = "Acme", status: str = "scored", safety: str = "no_known_catalog_concern",
                   assessment: str = "complete", evidence_state: str = "evaluated_applicable", dose_neutral: bool = False,
                   verification_neutral: bool = False, deduction: float = 0.0, floor: bool = False,
                   evidence_score: float = 10.0, mismatch: float = 0.0, extra_receipt: list | None = None,
                   module: str = "generic", category: str = "single_nutrient", signals: list | None = None) -> dict:
    if status != "scored":
        return {"dsld_id": pid, "brand_name": brand, "product_name": f"Product {pid}", "quality_score_status": status,
                "quality_assessment_status": assessment, "product_safety_status": safety,
                "quality_score_v4_100": None, "quality_tier": None, "_v4_module": module,
                "percentile_category": category, "_v4_config_fingerprint": CONFIG,
                "blocking_reason": "BANNED_X" if status == "suppressed_safety" else None,
                "quality_score_suppressed_reason": "BANNED_X" if status == "suppressed_safety" else "NOT_SCORED",
                "_v4_safety_gate": {"safety_signals": signals or []}}
    form_points = [("A1_bio_score", "earned", 12.0)]
    form_score = 12.0
    form_nominal = 0.0
    form_realized = 0.0
    if deduction:
        form_points.append(("weak_or_unidentified_botanical", "deduction", -deduction))
        form_nominal = -deduction
        if floor:
            form_points.append(("botanical_formulation_bounds", "floor", deduction))
        else:
            form_score -= deduction
            form_realized = -deduction
    pillars = {
        "formulation": {"score": form_score + mismatch, "max": 20,
                        "receipt": receipt(form_points, form_score, 20, nominal=form_nominal, realized=form_realized),
                        "components": {"raw_formulation": 18.0, "reference": 30.0}},
        "dose": ({"score": 11.4, "max": 20, "components": {"raw_dose": 11.4, "reference": 20.0},
                  "receipt": receipt([("botanical_clinical_dose", "neutral", 11.4)], 11.4, 20, basis="disclosed_no_reference")}
                 if dose_neutral else
                 {"score": 15.0, "max": 20, "components": {"raw_dose": 15.0, "reference": 20.0},
                  "receipt": receipt([("rda_ai_coverage", "earned", 15.0)], 15.0, 20)}),
        "evidence": {"score": evidence_score, "max": 20, "evidence_result_state": evidence_state,
                     "display_state": "assessed" if evidence_state.startswith("evaluated") else "applicability_unestablished",
                     "components": {"raw_evidence": evidence_score, "reference": 20.0},
                     "receipt": receipt([("clinical_evidence_pipeline", "earned", evidence_score)] if evidence_score else [],
                                        evidence_score, 20)},
        "transparency": {"score": 12.0, "max": 15, "components": {"raw_score": 12.0, "raw_max": 15.0},
                         "receipt": receipt([("clear_disclosure_base", "neutral", 9.0),
                                             ("complete_active_identity_dose_disclosure", "disclosure", 3.0)], 12.0, 15)},
        "verification": ({"score": 6.0, "max": 15, "components": {"tier": "unknown", "fail_open_neutral": True, "cert": 0.0},
                          "receipt": receipt([("neutral_baseline", "neutral", 6.0)], 6.0, 15)}
                         if verification_neutral else
                         {"score": 10.0, "max": 15, "components": {"tier": "verified", "fail_open_neutral": False, "cert": 4.0},
                          "receipt": receipt([("neutral_baseline", "neutral", 6.0), ("cert", "earned", 4.0)], 10.0, 15)}),
        "safety_hygiene": {"score": 10.0, "max": 10, "components": {"clean_base": 10.0},
                           "receipt": receipt([("catalog_screen", "neutral", 10.0)], 10.0, 10)},
    }
    if extra_receipt:
        for pillar, entry in extra_receipt:
            pillars[pillar]["receipt"]["entries"].append(entry)
    total = round(sum(p["score"] for p in pillars.values()) - mismatch, 1)
    return {
        "dsld_id": pid, "brand_name": brand, "product_name": f"Product {pid}", "_v4_module": module,
        "percentile_category": category, "primary_type": category,
        "quality_score_status": "scored", "quality_assessment_status": assessment, "product_safety_status": safety,
        "quality_score_v4_100": total, "quality_tier": "Good" if total >= 70 else "Needs improvement",
        "quality_score_confidence": "moderate", "route_confidence": "high",
        "_v4_config_fingerprint": CONFIG, "quality_pillars_v4": pillars,
        "_v4_safety_gate": {"safety_signals": signals or []},
        "_v4_completeness_gate": {"missing_fields": [], "score_cap": None, "verdict_ceiling": None},
        "_v4_module_breakdown": {"dimensions": {"formulation": {"components": {"A1_bio_score": 12.0}, "penalties": {}}}},
    }


def write_batch(scan_dir: Path, brand: str, products: list[dict], *, manifest: bool = True,
                stage_code: str = "code1", reference: str = "ref1") -> Path:
    stage_dir = scan_dir / f"output_{brand}_scored" / "scored"
    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / "scored_batch_1.json"
    data = json.dumps(products).encode()
    path.write_bytes(data)
    if manifest:
        (stage_dir / ".stage_manifest.json").write_text(json.dumps({
            "schema_version": "1.0.0", "stage": "score", "generated_at": "2026-10-19T00:00:00Z",
            "processing_complete": True, "owned_files": [path.name],
            "content_sha256": {path.name: hashlib.sha256(data).hexdigest()}, "run_id": f"run-{brand}",
            "input_fingerprints": {"stage_code_sha256_v1": stage_code, "reference_data_sha256_v1": reference},
        }))
    return stage_dir


def write_release(build_root: Path, products: list[dict], *, db_version: str = "2026.10.15") -> None:
    """A minimal dist: products_core + one detail blob per product (whole-number totals)."""
    from scoring_v4.quality_score import shipped_whole_score

    build_root.mkdir(parents=True, exist_ok=True)
    blobs = build_root / "detail_blobs"
    blobs.mkdir(exist_ok=True)
    db = sqlite3.connect(build_root / "pharmaguide_core.db")
    pillar_cols = [f"pillar_{name}_v4" for name in PILLAR_MAX]
    db.execute("CREATE TABLE products_core (dsld_id TEXT, product_name TEXT, brand_name TEXT, v4_module TEXT, "
               "primary_category TEXT, quality_score_v4_100 INTEGER, quality_tier TEXT, quality_score_status TEXT, "
               "quality_assessment_status TEXT, product_safety_status TEXT, quality_score_version TEXT, "
               "v4_config_fingerprint TEXT, has_third_party_testing INTEGER, percentile_rank REAL, "
               "detail_blob_sha256 TEXT, exported_at TEXT, blocking_reason TEXT, "
               + ", ".join(f"{c} REAL" for c in pillar_cols) + ")")
    for product in products:
        pillars = product.get("quality_pillars_v4") or {}
        blob = {k: v for k, v in product.items() if not k.startswith("_")}
        blob["v4_score_provenance"] = {"quality_score_version": "1.26.0-test"}
        text = json.dumps(blob)
        sha = hashlib.sha256(text.encode()).hexdigest()
        (blobs / f"{product['dsld_id']}.json").write_text(text)
        total = product.get("quality_score_v4_100")
        db.execute(
            "INSERT INTO products_core VALUES (" + ",".join("?" * (17 + len(pillar_cols))) + ")",
            (product["dsld_id"], product["product_name"], product["brand_name"], product.get("_v4_module"),
             product.get("percentile_category"), shipped_whole_score(total) if total is not None else None,
             product.get("quality_tier"), product["quality_score_status"], product["quality_assessment_status"],
             product["product_safety_status"], "1.26.0-test", "fp-release", 0, None, sha, "2026-10-15T00:00:00Z",
             product.get("blocking_reason"),
             *[(pillars.get(name) or {}).get("score") for name in PILLAR_MAX]),
        )
    db.commit()
    db.close()
    (build_root / "export_manifest.json").write_text(json.dumps({
        "schema_version": "2.5.0", "db_version": db_version, "generated_at": "2026-10-15T00:00:00Z",
        "quality_score_config_checksum": "sha256:cfg", "scoring_version": "4.5.0"}))
